"""Find a template on screen and click it once, with plugins and
extensions layered on top of natural_mouse.

    python examples/click_with_plugins.py templates/target.png
    python examples/click_with_plugins.py templates/target.png --dry-run

--dry-run swaps in natural_mouse's FakeInputExecutor: everything runs
(screen search, plugins) except the real mouse never moves.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mrfactory.mouse_ext import (
    ActionCancelled,
    FailSafeExecutor,
    FallbackLocator,
    FittsPathGenerator,
    LoggingPlugin,
    MultiScaleTemplateLocator,
    PluggableAutomator,
    RecordingPathGenerator,
    RetryLocator,
    ScreenshotOnMissPlugin,
    StatsPlugin,
)
from natural_mouse import (
    BezierPathGenerator,
    MovementProfile,
    TemplateMatchLocator,
    Win32InputExecutor,
)
from natural_mouse.input import FakeInputExecutor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template")
    parser.add_argument("--confidence", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--record", metavar="JSON", help="save the generated path(s) here")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Extensions: each wraps one of natural_mouse's strategy interfaces.
    locator = RetryLocator(
        FallbackLocator([TemplateMatchLocator(), MultiScaleTemplateLocator()]),
        attempts=2,
    )
    paths = RecordingPathGenerator(
        FittsPathGenerator(BezierPathGenerator(MovementProfile(curviness=0.3)))
    )
    executor = FakeInputExecutor() if args.dry_run else FailSafeExecutor(Win32InputExecutor())

    # Plugins: observe/adjust each action.
    stats = StatsPlugin()
    automator = PluggableAutomator(
        locator, executor, paths,
        plugins=[LoggingPlugin(), stats, ScreenshotOnMissPlugin("misses")],
    )

    try:
        clicked = automator.find_and_click(args.template, confidence=args.confidence)
    except ActionCancelled as e:
        print(f"Cancelled: {e}")
        return 2

    if args.record:
        paths.save_json(args.record)
    print(stats.summary())
    return 0 if clicked else 1


if __name__ == "__main__":
    sys.exit(main())
