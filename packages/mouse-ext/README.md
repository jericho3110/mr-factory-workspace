# mrfactory.mouse_ext

Plugins and extensions for
[`natural_mouse`](https://github.com/jericho3110/natural-mouse) (the
human-like mouse clicker). Part of the
[mr-factory workspace](../../README.md): distribution `mrfactory-mouse-ext`,
import `mrfactory.mouse_ext`. It **imports** `natural_mouse` rather than
copying it, so improvements made there show up here automatically.

📖 **[docs/](docs/)** explains the architecture and the concepts behind
it. See [Documentation](#documentation).

## Setup

From the workspace root, after the shared setup in the
[workspace README](../../README.md#setup):

```powershell
pip install -e ../Natural          # the original library (next to the workspace folder)
pip install -e packages/mouse-ext  # this package
```

## Two ways to extend

**Extensions** wrap one of `natural_mouse`'s own strategy interfaces, so
they also work with the plain `UIAutomator`:

| Extension | Wraps | What it adds |
| --- | --- | --- |
| `RetryLocator(inner, attempts, delay)` | `ScreenLocator` | retries a locate a bounded number of times, for elements that are still loading |
| `FallbackLocator([a, b, ...])` | `ScreenLocator` | tries locators in order, first hit wins |
| `MultiScaleTemplateLocator(scales)` | `ScreenLocator` | template matching that tolerates UI scaling/zoom changes |
| `FittsPathGenerator(inner)` | `PathGenerator` | re-times movements by Fitts's law: long moves take longer, but not proportionally longer |
| `RecordingPathGenerator(inner)` | `PathGenerator` | keeps every generated path; `save_json()` for plotting/tuning |
| `FailSafeExecutor(inner)` | `InputExecutor` | aborts the moment you grab the mouse, or when the cursor is in the top-left corner |

**Plugins** hook into each action. They need `PluggableAutomator`, a
drop-in subclass of `UIAutomator` with the same methods:

| Plugin | What it does |
| --- | --- |
| `LoggingPlugin` | logs matches, misses, timings, and errors |
| `StatsPlugin` | counts found/missed/ok/errors; `summary()` |
| `RegionGuardPlugin(allowed)` | cancels any click/scroll outside the allowed rectangles |
| `ScreenshotOnMissPlugin(dir)` | saves the screen when a template isn't found, so you can see why |

## Usage

```python
from natural_mouse import BezierPathGenerator, TemplateMatchLocator, Win32InputExecutor
from mrfactory.mouse_ext import (
    PluggableAutomator, RetryLocator, FittsPathGenerator, FailSafeExecutor,
    LoggingPlugin, RegionGuardPlugin, ActionCancelled,
)

automator = PluggableAutomator(
    locator=RetryLocator(TemplateMatchLocator()),
    executor=FailSafeExecutor(Win32InputExecutor()),
    path_generator=FittsPathGenerator(BezierPathGenerator()),
    plugins=[LoggingPlugin(), RegionGuardPlugin([(0, 0, 1920, 1080)])],
)

try:
    automator.find_and_click("templates/target.png")
except ActionCancelled as e:   # raised by a guard plugin or the fail-safe
    print("Stopped:", e)
```

A full runnable example: `python examples/click_with_plugins.py templates/target.png --dry-run`
(`--dry-run` searches the screen but never moves the mouse).

## Writing your own plugin

Subclass `Plugin` and override only the hooks you need:

```python
from mrfactory.mouse_ext import Plugin, ActionCancelled

class ConfirmPlugin(Plugin):
    def before_input(self, ctx):
        if input(f"{ctx.action} at {ctx.target}? [y/N] ") != "y":
            raise ActionCancelled("declined")
```

Hook order for one action: `before_action` → `after_locate` (click/locate)
→ `before_input` (click/scroll; may change `ctx.target`) → `after_action`,
or `on_error` instead of `after_action` if anything raised.

To ship a plugin from **another package**, advertise it under the entry
point group `mrfactory.mouse_ext.plugins` in that package's `pyproject.toml`;
`automator.plugins.load_entry_points()` will find it. Plugins named in a
config file can be loaded with `plugins.load_path("pkg.module:Class", **kwargs)`.

Writing your own extension is the same as adding a new strategy to
`natural_mouse`: subclass `ScreenLocator`, `PathGenerator`, or
`InputExecutor`, usually taking an `inner` one to wrap.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — extensions vs plugins, the patterns used (Decorator, Observer/hooks, Liskov, Open/Closed, entry-point discovery), testing approach, and a worked case study of how the fail-safe hooks into a loop it doesn't own.
- [docs/LEARNING_RESOURCES.md](docs/LEARNING_RESOURCES.md) — every concept this project adds on top of natural_mouse, tied to the file it's used in, with outside resources.
- The original project's [docs](https://github.com/jericho3110/natural-mouse/tree/main/docs) cover the foundations (Strategy, Dependency Injection, project structure, general roadmap).

## Layout

```text
docs/                 ARCHITECTURE.md, LEARNING_RESOURCES.md
src/mrfactory/mouse_ext/
  automator.py        PluggableAutomator (UIAutomator + plugin hooks)
  errors.py           ActionCancelled, FailSafeTriggered
  plugins/            base.py (Plugin, ActionContext), manager.py (PluginManager), built-in plugins
  extensions/         locators.py, paths.py, executors.py
examples/             click_with_plugins.py
tests/                unittest suite (no real mouse/screen needed)
```

## Tests

From this package's folder (`packages/mouse-ext/`), or run every
package at once with `python scripts/test_all.py` from the workspace root:

```powershell
python -m unittest discover -s tests -t .
```

Same as the original project: everything here performs one action per
call. Nothing loops, schedules, or runs unattended.

---

## References

- OpenCV template matching: <https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html>
- Entry points (plugin discovery): <https://packaging.python.org/en/latest/specifications/entry-points/>
- Fitts's law: <https://en.wikipedia.org/wiki/Fitts%27s_law>
- `natural-mouse` (the library mouse-ext extends) is a **private** repo: <https://github.com/jericho3110/natural-mouse>. Its links work only when signed in with access.
- Design concepts and their sources: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#references)
