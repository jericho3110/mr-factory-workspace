"""Refuses to move the mouse outside a set of allowed screen regions.

A safety net for template matching: if a template accidentally matches
something in the wrong window, the click is cancelled instead of landing
somewhere you didn't intend.
"""

from __future__ import annotations

from ..errors import ActionCancelled
from .base import ActionContext, Plugin, Region


class RegionGuardPlugin(Plugin):
    def __init__(self, allowed: list[Region]):
        """`allowed` = list of (left, top, width, height) rectangles."""
        super().__init__()
        if not allowed:
            raise ValueError("RegionGuardPlugin needs at least one allowed region.")
        self.allowed = list(allowed)

    def before_input(self, ctx: ActionContext) -> None:
        t = ctx.target
        if t is None:
            return
        if not any(left <= t.x < left + w and top <= t.y < top + h for left, top, w, h in self.allowed):
            raise ActionCancelled(
                f"{ctx.action} target ({t.x:.0f}, {t.y:.0f}) is outside every allowed region."
            )
