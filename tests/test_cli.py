from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "gitlab_tools", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_root_help_lists_milestones_command(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("gitlab-tools", result.stdout)
        self.assertIn("milestones", result.stdout)

    def test_milestones_help_lists_export_command(self) -> None:
        result = self.run_cli("milestones", "--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("export", result.stdout)

    def test_milestones_export_accepts_config_option(self) -> None:
        result = self.run_cli("milestones", "export", "--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--config", result.stdout)
        self.assertIn("milestones.config.txt", result.stdout)

    def test_missing_command_is_an_error(self) -> None:
        result = self.run_cli()

        self.assertNotEqual(0, result.returncode)
        self.assertIn("required", result.stderr.lower())

    def test_missing_config_in_missing_directory_has_clean_error(self) -> None:
        missing_config = PROJECT_ROOT / "does-not-exist" / "milestones.config.txt"

        result = self.run_cli("milestones", "export", "--config", str(missing_config))

        self.assertEqual(1, result.returncode)
        self.assertIn("配置文件不存在", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
