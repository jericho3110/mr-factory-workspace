"""`PathGenerator` decorators: wrap any generator (usually
`BezierPathGenerator`) and adjust or observe the paths it produces."""

from __future__ import annotations

import json
import math
import random

from natural_mouse import Path, PathGenerator, PathPoint, Point


class FittsPathGenerator(PathGenerator):
    """Re-times the wrapped generator's paths using Fitts's law,
    MT = a + b * log2(D / W + 1): long jumps take longer than short
    nudges, but not proportionally longer, the way real hand movements
    behave. The path's shape is untouched; only its delays are scaled.

    `a`/`b` are in seconds; `target_width` (W) is a typical target size in
    pixels; `variability` adds +/- that fraction of random spread."""

    def __init__(
        self,
        inner: PathGenerator,
        a: float = 0.08,
        b: float = 0.11,
        target_width: float = 24.0,
        variability: float = 0.15,
    ):
        self._inner = inner
        self.a, self.b = a, b
        self.target_width = target_width
        self.variability = variability

    def movement_time(self, distance: float) -> float:
        return self.a + self.b * math.log2(distance / self.target_width + 1)

    def generate(self, start: Point, end: Point) -> Path:
        path = self._inner.generate(start, end)
        wanted = self.movement_time(start.distance_to(end))
        wanted *= random.uniform(1 - self.variability, 1 + self.variability)
        scale = wanted / path.total_duration if path.total_duration > 0 else 1.0
        return Path([PathPoint(p.x, p.y, p.delay * scale) for p in path])


class RecordingPathGenerator(PathGenerator):
    """Keeps a copy of every path the wrapped generator produces, for
    debugging, plotting, or tuning a `MovementProfile`."""

    def __init__(self, inner: PathGenerator):
        self._inner = inner
        self.recordings: list[dict] = []

    def generate(self, start: Point, end: Point) -> Path:
        path = self._inner.generate(start, end)
        self.recordings.append({
            "start": start.as_tuple(),
            "end": end.as_tuple(),
            "duration": path.total_duration,
            "points": [(p.x, p.y, p.delay) for p in path],
        })
        return path

    def clear(self) -> None:
        self.recordings.clear()

    def save_json(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.recordings, f, indent=2)
