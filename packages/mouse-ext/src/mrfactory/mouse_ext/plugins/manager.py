"""Holds the active plugins, dispatches hooks to them, and loads plugins
from other installed packages.

Third-party plugins are discovered through Python entry points: any
installed package can advertise a plugin in its own pyproject.toml,

    [project.entry-points."mrfactory.mouse_ext.plugins"]
    my_plugin = "my_package.module:MyPlugin"

and `PluginManager.load_entry_points()` will find it without this package
ever knowing that plugin exists.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Iterator
from importlib.metadata import entry_points

from .base import ActionContext, Plugin

ENTRY_POINT_GROUP = "mrfactory.mouse_ext.plugins"


class PluginManager:
    def __init__(self, plugins: Iterable[Plugin] = ()):
        self._plugins: list[Plugin] = []
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: Plugin) -> Plugin:
        if not isinstance(plugin, Plugin):
            raise TypeError(f"{plugin!r} is not a Plugin instance.")
        if self.get(plugin.name) is not None:
            raise ValueError(f"A plugin named {plugin.name!r} is already registered.")
        self._plugins.append(plugin)
        return plugin

    def unregister(self, name: str) -> Plugin | None:
        plugin = self.get(name)
        if plugin is not None:
            self._plugins.remove(plugin)
        return plugin

    def get(self, name: str | None) -> Plugin | None:
        return next((p for p in self._plugins if p.name == name), None)

    def __iter__(self) -> Iterator[Plugin]:
        return iter(tuple(self._plugins))

    def __len__(self) -> int:
        return len(self._plugins)

    def dispatch(self, hook: str, ctx: ActionContext, *args) -> None:
        for plugin in self:
            getattr(plugin, hook)(ctx, *args)

    def load_path(self, spec: str, **kwargs) -> Plugin:
        """Instantiate and register a plugin from a "package.module:Class"
        string — handy for plugin lists kept in a config file."""
        return self.register(_import_object(spec)(**kwargs))

    def load_entry_points(self, group: str = ENTRY_POINT_GROUP) -> list[Plugin]:
        """Instantiate and register every plugin advertised under `group`
        by installed packages. Plugins whose name is already registered are
        skipped, so this is safe to call after registering some by hand."""
        loaded = []
        for ep in entry_points(group=group):
            plugin = ep.load()()
            if self.get(plugin.name) is None:
                loaded.append(self.register(plugin))
        return loaded


def _import_object(spec: str):
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise ValueError(f"Expected 'package.module:Name', got {spec!r}.")
    return getattr(importlib.import_module(module_name), attr)
