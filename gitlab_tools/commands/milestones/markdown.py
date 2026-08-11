from __future__ import annotations

from typing import Any


def render_milestone_markdown(
    scope_kind: str,
    scope_path: str,
    milestone: dict[str, Any],
    issues: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Milestone: {milestone.get('title', '')}",
        "",
        "## Summary",
        "",
        f"- Scope Type: {scope_kind}",
        f"- Scope Path: {scope_path}",
        f"- Milestone ID: {milestone.get('id', '')}",
        f"- Milestone IID: {milestone.get('iid', '')}",
        f"- State: {milestone.get('state', '')}",
        f"- Start Date: {milestone.get('start_date') or ''}",
        f"- Due Date: {milestone.get('due_date') or ''}",
        f"- Created At: {milestone.get('created_at') or ''}",
        f"- Updated At: {milestone.get('updated_at') or ''}",
        f"- Issue Count: {len(issues)}",
        "",
        "## Description",
        "",
        milestone.get("description") or "_No description_",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("_No issues found for this milestone._")
        lines.append("")
        return "\n".join(lines)

    for issue in issues:
        lines.extend(
            [
                f"- `{issue.get('references', {}).get('full') or issue.get('web_url') or issue.get('iid')}` {issue.get('title', '')}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_issue_markdown(issue: dict[str, Any]) -> str:
    author = (issue.get("author") or {}).get("name", "")
    assignees = ", ".join(user.get("name", "") for user in issue.get("assignees") or [] if user.get("name"))
    labels = ", ".join(issue.get("labels") or [])
    refs = issue.get("references") or {}

    lines = [
        f"# Issue: {issue.get('title', '')}",
        "",
        "## Metadata",
        "",
        f"- Issue ID: {issue.get('id', '')}",
        f"- Issue IID: {issue.get('iid', '')}",
        f"- Reference: {refs.get('full') or refs.get('short') or ''}",
        f"- State: {issue.get('state', '')}",
        f"- Author: {author}",
        f"- Assignees: {assignees}",
        f"- Labels: {labels}",
        f"- Created At: {issue.get('created_at') or ''}",
        f"- Updated At: {issue.get('updated_at') or ''}",
        f"- Closed At: {issue.get('closed_at') or ''}",
        f"- Due Date: {issue.get('due_date') or ''}",
        f"- Web URL: {issue.get('web_url') or ''}",
        "",
        "## Description",
        "",
        issue.get("description") or "_No description_",
        "",
    ]
    return "\n".join(lines)
