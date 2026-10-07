"""Exceptions shared by plugins and extensions.

They live in their own module so a plugin (e.g. `RegionGuardPlugin`) and
an extension (e.g. `FailSafeExecutor`) can both raise the same family of
errors without either one importing the other.
"""

from __future__ import annotations


class ActionCancelled(Exception):
    """Raised to stop an action before (or while) it touches the real
    mouse. Callers can catch this one type to handle every refusal, no
    matter which plugin or extension raised it."""


class FailSafeTriggered(ActionCancelled):
    """The user took over the mouse mid-movement (or parked it in the
    fail-safe corner), so the automated movement was aborted."""
