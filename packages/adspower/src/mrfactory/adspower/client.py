"""`AdsPower`: the one object most code needs (a *facade*).

    from mrfactory.adspower import AdsPower

    ads = AdsPower()
    ads.open(wait=60)                                # start the app, wait for its API
    ads.groups(name="acm")                           # groups whose name contains "acm"
    ads.profiles(group="Acme", tag="acme")     # by group and/or tag
    profile = ads.find_profile("shop 7", group="Acme")
    ads.open_profile(profile)                        # stays open after Python exits

    proxy = ads.choose_proxy(tag="Acme")          # an unused proxy tagged Acme
    ads.create_profile("Shop 8", group="Acme", tag="acme", proxy=proxy)
    ads.set_proxy(profile, ads.choose_proxy(tag="Acme"))

Every `group`, `tag`, and `profile` argument accepts either the object
(`Group`, `Tag`, `Profile`) or its name/ID as a string.

This class decides *what* to ask the API for and enforces the rules
between things (tags must exist, proxies must carry the tag). How to
talk HTTP is `api.py`'s job; what counts as a name match is
`matching.py`'s.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from pathlib import Path

from .api import LocalApi
from .batch import Batch, BatchCreator, BatchSettings, Created, free_proxies, plan
from .errors import (
    AdsPowerApiError,
    AdsPowerNotRunning,
    AmbiguousProfile,
    GroupNotFound,
    ProfileNotFound,
    ProxyNotFound,
    TagNotFound,
)
from .launcher import open_adspower
from .matching import contains, find_by_name_or_id, looks_like_profile_id, names, serial_order
from .models import Group, OpenedBrowser, Profile, Proxy, Tag
from .proxycheck import CHECK_URL, Fetch, ProxyCheck, check_browser

# Endpoints, in one place. v1 = GET with query parameters, v2 = POST with
# a JSON body. Tag endpoints are undocumented (see api.py).
GROUP_LIST = "/api/v1/group/list"
TAG_LIST = "/api/v2/browser-tags/list"
PROFILE_LIST = "/api/v2/browser-profile/list"
PROFILE_CREATE = "/api/v2/browser-profile/create"
PROFILE_UPDATE = "/api/v2/browser-profile/update"
BROWSER_START = "/api/v1/browser/start"
BROWSER_STOP = "/api/v1/browser/stop"
BROWSER_ACTIVE = "/api/v1/browser/active"
PROXY_LIST = "/api/v2/proxy-list/list"

# Largest page each list endpoint allows: fewer requests, same result.
GROUP_PAGE_SIZE = 2000
PROFILE_PAGE_SIZE = 100
TAG_PAGE_SIZE = 200
PROXY_PAGE_SIZE = 200

NO_PROXY = {"proxy_soft": "no_proxy"}

# A new profile needs a browser fingerprint. This is AdsPower's default:
# a Chrome kernel matching the generated user agent.
DEFAULT_FINGERPRINT = {"browser_kernel_config": {"type": "chrome", "version": "ua_auto"}}

# check_proxy closes the profile it opened and waits until it's really gone.
CLOSE_TIMEOUT = 15.0
CLOSE_POLL = 0.5


class AdsPower:
    def __init__(self, api: LocalApi | None = None):
        """`api` is injectable so tests (or a non-default address/API
        key) can supply their own."""
        self.api = api or LocalApi()

    # --- the app ---------------------------------------------------------

    def open(self, path: str | Path | None = None, wait: float = 0) -> Path:
        """Start AdsPower (from `path`, or its usual install location).
        If `wait` > 0, also wait up to that many seconds for its Local
        API to answer, so the next call can use it right away."""
        exe = open_adspower(path)
        if wait > 0:
            self.wait_until_running(wait)
        return exe

    def is_running(self) -> bool:
        return self.api.is_running()

    def wait_until_running(self, timeout: float, poll_every: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while not self.is_running():
            if time.monotonic() >= deadline:
                raise AdsPowerNotRunning(f"AdsPower's Local API didn't answer within {timeout:g}s.")
            time.sleep(poll_every)

    # --- groups ----------------------------------------------------------

    def groups(self, name: str | None = None) -> list[Group]:
        """Every group, or only those whose name contains `name`
        (ignoring case), in the order AdsPower lists them."""
        rows = self.api.get_all(GROUP_LIST, page_size=GROUP_PAGE_SIZE)
        return [g for g in map(Group.from_api, rows) if contains(g.name, name)]

    def find_group(self, name_or_id: str | Group) -> Group:
        """The group with this ID or name (ignoring case). Raises
        GroupNotFound otherwise."""
        if isinstance(name_or_id, Group):
            return name_or_id
        groups = self.groups()
        found = find_by_name_or_id(groups, name_or_id)
        if found is None:
            raise GroupNotFound(f"No group named or with ID {name_or_id!r}. Groups: {names(groups)}")
        return found

    # --- profile tags ----------------------------------------------------

    def tags(self, name: str | None = None) -> list[Tag]:
        """Every profile tag, or only those whose name contains `name`
        (ignoring case)."""
        rows = self.api.post_all(TAG_LIST, limit=TAG_PAGE_SIZE)
        return [t for t in map(Tag.from_api, rows) if contains(t.name, name)]

    def find_tag(self, name_or_id: str | Tag) -> Tag:
        """The profile tag with this ID or name (ignoring case). Raises
        TagNotFound otherwise. Tags are never created implicitly, so a
        typo can't quietly add a new tag."""
        if isinstance(name_or_id, Tag):
            return name_or_id
        tags = self.tags()
        found = find_by_name_or_id(tags, name_or_id)
        if found is None:
            raise TagNotFound(f"No profile tag named or with ID {name_or_id!r}. Tags: {names(tags)}")
        return found

    # --- profiles --------------------------------------------------------

    def profiles(self, group: str | Group | None = None, tag: str | Tag | None = None) -> list[Profile]:
        """Every profile, or only those in `group` and/or with `tag`,
        sorted by serial number. Both filters run on AdsPower's side."""
        rows = self.api.post_all(
            PROFILE_LIST,
            limit=PROFILE_PAGE_SIZE,
            group_id=self.find_group(group).id if group is not None else None,
            tag_ids=[self.find_tag(tag).id] if tag is not None else None,
        )
        return sorted(map(Profile.from_api, rows), key=lambda p: serial_order(p.serial_number))

    def search_profiles(
        self, text: str, group: str | Group | None = None, tag: str | Tag | None = None
    ) -> list[Profile]:
        """Profiles whose name, remark, serial number, or ID contains
        `text` (ignoring case), optionally only within `group`/`tag`.

        The Local API can't search by text, so this fetches the profiles
        (filtered by group/tag on the server) and filters them here."""
        return [p for p in self.profiles(group, tag) if p.matches(text)]

    def find_profile(self, text: str | Profile, group: str | Group | None = None) -> Profile:
        """Exactly one profile for `text`: its serial number or ID, or
        else the only profile whose name/remark contains it.

        Raises ProfileNotFound if nothing matches, and AmbiguousProfile
        (with the candidates in `.matches`) if several do."""
        if isinstance(text, Profile):
            return text
        text = text.strip()
        if not text:  # "" is contained in every name: it would "match" every profile
            raise ProfileNotFound("No profile given: pass a serial number, ID, or part of its name.")
        group = self.find_group(group) if group is not None else None

        # 1. Exact serial number or ID: one small request instead of
        #    downloading every profile.
        exact = self._exact_profile(text)
        if exact is not None and (group is None or exact.group_id == group.id):
            return exact

        # 2. Otherwise search names/remarks (in the group, if given).
        matches = self.search_profiles(text, group)
        if not matches:
            where = f" in group {group.name!r}" if group is not None else ""
            raise ProfileNotFound(f"No profile matches {text!r}{where}.")
        if len(matches) > 1:
            raise AmbiguousProfile(text, matches)
        return matches[0]

    def _exact_profile(self, text: str) -> Profile | None:
        """The profile whose serial number (all digits) or ID is `text`,
        looked up on AdsPower's side; None if there's none."""
        if text.isdigit():
            body = {"profile_no": [text]}
        elif looks_like_profile_id(text):
            body = {"profile_id": [text]}
        else:
            return None
        rows = self.api.post(PROFILE_LIST, {**body, "page": 1, "limit": 1}).get("list") or []
        return Profile.from_api(rows[0]) if rows else None

    def _profile(self, profile: str | Profile) -> Profile:
        return profile if isinstance(profile, Profile) else self.find_profile(profile)

    # --- a profile's browser --------------------------------------------

    def open_profile(self, profile: str | Profile) -> OpenedBrowser:
        """Open the profile's browser, like clicking "Open" in AdsPower.

        The browser is started *by the AdsPower app*, not by this
        program, so it stays open after this program exits (or
        crashes). Close it in AdsPower, or with `close_profile`.
        Opening a profile that's already open just returns its details."""
        profile_id = self._profile(profile).id
        try:
            data = self.api.get(BROWSER_START, user_id=profile_id)
        except AdsPowerApiError as e:
            # e.g. "SunBrowser 153 is updating, waiting for download." /
            # "... is not ready,please to download!" on a new or updated kernel
            if "download" in str(e).lower():
                raise AdsPowerApiError(
                    f"{e}\nAdsPower is still downloading the browser this profile needs. "
                    "Wait a minute or two and try again."
                ) from e
            raise
        return OpenedBrowser.from_api(profile_id, data)

    def is_profile_open(self, profile: str | Profile) -> bool:
        data = self.api.get(BROWSER_ACTIVE, user_id=self._profile(profile).id)
        return data.get("status") == "Active"

    def close_profile(self, profile: str | Profile) -> None:
        self.api.get(BROWSER_STOP, user_id=self._profile(profile).id)

    # --- proxies ---------------------------------------------------------

    def proxies(self, tag: str | None = None, unused: bool = False) -> list[Proxy]:
        """Proxies from AdsPower's Proxy List: all, or only those tagged
        `tag` (ignoring case), and/or only those no profile uses yet.

        Proxy tags can be read through the API but not set; tag proxies
        in the AdsPower app (Proxies > Proxy List)."""
        rows = self.api.post_all(PROXY_LIST, limit=PROXY_PAGE_SIZE)
        return [
            proxy for proxy in map(Proxy.from_api, rows)
            if (tag is None or proxy.has_tag(tag)) and not (unused and proxy.in_use)
        ]

    def choose_proxy(self, tag: str, proxy_id: str | None = None) -> Proxy:
        """A proxy tagged `tag`: the one with `proxy_id` if given (it
        must carry the tag), otherwise the first one no profile uses
        yet. Raises ProxyNotFound if there's no such proxy."""
        tagged = self.proxies(tag=tag)
        if proxy_id is not None:
            for proxy in tagged:
                if proxy.id == str(proxy_id):
                    return proxy
            raise ProxyNotFound(f"No proxy with ID {proxy_id!r} is tagged {tag!r}.")
        for proxy in tagged:
            if not proxy.in_use:
                return proxy
        raise ProxyNotFound(
            f"No unused proxy is tagged {tag!r} ({len(tagged)} tagged, all in use). "
            "Add or tag more proxies in AdsPower, or pick one by ID."
        )

    def current_proxy(self, profile: str | Profile) -> Proxy | None:
        """The Proxy List entry this profile uses, or None if it has no
        proxy or uses one typed straight into the profile (see
        `Profile.proxy` for its address in that case)."""
        serial = self._profile(profile).serial_number
        return next((proxy for proxy in self.proxies() if serial in proxy.used_by), None)

    def set_proxy(self, profile: str | Profile, proxy: Proxy | None) -> None:
        """Equip `profile` with `proxy` (from `choose_proxy()`), or remove
        its proxy with None. Takes effect the next time the profile's
        browser opens.

        This only sends the change. Which proxies are *allowed* (the tag
        rule) is decided by the caller choosing `proxy`, usually with
        `choose_proxy(tag=...)`."""
        body: dict = {"profile_id": self._profile(profile).id}
        if proxy is None:
            body["user_proxy_config"] = NO_PROXY
        else:
            body["proxyid"] = proxy.id
        self.api.post(PROFILE_UPDATE, body)

    # --- creating profiles ----------------------------------------------

    def create_profile(
        self,
        name: str,
        group: str | Group,
        tag: str | Tag,
        proxy: Proxy | None = None,
        remark: str = "",
    ) -> Profile:
        """Create a profile that is filed under `group` and tagged `tag`
        from the start, so AdsPower stays organized. Both must already
        exist (GroupNotFound / TagNotFound otherwise); nothing is created
        until they're both confirmed.

        `proxy` is optional: pass one from `choose_proxy()` to equip it,
        or leave it out for a profile without a proxy."""
        group = self.find_group(group)
        tag = self.find_tag(tag)
        body = {
            "name": name,
            "group_id": group.id,
            "profile_tag_ids": [tag.id],
            "remark": remark or None,
            "fingerprint_config": DEFAULT_FINGERPRINT,
        }
        if proxy is None:
            body["user_proxy_config"] = NO_PROXY
        else:
            body["proxyid"] = proxy.id

        data = self.api.post(PROFILE_CREATE, body)
        return Profile(
            id=str(data.get("profile_id", "")),
            serial_number=str(data.get("profile_no", "")),
            name=name,
            group_id=group.id,
            group_name=group.name,
            remark=remark,
            tags=(tag.name,),
            proxy=proxy.url if proxy else "",
        )

    # --- many profiles at once (batch.py) --------------------------------

    def plan_batch(
        self,
        names: Sequence[str],
        group: str | Group,
        tag: str | Tag,
        proxy_tag: str | None = None,
        remark: str = "",
    ) -> Batch:
        """Plan creating `names` in `group` with `tag`, each with its own
        unused proxy tagged `proxy_tag` (default: the tag's name). Creates
        nothing: look at `batch.planned` / `batch.summary()` first, then
        `create_batch(batch)`. GroupNotFound / TagNotFound for a typo."""
        group, tag = self.find_group(group), self.find_tag(tag)
        settings = BatchSettings(group, tag, proxy_tag or tag.name, remark)
        free = free_proxies(self.proxies(tag=settings.proxy_tag))
        planned = plan(list(names), self.profiles(), free)
        return Batch(settings, tuple(planned), len(free))

    def create_batch(self, batch: Batch, on_result: Callable[[Created], None] | None = None) -> list[Created]:
        """Create the batch's READY names, one at a time; returns one
        `Created` per name. `on_result` is called after each one. For a
        Stop button, use `BatchCreator` directly (it has `stop()`)."""
        creator = BatchCreator(self, on_result or (lambda created: None))
        return creator.run(batch.planned, batch.settings)

    # --- proxy health (proxycheck.py) -------------------------------------

    def check_proxy(self, profile: str | Profile, fetch: Fetch | None = None, url: str = CHECK_URL,
                    close_timeout: float = CLOSE_TIMEOUT) -> ProxyCheck:
        """Open the profile, load a "what is my IP?" page through its
        proxy, and close it again (only if this call opened it). Returns
        a ProxyCheck: `.ok`, `.ip`, `.error`, `.text`. Needs Playwright
        (`pip install "mrfactory-adspower[browser]"`) unless `fetch` is given."""
        profile = self._profile(profile)
        was_open = self.is_profile_open(profile)
        browser = self.open_profile(profile)
        try:
            return check_browser(browser, fetch=fetch, url=url, profile=profile)
        finally:
            if not was_open:
                self.close_profile(profile)
                self._wait_until_closed(profile, close_timeout)

    def _wait_until_closed(self, profile: Profile, timeout: float) -> bool:
        """AdsPower answers "closed" before the browser is really gone
        (about 2 s, seen live in Profile Runner); wait so the next open
        doesn't overlap. False if it's still open after `timeout`."""
        deadline = time.monotonic() + timeout
        while self.is_profile_open(profile):
            if time.monotonic() >= deadline:
                return False
            time.sleep(CLOSE_POLL)
        return True
