"""Turning results into text: aligned tables for people, JSON for
scripts. Nothing here talks to AdsPower or decides anything; it only
formats what it's given.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence

from ..models import Group, Profile, Proxy, Tag


def print_groups(groups: Sequence[Group], as_json: bool = False) -> None:
    if as_json:
        print_json(groups)
        return
    print_table(["ID", "NAME", "REMARK"], [[g.id, g.name, g.remark] for g in groups])
    print(f"\n{count(len(groups), 'group')}")


def print_tags(tags: Sequence[Tag], as_json: bool = False) -> None:
    if as_json:
        print_json(tags)
        return
    print_table(["ID", "NAME", "COLOR"], [[t.id, t.name, t.color] for t in tags])
    print(f"\n{count(len(tags), 'tag')}")


def print_profiles(profiles: Sequence[Profile], as_json: bool = False) -> None:
    if as_json:
        print_json(profiles)
        return
    rows = [
        [
            p.serial_number,
            shorten(p.name, 40),
            p.group_name,
            ", ".join(p.tags),
            p.id,
            p.last_open_time.strftime("%Y-%m-%d %H:%M") if p.last_open_time else "never",
            shorten(p.remark, 40),
        ]
        for p in profiles
    ]
    print_table(["SERIAL", "NAME", "GROUP", "TAGS", "ID", "LAST OPENED", "REMARK"], rows)
    print(f"\n{count(len(profiles), 'profile')}")


def print_proxies(proxies: Sequence[Proxy], as_json: bool = False) -> None:
    if as_json:
        print_json(proxies)
        return
    rows = [
        [p.id, p.type, p.address, ", ".join(p.tags), p.profile_count, shorten(p.remark, 40)]
        for p in proxies
    ]
    print_table(["ID", "TYPE", "ADDRESS", "TAGS", "PROFILES", "REMARK"], rows)
    print(f"\n{count(len(proxies), 'proxy', 'proxies')}")


def print_table(headers: list[str], rows: list[list]) -> None:
    """Left-aligned columns, each as wide as its widest cell."""
    rows = [[clean(str(cell)) for cell in row] for row in rows]
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]
    for row in [headers, *rows]:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip())


def print_json(value) -> None:
    """Dataclasses become objects; datetimes become ISO strings."""
    def convert(obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        return obj.isoformat() if hasattr(obj, "isoformat") else str(obj)

    print(json.dumps(value, default=convert, indent=2, ensure_ascii=False))


def describe_profile(profile: Profile) -> str:
    """One line: #12 "Shop 7" (Acme, ID k1abc)."""
    return f'#{profile.serial_number} "{clean(profile.name)}" ({profile.group_name}, ID {profile.id})'


def describe_proxy(proxy: Proxy | None, fallback: str = "") -> str:
    if proxy is not None:
        return f"{proxy.url} (proxy ID {proxy.id})"
    return fallback or "no proxy"


def count(n: int, noun: str, plural: str | None = None) -> str:
    """'1 profile', '3 profiles', '2 proxies'."""
    return f"{n} {noun if n == 1 else plural or noun + 's'}"


def clean(text: str) -> str:
    """Line breaks and tabs inside a name would break the table."""
    return " ".join(text.split())


def shorten(text: str, width: int) -> str:
    text = clean(text)
    return text if len(text) <= width else text[: width - 3] + "..."
