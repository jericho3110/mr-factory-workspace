"""Plain data objects for what the Local API returns.

The API returns loosely typed JSON (IDs and timestamps as strings, some
fields missing on older versions). Converting it once, here, means the
rest of the code works with named, typed attributes instead of
`row.get("profile_id", "")` scattered everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .matching import same_name


@dataclass(frozen=True)
class Group:
    id: str
    name: str
    remark: str = ""

    @classmethod
    def from_api(cls, row: dict) -> Group:
        return cls(
            id=str(row.get("group_id", "")),
            name=row.get("group_name") or "",
            remark=row.get("remark") or "",
        )


@dataclass(frozen=True)
class Tag:
    """A profile tag (AdsPower's "browser tags"). Proxy tags are a
    separate list; a proxy's tags are just names on `Proxy.tags`."""

    id: str
    name: str
    color: str = ""

    @classmethod
    def from_api(cls, row: dict) -> Tag:
        return cls(id=str(row.get("id", "")), name=row.get("name") or "", color=row.get("color") or "")


@dataclass(frozen=True)
class Profile:
    id: str
    serial_number: str
    name: str
    group_id: str
    group_name: str
    remark: str = ""
    tags: tuple[str, ...] = ()
    proxy: str = ""   # "socks5://host:port", or "" for no proxy (never the password)
    ip: str = ""
    ip_country: str = ""
    last_open_time: datetime | None = None

    @classmethod
    def from_api(cls, row: dict) -> Profile:
        """From a /api/v2/browser-profile/list row."""
        return cls(
            id=str(row.get("profile_id", "")),
            serial_number=str(row.get("profile_no", "")),
            name=row.get("name") or "",
            group_id=str(row.get("group_id", "")),
            group_name=row.get("group_name") or "",
            remark=row.get("remark") or "",
            tags=tuple(tag.get("name", "") for tag in row.get("profile_tags") or []),
            proxy=_describe_proxy_config(row.get("user_proxy_config") or {}),
            ip=row.get("ip") or "",
            ip_country=row.get("ip_country") or "",
            last_open_time=_parse_timestamp(row.get("last_open_time")),
        )

    def matches(self, text: str) -> bool:
        """True if `text` appears (ignoring case) in the profile's name,
        remark, serial number, or ID."""
        text = text.casefold()
        fields = (self.name, self.remark, self.serial_number, self.id)
        return any(text in field.casefold() for field in fields)

    def is_exactly(self, text: str) -> bool:
        """True if `text` is this profile's ID or serial number."""
        return text in (self.id, self.serial_number)

    def has_tag(self, name: str) -> bool:
        return any(same_name(tag, name) for tag in self.tags)


@dataclass(frozen=True)
class Proxy:
    """A proxy from AdsPower's Proxy List. Its username and password are
    deliberately not kept: nothing here needs them, and leaving them out
    means they can't end up printed or in JSON output by accident."""

    id: str
    type: str
    host: str
    port: str
    remark: str = ""
    tags: tuple[str, ...] = ()
    profile_count: int = 0
    used_by: tuple[str, ...] = ()   # serial numbers of the profiles using it

    @classmethod
    def from_api(cls, row: dict) -> Proxy:
        return cls(
            id=str(row.get("proxy_id", "")),
            type=row.get("type") or "",
            host=row.get("host") or "",
            port=str(row.get("port", "")),
            remark=row.get("remark") or "",
            tags=tuple(tag.get("name", "") for tag in row.get("proxy_tags") or []),
            profile_count=_to_int(row.get("profile_count")),
            used_by=tuple(str(serial) for serial in row.get("related_profile_no") or []),
        )

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """'socks5://host:port', the same form as `Profile.proxy`."""
        return f"{self.type}://{self.address}"

    @property
    def in_use(self) -> bool:
        """True if at least one profile already uses this proxy."""
        return self.profile_count > 0

    def has_tag(self, name: str) -> bool:
        """Tag names are compared ignoring case ("jericho" == "Jericho")."""
        return any(same_name(tag, name) for tag in self.tags)


@dataclass(frozen=True)
class OpenedBrowser:
    """What AdsPower returns after starting a profile's browser. The
    addresses let automation tools (Selenium, Puppeteer/Playwright)
    attach to the browser later."""

    profile_id: str
    debug_port: str
    puppeteer: str = ""   # ws://127.0.0.1:<port>/devtools/browser/<id>
    selenium: str = ""    # 127.0.0.1:<port>
    webdriver: str = ""   # path to the matching chromedriver.exe

    @classmethod
    def from_api(cls, profile_id: str, data: dict) -> OpenedBrowser:
        ws = data.get("ws") or {}
        return cls(
            profile_id=profile_id,
            debug_port=str(data.get("debug_port", "")),
            puppeteer=ws.get("puppeteer") or "",
            selenium=ws.get("selenium") or "",
            webdriver=data.get("webdriver") or "",
        )


def _describe_proxy_config(config: dict) -> str:
    """'type://host:port' from a profile's user_proxy_config. The
    password in that config is deliberately not read."""
    if config.get("proxy_soft") in (None, "", "no_proxy") or not config.get("proxy_host"):
        return ""
    return f"{config.get('proxy_type') or 'http'}://{config['proxy_host']}:{config.get('proxy_port', '')}"


def _parse_timestamp(value) -> datetime | None:
    """The API sends Unix seconds as a string; "0" or "" means never."""
    seconds = _to_int(value)
    return datetime.fromtimestamp(seconds) if seconds > 0 else None


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
