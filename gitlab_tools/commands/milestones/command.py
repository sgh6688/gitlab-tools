from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...common.gitlab_api import GitLabHttpError
from ...common.runtime_logging import setup_logging
from .config import load_config
from .exporter import MilestoneExporter


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
