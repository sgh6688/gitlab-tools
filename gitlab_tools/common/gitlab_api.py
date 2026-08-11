from __future__ import annotations

import json
import ssl
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


@dataclass(slots=True)
class GitLabClient:
    base_url: str
    token: str
    timeout_seconds: int = 30
    page_size: int = 100
    verify_ssl: bool = True
    ssl_context: ssl.SSLContext | None = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        if self.base_url.lower().startswith("https://") and not self.verify_ssl:
            self.ssl_context = ssl._create_unverified_context()

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        page = 1
        while True:
            query = dict(params or {})
            query.update({"per_page": self.page_size, "page": page})
            response = self._request_json(
                f"{self.base_url}/api/v4{path}",
                params=query,
            )
            payload = response["payload"]
            if not isinstance(payload, list):
                raise ValueError(f"GitLab API 返回了非列表数据: {path}")
            for item in payload:
                yield item
            next_page = response["headers"].get("X-Next-Page", "").strip()
            if not next_page:
                break
            page = int(next_page)


    def _request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        final_url = self._append_query(url, params)
        request = Request(
            final_url,
            headers={
                "PRIVATE-TOKEN": self.token,
                "Accept": "application/json",
                "User-Agent": "gitlab-tools/0.2.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds, context=self.ssl_context) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body)
                headers = {key: value for key, value in response.headers.items()}
                return {"payload": payload, "headers": headers}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GitLabHttpError(exc.code, body) from exc
        except URLError as exc:
            raise RuntimeError(f"网络请求失败: {exc}") from exc

    @staticmethod
    def _append_query(url: str, params: dict[str, Any]) -> str:
        parts = urlsplit(url)
        query = urlencode(params)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


class GitLabHttpError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"HTTP {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body
