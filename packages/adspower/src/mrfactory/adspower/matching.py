"""The rules for matching names and text, as small pure functions.

"Pure" means: the result depends only on the arguments, and nothing
else is read or changed (no API calls, no printing). That makes these
rules trivial to test and reuse: `client.py` decides *what* to fetch,
this module decides *what counts as a match*.

All comparisons ignore case with `casefold()`, the Unicode-correct
version of `lower()`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar


class Named(Protocol):
    """Anything with an `id` and a `name`: Group, Tag, ... A Protocol
    describes the *shape* an argument must have, without requiring it
    to inherit from anything (static duck typing)."""

    id: str
    name: str


N = TypeVar("N", bound=Named)


def contains(text: str, part: str | None) -> bool:
    """True if `part` appears in `text`, ignoring case. No `part` (None)
    means "no filter", so everything matches."""
    return part is None or part.casefold() in text.casefold()


def find_by_name_or_id(items: Iterable[N], name_or_id: str) -> N | None:
    """The first item whose `id` equals `name_or_id`, or whose `name`
    does (ignoring case); None if there's none."""
    wanted = str(name_or_id).strip()
    for item in items:
        if item.id == wanted or item.name.casefold() == wanted.casefold():
            return item
    return None


def names(items: Iterable[Named]) -> str:
    """'a, b, c' for error messages, or '(none)'."""
    return ", ".join(item.name for item in items) or "(none)"


def same_name(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


def serial_order(serial_number: str) -> tuple[int, int, str]:
    """A sort key: numeric serial numbers in number order (2 before 10),
    then anything non-numeric, alphabetically."""
    if serial_number.isdigit():
        return (0, int(serial_number), "")
    return (1, 0, serial_number)


def looks_like_profile_id(text: str) -> bool:
    """AdsPower profile IDs are short letters+digits like 'k1abc2de'. Used
    only to decide whether an exact ID lookup is worth a request."""
    return text.isalnum() and not text.isdigit() and any(ch.isdigit() for ch in text)
