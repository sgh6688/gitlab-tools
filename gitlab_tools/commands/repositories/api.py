from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol
from urllib.parse import quote

from ...common.gitlab_api import GitLabProtocolError


class RepositoryGitLabClient(Protocol):
    def get_json(self, path: str) -> dict[str, Any]: ...

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]: ...


class RepositoryTargetError(ValueError):
    """A user-specified project or group target is invalid or ambiguous."""


class RepositoryApi:
    """GitLab API operations owned by repository source export."""

    def __init__(self, client: RepositoryGitLabClient) -> None:
        self.client = client

    def resolve_project(self, project: str) -> dict[str, Any]:
        value = project.strip().strip("/")
        if not value:
            raise RepositoryTargetError("project 不能为空。")
        if "/" in value or value.isdigit():
            return self._validate_project(self.client.get_json(f"/projects/{quote(value, safe='')}"))

        params = {"search": value, "simple": "true"}
        exact_matches = [
            item
            for item in self.client.paginate("/projects", params=params)
            if str(item.get("name", "")).casefold() == value.casefold()
            or str(item.get("path", "")).casefold() == value.casefold()
        ]
        if not exact_matches:
            raise RepositoryTargetError(f"未找到名称为 {value!r} 的可见 project；建议使用完整 group/project 路径。")
        if len(exact_matches) > 1:
            paths = ", ".join(sorted(str(item.get("path_with_namespace", "")) for item in exact_matches))
            raise RepositoryTargetError(f"project 名称 {value!r} 不唯一: {paths}。请使用完整路径。")
        project_id = exact_matches[0].get("id")
        if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
            raise GitLabProtocolError("GitLab project 搜索结果缺少有效的 id。")
        return self._validate_project(self.client.get_json(f"/projects/{project_id}"))

    def list_group_projects(self, group: str, *, include_subgroups: bool) -> list[dict[str, Any]]:
        value = group.strip().strip("/")
        if not value:
            raise RepositoryTargetError("group 不能为空。")
        params = {
            "include_subgroups": str(include_subgroups).lower(),
            "with_shared": "false",
        }
        projects = list(
            self.client.paginate(
                f"/groups/{quote(value, safe='')}/projects",
                params=params,
            )
        )
        return [self._validate_project(project) for project in projects]

    @staticmethod
    def _validate_project(project: dict[str, Any]) -> dict[str, Any]:
        project_id = project.get("id")
        if isinstance(project_id, bool) or not isinstance(project_id, int) or project_id <= 0:
            raise GitLabProtocolError("GitLab project 响应缺少有效的 id。")
        for field in ("path_with_namespace", "http_url_to_repo"):
            value = project.get(field)
            if not isinstance(value, str) or not value.strip():
                raise GitLabProtocolError(f"GitLab project 响应缺少有效的 {field}。")
        return project
