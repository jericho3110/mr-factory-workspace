import os
import tempfile
import unittest
from unittest import mock

import cv2
import numpy as np

from mrfactory.mouse_ext import (
    FailSafeExecutor,
    FailSafeTriggered,
    FallbackLocator,
    FittsPathGenerator,
    MultiScaleTemplateLocator,
    RecordingPathGenerator,
    RetryLocator,
)
from natural_mouse import BezierPathGenerator, Match, MovementProfile, Point
from tests.fakes import FakeScreenLocator, PathWalkingExecutor

MATCH = Match(10, 10, 5, 5, 0.9)


class TestRetryLocator(unittest.TestCase):
    def test_succeeds_on_a_later_attempt(self):
        inner = FakeScreenLocator(None, None, MATCH)
        self.assertEqual(RetryLocator(inner, attempts=3, delay=0).locate("q"), MATCH)
        self.assertEqual(inner.calls, 3)

    def test_gives_up_after_attempts(self):
        inner = FakeScreenLocator(None)
        self.assertIsNone(RetryLocator(inner, attempts=2, delay=0).locate("q"))
        self.assertEqual(inner.calls, 2)


class TestFallbackLocator(unittest.TestCase):
    def test_uses_first_locator_that_matches(self):
        first, second = FakeScreenLocator(None), FakeScreenLocator(MATCH)
        self.assertEqual(FallbackLocator([first, second]).locate("q"), MATCH)
        self.assertEqual((first.calls, second.calls), (1, 1))


class TestFittsPathGenerator(unittest.TestCase):
    def test_duration_follows_fitts_law_and_shape_is_kept(self):
        inner = BezierPathGenerator(MovementProfile(overshoot_chance=0))
        fitts = FittsPathGenerator(inner, variability=0)
        start, end = Point(0, 0), Point(800, 0)

        path = fitts.generate(start, end)
        self.assertAlmostEqual(path.total_duration, fitts.movement_time(800), places=6)
        self.assertEqual(path.end, end)

    def test_longer_moves_take_longer(self):
        fitts = FittsPathGenerator(BezierPathGenerator(), variability=0)
        self.assertLess(fitts.movement_time(50), fitts.movement_time(1500))


class TestRecordingPathGenerator(unittest.TestCase):
    def test_records_and_saves(self):
        rec = RecordingPathGenerator(BezierPathGenerator())
        path = rec.generate(Point(0, 0), Point(100, 100))
        self.assertEqual(len(rec.recordings[0]["points"]), len(path))

        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "paths.json")
            rec.save_json(out)
            self.assertGreater(os.path.getsize(out), 0)


class TestFailSafeExecutor(unittest.TestCase):
    def test_normal_click_goes_through(self):
        inner = PathWalkingExecutor()
        FailSafeExecutor(inner).click(Point(900, 300), BezierPathGenerator())
        self.assertEqual(inner.clicks, [Point(900, 300)])

    def test_hand_movement_aborts_before_click(self):
        inner = PathWalkingExecutor(hijack_at=(3, Point(50, 900)))
        with self.assertRaises(FailSafeTriggered):
            FailSafeExecutor(inner).click(Point(900, 300), BezierPathGenerator())
        self.assertEqual(inner.clicks, [])
        self.assertEqual(len(inner.moves), 4)  # stopped right after the hijack

    def test_corner_blocks_scroll(self):
        inner = PathWalkingExecutor(start=Point(0, 0))
        with self.assertRaises(FailSafeTriggered):
            FailSafeExecutor(inner).scroll(-3)
        self.assertEqual(inner.scrolls, [])


class TestMultiScaleTemplateLocator(unittest.TestCase):
    def test_finds_template_saved_at_a_different_scale(self):
        rng = np.random.default_rng(0)
        blocks = rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)
        screen = cv2.resize(blocks, (800, 600), interpolation=cv2.INTER_NEAREST)
        crop = screen[200:300, 300:420]
        small = cv2.resize(crop, None, fx=0.8, fy=0.8, interpolation=cv2.INTER_AREA)

        with tempfile.TemporaryDirectory() as d:
            template = os.path.join(d, "t.png")
            cv2.imwrite(template, small)
            with mock.patch("mrfactory.mouse_ext.extensions.locators.grab_screen", return_value=screen):
                match = MultiScaleTemplateLocator(scales=(1.0, 1.25)).locate(template, confidence=0.8)
                all_matches = MultiScaleTemplateLocator(scales=(1.0, 1.25)).locate_all(template, confidence=0.8)

        self.assertIsNotNone(match)
        self.assertLessEqual(abs(match.x - 300), 3)
        self.assertLessEqual(abs(match.y - 200), 3)
        self.assertEqual(len(all_matches), 1)


if __name__ == "__main__":
    unittest.main()
