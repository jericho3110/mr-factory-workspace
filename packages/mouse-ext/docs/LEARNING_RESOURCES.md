# Learning Resources

A study guide tied directly to this codebase: every concept below is
used in `mrfactory.mouse_ext`, with the exact file to look at, plus
outside resources to go deeper.

(The `natural-mouse` links below point to a **private** repo; they work only when signed in with access.)

This picks up where the original project's guide leaves off. Concepts
already covered there (project structure, SOLID basics, Strategy,
Dependency Injection, value objects, type hints, test doubles) aren't
repeated:

- [natural-mouse: LEARNING_RESOURCES.md](https://github.com/jericho3110/natural-mouse/blob/main/docs/LEARNING_RESOURCES.md)
- [natural-mouse: PROGRAMMING_ROADMAP.md](https://github.com/jericho3110/natural-mouse/blob/main/docs/PROGRAMMING_ROADMAP.md) — the broader map of concepts
- [natural-mouse: SOFTWARE_ARCHITECTURE_STYLES.md](https://github.com/jericho3110/natural-mouse/blob/main/docs/SOFTWARE_ARCHITECTURE_STYLES.md) — monolith, layered, hexagonal, etc.

## 1. Depending on your own library

**What we did:** this project imports `natural_mouse` as an installed
package (`pip install -e ../Natural`) instead of copying its files in.
Fixes in Natural reach this project immediately, and there's exactly
one copy of each class.

**A subtle packaging point:** `natural_mouse` is *not* listed under
`dependencies` in `pyproject.toml`. It isn't published on PyPI, and if
it were listed, a fresh `pip install -e .` would go looking for a
package of that name on PyPI — and would install a stranger's package
if one ever existed with that name. This attack is called *dependency
confusion*. Documenting the manual install step is the safe choice for
a private, unpublished library.

- [pip docs — Local project installs (editable mode)](https://pip.pypa.io/en/stable/topics/local-project-installs/)

## 2. Open/Closed Principle

**Where:** the whole repo — see ARCHITECTURE.md Part 1. Every feature
here was added without editing `natural_mouse`.

- [Wikipedia — Open–closed principle](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle)

## 3. Design patterns

**Decorator** — every class in `extensions/` wraps an `inner` object of
the same interface (`RetryLocator`, `FittsPathGenerator`,
`FailSafeExecutor`, ...). Wrappers stack.

- [Refactoring.Guru — Decorator](https://refactoring.guru/design-patterns/decorator)

Not to be confused with Python's `@decorator` syntax, which is a
language feature for wrapping *functions*. Same idea, different level.

**Observer / hooks** — `PluggableAutomator` announces each stage of an
action; `PluginManager.dispatch` calls every plugin's matching hook.

- [Refactoring.Guru — Observer](https://refactoring.guru/design-patterns/observer)

**Chain of Responsibility** — `FallbackLocator` tries locators in order
until one succeeds.

- [Refactoring.Guru — Chain of Responsibility](https://refactoring.guru/design-patterns/chain-of-responsibility)

**Null Object / optional hooks** — the base `Plugin` defines every hook
as a method that does nothing, so subclasses override only what they
need and the dispatcher never checks "does this plugin have this hook?".

## 4. Liskov Substitution

**Where:** `PluggableAutomator` is a subclass of `UIAutomator` with
identical method signatures, so it can replace it anywhere.
`tests/test_plugins.py::test_is_a_drop_in_uiautomator` checks this.

- [Wikipedia — Liskov substitution principle](https://en.wikipedia.org/wiki/Liskov_substitution_principle)

## 5. Plugin systems and entry points

**Where:** `plugins/manager.py` (`load_entry_points`, `load_path`) and
the `[project.entry-points."mrfactory.mouse_ext.plugins"]` table in
`pyproject.toml`.

- [Python Packaging Guide — Creating and discovering plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — covers exactly the three approaches (naming convention, namespace packages, entry points); this project uses entry points.
- [Python docs — importlib.metadata, entry points](https://docs.python.org/3/library/importlib.metadata.html#entry-points)
- [pluggy](https://pluggy.readthedocs.io/) — pytest's plugin library. A heavier, more formal version of what `PluginManager` does; worth reading once you've understood the small version here.

## 6. Exceptions as control flow (vetoes)

**Where:** `errors.py`. Plugins raise `ActionCancelled` to stop an
action; `FailSafeTriggered` is a subclass of it. See ARCHITECTURE.md for
why an exception beats a `return False` here.

- [Python tutorial — User-defined exceptions](https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions)

## 7. Generators and iterators

**Where:** `_GuardedPath.__iter__` in `extensions/executors.py`, the
core of the fail-safe. A generator function pauses at each `yield`,
letting code run *between* items as the consumer asks for them. Also
`MultiScaleTemplateLocator._match_each_scale`, which yields one match
result per scale instead of building a list.

- [Python docs — Functional Programming HOWTO, Generators](https://docs.python.org/3/howto/functional.html#generators)
- [Python docs — Iterator types](https://docs.python.org/3/library/stdtypes.html#iterator-types)

## 8. Fitts's law

**Where:** `FittsPathGenerator` in `extensions/paths.py`. A classic
human-computer-interaction model: the time to reach a target grows with
the *logarithm* of distance / target size, `MT = a + b·log2(D/W + 1)`.
Doubling the distance adds a constant amount of time; it doesn't double
it. That's why it makes long cursor moves look more natural than a
fixed duration range.

- [Wikipedia — Fitts's law](https://en.wikipedia.org/wiki/Fitts%27s_law)

## 9. Multi-scale template matching

**Where:** `MultiScaleTemplateLocator` in `extensions/locators.py`.
OpenCV's `matchTemplate` only finds the template at exactly its saved
size, so a crop taken at 100% display scaling fails at 125%. Resizing
the template to several scales and keeping the best score fixes that,
at a speed cost proportional to the number of scales.

- [OpenCV — Template Matching tutorial](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html)

## 10. Logging

**Where:** `LoggingPlugin` uses the standard `logging` module with a
named logger (`mrfactory.mouse_ext`) instead of `print`, so the
application decides the format and level (`logging.basicConfig` in the
example script) and can silence it.

- [Python docs — Logging HOWTO](https://docs.python.org/3/howto/logging.html)

## 11. Testing techniques new in this project

- **Patching where it's used:** `mock.patch("mrfactory.mouse_ext.extensions.locators.grab_screen")`
  in `tests/test_extensions.py`.
  [Python docs — unittest.mock, where to patch](https://docs.python.org/3/library/unittest.mock.html#where-to-patch)
- **A fake that behaves like the real thing where it matters:**
  `PathWalkingExecutor` in `tests/fakes.py` iterates paths point by
  point, because the fail-safe depends on that behavior.
- **A spy plugin:** `HookRecorder` in `tests/test_plugins.py` only
  records which hooks ran, to assert hook order.

## 12. Git & commit conventions

Shared by every package in the workspace: see
[§7 of the workspace CONVENTIONS.md](../../../docs/CONVENTIONS.md#7-commit-messages).
Same shape as the original project: a short imperative summary line, then
a body explaining *why* and how it was verified.

The same file also explains the workspace's folder/package naming and
the `mrfactory` namespace package. That's worth reading as a packaging
lesson in its own right.

## 13. Suggested study order

1. Read ARCHITECTURE.md's comparison table (extension vs plugin).
2. Open `extensions/locators.py` → `RetryLocator`: the smallest Decorator.
3. Open `plugins/base.py`, then `automator.py`: see where each hook fires.
4. Read `plugins/region_guard.py` and its tests: a veto end to end.
5. Read ARCHITECTURE.md Part 3, then `extensions/executors.py` — the
   generator trick.
6. Do one exercise from ARCHITECTURE.md Part 4 without looking anything up.
