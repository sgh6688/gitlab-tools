from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...common.config import parse_bool, parse_kv_config


DEFAULT_OUTPUT_DIR = Path(r"D:\Downloads\ExportedByGitLabTools\Repositories")
EXISTING_POLICIES = {"skip", "update", "fail"}
CLONE_PROTOCOLS = {"http", "ssh"}


@dataclass(slots=True)
class RepositoryExportConfig:
    output_dir: Path = DEFAULT_OUTPUT_DIR
    projects: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    include_subgroups: bool = True
    existing: str = "skip"
    clone_protocol: str = "http"


def load_config(
    config_path: Path | None,
    *,
    cli_projects: list[str] | None = None,
    cli_groups: list[str] | None = None,
    output_dir: str | None = None,
    include_subgroups: bool | None = None,
    existing: str | None = None,
    clone_protocol: str | None = None,
) -> RepositoryExportConfig:
    raw = parse_kv_config(config_path) if config_path is not None else {}
    file_projects = _parse_list(raw.get("projects", ""))
    file_groups = _parse_list(raw.get("groups", ""))

    command_targets_given = bool(cli_projects or cli_groups)
    projects = _clean_targets(cli_projects or []) if command_targets_given else file_projects
    groups = _clean_targets(cli_groups or []) if command_targets_given else file_groups
    if not projects and not groups:
        raise ValueError("至少通过配置文件或命令行指定一个 project 或 group。")

    resolved_existing = existing or raw.get("existing", "skip").strip().lower() or "skip"
    if resolved_existing not in EXISTING_POLICIES:
        raise ValueError("existing 必须是 skip、update 或 fail。")
    resolved_clone_protocol = clone_protocol or raw.get("clone_protocol", "http").strip().lower() or "http"
    if resolved_clone_protocol not in CLONE_PROTOCOLS:
        raise ValueError("clone_protocol 必须是 http 或 ssh。")

    return RepositoryExportConfig(
        output_dir=Path(output_dir or raw.get("output_dir", str(DEFAULT_OUTPUT_DIR))),
        projects=projects,
        groups=groups,
        include_subgroups=(
            include_subgroups
            if include_subgroups is not None
            else parse_bool(raw.get("include_subgroups", "true"))
        ),
        existing=resolved_existing,
        clone_protocol=resolved_clone_protocol,
    )


def _parse_list(value: str) -> list[str]:
    return _clean_targets(value.split(","))


def _clean_targets(values: list[str]) -> list[str]:
    return [value.strip().strip("/") for value in values if value.strip().strip("/")]
