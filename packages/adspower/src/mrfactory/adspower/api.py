"""A small client for the AdsPower Local API, the HTTP server the
AdsPower app runs on this machine while it's open.

Only HTTP lives here: building URLs and JSON bodies, sending requests,
unwrapping the API's `{"code": 0, "data": ..., "msg": ...}` envelope,
paging, and rate limiting. What the data *means* is up to
`client.AdsPower`.

API reference: https://localapi-doc-en.adspower.com/
(The tag endpoints, /api/v2/browser-tags/*, aren't in those docs; they
are used by AdsPower's own MCP server, github.com/AdsPower/local-api-mcp-typescript.)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from .errors import AdsPowerApiError, AdsPowerNotRunning, ConfigError

DEFAULT_API_URL = "http://127.0.0.1:50325"

# The API allows 2 requests/second for small accounts (more for larger
# ones), so stay at or under that when fetching many pages in a row.
DEFAULT_MIN_INTERVAL = 0.5

# Requests from an earlier run (or another tool) still count against the
# limit, so a refusal is retried a few times after a pause.
RATE_LIMIT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0

# Paging stops at the first short page. If an API ever ignored the page
# number and kept sending full pages, the loop would never end; this cap
# turns that into an error instead (1000 pages = 100,000+ profiles).
MAX_PAGES = 1000

# Only these URL schemes may be opened. urllib also understands file:// and
# others, so an unchecked --api-url could make it read local files.
ALLOWED_SCHEMES = ("http", "https")


class LocalApi:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        opener: Callable = urllib.request.urlopen,
    ):
        """`base_url` and `api_key` default to the ADSPOWER_API_URL and
        ADSPOWER_API_KEY environment variables. The API key is only
        needed if API security verification is turned on in AdsPower.
        `opener` is swappable so tests never make real requests."""
        self.base_url = (base_url or os.environ.get("ADSPOWER_API_URL") or DEFAULT_API_URL).rstrip("/")
        if urllib.parse.urlsplit(self.base_url).scheme not in ALLOWED_SCHEMES:
            raise ConfigError(f"API URL must start with http:// or https://, got {self.base_url!r}.")
        self.api_key = api_key or os.environ.get("ADSPOWER_API_KEY")
        self.timeout = timeout
        self.min_interval = min_interval
        self.retry_delay = retry_delay
        self._open = opener
        self._last_request = 0.0

    def is_running(self) -> bool:
        """True if the Local API answers, i.e. AdsPower is open."""
        try:
            self._request("/status")
        except AdsPowerNotRunning:
            return False
        return True

    def get(self, path: str, **params) -> dict:
        """GET an endpoint (most /api/v1/ ones) and return its `data`
        part. Parameters that are None are left out."""
        return self._call(path, params=params)

    def post(self, path: str, body: dict | None = None) -> dict:
        """POST a JSON body (most /api/v2/ ones) and return its `data`
        part. Keys whose value is None are left out."""
        body = {key: value for key, value in (body or {}).items() if value is not None}
        return self._call(path, body=body)

    def get_all(self, path: str, page_size: int, **params) -> list[dict]:
        """Read every page of a GET list endpoint (`page`/`page_size`
        in the query string) and return all items."""
        return _read_all_pages(lambda page: self.get(path, page=page, page_size=page_size, **params), page_size)

    def post_all(self, path: str, limit: int, **body) -> list[dict]:
        """Read every page of a POST list endpoint (`page`/`limit` in
        the JSON body) and return all items."""
        return _read_all_pages(lambda page: self.post(path, {**body, "page": page, "limit": limit}), limit)

    def _call(self, path: str, params: dict | None = None, body: dict | None = None) -> dict:
        """Send the request, retrying if the API says "too many
        requests", and unwrap the `{"code", "data", "msg"}` envelope.

        Retrying is safe even for requests that change things: a
        rate-limit refusal means the request was not carried out."""
        response = self._request(path, params, body)
        for _ in range(RATE_LIMIT_RETRIES):
            if not _is_rate_limited(response):
                break
            time.sleep(self.retry_delay)
            response = self._request(path, params, body)
        if response.get("code") != 0:
            raise AdsPowerApiError(f"{path} failed: {response.get('msg') or response}")
        return response.get("data") or {}

    def _request(self, path: str, params: dict | None = None, body: dict | None = None) -> dict:
        """One HTTP request: GET with `params`, or POST with JSON `body`."""
        url = self.base_url + path
        query = {key: value for key, value in (params or {}).items() if value is not None}
        if query:
            url += "?" + urllib.parse.urlencode(query)

        if body is None:
            request = urllib.request.Request(url)  # noqa: S310 - scheme checked in __init__
        else:
            request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")  # noqa: S310
            request.add_header("Content-Type", "application/json")
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")

        self._wait_for_rate_limit()
        try:
            with self._open(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as e:  # answered, but with an error status
            raise AdsPowerApiError(f"{path} returned HTTP {e.code}") from e
        except (urllib.error.URLError, OSError) as e:  # nobody answered
            raise AdsPowerNotRunning(
                f"Can't reach the AdsPower Local API at {self.base_url}. "
                "Is AdsPower open? Start it with: adspower open"
            ) from e

        try:
            return json.loads(raw)
        except ValueError as e:
            raise AdsPowerApiError(f"{path} returned something that isn't JSON") from e

    def _wait_for_rate_limit(self) -> None:
        wait = self._last_request + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()


def _is_rate_limited(body: dict) -> bool:
    # The API reports this as an ordinary failure, e.g.
    # {"code": -1, "msg": "Too many request per second, please check"}
    return body.get("code") != 0 and "too many request" in str(body.get("msg", "")).lower()


def _read_all_pages(fetch_page: Callable[[int], dict], page_size: int) -> list[dict]:
    """Call `fetch_page(1)`, `fetch_page(2)`, ... until a page has fewer
    than `page_size` items, and return all items."""
    items: list[dict] = []
    page = 1
    while page <= MAX_PAGES:
        batch = fetch_page(page).get("list") or []
        items.extend(batch)
        if len(batch) < page_size:
            return items
        page += 1
    raise AdsPowerApiError(f"Stopped after {MAX_PAGES} full pages; the API may be ignoring the page number.")
