from __future__ import annotations

import re
from pathlib import Path


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
WHITESPACE_RE = re.compile(r"\s+")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_windows_name(value: str, fallback_prefix: str) -> str:
    candidate = WHITESPACE_RE.sub(" ", value.strip())
    candidate = INVALID_CHARS_RE.sub("-", candidate).strip(" .")
    candidate = candidate.replace("\n", " ").replace("\r", " ")
    candidate = WHITESPACE_RE.sub(" ", candidate)
    candidate = candidate[:120].rstrip(" .")
    basename = candidate.split(".", 1)[0].upper()
    if not candidate or basename in WINDOWS_RESERVED_NAMES:
        candidate = pinyin_fallback(value, fallback_prefix=fallback_prefix)
    return candidate


def pinyin_fallback(value: str, fallback_prefix: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_-]+", "-", value or "").strip("-").lower()
    joined = safe or fallback_prefix
    if joined.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        joined = f"{fallback_prefix}-{joined.lower()}"
    return joined[:120]


def unique_path(base_dir: Path, desired_name: str) -> Path:
    path = base_dir / desired_name
    if not path.exists():
        return path
    index = 2
    while True:
        alt = base_dir / f"{desired_name}__{index}"
        if not alt.exists():
            return alt
        index += 1


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|")
