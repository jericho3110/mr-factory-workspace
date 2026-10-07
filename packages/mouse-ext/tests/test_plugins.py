import unittest

from mrfactory.mouse_ext import (
    ActionCancelled,
    PluggableAutomator,
    Plugin,
    PluginManager,
    RegionGuardPlugin,
    StatsPlugin,
)
from natural_mouse import BezierPathGenerator, Match, Point, UIAutomator
from natural_mouse.input import FakeInputExecutor
from tests.fakes import FakeScreenLocator

MATCH = Match(x=100, y=200, width=40, height=20, confidence=0.95)


class HookRecorder(Plugin):
    def __init__(self):
        super().__init__()
        self.events = []

    def before_action(self, ctx):
        self.events.append("before_action")

    def after_locate(self, ctx):
        self.events.append("after_locate")

    def before_input(self, ctx):
        self.events.append("before_input")

    def after_action(self, ctx):
        self.events.append("after_action")

    def on_error(self, ctx, error):
        self.events.append("on_error")


class PinTarget(Plugin):
    def before_input(self, ctx):
        ctx.target = Point(1, 2)


def make(match=MATCH, plugins=()):
    executor = FakeInputExecutor()
    automator = PluggableAutomator(
        FakeScreenLocator(match), executor, BezierPathGenerator(), plugins=plugins,
    )
    return automator, executor


class TestPluggableAutomator(unittest.TestCase):
    def test_is_a_drop_in_uiautomator(self):
        automator, _ = make()
        self.assertIsInstance(automator, UIAutomator)

    def test_click_fires_hooks_in_order(self):
        recorder = HookRecorder()
        automator, executor = make(plugins=[recorder])

        self.assertTrue(automator.find_and_click("x.png"))
        self.assertEqual(recorder.events, ["before_action", "after_locate", "before_input", "after_action"])
        self.assertEqual(executor.calls[0][0], "click")

    def test_miss_skips_input_and_returns_false(self):
        recorder = HookRecorder()
        automator, executor = make(match=None, plugins=[recorder])

        self.assertFalse(automator.find_and_click("x.png"))
        self.assertEqual(recorder.events, ["before_action", "after_locate", "after_action"])
        self.assertEqual(executor.calls, [])

    def test_plugin_can_change_target(self):
        automator, executor = make(plugins=[PinTarget()])
        automator.find_and_click("x.png")
        self.assertEqual(executor.calls, [("click", Point(1, 2))])

    def test_scroll_moves_then_scrolls(self):
        recorder = HookRecorder()
        automator, executor = make(plugins=[recorder])
        automator.scroll(-3, at=Point(10, 10))

        self.assertEqual(executor.calls, [("move_to", Point(10, 10)), ("scroll", -3)])
        self.assertEqual(recorder.events, ["before_action", "before_input", "after_action"])

    def test_locate_returns_match_without_input(self):
        automator, executor = make()
        self.assertEqual(automator.locate("x.png"), MATCH)
        self.assertEqual(executor.calls, [])

    def test_use_registers_after_construction(self):
        automator, _ = make()
        recorder = automator.use(HookRecorder())
        automator.locate("x.png")
        self.assertIn("after_locate", recorder.events)


class TestRegionGuardPlugin(unittest.TestCase):
    def test_cancels_click_outside_allowed_regions(self):
        recorder = HookRecorder()
        automator, executor = make(plugins=[RegionGuardPlugin([(0, 0, 50, 50)]), recorder])

        with self.assertRaises(ActionCancelled):
            automator.find_and_click("x.png")
        self.assertEqual(executor.calls, [])
        self.assertEqual(recorder.events[-1], "on_error")

    def test_allows_click_inside(self):
        automator, executor = make(plugins=[RegionGuardPlugin([(0, 0, 1000, 1000)])])
        self.assertTrue(automator.find_and_click("x.png"))
        self.assertEqual(len(executor.calls), 1)


class TestStatsPlugin(unittest.TestCase):
    def test_counts_hits_misses_and_errors(self):
        stats = StatsPlugin()
        automator = PluggableAutomator(
            FakeScreenLocator(MATCH, None), FakeInputExecutor(), BezierPathGenerator(),
            plugins=[stats, RegionGuardPlugin([(0, 0, 1, 1)])],
        )
        with self.assertRaises(ActionCancelled):
            automator.find_and_click("x.png")  # found, then refused by the guard
        automator.find_and_click("x.png")      # missed

        click = stats.summary()["click"]
        self.assertEqual((click["found"], click["missed"], click["errors"], click["ok"]), (1, 1, 1, 1))
        self.assertEqual(stats.confidences, [0.95])


class TestPluginManager(unittest.TestCase):
    def test_rejects_duplicate_names(self):
        manager = PluginManager([StatsPlugin()])
        with self.assertRaises(ValueError):
            manager.register(StatsPlugin())

    def test_rejects_non_plugins(self):
        with self.assertRaises(TypeError):
            PluginManager([object()])

    def test_unregister(self):
        manager = PluginManager([StatsPlugin()])
        self.assertIsNotNone(manager.unregister("StatsPlugin"))
        self.assertEqual(len(manager), 0)

    def test_load_path(self):
        manager = PluginManager()
        plugin = manager.load_path("mrfactory.mouse_ext.plugins:RegionGuardPlugin", allowed=[(0, 0, 5, 5)])
        self.assertIsInstance(plugin, RegionGuardPlugin)
        self.assertIs(manager.get("RegionGuardPlugin"), plugin)


if __name__ == "__main__":
    unittest.main()
