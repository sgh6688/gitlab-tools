from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_OUTPUT_DIR = r"D:\Downloads\ExportedByGitLabTools"


@dataclass(slots=True)
class ScopeTarget:
    kind: str
    path: str


@dataclass(slots=True)
class AppConfig:
    gitlab_url: str
    token: str
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    request_timeout_seconds: int = 30
    page_size: int = 100
    verify_ssl: bool = True
    groups: list[ScopeTarget] = field(default_factory=list)
    projects: list[ScopeTarget] = field(default_factory=list)


def load_config(config_path: Path) -> AppConfig:
    raw = _parse_kv_config(config_path)

    gitlab_url = raw.get("gitlab_url", "").strip().rstrip("/")
    if not gitlab_url:
        raise ValueError("配置文件缺少 gitlab_url。")

    token = raw.get("token", "").strip()
    token_env_var = raw.get("token_env_var", "GITLAB_TOKEN").strip() or "GITLAB_TOKEN"
    if not token:
        token = os.environ.get(token_env_var, "").strip()
    if not token:
        raise ValueError(
            f"未找到 GitLab Token。请在配置文件的 token 中填写，或设置环境变量 {token_env_var}。"
        )

    output_dir = Path(raw.get("output_dir", DEFAULT_OUTPUT_DIR))
    timeout = int(raw.get("request_timeout_seconds", "30"))
    page_size = int(raw.get("page_size", "100"))
    verify_ssl = _parse_bool(raw.get("verify_ssl", "true"))

    groups = _parse_targets(raw.get("groups", ""), kind="group")
    projects = _parse_targets(raw.get("projects", ""), kind="project")
    if not groups and not projects:
        raise ValueError("至少配置一个 groups 或 projects。")

    return AppConfig(
        gitlab_url=gitlab_url,
        token=token,
        output_dir=output_dir,
        request_timeout_seconds=timeout,
        page_size=page_size,
        verify_ssl=verify_ssl,
        groups=groups,
        projects=projects,
    )


def _parse_targets(value: str, kind: str) -> list[ScopeTarget]:
    parsed: list[ScopeTarget] = []
    for item in value.split(","):
        path = item.strip().strip("/")
        if not path:
            continue
        parsed.append(ScopeTarget(kind=kind, path=path))
    return parsed


def _parse_kv_config(config_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    with config_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" not in line:
                raise ValueError(f"配置文件第 {line_number} 行格式错误，应为 key=value。")
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")
