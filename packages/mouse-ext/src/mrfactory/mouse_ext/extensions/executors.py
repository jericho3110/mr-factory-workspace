"""`InputExecutor` decorators."""

from __future__ import annotations

from collections.abc import Callable

from natural_mouse import InputExecutor, Path, PathGenerator, PathPoint, Point

from ..errors import FailSafeTriggered


class FailSafeExecutor(InputExecutor):
    """Aborts an automated movement the moment you grab the mouse.

    Before each step of a path it checks that the real cursor is still
    where the previous step put it. If it's more than `tolerance_px` away,
    a human moved it, so `FailSafeTriggered` is raised and nothing else is
    sent (including the click). As a second escape hatch, it also aborts
    if the cursor sits within `corner_px` of the top-left screen corner
    (0, 0), like pyautogui's fail-safe. Wraps any executor, e.g.
    `FailSafeExecutor(Win32InputExecutor())`.
    """

    def __init__(self, inner: InputExecutor, tolerance_px: float = 25.0, corner_px: float = 3.0):
        self._inner = inner
        self.tolerance_px = tolerance_px
        self.corner_px = corner_px

    def get_cursor_position(self) -> Point:
        return self._inner.get_cursor_position()

    def move_to(self, target: Point, path_generator: PathGenerator) -> None:
        self._check_corner()
        self._inner.move_to(target, self._guarded(path_generator))

    def click(
        self,
        target: Point | None,
        path_generator: PathGenerator,
        hold_range: tuple[float, float] = (0.06, 0.16),
    ) -> None:
        self._check_corner()
        self._inner.click(target, self._guarded(path_generator), hold_range)

    def scroll(self, amount: int, steps: int = 5, step_delay_range: tuple[float, float] = (0.05, 0.18)) -> None:
        self._check_corner()
        self._inner.scroll(amount, steps, step_delay_range)

    def _guarded(self, path_generator: PathGenerator | None) -> PathGenerator | None:
        if path_generator is None:
            return None
        return _GuardedPathGenerator(path_generator, self._check_position)

    def _check_corner(self) -> None:
        pos = self._inner.get_cursor_position()
        if pos.x <= self.corner_px and pos.y <= self.corner_px:
            raise FailSafeTriggered("Cursor is in the fail-safe corner (top-left).")

    def _check_position(self, expected: Point) -> None:
        self._check_corner()
        actual = self._inner.get_cursor_position()
        if actual.distance_to(Point(round(expected.x), round(expected.y))) > self.tolerance_px:
            raise FailSafeTriggered(
                f"Cursor was moved by hand: expected near ({expected.x:.0f}, {expected.y:.0f}), "
                f"found at ({actual.x:.0f}, {actual.y:.0f})."
            )


class _GuardedPathGenerator(PathGenerator):
    def __init__(self, inner: PathGenerator, check: Callable[[Point], None]):
        self._inner = inner
        self._check = check

    def generate(self, start: Point, end: Point) -> Path:
        return _GuardedPath(list(self._inner.generate(start, end)), start, self._check)


class _GuardedPath(Path):
    """A Path that runs `check(previous_point)` before handing out each
    point, and once more after the last one. Executors iterate a path as
    "send point, sleep, ask for next", so each check runs after the
    previous move has landed and before the next one (or the click) goes
    out."""

    def __init__(self, points: list[PathPoint], origin: Point, check: Callable[[Point], None]):
        super().__init__(points)
        self._origin = origin
        self._check = check

    def __iter__(self):
        expected = self._origin
        for point in super().__iter__():
            self._check(expected)
            yield point
            expected = point.point
        self._check(expected)
