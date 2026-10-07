"""The plugin contract: a set of optional hooks fired around each action.

Unlike the strategy interfaces in `natural_mouse` (`ScreenLocator`,
`InputExecutor`, `PathGenerator`), which *replace* a piece of behavior,
a plugin *observes or adjusts* an action while it runs: logging it,
timing it, refusing it, or nudging the click target. Any number of
plugins can be active at once; `PluggableAutomator` calls each hook on
every registered plugin, in registration order.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from natural_mouse import Match, Point

if TYPE_CHECKING:
    from ..automator import PluggableAutomator

Region = tuple[int, int, int, int]


@dataclass
class ActionContext:
    """Everything known about one action, passed to every hook.

    Hooks may read any field and may change `target` in `before_input`
    (e.g. to clamp or offset the click point). `extras` is a free-form
    scratchpad plugins can use to pass data between their own hooks.
    """

    action: str  # "click" | "scroll" | "locate"
    query: str | None = None
    region: Region | None = None
    confidence: float | None = None
    match: Match | None = None
    target: Point | None = None
    amount: int | None = None
    result: Any = None
    error: BaseException | None = None
    started_at: float = field(default_factory=time.perf_counter)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.started_at


class Plugin:
    """Base class for plugins. Every hook is optional — override only the
    ones you need. Raise `ActionCancelled` from any `before_*` hook to stop
    the action before the mouse moves.

    Hook order for one action:
        before_action -> after_locate (click/locate only)
        -> before_input (click/scroll only) -> after_action
    and `on_error` instead of `after_action` if anything raised.
    """

    name: str | None = None

    def __init__(self) -> None:
        if self.name is None:
            self.name = type(self).__name__

    def setup(self, automator: PluggableAutomator) -> None:
        """Called once when the plugin is attached to an automator."""

    def before_action(self, ctx: ActionContext) -> None:
        """Before anything happens."""

    def after_locate(self, ctx: ActionContext) -> None:
        """After the locator ran; `ctx.match` is the result (maybe None)."""

    def before_input(self, ctx: ActionContext) -> None:
        """Right before the mouse moves/clicks/scrolls. `ctx.target` may be
        changed here."""

    def after_action(self, ctx: ActionContext) -> None:
        """After a successful action; `ctx.result` holds its return value."""

    def on_error(self, ctx: ActionContext, error: BaseException) -> None:
        """The action raised `error` (it is re-raised after this hook)."""
