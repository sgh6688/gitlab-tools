from __future__ import annotations

import unittest
from collections.abc import Iterator
from typing import Any

from gitlab_tools.commands.repositories.api import RepositoryApi
from gitlab_tools.common.gitlab_api import GitLabProtocolError


class FakeClient:
    def __init__(self) -> None:
        self.get_responses: dict[str, dict[str, Any]] = {}
        self.page_responses: dict[tuple[str, tuple[tuple[str, Any], ...]], list[dict[str, Any]]] = {}
        self.get_calls: list[str] = []
        self.page_calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(self, path: str) -> dict[str, Any]:
        self.get_calls.append(path)
        return self.get_responses[path]

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        params = params or {}
        self.page_calls.append((path, params))
        yield from self.page_responses.get((path, tuple(sorted(params.items()))), [])


class RepositoryApiTests(unittest.TestCase):
    def test_current_username_is_loaded_from_authenticated_user_endpoint(self) -> None:
        client = FakeClient()
        client.get_responses["/user"] = {"id": 8, "username": "actual-gitlab-user"}

        username = RepositoryApi(client).current_username()

        self.assertEqual("actual-gitlab-user", username)
        self.assertEqual(["/user"], client.get_calls)

    def test_current_username_rejects_values_unsafe_for_http_basic(self) -> None:
        for username in ("", "domain:user", "domain\tuser"):
            with self.subTest(username=username):
                client = FakeClient()
                client.get_responses["/user"] = {"id": 8, "username": username}

                with self.assertRaisesRegex(GitLabProtocolError, "username"):
                    RepositoryApi(client).current_username()

    def test_full_project_path_is_url_encoded_and_looked_up_directly(self) -> None:
        client = FakeClient()
        client.get_responses["/projects/team%2Fplatform%2Ftool"] = {
            "id": 7,
            "path_with_namespace": "team/platform/tool",
            "http_url_to_repo": "https://gitlab.example.com/team/platform/tool.git",
        }

        project = RepositoryApi(client).resolve_project("team/platform/tool")

        self.assertEqual(7, project["id"])
        self.assertEqual(["/projects/team%2Fplatform%2Ftool"], client.get_calls)

    def test_exact_bare_project_name_can_be_resolved(self) -> None:
        client = FakeClient()
        params = {"search": "tool", "simple": "true"}
        client.page_responses[("/projects", tuple(sorted(params.items())))] = [
            {"id": 1, "name": "toolbox", "path": "toolbox", "path_with_namespace": "a/toolbox"},
            {"id": 2, "name": "tool", "path": "tool", "path_with_namespace": "b/tool"},
        ]
        client.get_responses["/projects/2"] = {
            "id": 2,
            "name": "tool",
            "path_with_namespace": "b/tool",
            "http_url_to_repo": "https://gitlab.example.com/b/tool.git",
        }

        project = RepositoryApi(client).resolve_project("tool")

        self.assertEqual(2, project["id"])
        self.assertEqual("https://gitlab.example.com/b/tool.git", project["http_url_to_repo"])
        self.assertEqual(["/projects/2"], client.get_calls)

    def test_ambiguous_bare_project_name_has_clear_error(self) -> None:
        client = FakeClient()
        params = {"search": "tool", "simple": "true"}
        client.page_responses[("/projects", tuple(sorted(params.items())))] = [
            {"id": 1, "name": "tool", "path": "tool", "path_with_namespace": "a/tool"},
            {"id": 2, "name": "tool", "path": "tool", "path_with_namespace": "b/tool"},
        ]

        with self.assertRaisesRegex(ValueError, "a/tool.*b/tool"):
            RepositoryApi(client).resolve_project("tool")

    def test_bare_name_search_rejects_invalid_project_id_before_detail_request(self) -> None:
        params = {"search": "tool", "simple": "true"}
        for invalid_id in (True, "2", 0, -1):
            with self.subTest(invalid_id=invalid_id):
                client = FakeClient()
                client.page_responses[("/projects", tuple(sorted(params.items())))] = [
                    {"id": invalid_id, "name": "tool", "path": "tool", "path_with_namespace": "b/tool"}
                ]
                with self.assertRaisesRegex(GitLabProtocolError, "有效的 id"):
                    RepositoryApi(client).resolve_project("tool")
                self.assertEqual([], client.get_calls)

    def test_group_projects_preserve_api_paths_and_include_subgroups(self) -> None:
        client = FakeClient()
        path = "/groups/team%2Fplatform/projects"
        params = {"include_subgroups": "true", "with_shared": "false"}
        projects = [
            {
                "id": 1,
                "path_with_namespace": "team/platform/a",
                "http_url_to_repo": "https://gitlab.example.com/team/platform/a.git",
            },
            {
                "id": 2,
                "path_with_namespace": "team/platform/sub/b",
                "http_url_to_repo": "https://gitlab.example.com/team/platform/sub/b.git",
            },
        ]
        client.page_responses[(path, tuple(sorted(params.items())))] = projects

        result = RepositoryApi(client).list_group_projects("team/platform", include_subgroups=True)

        self.assertEqual(projects, result)
        self.assertEqual((path, params), client.page_calls[0])

    def test_project_missing_required_field_is_protocol_error(self) -> None:
        complete = {
            "id": 7,
            "path_with_namespace": "team/tool",
            "http_url_to_repo": "https://gitlab.example.com/team/tool.git",
        }
        for missing_field in complete:
            with self.subTest(missing_field=missing_field):
                client = FakeClient()
                response = dict(complete)
                response.pop(missing_field)
                client.get_responses["/projects/team%2Ftool"] = response

                with self.assertRaisesRegex(GitLabProtocolError, missing_field):
                    RepositoryApi(client).resolve_project("team/tool")


if __name__ == "__main__":
    unittest.main()
