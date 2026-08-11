from __future__ import annotations

import unittest
from pathlib import Path

from gitlab_tools.commands.milestones.markdown import render_issue_markdown, render_milestone_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ISSUES = [
    {
        "id": 4201,
        "iid": 42,
        "title": "Add export status summary",
        "state": "closed",
        "author": {"name": "Example User"},
        "assignees": [{"name": "Example Maintainer"}],
        "labels": ["feature", "documentation"],
        "created_at": "2026-07-08T10:00:00Z",
        "updated_at": "2026-08-01T09:30:00Z",
        "closed_at": "2026-08-01T09:30:00Z",
        "due_date": "2026-09-15",
        "web_url": "https://gitlab.example.com/example-org/platform/api-service/-/issues/42",
        "references": {"full": "example-org/platform/api-service#42"},
        "description": (
            "Add a short summary after an export so operators can see the number of "
            "successful, skipped, and failed targets."
        ),
    },
    {
        "id": 1801,
        "iid": 18,
        "title": "Document offline installation",
        "state": "opened",
        "references": {"full": "example-org/platform/web-client#18"},
    },
]

MILESTONE = {
    "id": 101,
    "iid": 7,
    "title": "2026 Q3 delivery",
    "state": "active",
    "start_date": "2026-07-01",
    "due_date": "2026-09-30",
    "created_at": "2026-06-15T08:00:00Z",
    "updated_at": "2026-08-01T09:30:00Z",
    "description": "Prepare the example API and web client for the Q3 delivery window.",
}


class ExampleOutputTests(unittest.TestCase):
    def test_issue_example_matches_real_renderer(self) -> None:
        expected = render_issue_markdown(ISSUES[0])
        actual = (PROJECT_ROOT / "examples" / "issue-example.md").read_text(encoding="utf-8")
        self.assertEqual(expected, actual)

    def test_milestone_example_matches_real_renderer(self) -> None:
        expected = render_milestone_markdown("group", "example-org/platform", MILESTONE, ISSUES)
        actual = (PROJECT_ROOT / "examples" / "milestone-example.md").read_text(encoding="utf-8")
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
