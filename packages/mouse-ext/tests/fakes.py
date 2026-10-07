"""Shared test doubles."""

from __future__ import annotations

from natural_mouse import InputExecutor, Match, Point, ScreenLocator

# Point is immutable (a frozen dataclass), so one shared default is safe.
SCREEN_CENTER = Point(500, 500)


class FakeScreenLocator(ScreenLocator):
    """Returns queued results in order (then repeats the last one), and
    counts how many times it was asked."""

    def __init__(self, *results: Match | None):
        self._results = list(results) or [None]
        self.calls = 0

    def locate(self, query, region=None, confidence=0.85):
        result = self._results[min(self.calls, len(self._results) - 1)]
        self.calls += 1
        return result

    def locate_all(self, query, region=None, confidence=0.85):
        match = self.locate(query, region, confidence)
        return [match] if match else []


class PathWalkingExecutor(InputExecutor):
    """Unlike natural_mouse's FakeInputExecutor, this one actually iterates
    the generated path point by point (as Win32InputExecutor does), so
    wrappers that act per point can be tested. `hijack_at=(i, Point)`
    simulates a human moving the mouse right after step i."""

    def __init__(self, start: Point = SCREEN_CENTER, hijack_at: tuple[int, Point] | None = None):
        self.position = start
        self.hijack_at = hijack_at
        self.moves: list[Point] = []
        self.clicks: list[Point] = []
        self.scrolls: list[int] = []

    def get_cursor_position(self) -> Point:
        return self.position

    def move_to(self, target, path_generator):
        for i, p in enumerate(path_generator.generate(self.position, target)):
            self.position = Point(round(p.x), round(p.y))
            self.moves.append(self.position)
            if self.hijack_at and self.hijack_at[0] == i:
                self.position = self.hijack_at[1]

    def click(self, target, path_generator, hold_range=(0.06, 0.16)):
        if target is not None:
            self.move_to(target, path_generator)
        self.clicks.append(self.position)

    def scroll(self, amount, steps=5, step_delay_range=(0.05, 0.18)):
        self.scrolls.append(amount)
