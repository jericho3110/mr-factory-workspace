"""Plugins and extensions for `natural_mouse`.

- `PluggableAutomator`: a drop-in `UIAutomator` that fires plugin hooks.
- `plugins`: hook-based add-ons (logging, stats, safety, debugging).
- `extensions`: wrappers implementing natural_mouse's own strategy
  interfaces (`ScreenLocator`, `PathGenerator`, `InputExecutor`).
"""

from .automator import PluggableAutomator
from .errors import ActionCancelled, FailSafeTriggered
from .extensions import (
    FailSafeExecutor,
    FallbackLocator,
    FittsPathGenerator,
    MultiScaleTemplateLocator,
    RecordingPathGenerator,
    RetryLocator,
)
from .plugins import (
    ActionContext,
    LoggingPlugin,
    Plugin,
    PluginManager,
    RegionGuardPlugin,
    ScreenshotOnMissPlugin,
    StatsPlugin,
)

__all__ = [
    "PluggableAutomator",
    "ActionCancelled",
    "FailSafeTriggered",
    "FailSafeExecutor",
    "FallbackLocator",
    "FittsPathGenerator",
    "MultiScaleTemplateLocator",
    "RecordingPathGenerator",
    "RetryLocator",
    "ActionContext",
    "LoggingPlugin",
    "Plugin",
    "PluginManager",
    "RegionGuardPlugin",
    "ScreenshotOnMissPlugin",
    "StatsPlugin",
]
