from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gitlab_tools.commands.repositories.config import load_config as load_repository_config
from gitlab_tools.common.config import load_gitlab_config


class SharedGitLabConfigTests(unittest.TestCase):
    def test_token_falls_back_to_configured_environment_variable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gitlab.config.txt"
            path.write_text(
                "gitlab_url=https://gitlab.example.com/\n"
                "token=\n"
                "token_env_var=MY_GITLAB_TOKEN\n"
                "verify_ssl=false\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"MY_GITLAB_TOKEN": "secret-token"}, clear=False):
                config = load_gitlab_config(path)

        self.assertEqual("https://gitlab.example.com", config.gitlab_url)
        self.assertEqual("secret-token", config.token)
        self.assertFalse(config.verify_ssl)

    def test_gitlab_url_rejects_credentials_and_non_http_schemes(self) -> None:
        for value in ("ftp://gitlab.example.com", "https://user:secret@gitlab.example.com", "https:///missing"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "gitlab.config.txt"
                path.write_text(f"gitlab_url={value}\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "gitlab_url"):
                    load_gitlab_config(path)


class RepositoryExportConfigTests(unittest.TestCase):
    def test_cli_targets_replace_file_targets_and_override_scalars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repositories.config.txt"
            path.write_text(
                "output_dir=file-output\n"
                "projects=file-group/file-project\n"
                "groups=file-group\n"
                "include_subgroups=false\n"
                "existing=fail\n",
                encoding="utf-8",
            )

            config = load_repository_config(
                path,
                cli_projects=["cli-group/cli-project"],
                cli_groups=[],
                output_dir="cli-output",
                include_subgroups=True,
                existing="update",
            )

        self.assertEqual(["cli-group/cli-project"], config.projects)
        self.assertEqual([], config.groups)
        self.assertEqual(Path("cli-output"), config.output_dir)
        self.assertTrue(config.include_subgroups)
        self.assertEqual("update", config.existing)

    def test_file_targets_are_used_when_cli_has_no_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repositories.config.txt"
            path.write_text("projects=team/project-a,team/project-b\n", encoding="utf-8")

            config = load_repository_config(path)

        self.assertEqual(["team/project-a", "team/project-b"], config.projects)

    def test_at_least_one_target_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "project.*group"):
            load_repository_config(None)


if __name__ == "__main__":
    unittest.main()
