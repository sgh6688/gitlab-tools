from __future__ import annotations

import base64
import ctypes
import errno
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol
from urllib.parse import urlsplit

from ...common.config import GitLabConfig
from ...common.gitlab_api import GitLabClient, GitLabHttpError, GitLabProtocolError
from ...common.utils import ensure_directory, slugify_windows_name
from .api import RepositoryApi, RepositoryTargetError
from .config import RepositoryExportConfig


SNAPSHOT_METADATA_DIRECTORIES = {".git", ".hg", ".svn", ".bzr", "CVS", "__MACOSX"}
SNAPSHOT_METADATA_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


@dataclass(slots=True)
class ExportStats:
    discovered: int = 0
    cloned: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


class GitCommandError(RuntimeError):
    pass


class RepositoryProjectApi(Protocol):
    def current_username(self) -> str: ...

    def resolve_project(self, project: str) -> dict[str, Any]: ...

    def list_group_projects(self, group: str, *, include_subgroups: bool) -> list[dict[str, Any]]: ...


class RepositoryExporter:
    def __init__(
        self,
        config: RepositoryExportConfig,
        gitlab_config: GitLabConfig,
        logger: logging.Logger,
        api: RepositoryProjectApi | None = None,
    ) -> None:
        if config.existing == "update" and config.output_mode != "working-tree":
            raise ValueError("existing=update 要求 output_mode=working-tree，以保留更新所需的 .git 元数据。")
        self.config = config
        self.gitlab_config = gitlab_config
        self.logger = logger
        self._preflight_resolved_destinations: dict[str, Path] = {}
        self._resolved_git_http_username: str | None = None
        if api is None:
            client = GitLabClient(
                base_url=gitlab_config.gitlab_url,
                token=gitlab_config.token,
                timeout_seconds=gitlab_config.request_timeout_seconds,
                page_size=gitlab_config.page_size,
                verify_ssl=gitlab_config.verify_ssl,
            )
            api = RepositoryApi(client)
        self.api = api

    def run(self) -> ExportStats:
        self._verify_git()
        output_dir = ensure_directory(self.config.output_dir)
        projects, collection_failures = self._collect_projects()
        projects, preflight_failures = self._preflight_projects(projects)
        stats = ExportStats(
            discovered=len(projects) + preflight_failures,
            failed=collection_failures + preflight_failures,
        )
        self.logger.info("共发现 %s 个唯一 project，输出目录: %s", len(projects), output_dir)

        for project in projects:
            display_path = str(project.get("path_with_namespace") or project.get("name") or project.get("id"))
            try:
                outcome = self._export_project(project)
            except Exception as exc:  # noqa: BLE001
                stats.failed += 1
                self.logger.error("project 导出失败: %s: %s", display_path, exc)
                continue
            setattr(stats, outcome, getattr(stats, outcome) + 1)

        self.logger.info(
            "Repository export finished: discovered=%s, cloned=%s, updated=%s, skipped=%s, failed=%s",
            stats.discovered,
            stats.cloned,
            stats.updated,
            stats.skipped,
            stats.failed,
        )
        return stats

    def destination_for(self, project: dict[str, Any]) -> Path:
        namespace_path = str(project.get("path_with_namespace") or "").strip().strip("/")
        raw_parts = namespace_path.split("/") if namespace_path else []
        if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
            raise ValueError(f"project 返回了不安全的 path_with_namespace: {namespace_path!r}")
        safe_parts = [
            slugify_windows_name(part, fallback_prefix=f"path-{index}")
            for index, part in enumerate(raw_parts, start=1)
        ]
        output_root = self._resolve_with_existing_ancestor(self.config.output_dir.expanduser())
        destination = output_root.joinpath(*safe_parts)
        resolved_destination = self._resolve_with_existing_ancestor(destination)
        if resolved_destination != output_root and output_root not in resolved_destination.parents:
            raise ValueError(f"project 输出路径落在输出目录之外: {namespace_path!r}")
        return destination

    def _collect_projects(self) -> tuple[list[dict[str, Any]], int]:
        projects: list[dict[str, Any]] = []
        failures = 0
        for project in self.config.projects:
            self.logger.info("解析 project: %s", project)
            try:
                projects.append(self.api.resolve_project(project))
            except GitLabHttpError as exc:
                if exc.status_code != 404:
                    raise
                failures += 1
                self.logger.error("project 不存在或无权访问: %s", project)
            except RepositoryTargetError as exc:
                failures += 1
                self.logger.error("project 解析失败: %s: %s", project, exc)
        for group in self.config.groups:
            self.logger.info("枚举 group: %s, include_subgroups=%s", group, self.config.include_subgroups)
            try:
                projects.extend(
                    self.api.list_group_projects(group, include_subgroups=self.config.include_subgroups)
                )
            except GitLabHttpError as exc:
                if exc.status_code != 404:
                    raise
                failures += 1
                self.logger.error("group 不存在或无权访问: %s", group)
            except RepositoryTargetError as exc:
                failures += 1
                self.logger.error("group 枚举失败: %s: %s", group, exc)

        unique: dict[str, dict[str, Any]] = {}
        for project in projects:
            key = str(project.get("id") or project.get("path_with_namespace") or "")
            if not key:
                raise GitLabProtocolError("GitLab API 返回的 project 缺少 id 和 path_with_namespace。")
            unique[key] = project
        sorted_projects = sorted(
            unique.values(),
            key=lambda item: str(item.get("path_with_namespace") or "").casefold(),
        )
        return [project for project in sorted_projects if not self._is_excluded(project)], failures

    def _is_excluded(self, project: dict[str, Any]) -> bool:
        path = str(project.get("path_with_namespace") or "").strip().strip("/")
        if path in self.config.exclude_projects:
            self.logger.info("排除 project: %s", path)
            return True
        for group in self.config.exclude_groups:
            if path.startswith(f"{group}/"):
                self.logger.info("排除 group 下的 project: %s", path)
                return True
        return False

    def _preflight_projects(self, projects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        self._preflight_resolved_destinations.clear()
        destinations: dict[str, list[dict[str, Any]]] = {}
        resolved_destinations: dict[str, Path] = {}
        failures = 0
        for project in projects:
            try:
                destination = self.destination_for(project)
            except ValueError as exc:
                failures += 1
                self.logger.error("project 路径无效: %s", exc)
                continue
            resolved_destination = self._resolve_with_existing_ancestor(destination)
            collision_key = os.path.normcase(str(resolved_destination)).casefold()
            destinations.setdefault(collision_key, []).append(project)
            resolved_destinations[self._project_key(project)] = resolved_destination

        exportable: list[dict[str, Any]] = []
        for collision_group in destinations.values():
            if len(collision_group) == 1:
                project = collision_group[0]
                exportable.append(project)
                project_key = self._project_key(project)
                self._preflight_resolved_destinations[project_key] = resolved_destinations[project_key]
                continue
            failures += len(collision_group)
            paths = ", ".join(str(item.get("path_with_namespace") or item.get("id")) for item in collision_group)
            self.logger.error("多个 project 映射到同一 Windows 输出路径，已全部拒绝: %s", paths)
        return exportable, failures

    def _export_project(self, project: dict[str, Any]) -> str:
        destination = self.destination_for(project)
        self._assert_destination_unchanged(project, destination)
        display_path = str(project.get("path_with_namespace") or "")
        if destination.is_symlink():
            raise ValueError(f"目标路径不能是符号链接或目录联接: {destination}")
        if destination.exists():
            if self.config.existing == "skip":
                self.logger.info("跳过已存在目录: %s", destination)
                return "skipped"
            if self.config.existing == "fail":
                raise FileExistsError(f"目标目录已存在: {destination}")
            if not (destination / ".git").is_dir():
                raise ValueError(f"existing=update 但目标不是 Git 工作区: {destination}")
            self._assert_destination_unchanged(project, destination)
            clone_url = self._clone_url(project)
            with self._opened_git_directory(destination) as (git_directory, pass_fds):
                working_directory_fd = pass_fds[0] if pass_fds else None
                git_options = {
                    "pass_fds": pass_fds,
                    "working_directory_fd": working_directory_fd,
                }
                origin_url = self._run_git(
                    ["-C", git_directory, "remote", "get-url", "origin"], **git_options
                ).strip()
                if self._normalize_clone_url(origin_url) != self._normalize_clone_url(clone_url):
                    raise ValueError(f"existing=update 但 origin 与目标 project 不匹配: {destination}")
                branch = self._run_git(
                    ["-C", git_directory, "symbolic-ref", "--short", "HEAD"], **git_options
                ).strip()
                if not branch:
                    raise ValueError(f"existing=update 无法确定当前分支: {destination}")
                self.logger.info("更新 project: %s -> %s", display_path, destination)
                if self.config.clone_protocol == "ssh":
                    self._run_git(
                        ["-C", git_directory, "pull", "--ff-only", "--no-rebase", "--", "origin", branch],
                        **git_options,
                    )
                else:
                    self._update_from_isolated_mirror(
                        clone_url,
                        branch,
                        git_directory=git_directory,
                        pass_fds=pass_fds,
                        working_directory_fd=working_directory_fd,
                    )
            return "updated"

        clone_url = self._clone_url(project)
        ensure_directory(destination.parent)
        self._assert_destination_unchanged(project, destination)
        self.logger.info("克隆 project: %s -> %s", display_path, destination)
        if self.config.clone_protocol == "ssh":
            self._clone_ssh(project, clone_url, destination)
        else:
            self._clone_via_isolated_mirror(project, clone_url, destination)
        return "cloned"

    @staticmethod
    def _remove_snapshot_metadata(root: Path) -> None:
        for current_root, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
            current = Path(current_root)
            for name in list(directory_names):
                if name not in SNAPSHOT_METADATA_DIRECTORIES:
                    continue
                path = current / name
                if path.is_symlink():
                    path.unlink()
                else:
                    shutil.rmtree(path, onerror=RepositoryExporter._retry_remove_read_only)
                directory_names.remove(name)
            for name in file_names:
                if name in SNAPSHOT_METADATA_FILES:
                    (current / name).unlink()

    @staticmethod
    def _retry_remove_read_only(
        remove: Any,
        path: str,
        error_info: tuple[type[BaseException], BaseException, Any],
    ) -> None:
        error = error_info[1]
        if not isinstance(error, PermissionError):
            raise error
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        remove(path)

    def _clone_via_isolated_mirror(
        self,
        project: dict[str, Any],
        clone_url: str,
        destination: Path,
    ) -> None:
        output_root = self.config.output_dir.expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix=".gitlab-tools-", dir=output_root) as temporary_directory:
            temporary_root = Path(temporary_directory)
            template = temporary_root / "empty-template"
            template.mkdir()
            mirror = temporary_root / "mirror.git"
            staged_worktree = temporary_root / "worktree"
            self._run_git(
                ["clone", "--bare", "--template", str(template), "--", clone_url, str(mirror)],
                authenticated=bool(self.gitlab_config.token),
                isolated=True,
            )
            self._run_git(["clone", "--no-local", "--", str(mirror), str(staged_worktree)])
            self._run_git(["-C", str(staged_worktree), "remote", "set-url", "origin", clone_url])
            if self.config.output_mode == "snapshot":
                self._remove_snapshot_metadata(staged_worktree)
            self._assert_destination_unchanged(project, destination)
            self._rename_no_replace(staged_worktree, destination)
            try:
                self._assert_destination_unchanged(project, destination)
            except Exception:
                if destination.exists() and not staged_worktree.exists():
                    os.rename(destination, staged_worktree)
                raise

    def _update_from_isolated_mirror(
        self,
        clone_url: str,
        branch: str,
        *,
        git_directory: str,
        pass_fds: tuple[int, ...],
        working_directory_fd: int | None,
    ) -> None:
        output_root = self.config.output_dir.expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix=".gitlab-tools-update-", dir=output_root) as temporary_directory:
            temporary_root = Path(temporary_directory)
            template = temporary_root / "empty-template"
            template.mkdir()
            mirror = temporary_root / "mirror.git"
            self._run_git(
                ["init", "--bare", "--template", str(template), str(mirror)],
                isolated=True,
            )
            source_ref = f"refs/heads/{branch}"
            mirror_ref = "refs/heads/gitlab-tools-update"
            self._run_git(
                ["-C", str(mirror), "fetch", "--no-tags", "--", clone_url, f"{source_ref}:{mirror_ref}"],
                authenticated=bool(self.gitlab_config.token),
                isolated=True,
            )
            expected_commit = self._run_git(["-C", str(mirror), "rev-parse", mirror_ref], isolated=True).strip()
            self._run_git(
                ["-C", git_directory, "fetch", "--no-tags", "--", str(mirror), mirror_ref],
                pass_fds=pass_fds,
                working_directory_fd=working_directory_fd,
            )
            fetched_commit = self._run_git(
                ["-C", git_directory, "rev-parse", "FETCH_HEAD"],
                pass_fds=pass_fds,
                working_directory_fd=working_directory_fd,
            ).strip()
            if fetched_commit != expected_commit:
                raise GitCommandError("本地工作区获取的提交与已认证 GitLab 源不一致。")
            self._run_git(
                ["-C", git_directory, "merge", "--ff-only", expected_commit],
                pass_fds=pass_fds,
                working_directory_fd=working_directory_fd,
            )

    @staticmethod
    def _project_key(project: dict[str, Any]) -> str:
        return str(project.get("id") or project.get("path_with_namespace") or "")

    def _assert_destination_unchanged(self, project: dict[str, Any], destination: Path) -> None:
        expected = self._preflight_resolved_destinations.get(self._project_key(project))
        current = self._resolve_with_existing_ancestor(destination)
        if expected is None or current != expected:
            raise ValueError(f"project 输出路径在预检后发生变化，已拒绝操作: {destination}")

    @staticmethod
    def _resolve_with_existing_ancestor(path: Path) -> Path:
        candidate = path.expanduser().absolute()
        missing_parts: list[str] = []
        while not candidate.exists() and not candidate.is_symlink():
            parent = candidate.parent
            if parent == candidate:
                return path.expanduser().resolve(strict=False)
            missing_parts.append(candidate.name)
            candidate = parent
        resolved = candidate.resolve(strict=True)
        return resolved.joinpath(*reversed(missing_parts))

    def _verify_git(self) -> None:
        self._run_git(["--version"])

    def _run_git(
        self,
        arguments: list[str],
        *,
        authenticated: bool = False,
        isolated: bool = False,
        pass_fds: tuple[int, ...] = (),
        working_directory_fd: int | None = None,
    ) -> str:
        environment = self._git_environment(authenticated=authenticated)
        if isolated:
            environment["GIT_CONFIG_NOSYSTEM"] = "1"
            environment["GIT_CONFIG_GLOBAL"] = os.devnull
        run_options: dict[str, Any] = {
            "env": environment,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "check": False,
        }
        if os.name != "nt":
            run_options["pass_fds"] = pass_fds
            if working_directory_fd is not None:
                run_options["preexec_fn"] = lambda: os.fchdir(working_directory_fd)
        result = subprocess.run(["git", *arguments], **run_options)
        if result.returncode != 0:
            detail = self._sanitize_git_detail((result.stderr or result.stdout).strip())
            if (
                authenticated
                and self.gitlab_config.token
                and "could not read Username" in detail
                and "terminal prompts disabled" in detail
            ):
                detail += (
                    "\n诊断：Git HTTP Token 认证未被服务端接受或认证配置未生效。请保持 gitlab_url 与站点实际协议、主机、"
                    "端口一致；仅支持 HTTP 的内网站点应继续使用 http://，不要把仅支持 HTTP 的站点改成 HTTPS。"
                    "默认配置会通过同一 Token 查询真实 GitLab 用户名；也可在通用配置中显式设置 git_http_username。"
                    "Token 仍作为密码统一用于 API 和 clone。"
                )
            raise GitCommandError(f"git 命令失败，exit={result.returncode}: {detail}")
        return result.stdout

    def _sanitize_git_detail(self, detail: str) -> str:
        token = self.gitlab_config.token
        if not token:
            return detail
        username = self._resolved_git_http_username or self.gitlab_config.git_http_username
        encoded = base64.b64encode(
            f"{username}:{token}".encode("utf-8")
        ).decode("ascii")
        return detail.replace(token, "[REDACTED]").replace(encoded, "[REDACTED]")

    def _git_http_username(self) -> str:
        if self._resolved_git_http_username is not None:
            return self._resolved_git_http_username
        username = self.gitlab_config.git_http_username
        current_username = getattr(self.api, "current_username", None)
        if username == "oauth2" and self.gitlab_config.token and callable(current_username):
            resolved_username = current_username()
            if not isinstance(resolved_username, str) or not resolved_username:
                raise GitLabProtocolError("GitLab 当前用户响应缺少有效的 username。")
            username = resolved_username
        self._resolved_git_http_username = username
        return username

    @staticmethod
    def _normalize_clone_url(value: str) -> str:
        return value.strip().rstrip("/")

    def _clone_url(self, project: dict[str, Any]) -> str:
        field = "ssh_url_to_repo" if self.config.clone_protocol == "ssh" else "http_url_to_repo"
        clone_url = str(project.get(field) or "").strip()
        if not clone_url:
            display_path = str(project.get("path_with_namespace") or project.get("id") or "")
            raise ValueError(f"project {display_path} 缺少 {field}。")
        if any(character in clone_url for character in ("\x00", "\r", "\n")):
            raise ValueError("GitLab clone URL 包含非法控制字符。")
        if self.config.clone_protocol == "ssh":
            self._validate_ssh_clone_url(clone_url)
            return clone_url
        if clone_url.startswith("file://"):
            return clone_url
        clone_parts = urlsplit(clone_url)
        if clone_parts.scheme.lower() not in {"http", "https"}:
            raise ValueError("GitLab clone URL 必须使用 HTTP(S) 或 file:// 方案。")
        if clone_parts.username is not None or clone_parts.password is not None:
            raise ValueError("GitLab clone URL 不得包含用户名或密码。")
        if not clone_parts.hostname:
            raise ValueError("GitLab HTTP clone URL 缺少主机名。")
        try:
            port = clone_parts.port
            if port is not None and not (1 <= port <= 65535):
                raise ValueError
        except (ValueError, OverflowError):
            raise ValueError("GitLab HTTP clone URL 端口无效。") from None
        if self.gitlab_config.token and self._url_origin(clone_url) != self._url_origin(self.gitlab_config.gitlab_url):
            raise ValueError("GitLab HTTP clone URL 与配置的 GitLab 地址不同源，已拒绝发送 Token。")
        return clone_url

    def _validate_ssh_clone_url(self, clone_url: str) -> None:
        expected_host = (urlsplit(self.gitlab_config.gitlab_url).hostname or "").casefold()
        if clone_url.startswith("ssh://"):
            parts = urlsplit(clone_url)
            if parts.scheme != "ssh" or not parts.hostname or parts.password is not None or not parts.path:
                raise ValueError("GitLab SSH clone URL 无效。")
            clone_host = parts.hostname.casefold()
        else:
            match = re.fullmatch(r"(?:[^@/:]+@)?(\[[^\]]+\]|[^:/]+):(.+)", clone_url)
            if match is None:
                raise ValueError("GitLab SSH clone URL 必须使用 ssh:// 或 user@host:path 格式。")
            clone_host = match.group(1).strip("[]").casefold()
        if clone_host != expected_host:
            raise ValueError("GitLab SSH clone URL 主机与配置的 GitLab 地址不匹配。")

    def _git_environment(self, *, authenticated: bool = False) -> dict[str, str]:
        environment = os.environ.copy()
        token = self.gitlab_config.token
        if token:
            for key, value in list(environment.items()):
                if token in value:
                    del environment[key]
        environment["GIT_TERMINAL_PROMPT"] = "0"
        config_entries: list[tuple[str, str]] = []
        http_scope = self._gitlab_http_scope()
        if authenticated and token:
            username = self._git_http_username()
            credentials = base64.b64encode(
                f"{username}:{token}".encode("utf-8")
            ).decode("ascii")
            authorization_header = "Authorization" + ": " + "Basic " + credentials
            config_entries.append((f"http.{http_scope}.extraHeader", authorization_header))
        if not self.gitlab_config.verify_ssl:
            config_entries.append((f"http.{http_scope}.sslVerify", "false"))
        environment["GIT_CONFIG_COUNT"] = str(len(config_entries))
        for index, (key, value) in enumerate(config_entries):
            environment[f"GIT_CONFIG_KEY_{index}"] = key
            environment[f"GIT_CONFIG_VALUE_{index}"] = value
        return environment

    @contextmanager
    def _opened_git_directory(self, destination: Path) -> Iterator[tuple[str, tuple[int, ...]]]:
        if os.name == "nt":
            yield str(destination), ()
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags)
        try:
            stat_by_path = os.stat(destination, follow_symlinks=False)
            stat_by_fd = os.fstat(descriptor)
            if (stat_by_path.st_dev, stat_by_path.st_ino) != (stat_by_fd.st_dev, stat_by_fd.st_ino):
                raise ValueError(f"Git 工作区路径在打开时发生变化: {destination}")
            yield ".", (descriptor,)
        finally:
            os.close(descriptor)

    @staticmethod
    def _rename_no_replace(source: Path, destination: Path) -> None:
        if sys.platform == "darwin":
            rename_exclusive = 0x00000004
            rename_nofollow_any = 0x00000010
            libc = ctypes.CDLL(None, use_errno=True)
            result = libc.renamex_np(
                os.fsencode(source),
                os.fsencode(destination),
                rename_exclusive | rename_nofollow_any,
            )
            if result != 0:
                error_number = ctypes.get_errno()
                raise OSError(error_number, os.strerror(error_number), str(destination))
            return
        if sys.platform.startswith("linux"):
            at_fdcwd = -100
            rename_noreplace = 1
            libc = ctypes.CDLL(None, use_errno=True)
            try:
                renameat2 = libc.renameat2
            except AttributeError as exc:
                raise OSError(errno.ENOTSUP, "当前 Linux 运行库不支持原子 no-replace rename") from exc
            result = renameat2(
                at_fdcwd,
                os.fsencode(source),
                at_fdcwd,
                os.fsencode(destination),
                rename_noreplace,
            )
            if result != 0:
                error_number = ctypes.get_errno()
                raise OSError(error_number, os.strerror(error_number), str(destination))
            return
        if os.name != "nt":
            raise OSError(errno.ENOTSUP, f"当前平台不支持原子 no-replace rename: {sys.platform}")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(errno.EEXIST, "目标路径已存在", str(destination))
        os.rename(source, destination)

    @staticmethod
    def _url_origin(value: str) -> tuple[str, str, int]:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        hostname = (parts.hostname or "").casefold()
        if scheme not in {"http", "https"} or not hostname:
            raise ValueError(f"GitLab HTTP URL 无效: {value!r}")
        default_port = 443 if scheme == "https" else 80
        try:
            port = parts.port or default_port
        except ValueError as exc:
            raise ValueError(f"GitLab HTTP URL 端口无效: {value!r}") from exc
        return scheme, hostname, port

    def _gitlab_http_scope(self) -> str:
        scheme, hostname, port = self._url_origin(self.gitlab_config.gitlab_url)
        host = f"[{hostname}]" if ":" in hostname else hostname
        default_port = 443 if scheme == "https" else 80
        port_suffix = "" if port == default_port else f":{port}"
        return f"{scheme}://{host}{port_suffix}/"

    def _clone_ssh(self, project: dict[str, Any], clone_url: str, destination: Path) -> None:
        output_root = self.config.output_dir.expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix=".gitlab-tools-ssh-", dir=output_root) as temporary_directory:
            staged_worktree = Path(temporary_directory) / "worktree"
            self._run_git(["clone", "--", clone_url, str(staged_worktree)])
            if self.config.output_mode == "snapshot":
                self._remove_snapshot_metadata(staged_worktree)
            self._assert_destination_unchanged(project, destination)
            self._rename_no_replace(staged_worktree, destination)
            try:
                self._assert_destination_unchanged(project, destination)
            except Exception:
                if destination.exists() and not staged_worktree.exists():
                    os.rename(destination, staged_worktree)
                raise
