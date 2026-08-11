from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(slots=True)
class GitLabConfig:
    gitlab_url: str
    token: str = ""
    request_timeout_seconds: int = 30
    page_size: int = 100
    verify_ssl: bool = True


def load_gitlab_config(config_path: Path) -> GitLabConfig:
    raw = parse_kv_config(config_path)
    gitlab_url = raw.get("gitlab_url", "").strip().rstrip("/")
    if not gitlab_url:
        raise ValueError("GitLab 配置文件缺少 gitlab_url。")
    url_parts = urlsplit(gitlab_url)
    if (
        url_parts.scheme.lower() not in {"http", "https"}
        or not url_parts.hostname
        or url_parts.username is not None
        or url_parts.password is not None
    ):
        raise ValueError("gitlab_url 必须是无用户名和密码的有效 HTTP(S) URL。")

    token = raw.get("token", "").strip()
    token_env_var = raw.get("token_env_var", "GITLAB_TOKEN").strip() or "GITLAB_TOKEN"
    if not token:
        token = os.environ.get(token_env_var, "").strip()

    timeout = int(raw.get("request_timeout_seconds", "30"))
    page_size = int(raw.get("page_size", "100"))
    if timeout <= 0:
        raise ValueError("request_timeout_seconds 必须大于 0。")
    if not 1 <= page_size <= 100:
        raise ValueError("page_size 必须在 1 到 100 之间。")

    return GitLabConfig(
        gitlab_url=gitlab_url,
        token=token,
        request_timeout_seconds=timeout,
        page_size=page_size,
        verify_ssl=parse_bool(raw.get("verify_ssl", "true")),
    )


def parse_kv_config(config_path: Path) -> dict[str, str]:
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


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")
