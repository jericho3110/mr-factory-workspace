"""Counts actions, hits/misses, errors, and timings."""

from __future__ import annotations

from collections import defaultdict

from .base import ActionContext, Plugin


class StatsPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self._counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._durations: dict[str, list[float]] = defaultdict(list)
        self.confidences: list[float] = []

    def after_locate(self, ctx: ActionContext) -> None:
        self._counts[ctx.action]["found" if ctx.match else "missed"] += 1
        if ctx.match:
            self.confidences.append(ctx.match.confidence)

    def after_action(self, ctx: ActionContext) -> None:
        self._counts[ctx.action]["ok"] += 1
        self._durations[ctx.action].append(ctx.elapsed)

    def on_error(self, ctx: ActionContext, error: BaseException) -> None:
        self._counts[ctx.action]["errors"] += 1

    def summary(self) -> dict[str, dict[str, float]]:
        """Per action: its counters plus `avg_seconds` over successful runs."""
        out: dict[str, dict[str, float]] = {}
        for action, counts in self._counts.items():
            durations = self._durations[action]
            out[action] = dict(counts)
            out[action]["avg_seconds"] = sum(durations) / len(durations) if durations else 0.0
        return out
