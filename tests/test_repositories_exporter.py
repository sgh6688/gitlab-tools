from __future__ import annotations

import base64
import ctypes
import errno
import logging
import os
import stat
import subprocess
import tempfile
import threading
import unittest
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from gitlab_tools.commands.repositories.api import RepositoryTargetError
from gitlab_tools.commands.repositories.config import RepositoryExportConfig
from gitlab_tools.commands.repositories.exporter import GitCommandError, RepositoryExporter
from gitlab_tools.common.config import GitLabConfig


class FakeRepositoryApi:
    def __init__(self, projects: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> None:
        self.projects = projects
        self.groups = groups

    def resolve_project(self, project: str) -> dict[str, Any]:
        result = self.projects[project]
        if isinstance(result, Exception):
            raise result
        return result

    def list_group_projects(self, group: str, *, include_subgroups: bool) -> list[dict[str, Any]]:
        return self.groups[group]


class FakeRepositoryApiWithCurrentUser(FakeRepositoryApi):
    def __init__(self, projects: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> None:
        super().__init__(projects, groups)
        self.current_username_calls = 0

    def current_username(self) -> str:
        self.current_username_calls += 1
        return "actual-gitlab-user"


def quiet_logger() -> logging.Logger:
    logger = logging.getLogger("repository-export-tests")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


class RepositoryExporterTests(unittest.TestCase):
    def test_snapshot_cleanup_uses_exact_metadata_names(self) -> None:
        directory_names = {".git", ".svn", ".hg", ".bzr", "CVS", "__MACOSX"}
        removed_names = directory_names | {".DS_Store", "Thumbs.db", "desktop.ini"}
        retained_names = {"cvs", "__macosx", ".ds_store", "thumbs.DB", "Desktop.ini"}

        for name in removed_names | retained_names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / name
                if name in directory_names or name in {"cvs", "__macosx"}:
                    path.mkdir()
                else:
                    path.write_text("content", encoding="utf-8")

                RepositoryExporter._remove_snapshot_metadata(Path(directory))

                self.assertEqual(name in retained_names, path.exists(), name)

    def test_snapshot_cleanup_retries_read_only_git_metadata(self) -> None:
        retried: list[str] = []

        def remove(path: str) -> None:
            retried.append(path)

        with patch("gitlab_tools.commands.repositories.exporter.os.chmod") as chmod:
            RepositoryExporter._retry_remove_read_only(remove, "pack.idx", (PermissionError, PermissionError(), None))

        chmod.assert_called_once_with("pack.idx", stat.S_IWRITE | stat.S_IREAD)
        self.assertEqual(["pack.idx"], retried)

    def test_exporter_rejects_update_with_snapshot_when_constructed_directly(self) -> None:
        with self.assertRaisesRegex(ValueError, "working-tree"):
            RepositoryExporter(
                RepositoryExportConfig(
                    output_dir=Path("export"),
                    projects=["team/tool"],
                    existing="update",
                    output_mode="snapshot",
                ),
                GitLabConfig("https://gitlab.example.com"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )

    def test_linux_rename_no_replace_uses_atomic_renameat2(self) -> None:
        calls: list[tuple[bytes, bytes, int]] = []

        class FakeLibc:
            def renameat2(self, old_dir_fd: int, source: bytes, new_dir_fd: int, destination: bytes, flags: int) -> int:
                self.old_dir_fd = old_dir_fd
                self.new_dir_fd = new_dir_fd
                calls.append((source, destination, flags))
                return 0

        with patch("gitlab_tools.commands.repositories.exporter.sys.platform", "linux"):
            with patch("gitlab_tools.commands.repositories.exporter.ctypes.CDLL", return_value=FakeLibc()):
                RepositoryExporter._rename_no_replace(Path("source"), Path("destination"))

        self.assertEqual([(b"source", b"destination", 1)], calls)

    def test_linux_rename_no_replace_propagates_existing_destination(self) -> None:
        class FakeLibc:
            def renameat2(self, *_args: object) -> int:
                ctypes.set_errno(errno.EEXIST)
                return -1

        with patch("gitlab_tools.commands.repositories.exporter.sys.platform", "linux"):
            with patch("gitlab_tools.commands.repositories.exporter.ctypes.CDLL", return_value=FakeLibc()):
                with self.assertRaises(FileExistsError):
                    RepositoryExporter._rename_no_replace(Path("source"), Path("destination"))

    def test_windows_git_process_omits_posix_only_options_and_decodes_utf8(self) -> None:
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig("https://gitlab.example.com"),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )
        completed = subprocess.CompletedProcess(["git", "--version"], 0, "git 版本\n", "")

        with patch("gitlab_tools.commands.repositories.exporter.os.name", "nt"):
            with patch("gitlab_tools.commands.repositories.exporter.subprocess.run", return_value=completed) as run:
                result = exporter._run_git(["--version"])

        self.assertEqual("git 版本\n", result)
        options = run.call_args.kwargs
        self.assertEqual("utf-8", options["encoding"])
        self.assertEqual("replace", options["errors"])
        self.assertNotIn("pass_fds", options)
        self.assertNotIn("preexec_fn", options)

    def test_uncreated_destination_is_resolved_from_existing_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_parent = root / "real-parent"
            real_parent.mkdir()
            alias = root / "alias"
            alias.symlink_to(real_parent, target_is_directory=True)

            resolved = RepositoryExporter._resolve_with_existing_ancestor(alias / "new" / "project")

            self.assertEqual(real_parent.resolve() / "new" / "project", resolved)

    def test_git_auth_header_contains_real_basic_credentials(self) -> None:
        config = RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"])
        exporter = RepositoryExporter(
            config,
            GitLabConfig("https://gitlab.example.com", token="secret-token"),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )

        environment = exporter._git_environment(authenticated=True)

        expected = base64.b64encode(b"oauth2:secret-token").decode("ascii")
        self.assertEqual("http.https://gitlab.example.com/.extraHeader", environment["GIT_CONFIG_KEY_0"])
        self.assertEqual("Authorization" + ": " + "Basic " + expected, environment["GIT_CONFIG_VALUE_0"])
        self.assertNotIn("secret-token", environment["GIT_CONFIG_VALUE_0"])

    def test_git_auth_header_uses_configured_username_for_internal_http_gitlab(self) -> None:
        api = FakeRepositoryApiWithCurrentUser({}, {})
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig(
                "http://gitlab.internal",
                token="secret-token",
                git_http_username="domain-user",
            ),
            quiet_logger(),
            api,
        )

        environment = exporter._git_environment(authenticated=True)

        expected = base64.b64encode(b"domain-user:secret-token").decode("ascii")
        self.assertEqual("http.http://gitlab.internal/.extraHeader", environment["GIT_CONFIG_KEY_0"])
        self.assertEqual("Authorization" + ": " + "Basic " + expected, environment["GIT_CONFIG_VALUE_0"])
        self.assertEqual(0, api.current_username_calls)

    def test_default_oauth2_username_is_replaced_by_token_owners_gitlab_username(self) -> None:
        api = FakeRepositoryApiWithCurrentUser({}, {})
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig("http://gitlab.internal", token="secret-token"),
            quiet_logger(),
            api,
        )

        environment = exporter._git_environment(authenticated=True)

        expected = base64.b64encode(b"actual-gitlab-user:secret-token").decode("ascii")
        self.assertEqual("Authorization" + ": " + "Basic " + expected, environment["GIT_CONFIG_VALUE_0"])
        self.assertEqual(1, api.current_username_calls)

        exporter._git_environment(authenticated=True)
        self.assertEqual(1, api.current_username_calls)

    def test_username_prompt_error_is_explained_as_http_token_authentication_failure(self) -> None:
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig("http://gitlab.internal", token="secret-token"),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )
        result = SimpleNamespace(
            returncode=128,
            stdout="",
            stderr="fatal: could not read Username for 'http://gitlab.internal': terminal prompts disabled",
        )

        with patch("gitlab_tools.commands.repositories.exporter.subprocess.run", return_value=result):
            with self.assertRaises(GitCommandError) as caught:
                exporter._run_git(
                    ["clone", "http://gitlab.internal/team/tool.git"],
                    authenticated=True,
                )

        message = str(caught.exception)
        self.assertIn("Git HTTP Token 认证未被服务端接受或认证配置未生效", message)
        self.assertIn("git_http_username", message)
        self.assertIn("不要把仅支持 HTTP 的站点改成 HTTPS", message)

    def test_git_error_redacts_basic_credentials_with_configured_username(self) -> None:
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig(
                "http://gitlab.internal",
                token="secret-token",
                git_http_username="domain-user",
            ),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )
        encoded = base64.b64encode(b"domain-user:secret-token").decode("ascii")
        result = SimpleNamespace(returncode=1, stdout="", stderr=f"secret-token Basic {encoded}")

        with patch("gitlab_tools.commands.repositories.exporter.subprocess.run", return_value=result):
            with self.assertRaises(GitCommandError) as caught:
                exporter._run_git(["clone", "http://gitlab.internal/team/tool.git"])

        message = str(caught.exception)
        self.assertNotIn("secret-token", message)
        self.assertNotIn(encoded, message)
        self.assertIn("[REDACTED]", message)

    def test_real_git_http_process_sends_token_header(self) -> None:
        received_headers: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                received_headers.append(self.headers.get("Authorization", ""))
                self.send_response(401)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            exporter = RepositoryExporter(
                RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
                GitLabConfig(f"http://127.0.0.1:{server.server_port}", token="secret-token"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )
            with self.assertRaises(GitCommandError):
                exporter._run_git(
                    ["ls-remote", f"http://127.0.0.1:{server.server_port}/repo.git"], authenticated=True
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        expected = base64.b64encode(b"oauth2:secret-token").decode("ascii")
        self.assertIn("Basic " + expected, received_headers)

    def test_real_git_does_not_send_token_to_unrelated_origin(self) -> None:
        received_headers: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                received_headers.append(self.headers.get("Authorization", ""))
                self.send_response(401)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            exporter = RepositoryExporter(
                RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
                GitLabConfig("https://gitlab.example.com", token="secret-token"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )
            with self.assertRaises(GitCommandError):
                exporter._run_git(
                    ["ls-remote", f"http://127.0.0.1:{server.server_port}/repo.git"], authenticated=True
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertTrue(received_headers)
        self.assertEqual({""}, set(received_headers))

    def test_git_error_redacts_plain_and_encoded_credentials(self) -> None:
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig("https://gitlab.example.com", token="secret-token"),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )
        encoded = base64.b64encode(b"oauth2:secret-token").decode("ascii")
        result = SimpleNamespace(returncode=1, stdout="", stderr=f"secret-token Basic {encoded}")

        with patch("gitlab_tools.commands.repositories.exporter.subprocess.run", return_value=result):
            with self.assertRaises(GitCommandError) as caught:
                exporter._run_git(["clone", "https://gitlab.example.com/team/tool.git"])

        message = str(caught.exception)
        self.assertNotIn("secret-token", message)
        self.assertNotIn(encoded, message)
        self.assertIn("[REDACTED]", message)

    def test_real_git_does_not_forward_token_to_cross_origin_redirect(self) -> None:
        redirected_headers: list[str] = []

        class DestinationHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                redirected_headers.append(self.headers.get("Authorization", ""))
                self.send_response(401)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        destination_server = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)

        class SourceHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://127.0.0.1:{destination_server.server_port}{self.path}",
                )
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        source_server = ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        threads = [
            threading.Thread(target=destination_server.serve_forever, daemon=True),
            threading.Thread(target=source_server.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            exporter = RepositoryExporter(
                RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
                GitLabConfig(f"http://127.0.0.1:{source_server.server_port}", token="secret-token"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )
            with self.assertRaises(GitCommandError):
                exporter._run_git(
                    ["ls-remote", f"http://127.0.0.1:{source_server.server_port}/repo.git"], authenticated=True
                )
        finally:
            source_server.shutdown()
            destination_server.shutdown()
            source_server.server_close()
            destination_server.server_close()
            for thread in threads:
                thread.join(timeout=5)

        self.assertTrue(redirected_headers)
        self.assertEqual({""}, set(redirected_headers))

    def test_clone_url_with_token_must_match_configured_gitlab_origin(self) -> None:
        exporter = RepositoryExporter(
            RepositoryExportConfig(output_dir=Path("export"), projects=["team/tool"]),
            GitLabConfig("https://gitlab.example.com", token="secret-token"),
            quiet_logger(),
            FakeRepositoryApi({}, {}),
        )
        project = {
            "id": 7,
            "path_with_namespace": "team/tool",
            "http_url_to_repo": "https://evil.example.com/team/tool.git",
        }

        with self.assertRaisesRegex(ValueError, "不同源"):
            exporter._clone_url(project)

    def create_source_repository(self, directory: Path) -> Path:
        source = directory / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True)
        (source / "README.md").write_text("repository content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "initial"], check=True)
        return source

    def test_project_is_exported_as_clean_snapshot_under_namespace_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            (source / ".gitignore").write_text("build/\n", encoding="utf-8")
            (source / ".gitattributes").write_text("*.txt text\n", encoding="utf-8")
            github = source / ".github"
            github.mkdir()
            (github / "workflow.yml").write_text("name: test\n", encoding="utf-8")
            (source / ".DS_Store").write_text("metadata", encoding="utf-8")
            nested = source / "nested"
            nested.mkdir()
            (nested / "Thumbs.db").write_text("metadata", encoding="utf-8")
            svn_metadata = nested / ".svn"
            svn_metadata.mkdir()
            (svn_metadata / "entries").write_text("metadata", encoding="utf-8")
            subprocess.run(
                [
                    "git", "-C", str(source), "add", ".gitignore", ".gitattributes",
                    ".github/workflow.yml", ".DS_Store", "nested/Thumbs.db", "nested/.svn",
                ],
                check=True,
            )
            subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "metadata fixtures"], check=True)
            project = {
                "id": 7,
                "path_with_namespace": "team/platform/sub/tool",
                "http_url_to_repo": source.as_uri(),
            }
            config = RepositoryExportConfig(output_dir=root / "export", projects=["team/platform/sub/tool"])
            api = FakeRepositoryApi({"team/platform/sub/tool": project}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            destination = root / "export" / "team" / "platform" / "sub" / "tool"
            self.assertEqual("repository content\n", (destination / "README.md").read_text(encoding="utf-8"))
            self.assertFalse((destination / ".git").exists())
            self.assertFalse((destination / ".DS_Store").exists())
            self.assertFalse((destination / "nested" / "Thumbs.db").exists())
            self.assertFalse((destination / "nested" / ".svn").exists())
            self.assertEqual("build/\n", (destination / ".gitignore").read_text(encoding="utf-8"))
            self.assertEqual("*.txt text\n", (destination / ".gitattributes").read_text(encoding="utf-8"))
            self.assertEqual("name: test\n", (destination / ".github" / "workflow.yml").read_text(encoding="utf-8"))
            self.assertEqual(1, stats.cloned)
            self.assertEqual(0, stats.failed)

    def test_working_tree_output_mode_preserves_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            project = {"id": 7, "path_with_namespace": "team/tool", "http_url_to_repo": source.as_uri()}
            config = RepositoryExportConfig(
                output_dir=root / "export", projects=["team/tool"], output_mode="working-tree"
            )
            api = FakeRepositoryApi({"team/tool": project}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertTrue((root / "export" / "team" / "tool" / ".git").is_dir())
            self.assertEqual(1, stats.cloned)

    def test_ssh_snapshot_path_also_removes_git_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            project = {"id": 7, "path_with_namespace": "team/tool", "ssh_url_to_repo": str(source)}
            config = RepositoryExportConfig(
                output_dir=root / "export", projects=["team/tool"], clone_protocol="ssh"
            )
            api = FakeRepositoryApi({"team/tool": project}, {})
            exporter = RepositoryExporter(
                config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api
            )
            with patch.object(exporter, "_clone_url", return_value=str(source)):
                stats = exporter.run()

            destination = root / "export" / "team" / "tool"
            self.assertEqual("repository content\n", (destination / "README.md").read_text(encoding="utf-8"))
            self.assertFalse((destination / ".git").exists())
            self.assertEqual(1, stats.cloned)

    def test_direct_and_group_projects_are_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            project = {
                "id": 7,
                "path_with_namespace": "team/tool",
                "http_url_to_repo": source.as_uri(),
            }
            config = RepositoryExportConfig(
                output_dir=root / "export",
                projects=["team/tool"],
                groups=["team"],
            )
            api = FakeRepositoryApi({"team/tool": project}, {"team": [project]})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual(1, stats.discovered)
            self.assertEqual(1, stats.cloned)

    def test_bad_target_does_not_block_other_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            good = {"id": 7, "path_with_namespace": "team/good", "http_url_to_repo": source.as_uri()}
            config = RepositoryExportConfig(
                output_dir=root / "export",
                projects=["missing", "team/good"],
            )
            api = FakeRepositoryApi({"missing": RepositoryTargetError("not found"), "team/good": good}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual(1, stats.discovered)
            self.assertEqual(1, stats.cloned)
            self.assertEqual(1, stats.failed)

    def test_malformed_api_value_error_propagates_as_global_failure(self) -> None:
        config = RepositoryExportConfig(output_dir=Path("export"), projects=["bad"])
        api = FakeRepositoryApi({"bad": ValueError("malformed API response")}, {})

        with self.assertRaisesRegex(ValueError, "malformed API response"):
            RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

    def test_sanitized_destination_collision_fails_both_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            prefix = "p" * 120
            first = {"id": 1, "path_with_namespace": f"team/{prefix}a", "http_url_to_repo": source.as_uri()}
            second = {"id": 2, "path_with_namespace": f"team/{prefix}b", "http_url_to_repo": source.as_uri()}
            config = RepositoryExportConfig(output_dir=root / "export", projects=["first", "second"])
            api = FakeRepositoryApi({"first": first, "second": second}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual(0, stats.cloned)
            self.assertEqual(2, stats.failed)

    def test_post_truncation_windows_dot_collision_fails_both_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            stem = "a" * 119
            first = {"id": 1, "path_with_namespace": f"team/{stem}.x", "http_url_to_repo": source.as_uri()}
            second = {"id": 2, "path_with_namespace": f"team/{stem}", "http_url_to_repo": source.as_uri()}
            config = RepositoryExportConfig(output_dir=root / "export", projects=["first", "second"])
            api = FakeRepositoryApi({"first": first, "second": second}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual(0, stats.cloned)
            self.assertEqual(2, stats.failed)

    def test_existing_skip_policy_leaves_repository_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "export" / "team" / "tool"
            destination.mkdir(parents=True)
            marker = destination / "local.txt"
            marker.write_text("keep", encoding="utf-8")
            project = {
                "id": 7,
                "path_with_namespace": "team/tool",
                "http_url_to_repo": "unused",
            }
            config = RepositoryExportConfig(
                output_dir=root / "export",
                projects=["team/tool"],
                existing="skip",
            )
            api = FakeRepositoryApi({"team/tool": project}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual("keep", marker.read_text(encoding="utf-8"))
            self.assertEqual(1, stats.skipped)
            self.assertEqual(0, stats.failed)

    def test_existing_update_policy_fast_forwards_working_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            project = {
                "id": 7,
                "path_with_namespace": "team/tool",
                "http_url_to_repo": source.as_uri(),
            }
            api = FakeRepositoryApi({"team/tool": project}, {})
            first_config = RepositoryExportConfig(
                output_dir=root / "export", projects=["team/tool"], output_mode="working-tree"
            )
            RepositoryExporter(first_config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            destination = root / "export" / "team" / "tool"
            evil_source = root / "evil-source"
            subprocess.run(["git", "clone", "-q", str(source), str(evil_source)], check=True)
            branch = subprocess.run(
                ["git", "-C", str(destination), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            subprocess.run(["git", "-C", str(destination), "remote", "add", "evil", str(evil_source)], check=True)
            subprocess.run(["git", "-C", str(destination), "config", f"branch.{branch}.remote", "evil"], check=True)
            subprocess.run(
                ["git", "-C", str(destination), "config", f"branch.{branch}.merge", f"refs/heads/{branch}"],
                check=True,
            )

            (source / "README.md").write_text("updated content\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "update"], check=True)
            update_config = RepositoryExportConfig(
                output_dir=root / "export",
                projects=["team/tool"],
                existing="update",
                output_mode="working-tree",
            )

            stats = RepositoryExporter(
                update_config,
                GitLabConfig("https://gitlab.example.com"),
                quiet_logger(),
                api,
            ).run()

            self.assertEqual("updated content\n", (destination / "README.md").read_text(encoding="utf-8"))
            self.assertEqual(1, stats.updated)
            self.assertEqual(0, stats.failed)

    def test_ssh_update_runs_all_git_commands_through_opened_directory_handle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "export" / "team" / "tool"
            (destination / ".git").mkdir(parents=True)
            project = {
                "id": 7,
                "path_with_namespace": "team/tool",
                "ssh_url_to_repo": "git@gitlab.example.com:team/tool.git",
            }
            exporter = RepositoryExporter(
                RepositoryExportConfig(
                    output_dir=root / "export", projects=["team/tool"], existing="update",
                    output_mode="working-tree", clone_protocol="ssh",
                ),
                GitLabConfig("https://gitlab.example.com"), quiet_logger(), FakeRepositoryApi({}, {}),
            )
            exporter._preflight_resolved_destinations["7"] = destination.resolve()
            commands: list[tuple[list[str], tuple[int, ...], int | None]] = []

            def fake_git(arguments: list[str], **kwargs: object) -> str:
                commands.append((arguments, kwargs.get("pass_fds", ()), kwargs.get("working_directory_fd")))
                if "get-url" in arguments:
                    return "git@gitlab.example.com:team/tool.git\n"
                if "symbolic-ref" in arguments:
                    return "main\n"
                return ""

            with patch.object(exporter, "_opened_git_directory", return_value=nullcontext((".", (42,)))):
                with patch.object(exporter, "_run_git", side_effect=fake_git):
                    result = exporter._export_project(project)

            self.assertEqual("updated", result)
            self.assertEqual(3, len(commands))
            for arguments, command_pass_fds, working_directory_fd in commands:
                self.assertEqual(["-C", "."], arguments[:2])
                self.assertEqual((42,), command_pass_fds)
                self.assertEqual(42, working_directory_fd)

    def test_update_hook_cannot_read_authenticated_git_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            destination = root / "working-tree"
            subprocess.run(["git", "clone", "-q", str(source), str(destination)], check=True)
            marker = root / "captured-auth.txt"
            hook = destination / ".git" / "hooks" / "post-merge"
            hook.write_text(
                "#!/bin/sh\nprintf '%s|%s' \"${GIT_CONFIG_VALUE_0-unset}\" \"${GITLAB_TOKEN-unset}\" > "
                + repr(str(marker))
                + "\n",
                encoding="utf-8",
            )
            hook.chmod(0o700)
            (source / "README.md").write_text("updated safely\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "update"], check=True)
            exporter = RepositoryExporter(
                RepositoryExportConfig(
                    output_dir=root,
                    projects=["team/tool"],
                    existing="update",
                    output_mode="working-tree",
                ),
                GitLabConfig("https://gitlab.example.com", token="secret-token"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )
            with exporter._opened_git_directory(destination) as (git_directory, pass_fds):
                branch = exporter._run_git(
                    ["-C", git_directory, "symbolic-ref", "--short", "HEAD"],
                    pass_fds=pass_fds,
                    working_directory_fd=pass_fds[0] if pass_fds else None,
                ).strip()
                with patch.dict(os.environ, {"GITLAB_TOKEN": "secret-token"}):
                    exporter._update_from_isolated_mirror(
                        str(source),
                        branch,
                        git_directory=git_directory,
                        pass_fds=pass_fds,
                        working_directory_fd=pass_fds[0] if pass_fds else None,
                    )

            captured = marker.read_text(encoding="utf-8")
            self.assertEqual("unset|unset", captured)
            self.assertNotIn("secret-token", captured)
            self.assertEqual("updated safely\n", (destination / "README.md").read_text(encoding="utf-8"))

    def test_clone_install_rejects_namespace_swap_after_final_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "export"
            outside = root / "outside"
            (output / "team").mkdir(parents=True)
            outside.mkdir()
            project = {"id": 7, "path_with_namespace": "team/tool", "http_url_to_repo": "unused"}
            exporter = RepositoryExporter(
                RepositoryExportConfig(output_dir=output, projects=["team/tool"]),
                GitLabConfig("https://gitlab.example.com"),
                quiet_logger(),
                FakeRepositoryApi({}, {}),
            )
            exportable, failures = exporter._preflight_projects([project])
            self.assertEqual(0, failures)
            self.assertEqual([project], exportable)
            destination = exporter.destination_for(project)
            original_assert = exporter._assert_destination_unchanged
            calls = 0

            def assert_then_swap(candidate: dict[str, Any], path: Path) -> None:
                nonlocal calls
                original_assert(candidate, path)
                calls += 1
                if calls == 1:
                    (output / "team").rename(output / "team-original")
                    (output / "team").symlink_to(outside, target_is_directory=True)

            def fake_git(arguments: list[str], **kwargs: object) -> str:
                if arguments[:2] == ["clone", "--bare"]:
                    Path(arguments[-1]).mkdir()
                elif arguments[:2] == ["clone", "--no-local"]:
                    worktree = Path(arguments[-1])
                    (worktree / ".git").mkdir(parents=True)
                return ""

            with patch.object(exporter, "_assert_destination_unchanged", side_effect=assert_then_swap):
                with patch.object(exporter, "_run_git", side_effect=fake_git):
                    with self.assertRaises((OSError, ValueError)):
                        exporter._clone_via_isolated_mirror(project, "unused", destination)

            self.assertFalse((outside / "tool").exists())

    def test_update_rejects_repository_with_different_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_source = self.create_source_repository(root)
            second_source = root / "second-source"
            subprocess.run(["git", "clone", "-q", str(first_source), str(second_source)], check=True)
            project = {"id": 7, "path_with_namespace": "team/tool", "http_url_to_repo": first_source.as_uri()}
            api = FakeRepositoryApi({"team/tool": project}, {})
            initial = RepositoryExportConfig(
                output_dir=root / "export", projects=["team/tool"], output_mode="working-tree"
            )
            RepositoryExporter(initial, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            changed_project = {"id": 7, "path_with_namespace": "team/tool", "http_url_to_repo": str(second_source)}
            update = RepositoryExportConfig(
                output_dir=root / "export",
                projects=["team/tool"],
                existing="update",
                output_mode="working-tree",
            )

            stats = RepositoryExporter(
                update,
                GitLabConfig("https://gitlab.example.com"),
                quiet_logger(),
                FakeRepositoryApi({"team/tool": changed_project}, {}),
            ).run()

            self.assertEqual(0, stats.updated)
            self.assertEqual(1, stats.failed)

    def test_unsafe_namespace_path_is_rejected(self) -> None:
        project = {"id": 1, "path_with_namespace": "team/../outside", "http_url_to_repo": "unused"}
        config = RepositoryExportConfig(output_dir=Path("export"), projects=["bad"])
        api = FakeRepositoryApi({"bad": project}, {})
        exporter = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api)

        with self.assertRaisesRegex(ValueError, "不安全"):
            exporter.destination_for(project)

    def test_symlink_cannot_escape_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "export"
            outside = root / "outside"
            output.mkdir()
            outside.mkdir()
            try:
                (output / "team").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            project = {"id": 1, "path_with_namespace": "team/tool", "http_url_to_repo": "unused"}
            config = RepositoryExportConfig(output_dir=output, projects=["team/tool"])
            api = FakeRepositoryApi({"team/tool": project}, {})
            exporter = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api)

            with self.assertRaisesRegex(ValueError, "输出目录之外"):
                exporter.destination_for(project)

    def test_in_root_symlink_alias_collision_fails_both_projects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            output = root / "export"
            alias = output / "alias"
            alias.mkdir(parents=True)
            try:
                (output / "team").symlink_to(alias, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            first = {"id": 1, "path_with_namespace": "team/tool", "http_url_to_repo": source.as_uri()}
            second = {"id": 2, "path_with_namespace": "alias/tool", "http_url_to_repo": source.as_uri()}
            config = RepositoryExportConfig(output_dir=output, projects=["first", "second"])
            api = FakeRepositoryApi({"first": first, "second": second}, {})

            stats = RepositoryExporter(config, GitLabConfig("https://gitlab.example.com"), quiet_logger(), api).run()

            self.assertEqual(0, stats.cloned)
            self.assertEqual(2, stats.failed)


if __name__ == "__main__":
    unittest.main()
