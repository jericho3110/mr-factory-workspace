"""Proxy health check: does a profile's proxy actually carry traffic?

    result = ads.check_proxy("1234")        # open, check, close (client.py)
    result.ok, result.ip, result.error      # True, '198.51.100.7', ''
    result.text                             # 'ok (198.51.100.7)' or 'failed: ERR_...'

How: in the profile's own browser (so through its proxy, like every
page it loads) it opens a small "what is my IP?" page, by default
`https://api.ipify.org?format=json`, which answers `{"ip": "..."}`.
The page loads → the proxy works, and that's the exit IP sites see.
It doesn't load → Chrome's error code says why
(`ERR_PROXY_CONNECTION_FAILED`, `ERR_TUNNEL_CONNECTION_FAILED`, ...).

Talking to the browser needs Playwright, the one part of this package
that isn't standard library. It's an *optional* dependency:

    pip install "mrfactory-adspower[browser]"   # adds Playwright

Without it, `check_proxy` raises `ProxyCheckUnavailable` with that
command. Or pass your own `fetch(ws_endpoint, url) -> text` function
(the tests do; so can a program that already drives the browser).

ipify is a third-party service: it sees the proxy's IP, as every site
the profile visits does. Pass `url=` to use a different page that
answers the same way.
"""

from __future__ import annotations

import contextlib
import ipaddress
import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from .errors import AdsPowerError
from .models import OpenedBrowser, Profile

CHECK_URL = "https://api.ipify.org?format=json"
NAV_TIMEOUT_MS = 45_000

# (the browser's puppeteer ws:// address, url) -> the page's text; raises if it doesn't load.
Fetch = Callable[[str, str], str]

# Chrome's network error codes look like net::ERR_PROXY_CONNECTION_FAILED.
_ERROR_CODE = re.compile(r"\b(ERR_[A-Z_]+)\b")


class ProxyCheckUnavailable(AdsPowerError):
    """Playwright isn't installed, so the default check can't talk to the browser."""


@dataclass(frozen=True)
class ProxyCheck:
    ok: bool
    ip: str = ""            # the exit IP, when ok
    error: str = ""         # Chrome's error code (or a short reason), when not ok
    profile: Profile | None = None

    @property
    def text(self) -> str:
        """'ok (198.51.100.7)' or 'failed: ERR_PROXY_CONNECTION_FAILED'."""
        return f"ok ({self.ip})" if self.ok else f"failed: {self.error}"


def parse_ip(text: str) -> str | None:
    """The IP in a `{"ip": "..."}` answer, or None if it isn't a real
    IPv4/IPv6 address (so a proxy's block page can't pass as working)."""
    try:
        value = json.loads(text).get("ip", "")
        return str(ipaddress.ip_address(value))
    except (ValueError, AttributeError, TypeError):
        return None


def error_code(text: str) -> str:
    """Chrome's error code in `text` ('ERR_PROXY_AUTH_REQUESTED'), or
    its first line if there's none."""
    found = _ERROR_CODE.search(text)
    return found.group(1) if found else text.splitlines()[0] if text else ""


def check_browser(browser: OpenedBrowser, fetch: Fetch | None = None, url: str = CHECK_URL,
                  profile: Profile | None = None) -> ProxyCheck:
    """Check the proxy of a browser that's already open (from
    `ads.open_profile`). Never raises for a failing proxy: that's a
    result, `ok=False`. Raises ProxyCheckUnavailable without Playwright
    (and no `fetch`)."""
    fetch = fetch or playwright_fetch
    try:
        text = fetch(browser.puppeteer, url)
    except ProxyCheckUnavailable:
        raise
    except Exception as e:  # Playwright's errors (timeouts, net::ERR_...): a failed check
        return ProxyCheck(ok=False, error=error_code(str(e)) or "didn't load", profile=profile)
    ip = parse_ip(text)
    if ip is None:
        return ProxyCheck(ok=False, error="unexpected answer", profile=profile)
    return ProxyCheck(ok=True, ip=ip, profile=profile)


def playwright_fetch(ws_endpoint: str, url: str, timeout_ms: int = NAV_TIMEOUT_MS) -> str:
    """The default fetch: attach to the profile's browser with Playwright
    (it doesn't launch one), open `url` in a new tab, return the page's
    text, close that tab. The browser itself stays as it was."""
    try:
        from playwright.sync_api import sync_playwright  # optional: only needed here
    except ImportError as e:
        raise ProxyCheckUnavailable(
            'The proxy check needs Playwright: pip install "mrfactory-adspower[browser]"'
        ) from e
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return page.inner_text("body")
        finally:
            with contextlib.suppress(Exception):  # the tab may already be gone; nothing to clean up
                page.close(run_before_unload=False)
