# Libraries, built-ins, and dunder methods used

> **2026-10-09:** `mouse-ext` (`mrfactory.mouse_ext`) has moved into its own library,
> [natural-mouse](https://github.com/jericho3110/natural-mouse) (`natural_mouse.extensions`, `natural_mouse.plugins`). The
> lessons below still apply; where they name `packages/mouse-ext/...`, the code now
> lives in that repo (`src/natural_mouse/`, `tests/ext_fakes.py`, `docs/EXTENSIONS_AND_PLUGINS.md`).

A reference to **everything this workspace's code uses from Python and
from other libraries**: each standard-library module, built-in function,
dunder method, decorator, language feature, and external library, with
**where** it's used (file), **what for**, and **why it was chosen**
over the alternatives. It was compiled by scanning every `import`,
`def __x__`, and decorator in `packages/*/src`, `tests`, `examples`,
and `scripts/`.

Contents:

1. [The policy: standard library first](#1-the-policy-standard-library-first)
2. [Standard library modules](#2-standard-library-modules)
3. [Built-in functions](#3-built-in-functions)
4. [Dunder methods and attributes](#4-dunder-methods-and-attributes)
5. [Decorators](#5-decorators)
6. [Language features worth knowing](#6-language-features-worth-knowing)
7. [External libraries](#7-external-libraries)
8. [Adding a dependency: a checklist](#8-adding-a-dependency-a-checklist)
9. [Exercises](#9-exercises)
10. [References](#references)

---

## 1. The policy: standard library first

Python ships with a large **standard library** ("batteries included"):
modules like `json`, `pathlib`, and `urllib` that exist on every Python
installation. This workspace uses it **first**, and adds an external
library only when it does something the standard library can't do well.

| Package | External dependencies | Why |
| --- | --- | --- |
| `adspower` | **none** | HTTP + JSON, files, processes, and a CLI are all in the standard library. Installs instantly anywhere; nothing to keep updated |
| `mouse-ext` | `opencv-python`, `numpy`, and `natural_mouse` | image matching on screenshots is not something to write by hand (§7) |

Every dependency is code you didn't write, must keep updated, and must
trust. So each one has to earn its place.

---

## 2. Standard library modules

Grouped by job. "Where" lists the main files; the docs link explains
the topic in more depth.

### Language, typing, and data structures

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `__future__` | `from __future__ import annotations` | every module (25 files) | Type hints are stored as text, not evaluated at import. Allows `X \| None` and forward references (naming a class before it's defined) cheaply |
| `typing` | `Protocol`, `TypeVar`, `TYPE_CHECKING`, `Any` | `matching.py`, mouse-ext `plugins/base.py` | `Protocol`: typing by shape (§6 of adspower ARCHITECTURE). `TypeVar`: "same type out as in". `TYPE_CHECKING`: import something *only* for type hints, see below |
| `collections.abc` | `Callable`, `Iterable`, `Iterator`, `Sequence` | `api.py`, `cli/`, `matching.py`, mouse-ext | Abstract types for hints: "anything iterable", "anything callable". Preferred over the old `typing.Callable` aliases, which are deprecated (Ruff `UP035` enforces this) |
| `collections` | `defaultdict` | mouse-ext `plugins/stats.py` | A dict that creates missing entries automatically: `defaultdict(int)` starts every counter at 0, so `counts[action]["found"] += 1` never raises `KeyError` |
| `dataclasses` | `@dataclass`, `field()`, `asdict()`, `is_dataclass()` | `models.py`, `cli/output.py`, mouse-ext `plugins/base.py` | Generate `__init__`/`__repr__`/`__eq__` from fields (§4). `field(default_factory=dict)` gives each object its own fresh dict. `asdict()` turns objects into dicts for `--json` |
| `copy` | `copy.deepcopy` | `tests/fakes.py` (adspower) | Give each `FakeApi` its own copy of the sample data, so one test's changes can't leak into the next |

**`TYPE_CHECKING`, the circular-import escape hatch** (mouse-ext
`plugins/base.py`):

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:                        # True only for type checkers, never at runtime
    from ..automator import PluggableAutomator
```

`automator.py` imports `plugins`, and `plugins/base.py` wants to *name*
`PluggableAutomator` in a type hint. A real import would be circular.
Inside `if TYPE_CHECKING:` the import never runs, but editors and type
checkers still understand the hint.

### Text and data formats

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `json` | `loads`, `dumps`, `dump` | `api.py`, `cli/output.py`, mouse-ext `extensions/paths.py` (`RecordingPathGenerator.save_json`) | The Local API speaks JSON; `--json` output; saving recorded mouse paths. `ensure_ascii=False` keeps non-English names readable |
| `datetime` | `datetime.fromtimestamp`, `.now()`, `.strftime`, `.isoformat` | `models.py`, `cli/output.py`, `cli/app.py` | AdsPower sends Unix seconds as text; `fromtimestamp` makes a real date. `strftime("%Y-%m-%d %H:%M")` for tables, `isoformat()` for JSON |

### Files, operating system, processes

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `pathlib` | `Path`, `/`, `.is_file()`, `.mkdir()`, `.parent`, `.resolve()`, `.iterdir()` | `launcher.py`, `cli/app.py`, `scripts/test_all.py`, every `tests/__init__.py` | Paths as objects: `root / "AdsPower Global" / "AdsPower Global.exe"` works on every OS, instead of gluing strings with `\\`. Preferred over `os.path` |
| `os` | `os.environ.get`, `os.startfile` | `launcher.py`, `api.py`, `cli/app.py` | Read `ProgramFiles`, `LOCALAPPDATA`, `ADSPOWER_API_KEY`. `os.startfile` = "double-click this file" on Windows: starts AdsPower **detached** (it keeps running after we exit) |
| `sys` | `argv`, `exit`, `stderr`, `stdin`, `platform`, `executable`, `path` | `cli/`, `__main__.py`, `scripts/test_all.py`, `tests/__init__.py` | Exit codes (`sys.exit(main())`), errors to `stderr`, terminal detection on `stdin`, Windows-only code behind `sys.platform == "win32"`, running Python again with the *same* interpreter (`sys.executable`) |
| `subprocess` | `subprocess.run` | `scripts/test_all.py` | Run each package's tests in a separate process (their `tests` packages would clash in one). `cwd=` sets the folder; the return code tells pass/fail |
| `tempfile` | `TemporaryDirectory`, `gettempdir` | tests, `cli/app.py` | Tests build a fake `Program Files` tree in a folder that's deleted afterwards. `gettempdir()` is the crash log's fallback location |
| `ctypes` | `windll.kernel32.GetConsoleMode`, `c_uint32`, `byref` | `cli/prompts.py` | Call a Windows API function directly from Python, to tell a real console from `< NUL` (which fools `isatty()`). The standard library has no other way to ask |
| `msvcrt` | `get_osfhandle` | `cli/prompts.py` | Windows-only: turns Python's file number for stdin into the Windows "handle" that `GetConsoleMode` needs. Imported *inside* the function so other OSes never import it |

### Networking

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `urllib.request` | `Request`, `urlopen` | `api.py` | Send GET/POST requests. Enough for a local JSON API, so no `requests` dependency (§7) |
| `urllib.parse` | `urlencode`, `urlsplit` | `api.py` | Build `?user_id=k1a&page=2` safely (escapes special characters); `urlsplit(url).scheme` checks that a URL is http(s) before anything is opened |
| `urllib.error` | `URLError`, `HTTPError` | `api.py` | Tell "nobody answered" (`URLError` → `AdsPowerNotRunning`) from "answered with an error" (`HTTPError` → `AdsPowerApiError`). `HTTPError` is a subclass of `URLError`, so it's caught **first** |

### Time, math, randomness

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `time` | `monotonic`, `perf_counter`, `sleep`, `strftime` | `api.py`, `client.py`, mouse-ext | `monotonic()` measures waiting (rate limit, `--wait`): it never jumps if the clock changes. `perf_counter()` is the most precise timer, for measuring action durations. `sleep()` pauses. `strftime()` makes timestamped screenshot names |
| `math` | `log2` | mouse-ext `extensions/paths.py` | Fitts's law: movement time = a + b·log2(distance/width + 1) |
| `random` | `uniform` | mouse-ext `extensions/paths.py` | Human-like variation in movement time. (Tests set `variability=0` to make results exact) |

### Imports and packaging

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `importlib.metadata` | `version`, `PackageNotFoundError`, `entry_points` | adspower `__init__.py`, mouse-ext `plugins/manager.py` | Read installed metadata: the version for `--version`, and plugins other packages advertise ([MODULES_AND_PACKAGES §6](MODULES_AND_PACKAGES.md#6-distribution-packages-what-pip-installs)) |
| `importlib` | `import_module` | mouse-ext `plugins/manager.py` | Import a module whose name is only known at runtime (`"pkg.module:Class"` from a config string) |
| `importlib.util` | `find_spec` | mouse-ext `tests/__init__.py` | Check whether `natural_mouse` is importable *without* importing it |

### Command line, errors, logging

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `argparse` | `ArgumentParser`, `add_subparsers`, `parents=`, `add_mutually_exclusive_group`, `action="version"`/`"store_true"`, `RawDescriptionHelpFormatter` | `cli/app.py`, `scripts`, mouse-ext example | Generates `--help`, validates arguments, and reports errors, for free. Alternatives (`click`, `typer`) are nicer but are dependencies |
| `traceback` | `format_exc` | `cli/app.py` | Turn the current exception into text for the crash log |
| `logging` | `getLogger`, `basicConfig`, `INFO` | mouse-ext `plugins/logging_plugin.py`, example | Library code logs to a *named* logger (`"mrfactory.mouse_ext"`) and never configures output itself; the *application* (the example script) decides with `basicConfig`. That's the standard division of labour |

### Testing

| Module | What we use | Where | Why |
| --- | --- | --- | --- |
| `unittest` | `TestCase`, `assert*`, `addCleanup`, `discover` | every `tests/` | Built in, no install. (pytest is the popular alternative and runs these tests unchanged) |
| `unittest.mock` | `patch`, `patch.dict`, `Mock`, `side_effect` | `test_launcher.py`, `test_cli.py`, `test_client.py` | Replace a name for one test (`os.startfile`, `input`, `LocalApi`); `side_effect` makes a mock raise or return a sequence |
| `contextlib` | `redirect_stdout`, `redirect_stderr` | `test_cli.py`, `test_prompts.py` | Capture what the CLI prints, to assert on it |
| `io` | `StringIO`, `BytesIO` | tests | In-memory text/bytes "files": captured output, fake HTTP response bodies, fake stdin |

---

### Added with `gitship` and the adspower security fix (2026-10-08)

| Module | Where | What for | Why this one |
| --- | --- | --- | --- |
| `ipaddress` | `adspower/api.py` `_is_loopback`; `adspower/proxycheck.py` `parse_ip` | is the API host `127.x` / `::1`?; is the proxy check's answer a real IP? | parses IPv4 and IPv6 correctly; string checks like `startswith("127.")` miss `::1`, and a regex for IPv6 is easy to get wrong |
| `subprocess` | `gitship/runner.py` | run `git`, `gh` and checks | argument lists, no shell (no command injection) |
| `shutil.which` | `gitship/runner.py` | find `gh.exe` / `git.exe` on PATH | Windows needs the extension resolved |
| `hashlib` | `gitship/release.py` | SHA-256 of release assets | standard, fast, reads in 1 MB blocks |
| `fnmatch` | `gitship/scan.py` | `*.pem`, `__pycache__/*` patterns | shell-style patterns without touching the disk |
| `json` | `gitship/config.py` | `.gitship.json` | `tomllib` needs Python 3.11; the workspace supports 3.10 |
| `tempfile` | `gitship/workflow.py`, `release.py`, tests | commit-message file, SHA256SUMS, throwaway repos | unique names, cleaned up automatically |
| `urllib.request` | `gitship/release.py` | anonymous re-download of public release assets | proves strangers get the same bytes; only `https://github.com/` URLs |
## 3. Built-in functions

Always available, no import. The ones this code uses, with a real line:

| Built-in | Real example | What it does |
| --- | --- | --- |
| `print` | `print(f"error: {e}", file=sys.stderr)` | write text; `file=` picks stdout or stderr |
| `len` | `if len(profile.tags) == 1:` | size of a collection (calls `__len__`, §4) |
| `isinstance` | `if isinstance(name_or_id, Group): return name_or_id` | type check, also true for subclasses. Lets one parameter accept an object *or* a string |
| `hasattr` / `getattr` | `getattr(plugin, hook)(ctx)` | look up an attribute by name at runtime: dispatch to the hook method named in a string |
| `sorted` | `sorted(profiles, key=lambda p: serial_order(p.serial_number))` | a new sorted list; `key=` says what to compare by |
| `map` | `map(Group.from_api, rows)` | apply a function to every item, lazily |
| `any` / `all` | `any(same_name(tag, name) for tag in self.tags)` | "is at least one true?" (stops at the first) |
| `next` | `next((p for p in proxies if serial in p.used_by), None)` | first item of an iterator, or a default instead of an error |
| `zip` | `zip(row, widths, strict=True)` | walk several lists side by side; `strict=True` raises if lengths differ |
| `enumerate` | `for number, item in enumerate(shown, start=1):` | index + item, counting from 1 for the picker |
| `iter` | `return iter(tuple(self._plugins))` | get an iterator (calls `__iter__`) |
| `super` | `super().__init__(message)` | call the parent class's version of a method |
| `str` / `int` / `float` / `tuple` / `list` / `dict` / `set` | `tuple(tag.get("name", "") for tag in ...)` | conversions and constructors |
| `range`, `min`, `max`, `sum`, `round`, `abs` | mouse-ext path maths, stats | numbers |
| `open` | `with CRASH_LOG.open("a", encoding="utf-8") as log:` | open a file; always pass `encoding=` for text (Windows defaults vary) |
| `type` | `type(e).__name__` | the class of an object; used to print `ZeroDivisionError` in crash messages |

Two habits worth copying: **pass `key=` instead of sorting by hand**,
and **use `next(generator, default)`** for "first match or nothing"
instead of a loop with a flag variable.

---

## 4. Dunder methods and attributes

"Dunder" (double underscore) methods are **hooks Python calls for you**.
You don't call `obj.__len__()`; you write `len(obj)` and Python calls it.
Defining them makes your objects work with built-in syntax.

### Defined in this code

| Dunder | Where | Python calls it when... | Why here |
| --- | --- | --- | --- |
| `__init__` | 18 classes, e.g. `LocalApi`, `AdsPower`, every plugin | an object is created: `LocalApi(...)` | store the injected dependencies and settings |
| `__init__` + `super().__init__(msg)` | `errors.AmbiguousProfile` | the exception is created | keep extra data (`.matches`) *and* a normal message, by calling `Exception.__init__` |
| `__iter__` (generator) | mouse-ext `_GuardedPath` in `extensions/executors.py` | something loops over it: `for point in path:` | the fail-safe check runs between every point, because the executor's own loop *asks* for each point (full story: mouse-ext ARCHITECTURE Part 3) |
| `__iter__` | mouse-ext `PluginManager` | `for plugin in manager:` | returns `iter(tuple(self._plugins))`, a **snapshot**, so a plugin unregistering itself mid-loop can't break the loop |
| `__len__` | mouse-ext `PluginManager` | `len(manager)` | how many plugins are registered |
| `__call__` | `tests/fakes.py` `FakeOpener` | the object is called like a function: `opener(request, timeout=10)` | the fake can stand in for `urllib.request.urlopen` (a function) while remembering every request |

### Generated for you by `@dataclass`

`@dataclass` writes these from the field list (`Group`, `Tag`,
`Profile`, `Proxy`, `OpenedBrowser`, mouse-ext `ActionContext`):

| Dunder | Gives you |
| --- | --- |
| `__init__` | `Group(id="1", name="Acme")` |
| `__repr__` | readable printing: `Group(id='1', name='Acme', remark='')` |
| `__eq__` | `==` compares field values, so tests can `assertEqual(group, Group(...))` |
| `__hash__` (with `frozen=True`) | frozen dataclasses can go in sets and be dict keys |
| `__setattr__` blocked (with `frozen=True`) | `profile.name = "x"` raises `FrozenInstanceError`: immutable |

### Dunder attributes and names

| Name | Where | Meaning |
| --- | --- | --- |
| `__name__` / `"__main__"` | `scripts/test_all.py`, examples | the module's import name; `"__main__"` when run directly |
| `__all__` | each `__init__.py` | the public names |
| `__version__` | adspower `__init__.py` | the installed version, by convention |
| `__file__` | `tests/__init__.py`, `scripts/test_all.py` | this file's path, to find folders next to it |
| `__path__`, `__package__`, `__spec__` | (not set by us) | see [MODULES_AND_PACKAGES §2–§3](MODULES_AND_PACKAGES.md#2-modules) |
| `__future__` | every module | the future-features module (§2) |

Others you'll meet elsewhere: `__str__` (text for users, vs `__repr__`
for developers), `__enter__`/`__exit__` (what makes `with` work),
`__getitem__` (`obj[key]`), `__contains__` (`x in obj`), `__lt__`
(sorting), `__post_init__` (dataclass hook after `__init__`).

---

## 5. Decorators

A decorator (`@name` above a `def` or `class`) wraps or modifies what
follows it.

| Decorator | Where | Effect |
| --- | --- | --- |
| `@dataclass` / `@dataclass(frozen=True)` | `models.py`, mouse-ext `plugins/base.py` | generate the dunders in §4 |
| `@classmethod` | `Group.from_api`, `Profile.from_api`, `FakeResponse.json` | the method receives the **class** (`cls`), not an instance: an alternative constructor (`Profile.from_api(row)`) |
| `@property` | `Proxy.address`, `Proxy.url`, `Proxy.in_use`, `ActionContext.elapsed` | a method you read like an attribute (`proxy.in_use`, no parentheses): computed from other fields, never out of date |
| `@staticmethod` | mouse-ext `MultiScaleTemplateLocator._to_match` | a plain function that lives in a class for organization; receives neither `self` nor `cls` |

---

## 6. Language features worth knowing

| Feature | Real example | Notes |
| --- | --- | --- |
| f-strings with `!r` | `f"No group named {name_or_id!r}"` | `!r` uses `repr()`: shows `'Acmee'` with quotes, so empty or space-only input is visible |
| generator expressions | `any(text in f.casefold() for f in fields)` | like a list comprehension in `()`, but lazy: items are made one at a time |
| generator functions (`yield`) | `_GuardedPath.__iter__`, `_match_each_scale` | a function that pauses at each `yield`; how the fail-safe runs between mouse steps |
| comprehensions | `[g for g in groups if contains(g.name, name)]` | build lists/dicts/sets in one readable line |
| `lambda` | `lambda page: self.post(...)` | a small unnamed function, here passed to the shared paging loop |
| `*args` / `**kwargs` | `get(self, path, **params)` | accept any keyword arguments and pass them on |
| `{**a, "k": v}` | `{**body, "page": page}` | merge dicts into a new one without changing the original |
| `with` (context managers) | `with self._open(request) as response:` | the response is closed even if an error happens |
| `try / except / raise ... from` | `api.py` | catch specific errors, translate, keep the cause |
| `X \| None` types | everywhere | "an X or nothing"; needs 3.10+ at runtime, or `from __future__ import annotations` in hints |
| `if TYPE_CHECKING:` | mouse-ext `plugins/base.py` | imports for type hints only (§2) |

---

## 7. External libraries

### `natural_mouse` (our own, from `../Natural`)

The human-like mouse library this workspace extends. Not on PyPI; installed with
`pip install -e ../Natural`. Used only by mouse-ext.

| Name | What it is | Used for |
| --- | --- | --- |
| `UIAutomator` | the main class: find → move → click | `PluggableAutomator` subclasses it |
| `ScreenLocator`, `PathGenerator`, `InputExecutor` | the three strategy interfaces | every extension implements one of them |
| `TemplateMatchLocator`, `BezierPathGenerator`, `Win32InputExecutor` | the default implementations | wrapped by extensions in the example |
| `Point`, `Match`, `Path`, `PathPoint`, `MovementProfile` | value objects | positions, match results, movement paths |
| `screen.grab_screen` | screenshot as a numpy array | multi-scale matching, screenshot-on-miss |
| `input.FakeInputExecutor` | test double | mouse-ext tests |

**Why:** reuse instead of copy ([ARCHITECTURE §2](ARCHITECTURE.md#2-principles-applied-across-the-workspace)).
**Why not listed in `dependencies`:** dependency confusion
([MODULES_AND_PACKAGES §6](MODULES_AND_PACKAGES.md#6-distribution-packages-what-pip-installs)).

### `opencv-python` (`import cv2`), version ≥ 4.9

The standard computer-vision library. Used in mouse-ext
`extensions/locators.py` and `plugins/screenshot_on_miss.py`:

| Function | What it does here |
| --- | --- |
| `cv2.imread(path, cv2.IMREAD_COLOR)` | load the template image to look for |
| `cv2.resize(img, size, interpolation=cv2.INTER_AREA / INTER_LINEAR)` | try the template at other sizes (`INTER_AREA` for shrinking, `INTER_LINEAR` for enlarging: the usual quality choices) |
| `cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)` | slide the template over the screenshot and score every position from −1 to 1 |
| `cv2.minMaxLoc(result)` | the best score and where it is |
| `cv2.imwrite(path, image)` | save a screenshot when a match fails, for debugging |

**Why:** fast, well-tested template matching in C++; writing it by hand
would be slow and error-prone. **Alternatives:** Pillow (image loading
but no template matching), scikit-image (slower), `pyautogui.locateOnScreen`
(uses OpenCV underneath, less control). Note the import name `cv2`
differs from the distribution name `opencv-python`.

### `numpy` (`import numpy as np`), version ≥ 1.26

Arrays of numbers; OpenCV images *are* numpy arrays. Used directly once:

```python
ys, xs = np.where(result >= confidence)   # every position scoring above the threshold
```

`result >= confidence` compares the whole score grid at once
(**vectorized**, no Python loop), and `np.where` returns the
coordinates of the `True` cells: all matches, for `locate_all`.

**Why:** OpenCV needs it anyway, and whole-array operations are far
faster than Python loops over pixels.

### `playwright` (optional extra `[browser]`), version ≥ 1.40

- **Where:** `adspower/proxycheck.py` `playwright_fetch`, imported *inside*
  the function, so the package imports fine without it.
- **What for:** the proxy check attaches to the profile's already-open
  browser (`connect_over_cdp`) and loads one page through its proxy.
- **Why:** the browser is what actually uses the proxy, and the library
  never keeps proxy passwords. Playwright is maintained by Microsoft and
  ships its own driver.
- **Why optional:** everything else is standard library; an *extra*
  (`pip install "mrfactory-adspower[browser]"`) keeps it that way for
  users who never check proxies. Without it, a clear
  `ProxyCheckUnavailable` names the install command.
- **Alternatives:** Selenium (needs the matching chromedriver), a
  hand-written DevTools-protocol client over websockets (no standard
  library websocket client; much more code).

### Build and development tools (not imported by the code)

| Tool | Role | Why |
| --- | --- | --- |
| `setuptools` (≥ 68) | **build backend** named in each `pyproject.toml` | turns a project into an installable distribution; supports namespace packages and editable installs |
| `pip` | installer | installs distributions and creates the editable-install hooks |
| `ruff` | linter (`ruff.toml`) | catches bugs and style problems ([ARCHITECTURE §9](ARCHITECTURE.md#9-code-style-and-formatting)) |
| `gh` (GitHub CLI) | creating/pushing repos | publishing; not part of the code |

### Considered and not used

| Library | Would have given | Why not (yet) |
| --- | --- | --- |
| `requests` / `httpx` | nicer HTTP API, sessions | `urllib` is enough for one local JSON API; zero dependencies wins |
| `click` / `typer` | decorator-based CLIs | `argparse` is built in and covers every need so far |
| `pytest` | less boilerplate, better failure output | `unittest` needs no install; easy switch later |
| `pydantic` | validated models from JSON | `@dataclass` + `from_api` is enough for a few models |
| `selenium` | controlling the browser inside a profile | not needed; Playwright (below, optional) covers the one use |

---

## 8. Adding a dependency: a checklist

1. **Can the standard library do it** in reasonable code? If yes, use it.
2. **Is it well maintained?** Recent releases, many users, open issues answered.
3. **Is it the real package?** Check the exact name on PyPI (typo-squatting exists).
4. Add it to `dependencies` in `pyproject.toml` with a **lower bound**
   (`>=`), not an exact pin (libraries use ranges, [MODULES_AND_PACKAGES §8](MODULES_AND_PACKAGES.md#8-dependencies-and-their-versions)).
5. `pip install -e packages/<name>` again (metadata changed).
6. Document it **here**: what, where, why, alternatives.
7. Wrap it behind your own small interface if it touches the outside
   world (like `LocalApi` wraps `urllib`), so tests can fake it and it
   can be swapped later.

---

## 9. Exercises

1. **Dunder in action.** In a Python shell, make
   `class Box: def __len__(self): return 3`, then call `len(Box())`.
   Add `__iter__` returning `iter([1, 2, 3])` and use it in a `for` loop
   and in `list(Box())`.
2. **`frozen=True`.** Create `Group("1", "a")` and try `g.name = "b"`.
   Read the error. Then put two equal `Group`s in a `set`: how many
   items does it hold, and which dunders made that possible?
3. **`@property` vs a stored field.** Why is `Proxy.in_use` a property
   computed from `profile_count`, not a field set in `from_api`? What
   could go wrong with a stored field?
4. **`monotonic` vs `time`.** Read the docs for `time.time()` and
   `time.monotonic()`. Why would the rate limiter misbehave if it used
   `time.time()` while Windows adjusted the clock?
5. **Replace a library on paper.** If `adspower` switched from `urllib`
   to `requests`, which file(s) would change? Which tests? (Hint: what
   does `LocalApi(opener=...)` hide?)
6. **Find an unused import.** Add `import os` to `matching.py` and run
   `ruff check .`. Which rule reports it? Remove it again.

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

### §2 Standard library modules (official docs, one per module)

- Language and typing: [`__future__`](https://docs.python.org/3/library/__future__.html) · [`typing`](https://docs.python.org/3/library/typing.html) · [`collections.abc`](https://docs.python.org/3/library/collections.abc.html) · [`collections`](https://docs.python.org/3/library/collections.html) · [`dataclasses`](https://docs.python.org/3/library/dataclasses.html) · [`copy`](https://docs.python.org/3/library/copy.html)
- Data formats: [`json`](https://docs.python.org/3/library/json.html) · [`datetime`](https://docs.python.org/3/library/datetime.html)
- Files and OS: [`pathlib`](https://docs.python.org/3/library/pathlib.html) · [`os`](https://docs.python.org/3/library/os.html) · [`sys`](https://docs.python.org/3/library/sys.html) · [`subprocess`](https://docs.python.org/3/library/subprocess.html) · [`tempfile`](https://docs.python.org/3/library/tempfile.html) · [`ctypes`](https://docs.python.org/3/library/ctypes.html) · [`msvcrt`](https://docs.python.org/3/library/msvcrt.html)
- Networking: [`urllib.request`](https://docs.python.org/3/library/urllib.request.html) · [`urllib.parse`](https://docs.python.org/3/library/urllib.parse.html) · [`urllib.error`](https://docs.python.org/3/library/urllib.error.html)
- Time and numbers: [`time`](https://docs.python.org/3/library/time.html) · [`math`](https://docs.python.org/3/library/math.html) · [`random`](https://docs.python.org/3/library/random.html)
- Imports: [`importlib`](https://docs.python.org/3/library/importlib.html) · [`importlib.metadata`](https://docs.python.org/3/library/importlib.metadata.html)
- CLI, errors, logging: [`argparse`](https://docs.python.org/3/library/argparse.html) ([tutorial](https://docs.python.org/3/howto/argparse.html)) · [`traceback`](https://docs.python.org/3/library/traceback.html) · [`logging`](https://docs.python.org/3/library/logging.html) ([HOWTO](https://docs.python.org/3/howto/logging.html))
- Testing: [`unittest`](https://docs.python.org/3/library/unittest.html) · [`unittest.mock`](https://docs.python.org/3/library/unittest.mock.html) · [`contextlib`](https://docs.python.org/3/library/contextlib.html) · [`io`](https://docs.python.org/3/library/io.html)

Specific claims checked:

- ✔ `os.startfile` "returns as soon as the associated application is launched" and acts "like double-clicking the file in Explorer": `os.startfile.__doc__` in Python 3.14; docs: <https://docs.python.org/3/library/os.html#os.startfile>; the underlying Windows call: <https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew>
- ✔ `typing.Callable` is deprecated in favour of `collections.abc.Callable`: <https://docs.python.org/3/library/typing.html> · PEP 585: <https://peps.python.org/pep-0585/>
- `time.monotonic` (a clock that cannot go backwards): <https://docs.python.org/3/library/time.html#time.monotonic>
- `collections.defaultdict`: <https://docs.python.org/3/library/collections.html#collections.defaultdict>
- `GetConsoleMode` (the Windows console check): <https://learn.microsoft.com/en-us/windows/console/getconsolemode>
- `str.casefold`: <https://docs.python.org/3/library/stdtypes.html#str.casefold>

Further reading: Real Python on [`pathlib`](https://realpython.com/python-pathlib/), [`json`](https://realpython.com/python-json/), [`time`](https://realpython.com/python-time-module/), [`urllib.request`](https://realpython.com/urllib-request/), [`subprocess`](https://realpython.com/python-subprocess/), [`defaultdict`](https://realpython.com/python-defaultdict/), [`argparse`](https://realpython.com/command-line-interfaces-python-argparse/), [`logging`](https://realpython.com/python-logging/), [type checking](https://realpython.com/python-type-checking/).

### §3 Built-in functions

- **Official:** built-in functions: <https://docs.python.org/3/library/functions.html> · `zip(strict=True)`: <https://docs.python.org/3/library/functions.html#zip> · PEP 618: <https://peps.python.org/pep-0618/>
- **Official:** built-in types (`str`, `dict`, ...): <https://docs.python.org/3/library/stdtypes.html>
- **Official:** functional programming HOWTO (`map`, generators, `any`): <https://docs.python.org/3/howto/functional.html>

### §4 Dunder methods and attributes

- **Official:** data model, special method names: <https://docs.python.org/3/reference/datamodel.html>
- **Official:** `dataclasses` ✔ (eq + frozen → `__hash__` generated; assigning to a frozen field raises `FrozenInstanceError`; `default_factory` for mutable defaults): <https://docs.python.org/3/library/dataclasses.html> · PEP 557: <https://peps.python.org/pep-0557/>
- **Official:** tutorial, classes and iterators: <https://docs.python.org/3/tutorial/classes.html>
- Real Python, "Python's Magic Methods": <https://realpython.com/python-magic-methods/> · "Data Classes in Python": <https://realpython.com/python-data-classes/>

### §5 Decorators

- **Official:** PEP 318, decorators: <https://peps.python.org/pep-0318/>
- Real Python, "Primer on Python Decorators": <https://realpython.com/primer-on-python-decorators/> · "Python's property()": <https://realpython.com/python-property/> · "Instance, Class, and Static Methods": <https://realpython.com/instance-class-and-static-methods-demystified/>

### §6 Language features

- **Official:** exceptions ✔ (`KeyboardInterrupt` inherits from `BaseException` "so as to not be accidentally caught by code that catches `Exception`"; `raise ... from` sets `__cause__`): <https://docs.python.org/3/library/exceptions.html> · PEP 3134: <https://peps.python.org/pep-3134/>
- **Official:** errors tutorial: <https://docs.python.org/3/tutorial/errors.html> · `with` statement: <https://docs.python.org/3/reference/compound_stmts.html>
- **Official:** generators, PEP 255: <https://peps.python.org/pep-0255/> · `Protocol` (PEP 544): <https://peps.python.org/pep-0544/> · `X | Y` types (PEP 604): <https://peps.python.org/pep-0604/>
- Real Python: [generators](https://realpython.com/introduction-to-python-generators/), [f-strings](https://realpython.com/python-f-strings/), [protocols](https://realpython.com/python-protocol/), [exceptions](https://realpython.com/python-exceptions/)

### §7 External libraries

- **Official:** OpenCV template matching tutorial (`matchTemplate`, `minMaxLoc`, `TM_CCOEFF_NORMED`): <https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html>
- **Official:** OpenCV object detection API (`matchTemplate`): <https://docs.opencv.org/4.x/df/dfb/group__imgproc__object.html> · geometric transforms (`resize`, `INTER_AREA`): <https://docs.opencv.org/4.x/da/d54/group__imgproc__transform.html>
- **Official:** NumPy `where`: <https://numpy.org/doc/stable/reference/generated/numpy.where.html> · broadcasting/vectorization: <https://numpy.org/doc/stable/user/basics.broadcasting.html> · beginners guide: <https://numpy.org/doc/stable/user/absolute_beginners.html>
- PyPI pages (check the exact name before installing): [opencv-python](https://pypi.org/project/opencv-python/) · [numpy](https://pypi.org/project/numpy/)
- Fitts's law: <https://en.wikipedia.org/wiki/Fitts%27s_law>
- Tools: [setuptools](https://setuptools.pypa.io/en/latest/userguide/development_mode.html) · [pip](https://pip.pypa.io/en/stable/cli/pip_install/) · [Ruff](https://docs.astral.sh/ruff/) · [`gh repo create`](https://cli.github.com/manual/gh_repo_create)
- `natural-mouse` (the library mouse-ext extends) is a public repo (since October 2026): <https://github.com/jericho3110/natural-mouse>.

### §8 Adding a dependency

- PyPA, install_requires vs requirements files: <https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/>
- Supply chain attacks: <https://en.wikipedia.org/wiki/Supply_chain_attack>
