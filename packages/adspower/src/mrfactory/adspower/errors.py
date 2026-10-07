"""Exceptions raised by this package.

They all derive from `AdsPowerError`, so callers who don't care why
something failed can catch that one; callers who do can catch the
specific subclass.

    AdsPowerError
    ├── AdsPowerNotRunning     nobody answered at the API address
    ├── AdsPowerApiError       it answered, but refused
    ├── NotFound               a lookup found nothing
    │   ├── GroupNotFound
    │   ├── TagNotFound
    │   ├── ProfileNotFound
    │   └── ProxyNotFound
    └── AmbiguousProfile       a lookup found several; `.matches` has them
"""

from __future__ import annotations


class AdsPowerError(Exception):
    """Base class for every error this package raises."""


class AdsPowerNotRunning(AdsPowerError):
    """The Local API didn't answer: AdsPower is closed, still starting,
    or the API is on a different address."""


class AdsPowerApiError(AdsPowerError):
    """The Local API answered, but reported a failure (code != 0)."""


class NotFound(AdsPowerError):
    """A lookup by name or ID found nothing."""


class GroupNotFound(NotFound):
    """No group has the given name or ID."""


class TagNotFound(NotFound):
    """No profile tag has the given name or ID."""


class ProfileNotFound(NotFound):
    """No profile matches the given text."""


class ProxyNotFound(NotFound):
    """No proxy fits: wrong ID, wrong tag, or none unused left."""


class AmbiguousProfile(AdsPowerError):
    """Several profiles match, so it's unclear which one was meant. The
    candidates are in `.matches`, so a caller can ask the user."""

    def __init__(self, text: str, matches: list):
        self.text = text
        self.matches = matches
        super().__init__(f"{len(matches)} profiles match {text!r}; be more specific (serial number or ID).")
