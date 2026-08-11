from __future__ import annotations

import unittest
from collections.abc import Iterator
from typing import Any

from gitlab_tools.commands.milestones.api import MilestoneApi


class FakeGitLabClient:
    def __init__(self, responses: dict[tuple[str, tuple[tuple[str, Any], ...]], list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        params = params or {}
        self.calls.append((path, params))
        key = (path, tuple(sorted(params.items())))
        yield from self.responses.get(key, [])


class MilestoneApiTests(unittest.TestCase):
    def test_group_issues_are_filtered_by_milestone_id(self) -> None:
        path = "/groups/team%2Fplatform/issues"
        params = {"scope": "all", "state": "all", "milestone": "Sprint 1"}
        client = FakeGitLabClient(
            {
                (path, tuple(sorted(params.items()))): [
                    {"id": 1, "milestone": {"id": 10}},
                    {"id": 2, "milestone": {"id": 20}},
                ]
            }
        )

        issues = MilestoneApi(client).list_group_issues("team/platform", {"id": 10, "title": "Sprint 1"})

        self.assertEqual([1], [issue["id"] for issue in issues])

    def test_all_milestone_states_are_merged_without_duplicates(self) -> None:
        path = "/projects/team%2Fproject/milestones"
        client = FakeGitLabClient(
            {
                (path, (("state", "active"),)): [{"id": 1, "state": "active"}],
                (path, (("state", "closed"),)): [
                    {"id": 1, "state": "closed"},
                    {"id": 2, "state": "closed"},
                ],
            }
        )

        milestones = MilestoneApi(client).list_project_milestones("team/project")

        self.assertEqual([1, 2], sorted(item["id"] for item in milestones))


if __name__ == "__main__":
    unittest.main()
