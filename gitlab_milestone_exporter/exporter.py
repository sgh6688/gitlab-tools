from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import AppConfig, ScopeTarget
from .gitlab_api import GitLabClient
from .markdown import render_issue_markdown, render_milestone_markdown
from .utils import ensure_directory, slugify_windows_name, unique_path


@dataclass(slots=True)
class ExportStats:
    scopes_processed: int = 0
    milestones_exported: int = 0
    issues_exported: int = 0


class Exporter:
    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.client = GitLabClient(
            base_url=config.gitlab_url,
            token=config.token,
            timeout_seconds=config.request_timeout_seconds,
            page_size=config.page_size,
            verify_ssl=config.verify_ssl,
        )

    def run(self) -> ExportStats:
        stats = ExportStats()
        output_dir = ensure_directory(self.config.output_dir)
        self.logger.info("导出开始，输出目录: %s", output_dir)
        for target in [*self.config.groups, *self.config.projects]:
            self.logger.info("开始处理 %s: %s", target.kind, target.path)
            entity_dir = self._prepare_entity_dir(output_dir, target)
            milestones = self._load_milestones(target)
            self.logger.info("%s: %s 共发现 %s 个 milestone", target.kind, target.path, len(milestones))
            stats.scopes_processed += 1
            self._write_scope_index(entity_dir, target, milestones)
            for milestone in milestones:
                self.logger.info("正在导出 milestone: [%s] %s", milestone.get("id", ""), milestone.get("title", ""))
                issues = self._load_issues(target, milestone)
                self._write_milestone_bundle(entity_dir, target, milestone, issues)
                self.logger.info(
                    "milestone 导出完成: [%s] %s，issues=%s",
                    milestone.get("id", ""),
                    milestone.get("title", ""),
                    len(issues),
                )
                stats.milestones_exported += 1
                stats.issues_exported += len(issues)
            self.logger.info("处理完成 %s: %s", target.kind, target.path)
        self.logger.info(
            "导出结束，scopes=%s, milestones=%s, issues=%s",
            stats.scopes_processed,
            stats.milestones_exported,
            stats.issues_exported,
        )
        return stats

    def _prepare_entity_dir(self, output_dir: Path, target: ScopeTarget) -> Path:
        safe_path = slugify_windows_name(target.path.replace("/", "__"), fallback_prefix=target.kind)
        entity_dir = output_dir / f"{target.kind}__{safe_path}"
        return ensure_directory(entity_dir)

    def _load_milestones(self, target: ScopeTarget) -> list[dict[str, Any]]:
        if target.kind == "group":
            milestones = self.client.list_group_milestones(target.path)
        else:
            milestones = self.client.list_project_milestones(target.path)
        return sorted(milestones, key=lambda item: ((item.get("title") or "").lower(), item.get("id", 0)))

    def _load_issues(self, target: ScopeTarget, milestone: dict[str, Any]) -> list[dict[str, Any]]:
        if target.kind == "group":
            issues = self.client.list_group_issues_for_milestone(target.path, milestone)
        else:
            issues = self.client.list_project_issues_for_milestone(target.path, milestone)
        self.logger.info(
            "已获取 issue 列表: milestone=[%s] %s, count=%s",
            milestone.get("id", ""),
            milestone.get("title", ""),
            len(issues),
        )
        return sorted(issues, key=lambda item: (item.get("iid", 0), item.get("id", 0)))

    def _write_scope_index(self, entity_dir: Path, target: ScopeTarget, milestones: list[dict[str, Any]]) -> None:
        lines = [
            f"# Export Index: {target.path}",
            "",
            f"- Scope Type: {target.kind}",
            f"- Scope Path: {target.path}",
            f"- Milestone Count: {len(milestones)}",
            "",
            "## Milestones",
            "",
        ]
        if not milestones:
            lines.append("_No milestones found._")
        else:
            for milestone in milestones:
                lines.append(
                    f"- `{milestone.get('title', '')}` | id={milestone.get('id', '')} | state={milestone.get('state', '')}"
                )
        (entity_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_milestone_bundle(
        self,
        entity_dir: Path,
        target: ScopeTarget,
        milestone: dict[str, Any],
        issues: list[dict[str, Any]],
    ) -> None:
        milestone_prefix = self._milestone_date_prefix(milestone)
        milestone_title = slugify_windows_name(
            milestone.get("title", ""),
            fallback_prefix=f"milestone-{milestone['id']}",
        )
        milestone_name = f"{milestone_prefix}_{milestone_title}"
        milestone_dir = entity_dir / milestone_name
        ensure_directory(milestone_dir)

        milestone_md = render_milestone_markdown(target.kind, target.path, milestone, issues)
        (milestone_dir / "milestone.md").write_text(milestone_md + "\n", encoding="utf-8")

        issues_dir = ensure_directory(milestone_dir / "issues")
        for index, issue in enumerate(issues, start=1):
            issue_title = slugify_windows_name(issue.get("title", ""), fallback_prefix=f"issue-{issue.get('iid', issue.get('id', index))}")
            issue_name = f"{index:03d}_iid-{issue.get('iid', '')}_{issue_title}.md"
            issue_path = unique_path(issues_dir, issue_name)
            issue_path.write_text(render_issue_markdown(issue) + "\n", encoding="utf-8")

    def _milestone_date_prefix(self, milestone: dict[str, Any]) -> str:
        if str(milestone.get("state", "")).lower() == "closed":
            closed_value = self._first_non_empty(milestone.get("closed_at"), milestone.get("updated_at"))
            closed_date = self._normalize_date_string(closed_value)
            if closed_date:
                return closed_date

        due_date = self._normalize_date_string(milestone.get("due_date"))
        if due_date:
            today = date.today().strftime("%Y%m%d")
            if due_date <= today:
                return due_date

        return "20269999"

    @staticmethod
    def _first_non_empty(*values: Any) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    @staticmethod
    def _normalize_date_string(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if len(text) >= 10:
            raw = text[:10]
            try:
                return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                pass
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 8:
            return digits[:8]
        return ""
