from __future__ import annotations

import subprocess
import sys
import tempfile
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

    def test_root_help_lists_feature_commands(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("gitlab-tools", result.stdout)
        self.assertIn("milestones", result.stdout)
        self.assertIn("repositories", result.stdout)

    def test_repositories_export_has_friendly_configuration_options(self) -> None:
        result = self.run_cli("repositories", "export", "--help")

        self.assertEqual(0, result.returncode, result.stderr)
        for option in (
            "--gitlab-config",
            "--config",
            "--project",
            "--group",
            "--output-dir",
            "--include-subgroups",
            "--existing",
        ):
            self.assertIn(option, result.stdout)

    def test_repositories_help_lists_init_config(self) -> None:
        result = self.run_cli("repositories", "--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("init-config", result.stdout)

    def test_repositories_init_config_creates_templates_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            first = self.run_cli("repositories", "init-config", "--directory", str(destination))

            self.assertEqual(0, first.returncode, first.stderr)
            gitlab_config = destination / "gitlab.config.txt"
            repositories_config = destination / "repositories.config.txt"
            batch_file = destination / "run_repositories_export.bat"
            self.assertTrue(gitlab_config.is_file())
            self.assertTrue(repositories_config.is_file())
            self.assertTrue(batch_file.is_file())
            gitlab_config.write_text("keep\n", encoding="utf-8")

            second = self.run_cli("repositories", "init-config", "--directory", str(destination))

            self.assertEqual(1, second.returncode)
            self.assertEqual("keep\n", gitlab_config.read_text(encoding="utf-8"))
            self.assertIn("已存在", second.stderr)

    def test_repositories_init_config_concurrent_calls_never_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            command = [
                sys.executable,
                "-m",
                "gitlab_tools",
                "repositories",
                "init-config",
                "--directory",
                directory,
            ]
            processes = [
                subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(2)
            ]
            results = [process.communicate(timeout=30) + (process.returncode,) for process in processes]

            self.assertEqual([0, 1], sorted(result[2] for result in results))
            destination = Path(directory)
            for name in ("gitlab.config.txt", "repositories.config.txt", "run_repositories_export.bat"):
                self.assertTrue((destination / name).is_file())

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

    def test_repository_export_missing_gitlab_config_has_clean_error(self) -> None:
        missing_config = PROJECT_ROOT / "does-not-exist" / "gitlab.config.txt"

        result = self.run_cli(
            "repositories",
            "export",
            "--gitlab-config",
            str(missing_config),
            "--project",
            "team/tool",
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("GitLab 配置文件不存在", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_repository_export_unwritable_log_directory_has_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            gitlab_config = config_dir / "gitlab.config.txt"
            feature_config = config_dir / "repositories.config.txt"
            gitlab_config.write_text("gitlab_url=https://gitlab.example.com\n", encoding="utf-8")
            feature_config.write_text("projects=team/tool\n", encoding="utf-8")
            config_dir.chmod(0o500)
            try:
                result = self.run_cli(
                    "repositories",
                    "export",
                    "--gitlab-config",
                    str(gitlab_config),
                    "--config",
                    str(feature_config),
                )
            finally:
                config_dir.chmod(0o700)

        self.assertEqual(3, result.returncode)
        self.assertIn("无法创建日志文件", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
