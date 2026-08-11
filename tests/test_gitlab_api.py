from __future__ import annotations

import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from gitlab_tools.common.gitlab_api import GitLabClient, GitLabHttpError, GitLabProtocolError


class StubGitLabClient(GitLabClient):
    def __init__(self) -> None:
        super().__init__("https://gitlab.example.com", "")
        self.responses: list[dict[str, Any]] = [
            {"payload": [{"id": 1}], "headers": {"x-next-page": "2"}},
            {"payload": [{"id": 2}], "headers": {}},
        ]

    def _request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        return self.responses.pop(0)


class GitLabClientTests(unittest.TestCase):
    def test_pagination_header_is_case_insensitive(self) -> None:
        projects = list(StubGitLabClient().paginate("/projects"))

        self.assertEqual([{"id": 1}, {"id": 2}], projects)

    def test_invalid_pagination_header_is_protocol_error(self) -> None:
        client = StubGitLabClient()
        client.responses = [{"payload": [{"id": 1}], "headers": {"x-next-page": "invalid"}}]

        with self.assertRaisesRegex(GitLabProtocolError, "X-Next-Page"):
            list(client.paginate("/projects"))

    def test_non_object_page_item_is_protocol_error(self) -> None:
        client = StubGitLabClient()
        client.responses = [{"payload": ["invalid"], "headers": {}}]

        with self.assertRaisesRegex(GitLabProtocolError, "非对象元素"):
            list(client.paginate("/projects"))

    def test_non_advancing_numeric_pagination_is_protocol_error(self) -> None:
        for next_page in ("0", "-1", "1"):
            with self.subTest(next_page=next_page):
                client = StubGitLabClient()
                client.responses = [{"payload": [], "headers": {"X-Next-Page": next_page}}]
                with self.assertRaisesRegex(GitLabProtocolError, "未向前推进"):
                    list(client.paginate("/projects"))

    def test_api_token_is_not_forwarded_to_cross_origin_redirect(self) -> None:
        redirected_tokens: list[str] = []

        class DestinationHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                redirected_tokens.append(self.headers.get("PRIVATE-TOKEN", ""))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format: str, *args: object) -> None:
                return

        destination = ThreadingHTTPServer(("127.0.0.1", 0), DestinationHandler)

        class SourceHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/redirected")
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        source = ThreadingHTTPServer(("127.0.0.1", 0), SourceHandler)
        threads = [
            threading.Thread(target=destination.serve_forever, daemon=True),
            threading.Thread(target=source.serve_forever, daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            client = GitLabClient(f"http://127.0.0.1:{source.server_port}", token="secret-token")
            with self.assertRaisesRegex(GitLabProtocolError, "跨 origin"):
                client.get_json("/projects/1")
        finally:
            source.shutdown()
            destination.shutdown()
            source.server_close()
            destination.server_close()
            for thread in threads:
                thread.join(timeout=5)

        self.assertEqual([], redirected_tokens)

    def test_http_error_body_redacts_echoed_api_token(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = b"request rejected: secret-token"
                self.send_response(500)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = GitLabClient(f"http://127.0.0.1:{server.server_port}", token="secret-token")
            with self.assertRaises(GitLabHttpError) as caught:
                client.get_json("/projects/1")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        message = str(caught.exception)
        self.assertNotIn("secret-token", message)
        self.assertIn("[REDACTED]", message)


if __name__ == "__main__":
    unittest.main()
