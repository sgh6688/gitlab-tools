from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gitlab_tools.commands.milestones.command import run_init_config as run_milestone_init_config
from gitlab_tools.commands.repositories.command import run_export as run_repository_export
from gitlab_tools.commands.repositories.command import run_init_config as run_repository_init_config


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

    def test_milestones_help_lists_export_and_init_config_commands(self) -> None:
        result = self.run_cli("milestones", "--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("export", result.stdout)
        self.assertIn("init-config", result.stdout)

    def test_milestones_init_config_creates_templates_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            first = self.run_cli("milestones", "init-config", "--directory", str(destination))

            self.assertEqual(0, first.returncode, first.stderr)
            config_file = destination / "milestones.config.txt"
            batch_file = destination / "run_milestones_export.bat"
            self.assertTrue(config_file.is_file())
            self.assertTrue(batch_file.is_file())
            config_file.write_text("keep\n", encoding="utf-8")

            second = self.run_cli("milestones", "init-config", "--directory", str(destination))

            self.assertEqual(1, second.returncode)
            self.assertEqual("keep\n", config_file.read_text(encoding="utf-8"))
            self.assertIn("已存在", second.stderr)

    def test_init_config_write_failure_removes_partial_files_for_all_features(self) -> None:
        real_open = Path.open

        class FailingWriteHandle:
            def __init__(self, handle: Any) -> None:
                self.handle = handle

            def __enter__(self) -> "FailingWriteHandle":
                return self

            def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
                self.handle.close()

            def write(self, content: str) -> int:
                self.handle.write(content[:5])
                self.handle.flush()
                raise OSError("simulated disk-full failure")

        def failing_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            handle = real_open(path, *args, **kwargs)
            mode = str(args[0]) if args else str(kwargs.get("mode", "r"))
            return FailingWriteHandle(handle) if mode == "x" else handle

        for initializer in (run_milestone_init_config, run_repository_init_config):
            with self.subTest(initializer=initializer.__module__), tempfile.TemporaryDirectory() as directory:
                with patch.object(Path, "open", new=failing_open):
                    result = initializer(Namespace(directory=directory))

                self.assertEqual(3, result)
                self.assertEqual([], list(Path(directory).iterdir()))

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
            args = Namespace(gitlab_config=str(gitlab_config), config=str(feature_config))
            stderr = StringIO()

            with (
                patch(
                    "gitlab_tools.commands.repositories.command.setup_logging",
                    side_effect=OSError("simulated log write failure"),
                ),
                redirect_stderr(stderr),
            ):
                result = run_repository_export(args)

        self.assertEqual(3, result)
        self.assertIn("无法创建日志文件", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
