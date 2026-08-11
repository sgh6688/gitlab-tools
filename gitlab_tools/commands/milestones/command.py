from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path

from ...common.gitlab_api import GitLabHttpError
from ...common.runtime_logging import setup_logging
from .config import load_config
from .exporter import MilestoneExporter


CONFIG_TEMPLATES = {
    "milestones.config.txt": "milestones.example.txt",
    "run_milestones_export.bat": "run_milestones_export.bat",
}


def register_parser(commands: argparse._SubParsersAction) -> None:
    milestones = commands.add_parser(
        "milestones",
        help="Work with GitLab milestones.",
        description="Commands for exporting and processing GitLab milestones.",
    )
    actions = milestones.add_subparsers(dest="milestones_command", required=True, title="commands")
    export_parser = actions.add_parser(
        "export",
        help="Export milestones and their issues as Markdown.",
        description="Export GitLab milestones and their issues into Markdown folders.",
    )
    export_parser.add_argument(
        "--config",
        default="milestones.config.txt",
        help="Path to the milestone export config file. Default: milestones.config.txt",
    )
    export_parser.set_defaults(handler=run_export)

    init_parser = actions.add_parser(
        "init-config",
        help="Create editable milestone export config templates.",
        description="Create milestones.config.txt and the Windows runner without overwriting files.",
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

    print(f"已创建 Milestone 导出配置: {destination_dir}")
    return 0


def run_export(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        print(f"配置文件不存在: {config_path}", file=sys.stderr)
        return 1

    log_path = config_path.parent / "milestones-export.log"
    logger = setup_logging(log_path)

    try:
        logger.info("Milestone 导出启动，配置文件: %s", config_path)
        logger.info("日志文件: %s", log_path)
        config = load_config(config_path)
        stats = MilestoneExporter(config, logger).run()
    except FileNotFoundError:
        logger.error("配置文件不存在: %s", config_path)
        return 1
    except GitLabHttpError as exc:
        logger.error("GitLab API 请求失败，HTTP %s: %s", exc.status_code, exc.body[:500])
        return 2
    except Exception as exc:  # noqa: BLE001
        logger.exception("Milestone 导出失败: %s", exc)
        return 3

    logger.info("Milestone export finished.")
    logger.info("Scopes processed: %s", stats.scopes_processed)
    logger.info("Milestones exported: %s", stats.milestones_exported)
    logger.info("Issues exported: %s", stats.issues_exported)
    logger.info("Output directory: %s", config.output_dir)
    return 0
