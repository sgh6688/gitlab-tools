from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .exporter import Exporter
from .gitlab_api import GitLabHttpError
from .runtime_logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitlab-milestone-exporter",
        description="Export GitLab milestones and issues into Markdown folders.",
    )
    parser.add_argument(
        "--config",
        default="config.txt",
        help="Path to config file. Default: config.txt",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()
    log_path = config_path.parent / "export.log"
    logger = setup_logging(log_path)

    try:
        logger.info("程序启动，配置文件: %s", config_path)
        logger.info("日志文件: %s", log_path)
        config = load_config(config_path)
        exporter = Exporter(config, logger)
        stats = exporter.run()
    except FileNotFoundError:
        logger.error("配置文件不存在: %s", config_path)
        return 1
    except GitLabHttpError as exc:
        logger.error("GitLab API 请求失败，HTTP %s: %s", exc.status_code, exc.body[:500])
        return 2
    except Exception as exc:  # noqa: BLE001
        logger.exception("导出失败: %s", exc)
        return 3

    logger.info("Export finished.")
    logger.info("Scopes processed: %s", stats.scopes_processed)
    logger.info("Milestones exported: %s", stats.milestones_exported)
    logger.info("Issues exported: %s", stats.issues_exported)
    logger.info("Output directory: %s", config.output_dir)
    return 0
