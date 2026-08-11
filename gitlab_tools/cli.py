"""Command-line interface for the GitLab tools collection."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .commands.milestones.command import register_parser as register_milestones_parser
from .commands.repositories.command import register_parser as register_repositories_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitlab-tools",
        description="A collection of extensible GitLab automation and export tools.",
    )
    commands = parser.add_subparsers(dest="command", required=True, title="commands")
    register_milestones_parser(commands)
    register_repositories_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_standard_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def _configure_standard_streams() -> None:
    """Keep CLI output Unicode-safe on Windows and when redirected."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")
