from __future__ import annotations

import json
import ssl
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
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
                raise GitLabProtocolError(f"GitLab API 返回了非列表数据: {path}")
            for item in payload:
                if not isinstance(item, dict):
                    raise GitLabProtocolError(f"GitLab API 列表包含非对象元素: {path}")
                yield item
            next_page = next(
                (
                    str(value).strip()
                    for key, value in response["headers"].items()
                    if str(key).lower() == "x-next-page"
                ),
                "",
            )
            if not next_page:
                break
            try:
                next_page_number = int(next_page)
            except ValueError as exc:
                raise GitLabProtocolError(f"GitLab API 返回了无效的 X-Next-Page: {next_page!r}") from exc
            if next_page_number <= page:
                raise GitLabProtocolError(
                    f"GitLab API 的 X-Next-Page 未向前推进: current={page}, next={next_page_number}"
                )
            page = next_page_number

    def get_json(self, path: str) -> dict[str, Any]:
        response = self._request_json(f"{self.base_url}/api/v4{path}", params={})
        payload = response["payload"]
        if not isinstance(payload, dict):
            raise GitLabProtocolError(f"GitLab API 返回了非对象数据: {path}")
        return payload


    def _request_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        final_url = self._append_query(url, params)
        headers = {
            "Accept": "application/json",
            "User-Agent": "gitlab-tools/0.3.6",
        }
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        request = Request(final_url, headers=headers, method="GET")
        opener = build_opener(
            SameOriginRedirectHandler(),
            HTTPSHandler(context=self.ssl_context),
        )
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise GitLabProtocolError("GitLab API 返回了无效 JSON。") from exc
                headers = {key: value for key, value in response.headers.items()}
                return {"payload": payload, "headers": headers}
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if self.token:
                body = body.replace(self.token, "[REDACTED]")
            raise GitLabHttpError(exc.code, body) from exc
        except URLError as exc:
            raise RuntimeError(f"网络请求失败: {exc}") from exc

    @staticmethod
    def _append_query(url: str, params: dict[str, Any]) -> str:
        parts = urlsplit(url)
        query = urlencode(params)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


class GitLabProtocolError(RuntimeError):
    """GitLab returned malformed JSON, schema, or pagination metadata."""


class SameOriginRedirectHandler(HTTPRedirectHandler):
    """Allow redirects only when scheme, host, and effective port stay unchanged."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        if _http_origin(req.full_url) != _http_origin(newurl):
            raise GitLabProtocolError("GitLab API 拒绝跨 origin 重定向，以防止 Token 泄漏。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_origin(value: str) -> tuple[str, str, int]:
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").casefold()
    if scheme not in {"http", "https"} or not hostname:
        raise GitLabProtocolError(f"GitLab API URL 无效: {value!r}")
    default_port = 443 if scheme == "https" else 80
    try:
        port = parts.port or default_port
    except ValueError as exc:
        raise GitLabProtocolError(f"GitLab API URL 端口无效: {value!r}") from exc
    return scheme, hostname, port


class GitLabHttpError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"HTTP {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body
