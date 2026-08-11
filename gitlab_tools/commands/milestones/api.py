from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol
from urllib.parse import quote


class PaginatedGitLabClient(Protocol):
    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]: ...


class MilestoneApi:
    """GitLab API operations owned by the milestones feature."""

    def __init__(self, client: PaginatedGitLabClient) -> None:
        self.client = client

    def list_group_milestones(self, group_path: str) -> list[dict[str, Any]]:
        return self._list_all_milestones(f"/groups/{self._encode_path(group_path)}/milestones")

    def list_project_milestones(self, project_path: str) -> list[dict[str, Any]]:
        return self._list_all_milestones(f"/projects/{self._encode_path(project_path)}/milestones")

    def list_group_issues(self, group_path: str, milestone: dict[str, Any]) -> list[dict[str, Any]]:
        issues = list(
            self.client.paginate(
                f"/groups/{self._encode_path(group_path)}/issues",
                params={"scope": "all", "state": "all", "milestone": milestone["title"]},
            )
        )
        milestone_id = milestone["id"]
        return [issue for issue in issues if (issue.get("milestone") or {}).get("id") == milestone_id]

    def list_project_issues(self, project_path: str, milestone: dict[str, Any]) -> list[dict[str, Any]]:
        return list(
            self.client.paginate(
                f"/projects/{self._encode_path(project_path)}/milestones/{milestone['id']}/issues",
                params={"state": "all"},
            )
        )

    def _list_all_milestones(self, path: str) -> list[dict[str, Any]]:
        milestones_by_id: dict[int, dict[str, Any]] = {}
        for state in ("active", "closed"):
            for milestone in self.client.paginate(path, params={"state": state}):
                milestones_by_id[int(milestone["id"])] = milestone
        return list(milestones_by_id.values())

    @staticmethod
    def _encode_path(path: str) -> str:
        return quote(path, safe="")
