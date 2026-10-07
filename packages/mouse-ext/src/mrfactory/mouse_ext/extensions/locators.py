"""Extra `ScreenLocator` strategies.

`RetryLocator` and `FallbackLocator` are decorators: they wrap other
locators and add behavior around them. `MultiScaleTemplateLocator` is a
standalone strategy. All three are plain `ScreenLocator`s, so they work
with the original `UIAutomator` as well as `PluggableAutomator`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

import cv2
import numpy as np

from natural_mouse import Match, ScreenLocator
from natural_mouse.screen import grab_screen

Region = tuple[int, int, int, int]


class RetryLocator(ScreenLocator):
    """Retries a locate a fixed number of times, for elements that take a
    moment to appear (a page still loading, an animation finishing).

    The retries are bounded and happen inside the single action you asked
    for. This does not repeat actions or run anything unattended."""

    def __init__(self, inner: ScreenLocator, attempts: int = 3, delay: float = 0.4):
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        self._inner = inner
        self._attempts = attempts
        self._delay = delay

    def locate(self, query: str, region: Region | None = None, confidence: float = 0.85) -> Match | None:
        for attempt in range(self._attempts):
            match = self._inner.locate(query, region, confidence)
            if match is not None:
                return match
            if attempt < self._attempts - 1:
                time.sleep(self._delay)
        return None

    def locate_all(self, query: str, region: Region | None = None, confidence: float = 0.85) -> list[Match]:
        for attempt in range(self._attempts):
            matches = self._inner.locate_all(query, region, confidence)
            if matches:
                return matches
            if attempt < self._attempts - 1:
                time.sleep(self._delay)
        return []


class FallbackLocator(ScreenLocator):
    """Tries several locators in order and returns the first hit, e.g. a
    fast exact matcher first and a slower, more forgiving one second."""

    def __init__(self, locators: Sequence[ScreenLocator]):
        if not locators:
            raise ValueError("FallbackLocator needs at least one locator.")
        self._locators = list(locators)

    def locate(self, query: str, region: Region | None = None, confidence: float = 0.85) -> Match | None:
        for locator in self._locators:
            match = locator.locate(query, region, confidence)
            if match is not None:
                return match
        return None

    def locate_all(self, query: str, region: Region | None = None, confidence: float = 0.85) -> list[Match]:
        for locator in self._locators:
            matches = locator.locate_all(query, region, confidence)
            if matches:
                return matches
        return []


class MultiScaleTemplateLocator(ScreenLocator):
    """Template matching that also tries the template resized to several
    scales, so a crop taken at one display scaling / zoom level still
    matches after the UI grows or shrinks a little. Slower than
    `TemplateMatchLocator` roughly in proportion to `len(scales)`."""

    def __init__(self, scales: Sequence[float] = (0.8, 0.9, 1.0, 1.1, 1.25)):
        self._scales = tuple(scales)

    def locate(self, query: str, region: Region | None = None, confidence: float = 0.85) -> Match | None:
        best: Match | None = None
        for result, w, h in self._match_each_scale(query, region):
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if best is None or max_val > best.confidence:
                best = self._to_match(max_loc[0], max_loc[1], w, h, max_val, region)
        return best if best is not None and best.confidence >= confidence else None

    def locate_all(self, query: str, region: Region | None = None, confidence: float = 0.85) -> list[Match]:
        candidates: list[Match] = []
        for result, w, h in self._match_each_scale(query, region):
            ys, xs = np.where(result >= confidence)
            candidates.extend(
                self._to_match(x, y, w, h, result[y, x], region) for y, x in zip(ys, xs, strict=True)
            )
        # Keep the strongest candidate among overlapping ones.
        matches: list[Match] = []
        for c in sorted(candidates, key=lambda m: m.confidence, reverse=True):
            if not any(abs(c.x - m.x) < m.width // 2 and abs(c.y - m.y) < m.height // 2 for m in matches):
                matches.append(c)
        return matches

    def _match_each_scale(self, query: str, region: Region | None):
        template = cv2.imread(query, cv2.IMREAD_COLOR)
        if template is None:
            raise FileNotFoundError(f"Could not load template image: {query}")
        screen = grab_screen(region)
        for scale in self._scales:
            resized = template if scale == 1.0 else cv2.resize(
                template, None, fx=scale, fy=scale,
                interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
            )
            h, w = resized.shape[:2]
            if h < 4 or w < 4 or h > screen.shape[0] or w > screen.shape[1]:
                continue
            yield cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED), w, h

    @staticmethod
    def _to_match(x, y, w, h, value, region: Region | None) -> Match:
        ox, oy = (region[0], region[1]) if region else (0, 0)
        return Match(int(x + ox), int(y + oy), int(w), int(h), float(value))
