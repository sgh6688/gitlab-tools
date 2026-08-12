from __future__ import annotations

import json
import base64
import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RepositoryCliIntegrationTests(unittest.TestCase):
    def test_cli_reads_configs_calls_api_and_clones_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.create_source_repository(root)
            http_root = root / "http-root"
            bare_repository = http_root / "team" / "tool.git"
            bare_repository.parent.mkdir(parents=True)
            subprocess.run(["git", "clone", "--bare", "-q", str(source), str(bare_repository)], check=True)
            subprocess.run(["git", "-C", str(bare_repository), "update-server-info"], check=True)
            output = root / "export"
            expected_token = "integration-token"
            expected_username = "actual-gitlab-user"
            expected_basic = "Basic " + base64.b64encode(
                f"{expected_username}:{expected_token}".encode("utf-8")
            ).decode("ascii")

            class Handler(SimpleHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802
                    if not self.path.startswith("/api/v4/"):
                        if self.headers.get("Authorization") != expected_basic:
                            self.send_response(401)
                            self.send_header("WWW-Authenticate", 'Basic realm="GitLab"')
                            self.end_headers()
                            return
                        super().do_GET()
                        return
                    if self.headers.get("PRIVATE-TOKEN") != expected_token:
                        self.send_response(401)
                        self.end_headers()
                        return
                    if self.path.startswith("/api/v4/user"):
                        payload = json.dumps({"id": 8, "username": expected_username}).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    if not self.path.startswith("/api/v4/projects/team%2Ftool"):
                        self.send_response(404)
                        self.end_headers()
                        return
                    payload = json.dumps(
                        {
                            "id": 9,
                            "name": "tool",
                            "path_with_namespace": "team/tool",
                            "http_url_to_repo": f"http://127.0.0.1:{server.server_port}/team/tool.git",
                        }
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(self, format: str, *args: object) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(http_root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                gitlab_config = root / "gitlab.config.txt"
                gitlab_config.write_text(
                    f"gitlab_url=http://127.0.0.1:{server.server_port}\n"
                    f"token={expected_token}\n",
                    encoding="utf-8",
                )
                feature_config = root / "repositories.config.txt"
                feature_config.write_text(
                    f"output_dir={output}\nprojects=team/tool\n",
                    encoding="utf-8",
                )

                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "gitlab_tools",
                        "repositories",
                        "export",
                        "--gitlab-config",
                        str(gitlab_config),
                        "--config",
                        str(feature_config),
                    ],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            self.assertEqual(0, result.returncode, result.stderr)
            destination = output / "team" / "tool"
            self.assertFalse((destination / ".git").exists())
            self.assertEqual("integration\n", (destination / "README.md").read_text(encoding="utf-8"))

    def create_source_repository(self, directory: Path) -> Path:
        source = directory / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True)
        (source / "README.md").write_text("integration\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "initial"], check=True)
        return source


if __name__ == "__main__":
    unittest.main()
