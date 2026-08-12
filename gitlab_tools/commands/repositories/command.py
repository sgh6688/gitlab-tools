from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from ...common.config import load_gitlab_config
from ...common.gitlab_api import GitLabHttpError, GitLabProtocolError
from ...common.runtime_logging import setup_logging
from .config import load_config
from .exporter import GitCommandError, RepositoryExporter


DEFAULT_FEATURE_CONFIG = Path("repositories.config.txt")
CONFIG_TEMPLATES = {
    "gitlab.config.txt": "gitlab.example.txt",
    "repositories.config.txt": "repositories.example.txt",
    "run_repositories_export.bat": "run_repositories_export.bat",
}


def register_parser(commands: Any) -> None:
    repositories = commands.add_parser(
        "repositories",
        help="Export GitLab project repositories.",
        description="Commands for exporting project source repositories.",
    )
    actions = repositories.add_subparsers(dest="repositories_command", required=True, title="commands")
    export_parser = actions.add_parser(
        "export",
        help="Clone projects while preserving their GitLab namespace paths.",
        description="Export one project or all projects under a group as clean snapshots or Git working trees.",
    )
    export_parser.add_argument(
        "--gitlab-config",
        default="gitlab.config.txt",
        help="Shared GitLab connection config. Default: gitlab.config.txt",
    )
    export_parser.add_argument(
        "--config",
        help="Repository export config. If omitted, repositories.config.txt is loaded when present.",
    )
    export_parser.add_argument(
        "--project",
        action="append",
        help="Project ID, full path, or exact project name. Repeatable.",
    )
    export_parser.add_argument(
        "--group",
        action="append",
        help="Group ID or full path. Repeatable.",
    )
    export_parser.add_argument("--output-dir", help="Override the export root directory.")
    export_parser.add_argument(
        "--include-subgroups",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include projects in subgroups. Default: true.",
    )
    export_parser.add_argument(
        "--existing",
        choices=("skip", "update", "fail"),
        help="How to handle an existing project directory. Default: skip.",
    )
    export_parser.add_argument(
        "--clone-protocol",
        choices=("http", "ssh"),
        help="Clone with the GitLab HTTP or SSH URL. Default: http.",
    )
    export_parser.add_argument(
        "--output-mode",
        choices=("snapshot", "working-tree"),
        help="Export a clean source snapshot or retain Git metadata. Default: snapshot.",
    )
    export_parser.set_defaults(handler=run_export)

    init_parser = actions.add_parser(
        "init-config",
        help="Create editable repository export config templates.",
        description="Create gitlab.config.txt, repositories.config.txt, and the Windows runner without overwriting files.",
    )
    init_parser.add_argument(
        "--directory",
        default=".",
        help="Directory in which to create configuration files. Default: current directory.",
    )
    init_parser.set_defaults(handler=run_init_config)


def run_init_config(args: argparse.Namespace) -> int:
    destination_dir = Path(args.directory).expanduser().resolve()
    created: list[Path] = []
    try:
        template_root = files("gitlab_tools.templates")
        contents = {
            destination_name: template_root.joinpath(template_name).read_text(encoding="utf-8")
            for destination_name, template_name in CONFIG_TEMPLATES.items()
        }
        destination_dir.mkdir(parents=True, exist_ok=True)
        for destination_name, content in contents.items():
            destination = destination_dir / destination_name
            with destination.open("x", encoding="utf-8", newline="") as handle:
                created.append(destination)
                handle.write(content)
    except FileExistsError as exc:
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        print(f"配置文件已存在，未覆盖任何文件: {exc.filename}", file=sys.stderr)
        return 1
    except OSError as exc:
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        print(f"创建配置文件失败: {exc}", file=sys.stderr)
        return 3

    print(f"已创建 Repository 导出配置: {destination_dir}")
    return 0


def run_export(args: argparse.Namespace) -> int:
    gitlab_config_path = Path(args.gitlab_config).expanduser().resolve()
    if not gitlab_config_path.is_file():
        print(f"GitLab 配置文件不存在: {gitlab_config_path}", file=sys.stderr)
        return 1

    feature_config_path = _resolve_feature_config(args.config)
    if args.config and feature_config_path is None:
        print(f"Repository 导出配置文件不存在: {Path(args.config).expanduser().resolve()}", file=sys.stderr)
        return 1

    log_dir = feature_config_path.parent if feature_config_path is not None else Path.cwd()
    log_path = log_dir / "repositories-export.log"
    try:
        logger = setup_logging(log_path)
    except OSError as exc:
        print(f"无法创建日志文件 {log_path}: {exc}", file=sys.stderr)
        return 3

    try:
        gitlab_config = load_gitlab_config(gitlab_config_path)
        export_config = load_config(
            feature_config_path,
            cli_projects=args.project,
            cli_groups=args.group,
            output_dir=args.output_dir,
            include_subgroups=args.include_subgroups,
            existing=args.existing,
            clone_protocol=args.clone_protocol,
            output_mode=args.output_mode,
        )
        logger.info("Repository 导出启动，GitLab 配置: %s", gitlab_config_path)
        logger.info("Repository 功能配置: %s", feature_config_path or "未使用（命令行参数）")
        if not gitlab_config.token:
            logger.warning("未配置 Token，仅能访问公开可见的 GitLab project。")
        stats = RepositoryExporter(export_config, gitlab_config, logger).run()
    except (FileNotFoundError, ValueError) as exc:
        logger.error("配置错误: %s", exc)
        return 1
    except GitLabHttpError as exc:
        logger.error("GitLab API 请求失败，HTTP %s: %s", exc.status_code, exc.body[:500])
        return 2
    except GitLabProtocolError as exc:
        logger.error("GitLab API 响应无效: %s", exc)
        return 2
    except GitCommandError as exc:
        logger.error("Git 执行失败: %s", exc)
        return 3
    except Exception as exc:  # noqa: BLE001
        logger.exception("Repository 导出失败: %s", exc)
        return 3

    logger.info("Projects discovered: %s", stats.discovered)
    logger.info("Repositories cloned: %s", stats.cloned)
    logger.info("Repositories updated: %s", stats.updated)
    logger.info("Repositories skipped: %s", stats.skipped)
    logger.info("Repositories failed: %s", stats.failed)
    logger.info("Output directory: %s", export_config.output_dir)
    return 4 if stats.failed else 0


def _resolve_feature_config(value: str | None) -> Path | None:
    if value:
        candidate = Path(value).expanduser().resolve()
        return candidate if candidate.is_file() else None
    candidate = DEFAULT_FEATURE_CONFIG.resolve()
    return candidate if candidate.is_file() else None
