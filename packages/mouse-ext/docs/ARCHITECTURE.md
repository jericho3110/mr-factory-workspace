# Architecture

This document has two audiences: (1) explaining how `mrfactory.mouse_ext`
works, and (2) teaching the reasoning behind *why* it's built this way,
so the approach can be reused on other projects. It assumes you've read
the original project's
[ARCHITECTURE.md](https://github.com/jericho3110/natural-mouse/blob/main/docs/ARCHITECTURE.md)
— Dependency Inversion, the Strategy pattern, and the Composition Root
are explained there and only referenced here.

## What this project does

Adds features to `natural_mouse` **without editing it**. `natural_mouse`
is installed as a separate package (`pip install -e ../Natural`) and
imported, never copied. Everything here is built on its public API.

There are two independent ways to add a feature, and choosing the right
one is the main design idea of this project:

```text
                      examples/click_with_plugins.py
                      (composition root: picks the concrete pieces)
                                     |
                                     v
     plugins ------------>  PluggableAutomator  (subclass of natural_mouse.UIAutomator)
  (observe/adjust each      /        |        \
   action via hooks)       v         v         v
                    ScreenLocator InputExecutor PathGenerator     <- natural_mouse's interfaces
                           ^         ^         ^
                           |         |         |                  <- extensions wrap one of these
             RetryLocator  |   FailSafeExecutor   FittsPathGenerator
             FallbackLocator   (wraps Win32...)   RecordingPathGenerator
             MultiScaleTemplateLocator            (wrap BezierPathGenerator)
```

| | Extension | Plugin |
| --- | --- | --- |
| **Changes** | *how* one step is done (find, move, click) | *what happens around* a whole action |
| **Is a** | `ScreenLocator` / `PathGenerator` / `InputExecutor` | `Plugin` |
| **How many** | one per slot, but they stack by wrapping | any number, all called in order |
| **Works with plain `UIAutomator`?** | yes | no, needs `PluggableAutomator` |
| **Examples** | retry a locate, re-time a path, abort on hand movement | log, count, refuse a target, screenshot a miss |

Rule of thumb: if the feature needs to be *inside* one step (e.g. check
the cursor between every point of a path), it's an extension. If it
only needs to know *that* a step happened and maybe veto the next one,
it's a plugin.

---

## Part 1: The principles, with real examples from this code

### Open/Closed Principle (the big one here)

**The idea:** code should be *open for extension* but *closed for
modification* — you add behavior by writing new code, not by editing
code that already works.

**Where it lives here:** this whole repository. Not one line of
`natural_mouse` was changed to add retries, multi-scale matching,
Fitts's-law timing, a fail-safe, logging, or stats. That's only possible
because the original project already put abstract interfaces at every
seam. The previous project *designed* for extension; this one *proves*
the design worked. (Its ARCHITECTURE.md Part 4 says: "If any of these
end up requiring a change to `automator.py`, that's a sign the
abstraction has a leak." None did.)

### The Decorator pattern (every extension)

**The idea:** wrap an object in another object that has the *same
interface*, adds something, and delegates the rest to the inner one.
Because the wrapper looks exactly like what it wraps, wrappers can be
stacked.

**Where it lives here:** every extension takes an `inner` of the same
type it implements:

```python
locator = RetryLocator(                       # a ScreenLocator...
    FallbackLocator([                         # ...wrapping a ScreenLocator...
        TemplateMatchLocator(),               # ...wrapping two more
        MultiScaleTemplateLocator(),
    ]),
    attempts=2,
)
```

`UIAutomator` receives the outermost one and has no idea there's a stack
behind it. Compare this with the alternative, subclassing:
`RetryingMultiScaleFallbackTemplateLocator` — one class per combination,
which explodes quickly. Wrapping composes; inheritance multiplies.

`FallbackLocator` is also a small **Chain of Responsibility**: a list of
handlers, each tried in turn until one handles the request.

### Hooks / the Observer pattern (every plugin)

**The idea:** a subject announces events ("I'm about to click", "I just
located something") to any number of observers that registered
interest. The subject doesn't know or care what the observers do.

**Where it lives here:** `PluggableAutomator` is the subject;
`PluginManager.dispatch(hook, ctx)` calls the named hook on every
registered `Plugin`. The base `Plugin` class defines every hook as a
no-op, so a plugin overrides only what it cares about — `StatsPlugin`
uses three hooks, `RegionGuardPlugin` uses one.

Two details make these hooks more than just notifications:

- **A shared context object.** Every hook gets the same `ActionContext`
  (`plugins/base.py`) for the action, so a plugin can *change* things —
  `before_input` may replace `ctx.target` — and can stash its own data
  in `ctx.extras` between hooks.
- **Veto by exception.** Any `before_*` hook may raise `ActionCancelled`
  to stop the action before the mouse moves. Exceptions were chosen
  over a return value (`return False`) because a refusal must not be
  silently ignored: a caller who forgot to check a return value would
  click anyway; a caller who forgot to catch an exception gets a loud
  stop instead.

### Liskov Substitution (PluggableAutomator is a drop-in)

**The idea:** a subclass must be usable anywhere its parent is, without
the caller noticing a difference (other than the added behavior).

**Where it lives here:** `PluggableAutomator(UIAutomator)` keeps the
exact constructor parameters, method signatures, and return values of
`UIAutomator`. With no plugins registered it behaves identically. The
test `test_is_a_drop_in_uiautomator` pins this down. That's why the
Natural project's own CLI and GUI could switch to it by changing one
constructor call.

One honest trade-off: `PluggableAutomator` reads `UIAutomator`'s
underscore attributes (`self._locator`, etc.). In Python the single
underscore means "internal, but subclasses may use it", so this is
allowed, but it does couple the two classes: if `natural_mouse` renamed
those attributes, `PluggableAutomator` would break. The alternative —
re-implementing `UIAutomator` from scratch — would duplicate its logic
instead, which is worse.

### Plugin discovery (entry points)

**The idea:** let *other packages* add plugins without this package
importing them, or even knowing they exist.

**Where it lives here:** `PluginManager.load_entry_points()`
(`plugins/manager.py`) asks Python's packaging metadata, "which installed
packages advertised something under the group
`mrfactory.mouse_ext.plugins`?" A package does that in its own
`pyproject.toml`. This package's `pyproject.toml` advertises its own
`LoggingPlugin` and `StatsPlugin` this way, as a working example. This
is the same mechanism pytest, Flask, and many other tools use for their
plugin ecosystems.

`load_path("package.module:Class")` is the lighter alternative: name a
plugin in a string, e.g. from a config file.

### A small exception hierarchy

`FailSafeTriggered` is a subclass of `ActionCancelled` (`errors.py`).
Callers who don't care *why* an action stopped catch `ActionCancelled`
once and handle both; callers who do care can catch the specific one.
They live in their own module so a plugin and an extension can raise the
same family without importing each other.

---

## Part 2: Testing philosophy

Same rule as the original project: nothing in the test suite touches the
real screen or mouse.

- **Plugins** are tested through `PluggableAutomator` with natural_mouse's
  own `FakeInputExecutor` and a `FakeScreenLocator` (`tests/fakes.py`).
  `HookRecorder`, a tiny plugin defined in the test, records which hooks
  fired, so the tests assert the exact hook order.
- **`FailSafeExecutor`** needed a new fake. `FakeInputExecutor` never
  iterates a path — it jumps straight to the target — so a per-point
  check would never run. `PathWalkingExecutor` walks the path point by
  point like `Win32InputExecutor` does, and can simulate "a human moved
  the mouse after step 3."
- **`MultiScaleTemplateLocator`** is tested without a screen by replacing
  `grab_screen` with `unittest.mock.patch` and a synthetic image. Note
  that it's patched where it's *used*
  (`mrfactory.mouse_ext.extensions.locators.grab_screen`), not where it's
  defined — `from x import y` copies the name into the importing module.
- **Randomness** is handled by turning it off where the test needs an
  exact number (`variability=0`, `overshoot_chance=0`) rather than by
  seeding, so the test states its assumption out loud.

---

## Part 3: Worked example — designing the fail-safe

A good case study in "how do I add behavior *inside* a loop I don't
own?"

**The goal:** abort a movement the instant the user grabs the mouse.
That means checking the real cursor position *between every step* of
the path.

**The problem:** the loop that walks the path lives inside
`Win32InputExecutor.move_to` in `natural_mouse`:

```python
for path_point in path:
    self._send_absolute_move(...)
    time.sleep(path_point.delay)
```

We can't edit it (Open/Closed), and wrapping the executor only gives us
control *before* and *after* `move_to`, not during.

**Options considered:**

1. *Subclass `Win32InputExecutor` and copy `move_to` with a check
   added.* Works, but duplicates its loop, and only works for that one
   executor.
2. *Add an `on_step` callback to `InputExecutor`.* Clean, but that's
   editing `natural_mouse`, and every executor would need updating.
3. *Hand the executor a path that checks itself.* ✔

**The solution:** the executor gets its path from the path generator we
pass in. So `FailSafeExecutor` passes a wrapped generator whose paths
are a `_GuardedPath` — a `Path` subclass whose `__iter__` is a Python
**generator function**:

```python
def __iter__(self):
    expected = self._origin
    for point in super().__iter__():
        self._check(expected)     # runs when the executor asks for the next point
        yield point
        expected = point.point
    self._check(expected)         # runs after the last move, before the click
```

A generator pauses at each `yield` and resumes only when the consumer
asks for the next item. The executor's loop is "send, sleep, ask for
next" — so each `_check` runs exactly after the previous move landed
and before the next one goes out. The final check, after the loop,
runs before `click()` presses the button. Raising inside the generator
propagates straight out of the executor's `for` loop, so nothing more is
sent.

**The lesson:** when you can't change a loop, look at what the loop
*consumes*. Controlling the iterator gives you a hook into every
iteration, for free, without the loop knowing.

---

## Part 4: Extension points (exercises)

Each should only need a new file (plus wiring in a composition root):

- **A `ConfirmPlugin`** that asks "click here? [y/N]" in `before_input`
  and raises `ActionCancelled` on "no". (Sketch in the README.)
- **A `JitterTargetPlugin`** that nudges `ctx.target` by a pixel or two
  in `before_input`. Compare: should this be a plugin, or is it really a
  path-generator concern? (Hint: which object owns "where exactly to
  click"?)
- **A `CachingLocator`** extension that remembers a match's position and
  first checks just that small region before searching the full screen.
- **A third-party plugin package**: make a separate tiny project that
  advertises a plugin under `mrfactory.mouse_ext.plugins` in its
  `pyproject.toml`, `pip install -e` it, and confirm
  `load_entry_points()` finds it without this package changing.

If any of these require editing `PluggableAutomator` or a `natural_mouse`
file, that's the signal a hook or interface is missing.

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

- Open–closed principle: <https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle> · Liskov substitution principle: <https://en.wikipedia.org/wiki/Liskov_substitution_principle>
- Refactoring Guru: [Decorator](https://refactoring.guru/design-patterns/decorator) · [Observer](https://refactoring.guru/design-patterns/observer) · [Strategy](https://refactoring.guru/design-patterns/strategy) · [Chain of Responsibility](https://refactoring.guru/design-patterns/chain-of-responsibility) · [Adapter](https://refactoring.guru/design-patterns/adapter)
- **Official:** entry points specification: <https://packaging.python.org/en/latest/specifications/entry-points/> · creating and discovering plugins: <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/> · `importlib.metadata`: <https://docs.python.org/3/library/importlib.metadata.html>
- **Official:** generators, PEP 255: <https://peps.python.org/pep-0255/> · Real Python, generators: <https://realpython.com/introduction-to-python-generators/>
- **Official:** exceptions: <https://docs.python.org/3/library/exceptions.html>
- **Official:** `unittest.mock`, where to patch: <https://docs.python.org/3/library/unittest.mock.html#where-to-patch>
- OpenCV template matching: <https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html>
- Fitts's law: <https://en.wikipedia.org/wiki/Fitts%27s_law>
- `natural-mouse` (the library mouse-ext extends) is a **private** repo: <https://github.com/jericho3110/natural-mouse>. Its links work only when signed in with access.
