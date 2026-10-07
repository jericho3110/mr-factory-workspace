"""`UIAutomator` with plugin hooks.

`PluggableAutomator` is a drop-in subclass of `natural_mouse.UIAutomator`:
same constructor, same `find_and_click` / `locate` / `scroll` signatures,
same return values. The only addition is that every action is wrapped in
an `ActionContext` and announced to the registered plugins at each stage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from natural_mouse import (
    InputExecutor,
    Match,
    PathGenerator,
    Point,
    ScreenLocator,
    UIAutomator,
)

from .plugins.base import ActionContext, Plugin, Region
from .plugins.manager import PluginManager


class PluggableAutomator(UIAutomator):
    def __init__(
        self,
        locator: ScreenLocator,
        executor: InputExecutor,
        path_generator: PathGenerator,
        plugins: PluginManager | Iterable[Plugin] = (),
        click_hold_range: tuple[float, float] = (0.06, 0.16),
    ):
        super().__init__(locator, executor, path_generator, click_hold_range)
        self.plugins = plugins if isinstance(plugins, PluginManager) else PluginManager(plugins)
        for plugin in self.plugins:
            plugin.setup(self)

    def use(self, plugin: Plugin) -> Plugin:
        """Register another plugin after construction."""
        self.plugins.register(plugin)
        plugin.setup(self)
        return plugin

    def find_and_click(
        self,
        query: str,
        region: Region | None = None,
        confidence: float = 0.85,
        center_bias: float = 0.6,
    ) -> bool:
        ctx = ActionContext("click", query=query, region=region, confidence=confidence)

        def body() -> bool:
            if not self._locate_into(ctx):
                return False
            ctx.target = ctx.match.random_point(center_bias)
            self.plugins.dispatch("before_input", ctx)
            self._executor.click(ctx.target, self._path_generator, self._click_hold_range)
            return True

        return self._run(ctx, body)

    def locate(
        self,
        query: str,
        region: Region | None = None,
        confidence: float = 0.85,
    ) -> Match | None:
        ctx = ActionContext("locate", query=query, region=region, confidence=confidence)
        return self._run(ctx, lambda: ctx.match if self._locate_into(ctx) else None)

    def scroll(
        self,
        amount: int,
        steps: int = 5,
        step_delay_range: tuple[float, float] = (0.05, 0.18),
        at: Point | None = None,
    ) -> None:
        ctx = ActionContext("scroll", amount=amount, target=at)

        def body() -> None:
            self.plugins.dispatch("before_input", ctx)
            if ctx.target is not None:
                self._executor.move_to(ctx.target, self._path_generator)
            self._executor.scroll(ctx.amount, steps, step_delay_range)

        self._run(ctx, body)

    def _locate_into(self, ctx: ActionContext) -> bool:
        ctx.match = self._locator.locate(ctx.query, ctx.region, ctx.confidence)
        self.plugins.dispatch("after_locate", ctx)
        return ctx.match is not None

    def _run(self, ctx: ActionContext, body: Callable):
        try:
            self.plugins.dispatch("before_action", ctx)
            ctx.result = body()
        except Exception as error:
            ctx.error = error
            self.plugins.dispatch("on_error", ctx, error)
            raise
        self.plugins.dispatch("after_action", ctx)
        return ctx.result
