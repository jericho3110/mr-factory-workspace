# Workspace architecture

This file explains *why* the workspace is built the way it is: the
software-engineering ideas behind the layout, the packaging files, the
commands, the code style, and the tests. [CONVENTIONS.md](CONVENTIONS.md)
lists the rules. This file gives the reasons for them.

The design patterns *inside* `mouse-ext` (Decorator, Observer/hooks,
Liskov, Open/Closed, entry-point discovery) are explained in
[packages/mouse-ext/docs/ARCHITECTURE.md](../packages/mouse-ext/docs/ARCHITECTURE.md)
and are only referenced here.

Contents:

1. [The big picture](#1-the-big-picture)
2. [Principles applied across the workspace](#2-principles-applied-across-the-workspace)
3. [Packaging: `pyproject.toml`, line by line](#3-packaging-pyprojecttoml-line-by-line)
4. [The `src/` layout](#4-the-src-layout)
5. [The `mrfactory` namespace package](#5-the-mrfactory-namespace-package)
6. [Inside one package: modules and public API](#6-inside-one-package-modules-and-public-api)
7. [Every command, explained](#7-every-command-explained)
8. [Testing architecture](#8-testing-architecture)
9. [Code style and formatting](#9-code-style-and-formatting)
10. [Git: `.gitignore` and commit messages](#10-git-gitignore-and-commit-messages)
11. [Trade-offs and what's not done (yet)](#11-trade-offs-and-whats-not-done-yet)
12. [Glossary](#12-glossary)
13. [References](#references)

---

## 1. The big picture

```text
Movement/
├── Natural/                  separate project: natural_mouse (human-like mouse mover)
└── Modules/                  this workspace (one git repo)
    ├── README.md, docs/, scripts/
    └── packages/
        ├── mouse-ext/        mrfactory-mouse-ext  ──imports──▶  natural_mouse
        └── adspower/         mrfactory-adspower   (no dependencies)
```

The workspace is a **monorepo**: one git repository holding several
independent packages. Each package:

- has its own `pyproject.toml`, so it can be installed on its own
  (`pip install -e packages/adspower`) and could later be moved to its
  own repo or published without changes;
- has its own tests, README, and version number;
- installs under one shared import prefix, `mrfactory.*`.

> Which named architecture styles this is (and isn't): see
> [ARCHITECTURE_STYLES.md](ARCHITECTURE_STYLES.md).

**Why a monorepo instead of one big package?** A single package would
make `pip install` drag in OpenCV and NumPy just to open AdsPower. Separate
packages let you install only what you need, keep each one small enough
to understand in one sitting, and force the boundaries between them to
be explicit (one package can only use another through its public API).

**Why a monorepo instead of one repo per package?** While everything is
small and changes together, one repo means one clone, one venv, one
`git log`, and one place for shared docs and tooling (`scripts/test_all.py`).
The packages are already shaped so they could be split later.

---

## 2. Principles applied across the workspace

### Single Responsibility / high cohesion

> "A module should have one, and only one, reason to change." (Robert C. Martin)

Applied at every scale:

| Scale | Example | Its one job |
| --- | --- | --- |
| Package | `adspower` | Work with the AdsPower app |
| Module | `launcher.py` | Find and start an executable |
| Module | `api.py` | Talk HTTP to AdsPower's Local API |
| Module | `matching.py` | Decide what counts as a name match (pure functions) |
| Subpackage | `cli/` | Turn command-line arguments into calls and text |
| Function | `adspower_candidates()` | List where AdsPower might be installed |
| Function | `find_adspower()` | Return the first candidate that exists |
| Function | `open_app()` | Start an executable |

Because each function does one thing, each one can be tested on its own,
and `open_app()` can be reused for any other app without changes.

The test from [CONVENTIONS.md §1](CONVENTIONS.md#1-layout), "if you can't
describe it in one sentence without *and*, it's two packages", is a quick
way to check cohesion.

### Low coupling and explicit boundaries

Packages talk to each other only through public imports
(`from mrfactory.mouse_ext import ...`), never through files or private
modules. A package's internals can then be rewritten freely as long as
its public API stays the same. This is **information hiding**: each
package hides its design decisions behind a small interface.

### One-way dependencies (the Acyclic Dependencies Principle)

```text
mouse-ext ──▶ natural_mouse        adspower  (depends on nothing)
```

Dependencies form a graph with no cycles. If A imports B and B imports
A, neither can be installed, tested, or understood alone, so
[CONVENTIONS.md §4](CONVENTIONS.md#4-dependencies-between-packages) says
the shared part moves into a third package instead.

### Reuse by importing, never by copying (DRY)

`mouse-ext` imports `natural_mouse` from the sibling `Natural/` project
rather than copying its code. A copy would drift: bug fixes in `Natural`
would never arrive, and there'd be two versions of the truth.
"Don't Repeat Yourself" applies to whole libraries, not just functions.

### Open/Closed

`mouse-ext` adds features to `natural_mouse` without editing a line of
it. See the [mouse-ext architecture doc](../packages/mouse-ext/docs/ARCHITECTURE.md#openclosed-principle-the-big-one-here).

### Choose the simplest mechanism that works (KISS)

`adspower` launches the `.exe` directly instead of finding and clicking
its icon with `mouse-ext`. Starting a process doesn't depend on screen
layout, window position, or a template image, so it fails far less
often. Before automating the UI, check whether there's a direct way
(a file, a command, an API).

### Convention over configuration

Every package has the same shape (§1 of CONVENTIONS) and its three
names are derived from one short name (§2 of CONVENTIONS). Nobody has
to decide where tests go or what to call the distribution, and tools
can rely on it: `scripts/test_all.py` finds packages just by looking for
a `tests/` folder.

### Fail loudly and helpfully

`open_adspower()` raises `FileNotFoundError` listing every place it
looked, and suggests `--path`. `main()` turns that into a message and
exit code `1`. Errors are never swallowed silently. The same reasoning
explains why `mouse-ext` plugins veto an action by raising an exception
rather than returning `False`.

---

## 3. Packaging: `pyproject.toml`, line by line

### What it is and why we use it

`pyproject.toml` is the **standard config file for a Python project**.
It tells any tool (pip, build, uv, an IDE) three things:

1. **How to build** the package ([PEP 517](https://peps.python.org/pep-0517/)/[518](https://peps.python.org/pep-0518/)): which build tool to use.
2. **What the package is** ([PEP 621](https://peps.python.org/pep-0621/)): name, version, Python version, dependencies, commands.
3. **Tool settings** (`[tool.*]` tables): here, where setuptools should find the code.

Before it existed, projects used `setup.py`, an ordinary Python script
that pip had to *run* to learn anything about the package. That was
hard to read reliably and could do anything when executed. `pyproject.toml`
is plain data, which makes it easy to read, safe to parse, and the same
for every build tool. It replaces `setup.py`, `setup.cfg`, and
`requirements.txt` for describing a library.

Without a `pyproject.toml`, the folder is just loose `.py` files: `pip`
can't install it, there's no console command, and there's no way for
other code to `import mrfactory.adspower` except by editing `sys.path`.

### Section by section (from `packages/mouse-ext/pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

pip doesn't build packages itself. It creates a temporary isolated
environment, installs whatever `requires` lists into it, and calls the
**build backend** named here. We use setuptools because it's the most
widely used backend and supports namespace packages and editable
installs well. Version 68+ handles everything in this file, including
modern editable installs.

```toml
[project]
name = "mrfactory-mouse-ext"
version = "0.1.0"
description = "Plugins and extensions for natural_mouse."
requires-python = ">=3.10"
```

- `name` is the **distribution name**, what `pip install` / `pip uninstall`
  and `pip list` use. It's separate from the import name
  (`mrfactory.mouse_ext`); see [CONVENTIONS.md §2](CONVENTIONS.md#2-naming).
- `version` follows [Semantic Versioning](https://semver.org/):
  `MAJOR.MINOR.PATCH`. `0.x` signals "still changing, no stability promise yet".
- `requires-python` stops pip from installing on a Python that's too old.
  3.10 is the minimum because `PluginManager` calls
  `importlib.metadata.entry_points(group=...)`, which was added in 3.10.

```toml
dependencies = [
    "opencv-python>=4.9",
    "numpy>=1.26",
]
```

Third-party packages pip installs automatically. They're **lower
bounds** (`>=`), not exact pins (`==`). A library should accept any
compatible version so it can coexist with other libraries in one
environment. Exact pins belong in an *application's* lock file, not in
a library's metadata.

`natural_mouse` is deliberately *not* listed (see the comment in the
file). It isn't on PyPI, so pip would search PyPI for that name and
could install a stranger's package. This attack is called
**dependency confusion**, and it's why it's installed manually from
`../Natural`.

```toml
[project.scripts]                                   # adspower only
adspower = "mrfactory.adspower.cli:main"
```

A **console script**. On install, pip generates a small
`adspower.exe` in `venv\Scripts\` that imports
`mrfactory.adspower.cli` and calls `main()`. Its return value
becomes the process exit code. That's why `main()` returns an `int`
instead of calling `sys.exit` itself, which also makes it easy to test
(`self.assertEqual(cli.main(["profiles", "-g", "nope"]), 1)`).

```toml
[project.entry-points."mrfactory.mouse_ext.plugins"]   # mouse-ext only
logging = "mrfactory.mouse_ext.plugins:LoggingPlugin"
```

An **entry point** is a named pointer to an object, written into the
installed package's metadata. Any program can later ask, "which
installed packages registered something under this group?"
(`importlib.metadata.entry_points(group=...)`). Console scripts are
themselves entry points (group `console_scripts`). This is how
`PluginManager.load_entry_points()` finds plugins from packages it has
never heard of.

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["mrfactory.mouse_ext*"]
namespaces = true
```

Tells setuptools where the code is (`src/`, see §4), to ship *only* this
package's subpackage, and that `mrfactory` is a namespace package with no
`__init__.py` (see §5).

---

## 4. The `src/` layout

```text
packages/adspower/
├── pyproject.toml
├── src/mrfactory/adspower/   ← the importable code lives one level down
└── tests/
```

The alternative "flat" layout puts `mrfactory/` directly next to
`pyproject.toml`. We use `src/` because:

- **It prevents accidental imports.** In a flat layout, running Python
  from the package folder imports the code straight from the folder,
  even if the package isn't installed or is installed wrong. Tests pass
  on your machine and fail for everyone else. With `src/`, the code is
  only importable if it's installed (or if a test explicitly adds `src/`
  to the path, see §8).
- **It separates shipped code from everything else.** Only what's under
  `src/` ends up in the package. Tests, docs, examples, and scripts
  can't leak into it.
- It's the layout the [Python Packaging Guide recommends](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).

---

## 5. The `mrfactory` namespace package

> The full story of modules, packages, `import`, and versions, with
> exercises, is in [MODULES_AND_PACKAGES.md](MODULES_AND_PACKAGES.md).

Every package's code is under `src/mrfactory/<module>/`, and **none** of
them has a `src/mrfactory/__init__.py`.

A folder **with** `__init__.py` is a *regular package*: Python treats
the first one it finds as the whole package and stops looking. A folder
**without** one is a *namespace package* ([PEP 420](https://peps.python.org/pep-0420/)):
Python collects every `mrfactory/` folder it finds on `sys.path` and
merges them. So two separately installed distributions can each
contribute one piece:

```text
site-packages (or editable paths)
  packages/mouse-ext/src/mrfactory/mouse_ext/   ┐
  packages/adspower/src/mrfactory/adspower/     ┘──▶  import mrfactory.mouse_ext
                                                      import mrfactory.adspower
```

**Why bother?**

- **One recognisable prefix.** You can tell at a glance that
  `mrfactory.adspower` is our code and `natural_mouse` or `cv2` is not.
- **No name collisions.** A future `mrfactory.logging` can never clash
  with the standard library's `logging`.
- **Independent installs.** Each package still installs, uninstalls, and
  versions on its own. This is the same approach large projects such as
  the Google Cloud and Azure SDKs use (`google.cloud.storage`,
  `azure.storage.blob`, ...).

---

## 6. Inside one package: modules and public API

```text
src/mrfactory/adspower/
  __init__.py    public API: re-exports what users may import
  __main__.py    makes `python -m mrfactory.adspower` work
  client.py      AdsPower: the class most code uses
  api.py         LocalApi: HTTP to AdsPower's Local API
  models.py      Group, Tag, Profile, Proxy: typed data
  matching.py    name/text matching rules
  errors.py      the package's exceptions
  launcher.py    find and start the app
  cli/           the `adspower` command (app, commands, prompts, output)
```

How these layers fit together, and the concepts behind each one, is in
[packages/adspower/docs/ARCHITECTURE.md](../packages/adspower/docs/ARCHITECTURE.md).

### `__init__.py` as the public face (the Facade idea)

```python
from .client import AdsPower
from .models import Group, Profile
...
__all__ = ["AdsPower", "LocalApi", "Group", "Profile", ...]
```

Users write `from mrfactory.adspower import AdsPower` and never
need to know the file is called `client.py`. The internal files can
then be split, merged, or renamed without breaking anyone. `__all__`
lists the public names explicitly: it controls `from x import *`, and
it documents what the package promises to keep stable. Anything not
listed (or starting with `_`) is internal.

`mouse-ext/__init__.py` does the same on a larger scale, re-exporting
classes from `automator.py`, `errors.py`, `plugins/`, and `extensions/`
into one flat namespace.

### `__main__.py`

When you run `python -m some.package`, Python executes
`some/package/__main__.py`. Ours is three lines that call `cli.main()`
and pass its return value to `sys.exit`. The real logic stays in
importable modules, where it can be tested. This is the same code path
as the `adspower` console script.

### Relative imports inside a package

Inside a package, modules import each other with a leading dot
(`from .cli import main`). That keeps the package working even if
it were renamed or moved, and makes it obvious at a glance which
imports are internal.

### Separate pure logic from side effects

`launcher.py` is ordered from "pure" to "does something to the world":

1. `adspower_candidates()`: only reads environment variables, returns paths.
2. `find_adspower()`: only checks whether files exist.
3. `open_app()`: actually starts a process (`os.startfile`).

The pure parts are trivial to test. The side effect is isolated in one
call that tests can mock. This is the same idea behind "functional core,
imperative shell" and, in `mouse-ext`, behind injecting the
`InputExecutor` so that the only code touching the real mouse is one
replaceable object.

### The CLI is a thin adapter

The `cli/` package contains no business logic. It parses arguments with
`argparse`, calls a method on `AdsPower`, and translates the result into
output and an exit code (`0` = success, `1` = failure, the Unix
convention every shell and CI system understands). The library function
raises an exception; the CLI decides how to show it to a human. Keeping
these apart means the same function serves the CLI, other Python code,
and tests.

### When a module becomes a package

`adspower`'s CLI started as one file, `cli.py`. By v0.2 it was ~350
lines doing four jobs (parsing, running commands, asking questions,
formatting output), so in v0.3 it became a **subpackage**, `cli/`, with
one module per job. Two details made that refactor invisible to users:

- `cli/__init__.py` re-exports `main` (`from .app import main`), so the
  import path `mrfactory.adspower.cli:main`, used by `pyproject.toml`
  and `__main__.py`, didn't change. A package's `__init__.py` can keep
  its old public names stable while everything behind them moves.
- The 100+ tests passed before and after. **Tests are what make
  refactoring safe**: you change the structure, and they prove the
  behaviour didn't change.

A rough guide for when to split: a file that has several unrelated
reasons to change, or that you can't describe without "and", wants to
become a package.

---

## 7. Every command, explained

### Setting up

```powershell
python -m venv venv
```

Creates a **virtual environment** in the folder `venv/`: a private copy
of the Python interpreter plus its own empty `site-packages` folder.
Packages installed into it don't affect your system Python or other
projects, and other projects' packages don't affect this one. Different
projects often need different versions of the same library; venvs let
them coexist. `python -m venv` (instead of a separate `venv` command)
runs the `venv` module of whichever `python` you invoked, so you know
exactly which interpreter the environment is based on.

```powershell
venv\Scripts\activate
```

**Activates** the venv for the current terminal: it puts
`venv\Scripts\` first on `PATH`, so `python` and `pip` now mean the
venv's copies, and console scripts like `adspower` become
available. Your prompt shows `(venv)`. `deactivate` undoes it. (On
macOS/Linux it's `source venv/bin/activate`.) If PowerShell refuses to
run the script, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

```powershell
pip install -e packages/adspower
```

Installs the package in **editable** (development) mode:

- **What pip does:** reads `pyproject.toml`, builds the package with the
  backend from `[build-system]`, installs any `dependencies`, generates
  console scripts (`adspower.exe`), and writes the package
  metadata (including entry points).
- **What `-e` changes:** instead of *copying* the code into
  `site-packages`, pip adds a small pointer there (a `.pth` file or
  import hook) that points back at `packages/adspower/src/`. Python then
  imports the code straight from your working folder.
- **Why that matters:** edit `launcher.py`, run it again, and the change
  is live. No reinstall needed. Without `-e` you'd get a frozen snapshot
  and would need to reinstall after every edit.
- **When to re-run it anyway:** after changing `pyproject.toml` itself
  (new dependency, new console script, new entry point, version bump).
  That metadata is only written at install time.

> **A real example from this workspace.** `adspower` v0.1 replaced the
> `open-adspower` command with `adspower`, a change to
> `[project.scripts]` in `pyproject.toml`. The *code* was live
> immediately (`python -m mrfactory.adspower` worked), but typing
> `adspower` didn't: `venv\Scripts\adspower.exe` is a small launcher
> that pip generates **during install**, and no install had happened
> since. Running `pip install -e packages/adspower` again:
>
> 1. read the new `pyproject.toml`,
> 2. generated `venv\Scripts\adspower.exe` (pointing at `mrfactory.adspower.cli:main`),
> 3. rewrote the package metadata (version, description, entry points),
> 4. kept pointing at `packages/adspower/src`, so later code edits are
>    live again with no reinstall.
>
> Rule of thumb: **edited a `.py` file → nothing to do; edited
> `pyproject.toml` → re-run `pip install -e`.**

```powershell
pip install -e ../Natural
```

Same thing for the sibling `Natural` project, so `import natural_mouse`
works and always reflects the current `Natural` source. This is how
`mouse-ext` reuses it without copying it.

Useful related commands:

| Command | What it does |
| --- | --- |
| `pip list` | Show installed distributions (editable ones show their source folder) |
| `pip show mrfactory-adspower` | Version, location, dependencies of one package |
| `pip uninstall mrfactory-adspower` | Remove it (uses the distribution name, not the import name) |
| `python -c "import mrfactory.adspower as m; print(m.__file__)"` | Check which file actually gets imported |

### Running

| Command | What happens |
| --- | --- |
| `adspower --help` | The console script from `[project.scripts]` calls `cli.main()`; argparse prints the generated help |
| `adspower profiles -g Shopify` | argparse picks the `profiles` subcommand and calls `AdsPower.profiles(group="Shopify")` |
| `python -m mrfactory.adspower ...` | Python finds the package on `sys.path` and runs its `__main__.py` (works even if the script isn't on `PATH`) |
| `python examples/click_with_plugins.py templates/target.png --dry-run` | Runs the mouse-ext example script directly as a file |

**Why `python -m` rather than `python path/to/file.py`?** `-m` runs a
module by its *import* name, with the package set up properly, so
relative imports (`from .cli import main`) work. Running a file
inside a package by path breaks them. The same reasoning applies to
`python -m pip` and `python -m unittest`: `-m` guarantees you're using
the tool belonging to *this* Python, not some other one on `PATH`.

### Testing

```powershell
python -m unittest discover -s tests -t .
```

- `unittest`: Python's built-in test framework (no install needed).
- `discover`: find tests automatically instead of listing them:
  every `test*.py` file, every `TestCase` subclass, every `test_*` method.
- `-s tests`: **s**tart looking in the `tests/` folder.
- `-t .`: the **t**op-level directory is the package folder, so tests
  are imported as `tests.test_launcher`. That makes `tests` a real
  package, so `tests/__init__.py` runs first (it sets up `sys.path`,
  see §8) and tests can share helpers (`from tests.fakes import ...`).

```powershell
python scripts/test_all.py [package ...]
```

Runs the command above once per package, each in a **separate process**
with its own folder as the working directory. Every package has a
top-level package called `tests`, and Python caches imports by name.
In a single process, the second package's `tests` would be confused
with the first. Separate processes also prove each package's tests pass
on their own. The script prints a summary and exits with `1` if anything
failed, so it can be used in CI unchanged.

---

## 8. Testing architecture

### Tests run without installing

Each `tests/__init__.py` inserts the package's `src/` folder at the
front of `sys.path`. So `python -m unittest discover ...` works on a
fresh clone, before `pip install -e`, and always tests the source in
front of you rather than some other installed copy. `mouse-ext`'s
version also falls back to `../Natural/src` if `natural_mouse` isn't
installed.

### Never touch the real world

Tests must not move the mouse, read the real screen, or launch real
programs. They'd be slow, flaky, dependent on the machine, and could do
something unwanted. Instead, we replace the **boundary** (the one place
that touches the outside world) with a stand-in:

| Technique | Where | Example |
| --- | --- | --- |
| **Fake**: a small working implementation of an interface | `mouse-ext/tests/fakes.py` | `FakeScreenLocator`, `PathWalkingExecutor` |
| **Fake API**: duck-types `LocalApi` with canned data | `adspower/tests/fakes.py` | `FakeApi`, `FakeOpener` (replaces `urlopen`) |
| **Mock**: a stand-in that records how it was called | `adspower/tests/test_launcher.py` | `mock.patch("...launcher.os.startfile", create=True)` then `assert_called_once_with(exe)` |
| **Temporary filesystem** | `adspower` tests | `tempfile.TemporaryDirectory()` builds a fake `Program Files` tree |
| **Patched environment** | `adspower` tests | `mock.patch.dict(os.environ, {...})` points `ProgramFiles` at the temp folder |

Details worth knowing:

- **Patch where it's used, not where it's defined.** The mock targets
  `mrfactory.adspower.launcher.os.startfile`, the name the code under
  test actually looks up.
- **`create=True`**: `os.startfile` exists only on Windows. This lets
  the mock be created on any OS, so the tests also run on macOS/Linux CI.
- **`addCleanup`** undoes every patch and deletes the temp folder even
  if a test fails, so one test can never leak state into the next.
- **Test behaviour, not implementation**: test names describe outcomes
  (`test_explicit_path_wins`, `test_missing_raises_and_does_not_launch`),
  so they still make sense after a refactor.

Fakes and mocks only work cleanly because the code was designed for
them. Side effects are isolated (§6), and in `mouse-ext` the screen and
mouse are injected objects. **Testability is a design property**, not
something added afterwards.

### Arrange, Act, Assert

Each test sets up a situation (create a fake install), does one thing
(`open_adspower()`), and checks the result (returned path, mock calls).
Keeping these three steps visible keeps tests short and readable.

---

## 9. Code style and formatting

The style follows [PEP 8](https://peps.python.org/pep-0008/), Python's
official style guide, so the code looks like most other Python code and
anyone can read it without adjusting.

| Choice | Why |
| --- | --- |
| `snake_case` functions/modules, `PascalCase` classes, `UPPER_SNAKE_CASE` constants (`ADSPOWER_EXE`) | PEP 8. The case alone tells you what kind of thing a name is |
| Leading `_` for internal names (`_SRC`, `_GuardedPath`, `self._locator`) | Python's convention for "not part of the public API" |
| Docstrings on modules, classes, and non-obvious functions ([PEP 257](https://peps.python.org/pep-0257/)) | Explain *why* and *how to use*, shown by `help()` and IDE tooltips |
| Comments explain *why*, not *what* | The code already says what. Comments are for reasons that aren't visible (e.g. why `natural_mouse` isn't a dependency) |
| Type hints on public functions (`def open_app(path: str \| Path) -> Path`) | Document inputs/outputs, enable IDE autocomplete, and let a checker such as mypy or Pyright catch mistakes |
| `from __future__ import annotations` at the top of modules | Stores type hints as strings instead of evaluating them at import time: allows forward references, and keeps modern syntax cheap |
| `pathlib.Path` instead of string paths | Joins with `/`, handles Windows separators, has `.is_file()`, `.parent`, etc. |
| Imports grouped: standard library, then third-party, then local, alphabetical within each group | PEP 8; makes it easy to see what a module depends on |
| Small functions with early returns | Each is readable without scrolling and testable on its own |
| `argparse` for CLIs | Standard library; free `--help`, error messages, and validation |

### The linter: Ruff

A **linter** reads code without running it and reports likely mistakes
and style problems. Humans miss these in review; a tool never gets
tired. The workspace uses [Ruff](https://docs.astral.sh/ruff/),
configured once for every package in [`ruff.toml`](../ruff.toml) at the
root:

```powershell
pip install ruff          # once, into the venv
ruff check .              # report problems
ruff check . --fix        # fix the ones that are safe to fix automatically
```

The config sets `line-length = 120` (PEP 8 suggests 79, but that's
cramped with descriptive names; many projects use 88–120) and
`target-version = "py310"` to match `requires-python`. The rule sets
turned on, and what each one caught the first time it ran on this code:

| Rule set | Checks | Caught here |
| --- | --- | --- |
| `E`, `W` (pycodestyle) | PEP 8 layout | 3 lines over 120 characters; an ambiguous variable name `l` (looks like `1`) → renamed `left` |
| `F` (pyflakes) | unused imports/variables, undefined names | nothing (good) |
| `I` (isort) | import order: stdlib, third-party, first-party | 6 unsorted import blocks (auto-fixed) |
| `B` (bugbear) | patterns that are usually bugs | `zip()` without `strict=` (silently drops data if lengths differ); a function call as a default argument |
| `UP` (pyupgrade) | modern syntax for Python 3.10 | `typing.Callable` → `collections.abc.Callable` (the `typing` aliases are deprecated) |
| `SIM` (simplify) | simpler equivalents | nested `with` blocks → one `with a, b:` |

**Fix the cause, or explain the exception.** Every finding was either
fixed or, when the rule didn't apply, the code was changed to make the
intent explicit (the "call in a default" was an immutable `Point`, now a
named constant `SCREEN_CENTER`). A blanket `# noqa` would hide the next
real problem on that line. The one rule switched off (`SIM108`, "use a
ternary") is listed with its reason in `ruff.toml`.

Run `ruff check .` before every commit, together with
`python scripts/test_all.py`. Not adopted yet: `ruff format` (an
automatic formatter; adopting it means one large reformatting commit)
and a type checker (mypy or Pyright, which would check the type hints).

---

## 10. Git: `.gitignore` and commit messages

`.gitignore` keeps out anything that is **generated or machine-specific**:

| Pattern | What it is | Why it's ignored |
| --- | --- | --- |
| `venv/`, `.venv/` | The virtual environment | Huge, OS-specific, recreated with one command |
| `__pycache__/`, `*.pyc` | Compiled bytecode Python caches | Regenerated automatically |
| `*.egg-info/`, `build/`, `dist/` | Build and install artifacts | Produced by pip/setuptools |
| `misses/`, `*.paths.json`, `templates/*` | Screenshots, recorded paths, user templates | Personal runtime data, not source |

The rule: commit what a person wrote; ignore what a tool can regenerate.

Commit message rules are in [CONVENTIONS.md §7](CONVENTIONS.md#7-commit-messages).
The reasoning: the history is documentation. An imperative summary
("Add X") reads like a changelog entry. A package prefix
("adspower: ...") makes `git log` filterable per package in a monorepo.
A body that explains *why* preserves the reasoning the diff can't show.
One logical change per commit makes changes easy to review, revert, and
bisect.

---

## 11. Trade-offs and what's not done (yet)

Every design has costs. These ones are known:

- **Manual installs of sibling projects.** Because `natural_mouse` and
  `mrfactory-*` packages aren't published, they can't be listed as
  dependencies and must be installed by hand in the right order. A fix
  would be a private package index, or a workspace tool such as
  [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/).
- **No lock file.** Dependency versions aren't pinned, so two machines
  might install different OpenCV versions. Fine for development; an
  application deployed somewhere would want a lock file.
- **`unittest` instead of pytest.** Chosen because it's built in and
  needs no install. pytest has less boilerplate and better failure
  output; switching would be easy since pytest runs `unittest` tests as-is.
- **Linting, but no auto-formatting or type checking yet.** Ruff checks
  every package (§9). `ruff format` and mypy/Pyright would be the next steps.
- **No CI.** `scripts/test_all.py` and `ruff check .` already return
  proper exit codes, so a GitHub Actions workflow could run both on every
  push. That's the next step to stop relying on remembering to run them.
- **`sys.path` edits in `tests/__init__.py`.** Convenient (no install
  needed), but slightly magical. The cleaner alternative is "always
  `pip install -e` first, then test".

---

## 12. Glossary

| Term | Meaning |
| --- | --- |
| **Module** | One `.py` file |
| **Package (import package)** | A folder of modules you can `import` |
| **Distribution** | What pip installs: built from a `pyproject.toml`, has a name and version (`mrfactory-adspower`) |
| **Namespace package** | A package folder with no `__init__.py` whose contents can come from several distributions |
| **Build backend** | The tool pip calls to turn source into an installable package (setuptools here) |
| **Editable install** | An install that points at your source folder instead of copying it (`pip install -e`) |
| **Virtual environment** | An isolated Python with its own installed packages |
| **Entry point** | A named pointer to a Python object, published in package metadata, discoverable at runtime |
| **Console script** | An entry point pip turns into a command-line program |
| **Public API** | The names a package promises to keep stable (`__all__` in `__init__.py`) |
| **Fake / mock** | Test stand-ins for real-world boundaries: a fake works, a mock records calls |
| **Composition root** | The one place that picks concrete classes and wires them together (`examples/click_with_plugins.py`) |
| **Monorepo** | One repository containing several independently installable packages |

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

### §1–§2 The big picture and principles

- Single-responsibility principle: <https://en.wikipedia.org/wiki/Single-responsibility_principle>
- Separation of concerns: <https://en.wikipedia.org/wiki/Separation_of_concerns>
- Information hiding (Parnas): <https://en.wikipedia.org/wiki/Information_hiding>
- Acyclic dependencies principle: <https://en.wikipedia.org/wiki/Acyclic_dependencies_principle>
- Don't repeat yourself: <https://en.wikipedia.org/wiki/Don%27t_repeat_yourself>
- KISS principle: <https://en.wikipedia.org/wiki/KISS_principle>
- Convention over configuration: <https://en.wikipedia.org/wiki/Convention_over_configuration>
- Open–closed principle: <https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle>
- Monorepo: <https://en.wikipedia.org/wiki/Monorepo>
- SOLID overview: <https://en.wikipedia.org/wiki/SOLID>

### §3 Packaging: `pyproject.toml`

- **Official:** PyPA, "Writing your pyproject.toml": <https://packaging.python.org/en/latest/guides/writing-pyproject-toml/>
- **Official:** PyPA, `pyproject.toml` specification: <https://packaging.python.org/en/latest/specifications/pyproject-toml/>
- **Official:** PEP 517 (build backends): <https://peps.python.org/pep-0517/> · PEP 518 (`[build-system]`): <https://peps.python.org/pep-0518/> · PEP 621 (`[project]`): <https://peps.python.org/pep-0621/>
- **Official:** setuptools, configuring via `pyproject.toml`: <https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html>
- **Official:** PyPA, entry points specification: <https://packaging.python.org/en/latest/specifications/entry-points/>
- **Official:** PyPA, version specifiers ✔ (`>=`, `~=`, pre-releases): <https://packaging.python.org/en/latest/specifications/version-specifiers/>
- PyPA, "install_requires vs requirements files" (libraries use ranges, apps pin): <https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/>
- Semantic Versioning: <https://semver.org/>
- Supply chain attacks (background to dependency confusion): <https://en.wikipedia.org/wiki/Supply_chain_attack>
- Alex Birsan, "Dependency Confusion" (2021), the original disclosure: <https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610> (Medium blocks automated link checks; open it in a browser)
- Real Python, "How to Manage Python Projects With pyproject.toml": <https://realpython.com/python-pyproject-toml/>

### §4 The `src/` layout

- **Official:** PyPA, "src layout vs flat layout": <https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/>
- *The Hitchhiker's Guide to Python*, structuring your project: <https://docs.python-guide.org/writing/structure/>

### §5 The `mrfactory` namespace package

- **Official:** PEP 420, implicit namespace packages: <https://peps.python.org/pep-0420/>
- **Official:** Python import reference, namespace packages ✔: <https://docs.python.org/3/reference/import.html#namespace-packages>
- **Official:** PyPA, packaging namespace packages: <https://packaging.python.org/en/latest/guides/packaging-namespace-packages/>
- Real Python, "What's a Python Namespace Package": <https://realpython.com/python-namespace-package/>

### §6 Inside one package

- **Official:** Python tutorial, modules and packages: <https://docs.python.org/3/tutorial/modules.html>
- **Official:** `__main__` (top-level code, `__main__.py`): <https://docs.python.org/3/library/__main__.html>
- **Official:** PEP 328, absolute and relative imports: <https://peps.python.org/pep-0328/>
- Real Python, "Defining Main Functions in Python": <https://realpython.com/python-main-function/>
- For the full story see [MODULES_AND_PACKAGES.md](MODULES_AND_PACKAGES.md#references).

### §7 Every command, explained

- **Official:** `venv`: <https://docs.python.org/3/library/venv.html> · tutorial: <https://docs.python.org/3/tutorial/venv.html>
- **Official:** PyPA, installing packages with pip and virtual environments: <https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/>
- **Official:** setuptools, development mode / editable installs ✔ (reinstall after metadata changes): <https://setuptools.pypa.io/en/latest/userguide/development_mode.html>
- **Official:** pip, local project installs: <https://pip.pypa.io/en/stable/topics/local-project-installs/> · `pip install`: <https://pip.pypa.io/en/stable/cli/pip_install/>
- **Official:** PEP 660, editable installs: <https://peps.python.org/pep-0660/>
- **Official:** command line and `-m`: <https://docs.python.org/3/using/cmdline.html>
- **Official:** `unittest` (incl. `discover`): <https://docs.python.org/3/library/unittest.html> · `subprocess`: <https://docs.python.org/3/library/subprocess.html>
- Real Python, "Python Virtual Environments: A Primer": <https://realpython.com/python-virtual-environments-a-primer/>

### §8 Testing architecture

- **Official:** `unittest.mock`, where to patch: <https://docs.python.org/3/library/unittest.mock.html#where-to-patch>
- Martin Fowler, "TestDouble": <https://martinfowler.com/bliki/TestDouble.html>
- Martin Fowler, "Mocks Aren't Stubs": <https://martinfowler.com/articles/mocksArentStubs.html>
- Ham Vocke, "The Practical Test Pyramid": <https://martinfowler.com/articles/practical-test-pyramid.html>
- Real Python, "Getting Started With Testing in Python": <https://realpython.com/python-testing/> · "Understanding the Python Mock Object Library": <https://realpython.com/python-mock-library/>

### §9 Code style and linting

- **Official:** PEP 8: <https://peps.python.org/pep-0008/> · PEP 257 (docstrings): <https://peps.python.org/pep-0257/> · PEP 563 (`from __future__ import annotations`): <https://peps.python.org/pep-0563/>
- **Official:** Ruff docs: <https://docs.astral.sh/ruff/> · rules: <https://docs.astral.sh/ruff/rules/> · configuration: <https://docs.astral.sh/ruff/configuration/>
- Real Python, "How to Write Beautiful Python Code With PEP 8": <https://realpython.com/python-pep8/> · "Ruff: A Modern Python Linter": <https://realpython.com/ruff-python/>

### §10 Git

- **Official:** `gitignore`: <https://git-scm.com/docs/gitignore> · `git commit`: <https://git-scm.com/docs/git-commit>
- Chris Beams, "How to Write a Git Commit Message": <https://cbea.ms/git-commit/>
- Keep a Changelog: <https://keepachangelog.com/en/1.1.0/>

### §11 Trade-offs

- **Official:** pip, repeatable installs (lock files): <https://pip.pypa.io/en/stable/topics/repeatable-installs/> · `pip freeze`: <https://pip.pypa.io/en/stable/cli/pip_freeze/>
- **Official:** GitHub secret scanning: <https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning>
- Robert C. Martin, *Clean Architecture* (book): SRP, acyclic dependencies, component cohesion
