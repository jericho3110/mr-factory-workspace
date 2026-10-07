"""Stand-ins for the AdsPower Local API, so tests never need AdsPower
running."""

from __future__ import annotations

import copy
import io
import json

GROUPS = [
    {"group_id": "0", "group_name": "Ungrouped", "remark": ""},
    {"group_id": "101", "group_name": "Shopify", "remark": "stores"},
    {"group_id": "102", "group_name": "Socials", "remark": None},
    {"group_id": "103", "group_name": "Jericho", "remark": ""},
]

TAGS = [
    {"id": "900", "name": "jericho", "color": "blue"},
    {"id": "901", "name": "Sales", "color": "yellow"},
]

PROFILES = [
    {"profile_id": "k1a", "profile_no": "10", "name": "John Shop", "group_id": "101",
     "group_name": "Shopify", "remark": "main store", "last_open_time": "1700000000",
     "profile_tags": [{"id": "900", "name": "jericho", "color": "blue"}],
     "user_proxy_config": {"proxy_soft": "other", "proxy_type": "http", "proxy_host": "1.1.1.1",
                           "proxy_port": "8000", "proxy_user": "u", "proxy_password": "secret"}},
    {"profile_id": "k1b", "profile_no": "2", "name": "Jane Shop", "group_id": "101",
     "group_name": "Shopify", "remark": "", "last_open_time": "0", "profile_tags": [],
     "user_proxy_config": {"proxy_soft": "no_proxy"}},
    {"profile_id": "k2a", "profile_no": "3", "name": "Insta\nmain", "group_id": "102",
     "group_name": "Socials", "remark": "johnny's account", "last_open_time": "",
     "profile_tags": [{"id": "901", "name": "Sales", "color": "yellow"}]},
]

PROXIES = [
    {"proxy_id": "p1", "type": "http", "host": "1.1.1.1", "port": "8000", "user": "u", "password": "secret",
     "remark": "", "profile_count": "2", "related_profile_no": ["10", "99"],
     "proxy_tags": [{"id": "1", "name": "Jericho", "color": "red"}]},
    {"proxy_id": "p2", "type": "socks5", "host": "2.2.2.2", "port": "9000", "user": "u", "password": "secret",
     "remark": "spare", "profile_count": "0", "related_profile_no": [],
     "proxy_tags": [{"id": "1", "name": "Jericho", "color": "red"}]},
    {"proxy_id": "p3", "type": "http", "host": "3.3.3.3", "port": "8000", "user": "", "password": "",
     "remark": "", "profile_count": "0", "proxy_tags": [{"id": "2", "name": "Support", "color": "red"}]},
]


class FakeApi:
    """Duck-types `LocalApi`: same methods, canned data, records calls.

    It's a small *stateful* fake: it remembers which browsers are open,
    which profiles were created, and proxy changes, so tests can check
    the effect of an action rather than only that a call was made."""

    base_url = "http://fake"

    def __init__(self, running: bool = True):
        self.running = running
        self.calls: list[tuple[str, dict]] = []
        self.open_browsers: set[str] = set()
        self.created: list[dict] = []
        self.updates: list[dict] = []
        # Copies, so one test's changes can't leak into another's data.
        self.profiles = copy.deepcopy(PROFILES)
        self.proxies = copy.deepcopy(PROXIES)

    def is_running(self) -> bool:
        return self.running

    def get_all(self, path: str, page_size: int, **params) -> list[dict]:
        self.calls.append((path, params))
        if path == "/api/v1/group/list":
            return list(GROUPS)
        raise AssertionError(f"unexpected path {path}")

    def post_all(self, path: str, limit: int, **body) -> list[dict]:
        self.calls.append((path, body))
        if path == "/api/v2/browser-tags/list":
            return list(TAGS)
        if path == "/api/v2/proxy-list/list":
            return list(self.proxies)
        if path == "/api/v2/browser-profile/list":
            return self._profiles_matching(body)
        raise AssertionError(f"unexpected path {path}")

    def get(self, path: str, **params) -> dict:
        self.calls.append((path, params))
        profile_id = params["user_id"]
        if path == "/api/v1/browser/start":
            self.open_browsers.add(profile_id)
            return {"ws": {"puppeteer": f"ws://127.0.0.1:1/{profile_id}", "selenium": "127.0.0.1:1"},
                    "debug_port": "1", "webdriver": "C:/chromedriver.exe"}
        if path == "/api/v1/browser/active":
            return {"status": "Active" if profile_id in self.open_browsers else "Inactive"}
        if path == "/api/v1/browser/stop":
            self.open_browsers.discard(profile_id)
            return {}
        raise AssertionError(f"unexpected path {path}")

    def post(self, path: str, body: dict | None = None) -> dict:
        self.calls.append((path, body))
        if path == "/api/v2/browser-profile/list":  # single-page exact lookup
            return {"list": self._profiles_matching(body)[: body.get("limit", 1)]}
        if path == "/api/v2/browser-profile/create":
            self.created.append(body)
            return {"profile_id": "new1", "profile_no": "500"}
        if path == "/api/v2/browser-profile/update":
            self.updates.append(body)
            self._apply_update(body)
            return {}
        raise AssertionError(f"unexpected path {path}")

    def _profiles_matching(self, body: dict) -> list[dict]:
        group_id, tag_ids = body.get("group_id"), body.get("tag_ids")
        serials, ids = body.get("profile_no"), body.get("profile_id")
        return [
            p for p in self.profiles
            if (group_id is None or p["group_id"] == group_id)
            and (tag_ids is None or any(t["id"] in tag_ids for t in p["profile_tags"]))
            and (serials is None or p["profile_no"] in serials)
            and (ids is None or p["profile_id"] in ids)
        ]

    def _apply_update(self, body: dict) -> None:
        profile = next(p for p in self.profiles if p["profile_id"] == body["profile_id"])
        if "proxyid" in body:
            proxy = next(x for x in self.proxies if x["proxy_id"] == body["proxyid"])
            profile["user_proxy_config"] = {"proxy_soft": "other", "proxy_type": proxy["type"],
                                            "proxy_host": proxy["host"], "proxy_port": proxy["port"]}
        elif "user_proxy_config" in body:
            profile["user_proxy_config"] = body["user_proxy_config"]


class FakeResponse(io.BytesIO):
    """What `urlopen` returns: a readable, closeable body."""

    @classmethod
    def json(cls, body: dict) -> FakeResponse:
        return cls(json.dumps(body).encode())


class FakeOpener:
    """Replaces `urllib.request.urlopen`: returns queued responses (or
    raises queued exceptions) in order, and keeps every request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return FakeResponse.json(response)
