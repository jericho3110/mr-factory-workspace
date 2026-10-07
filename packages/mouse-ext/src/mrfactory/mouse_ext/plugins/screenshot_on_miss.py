"""Saves what the screen looked like whenever a template isn't found.

When a click silently misses, the usual question is "what was actually on
screen?" — this answers it. Compare the saved image with the template to
see whether the layout changed, the theme changed, or the element simply
wasn't visible.
"""

from __future__ import annotations

import time
from pathlib import Path as FsPath

import cv2

from natural_mouse.screen import grab_screen

from .base import ActionContext, Plugin


class ScreenshotOnMissPlugin(Plugin):
    def __init__(self, directory: str = "misses"):
        super().__init__()
        self.directory = FsPath(directory)
        self.saved: list[FsPath] = []

    def after_locate(self, ctx: ActionContext) -> None:
        if ctx.match is not None:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        stem = FsPath(ctx.query or "query").stem
        path = self.directory / f"{time.strftime('%Y%m%d-%H%M%S')}_{stem}.png"
        cv2.imwrite(str(path), grab_screen(ctx.region))
        ctx.extras["miss_screenshot"] = path
        self.saved.append(path)
