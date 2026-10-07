"""Logs every action through the standard `logging` module."""

from __future__ import annotations

import logging

from .base import ActionContext, Plugin


class LoggingPlugin(Plugin):
    def __init__(self, logger: logging.Logger | None = None, level: int = logging.INFO):
        super().__init__()
        self._log = logger or logging.getLogger("mrfactory.mouse_ext")
        self._level = level

    def after_locate(self, ctx: ActionContext) -> None:
        if ctx.match is None:
            self._log.log(self._level, "%s: %s not found (confidence >= %s)",
                          ctx.action, ctx.query, ctx.confidence)
        else:
            m = ctx.match
            self._log.log(self._level, "%s: %s found at (%d, %d) %dx%d, confidence %.3f",
                          ctx.action, ctx.query, m.x, m.y, m.width, m.height, m.confidence)

    def after_action(self, ctx: ActionContext) -> None:
        detail = f" amount={ctx.amount}" if ctx.action == "scroll" else ""
        target = f" at ({ctx.target.x:.0f}, {ctx.target.y:.0f})" if ctx.target else ""
        self._log.log(self._level, "%s done%s%s -> %r in %.3fs",
                      ctx.action, detail, target, ctx.result, ctx.elapsed)

    def on_error(self, ctx: ActionContext, error: BaseException) -> None:
        self._log.warning("%s failed after %.3fs: %s: %s",
                          ctx.action, ctx.elapsed, type(error).__name__, error)
