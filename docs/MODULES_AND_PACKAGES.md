# Modules, packages, and versions

Everything about how Python code is split into files, found by
`import`, bundled into something `pip` can install, and versioned.
Every idea is shown on this workspace, with real output from it, so you
can open the files and try each one.

Contents:

1. [The vocabulary](#1-the-vocabulary)
2. [Modules](#2-modules)
3. [Packages](#3-packages)
4. [How `import` finds and runs code](#4-how-import-finds-and-runs-code)
5. [Imports in practice: styles, public API, and pitfalls](#5-imports-in-practice-styles-public-api-and-pitfalls)
6. [Distribution packages: what `pip` installs](#6-distribution-packages-what-pip-installs)
7. [Versions](#7-versions)
8. [Dependencies and their versions](#8-dependencies-and-their-versions)
9. [Organizing code: when to split](#9-organizing-code-when-to-split)
10. [Cheat sheet](#10-cheat-sheet)
11. [Exercises](#11-exercises)
12. [References](#references)

---

## 1. The vocabulary

The word "package" means two different things in Python. Most
confusion comes from that.

| Term | What it is | Example here |
| --- | --- | --- |
| **Module** | One `.py` file. The smallest unit you can `import` | `client.py` → `mrfactory.adspower.client` |
| **Package** (import package) | A **folder** of modules you can `import`; it can contain more packages | `adspower/` → `mrfactory.adspower` |
| **Subpackage** | A package inside a package | `cli/` → `mrfactory.adspower.cli` |
| **Regular package** | A package folder **with** an `__init__.py` | `mrfactory.adspower`, `mrfactory.adspower.cli` |
| **Namespace package** | A package folder **without** `__init__.py`, which can be spread over several places | `mrfactory` |
| **Distribution package** (a "distribution") | What `pip install` installs: code + metadata (name, version, dependencies), built from a `pyproject.toml` | `mrfactory-adspower` |
| **Project** | The folder with the `pyproject.toml` you build a distribution from | `packages/adspower/` |
| **Library** | Code meant to be imported by other code | `mrfactory.adspower` (the `AdsPower` class) |
| **Application / tool** | Code meant to be run | the `adspower` command |
| **Script** | A single `.py` file you run directly | `scripts/test_all.py` |

So, strictly: **`adspower` is a package** (a folder of modules with an
`__init__.py`), part of the **namespace package** `mrfactory`, shipped
as the **distribution** `mrfactory-adspower`, built from the **project**
`packages/adspower/`. It is both a **library** and, through its `cli/`
subpackage, an **application**.

Inside Python you can tell a module from a package by one attribute:

```python
>>> import mrfactory.adspower.client, mrfactory.adspower.cli
>>> hasattr(mrfactory.adspower.client, "__path__")   # a module
False
>>> hasattr(mrfactory.adspower.cli, "__path__")      # a package: it has a folder to search
True
```

---

## 2. Modules

A module is a `.py` file. Importing it **runs the file once, top to
bottom**, and whatever names exist at the end (functions, classes,
constants, imported names) become the module's attributes.

```python
# matching.py (simplified)
def contains(text, part): ...        # defines matching.contains

# elsewhere
from mrfactory.adspower import matching
matching.contains("Jericho", "jer")  # True
```

What every module knows about itself. These double-underscore names
are called **"dunder"** names: Python sets or reads them itself, and
they are spelled with two underscores on each side so they never clash
with your own names.

| Attribute | Value (real, from this workspace) | Use |
| --- | --- | --- |
| `__name__` | its full import name, `"mrfactory.adspower.client"`, or `"__main__"` if run directly | `if __name__ == "__main__":` |
| `__file__` | the path of the `.py` file (`...\adspower\client.py`); for a package, its `__init__.py`; **none** for a namespace package | finding files next to the code |
| `__package__` | the package it belongs to: `"mrfactory.adspower"` for `client.py` | what relative imports (`from .models`) start from |
| `__path__` | **packages only**: the folders to search for its submodules (§3) | how `import package.sub` finds `sub` |
| `__doc__` | the module docstring | `help(module)` |
| `__spec__` | how it was found and loaded (name, origin file, loader, search locations) | debugging imports |
| `__all__` | *you* set it: the public names (§5) | `from x import *`, documenting the API |
| `__version__` | *you* set it, by convention (§7) | `mrfactory.adspower.__version__` |

Related special **files**:

| File | Runs when | Purpose |
| --- | --- | --- |
| `__init__.py` | the package is imported | makes a folder a regular package; its front door (§3) |
| `__main__.py` | `python -m package` | makes a package runnable |
| `__pycache__/*.pyc` | (written automatically) | cached bytecode so the next import starts faster; never edit or commit it |

### Running a module vs importing it

```python
if __name__ == "__main__":
    sys.exit(main())
```

When you run `python scripts/test_all.py`, that file's `__name__` is
`"__main__"`, so the block runs. When another file imports it,
`__name__` is its import name, so the block is skipped. This one line
lets a file be **both** an importable module **and** a runnable script.
`launcher.py` used this before the CLI moved to `cli/`.

### `python -m` runs a module by its import name

```powershell
python -m mrfactory.adspower        # runs mrfactory/adspower/__main__.py
python -m unittest discover ...     # runs the standard library's unittest/__main__.py
python -m pip install ...
```

`-m` finds the module through the normal import system, so it's set up
as part of its package and relative imports (`from .cli import main`)
work. Running the same file by path (`python src/mrfactory/adspower/cli/app.py`)
would fail with *"attempted relative import with no known parent
package"*, because a file run by path is a lone `__main__` module with
no package around it. For a **package**, `-m` runs its `__main__.py`;
ours is three lines that call `cli.main()`.

---

## 3. Packages

### Regular packages and `__init__.py`

A folder becomes a regular package by containing `__init__.py`.
Importing the package **runs `__init__.py`**, and its names become the
package's attributes. That makes `__init__.py` the package's **front
door**:

```python
# mrfactory/adspower/__init__.py (shortened)
from .client import AdsPower
from .models import Group, Profile, Proxy, Tag
__version__ = version("mrfactory-adspower")
__all__ = ["__version__", "AdsPower", "Group", ...]
```

Users write `from mrfactory.adspower import AdsPower` and never need to
know it lives in `client.py`. That's **re-exporting**, and it's what lets
you reorganize files without breaking anyone (§9).

**Cost to know:** everything `__init__.py` imports is loaded the moment
anyone imports the package. Real output from this workspace:

```text
>>> import mrfactory.adspower
loaded: mrfactory, mrfactory.adspower, .api, .client, .errors, .launcher, .matching, .models
```

8 modules for one import. That's fine here (all small, standard library
only). Notice what's **not** loaded: `cli/`. The front door doesn't
import the command-line code, so Python code using the library never
pays for argparse, prompts, or table formatting. `cli/` loads only when
the `adspower` command runs. A package with heavy dependencies (say,
OpenCV) might likewise import them lazily inside functions, so that
importing the package stays fast.

### `__init__.py` in depth

**When it runs.** Once, the first time anything inside the package is
imported, and **parents before children**:

```text
import mrfactory.adspower.cli.app
  1. mrfactory            (namespace package: nothing to run)
  2. mrfactory.adspower   runs adspower/__init__.py
  3. mrfactory.adspower.cli   runs cli/__init__.py
  4. mrfactory.adspower.cli.app   runs app.py
```

So even `from mrfactory.adspower.matching import contains` runs
`adspower/__init__.py` first, and with it everything that file imports.

**Three common styles**, all used in this workspace:

| Style | Example | Good for |
| --- | --- | --- |
| **Empty** (just a docstring, or nothing) | `tests/__init__.py` in mouse-ext is nearly this | packages whose modules are imported directly |
| **Re-exporting front door** | `adspower/__init__.py`, `mouse_ext/__init__.py` | a library with a small public API over many files |
| **Small and specific** | `cli/__init__.py` re-exports only `main` and `build_parser` | a subpackage with one entry point |

**Good things to put in it:** the module docstring (what the package
is for), re-exports of the public API, `__all__`, `__version__`.

**Things to keep out of it:**

- **Real logic.** It's hard to find there, and it runs on every import. Put it in a module.
- **Side effects:** network calls, opening files, printing, changing
  global settings. Importing should be safe and fast.
- **Imports of submodules that import the package back.** That's a
  circular import waiting to happen. In `adspower`, submodules import
  each other (`from .models import ...`), never the package itself
  (`from mrfactory.adspower import ...`).

**Special cases here:**

- `src/mrfactory/` has **no** `__init__.py` on purpose: that's what makes
  it a namespace package (below).
- Each `tests/__init__.py` does one unusual job: it adds `src/` to
  `sys.path`, so tests can import the package without installing it.
  It runs first because `unittest discover -t .` imports `tests` as a
  package before any test module.

### `__path__`: where a package looks for its submodules

Every package has a `__path__`: a **list of folders** where Python looks
when you import something *inside* that package. Plain modules don't
have one. That's exactly how Python tells a package from a module.

Real output from this workspace (with the source folders on the path):

```text
mrfactory.adspower.__path__  = ['...\\packages\\adspower\\src\\mrfactory\\adspower']
mrfactory.adspower.cli.__path__ = ['...\\packages\\adspower\\src\\mrfactory\\adspower\\cli']
mrfactory.adspower.client    has __path__? False      (a module)

mrfactory.__path__ = _NamespacePath([
    '...\\packages\\adspower\\src\\mrfactory',
    '...\\packages\\mouse-ext\\src\\mrfactory',
])
```

Reading that output:

- A **regular package** has one folder in `__path__`: the folder its
  `__init__.py` is in.
- The **namespace package** `mrfactory` has **two** folders, one from
  each distribution. `import mrfactory.adspower` searches both and finds
  `adspower` in the first; `import mrfactory.mouse_ext` finds
  `mouse_ext` in the second. This list *is* the namespace merge.
- Its type is `_NamespacePath`, not `list`, because it's recomputed if
  `sys.path` changes. A newly installed distribution can join the namespace.
- In the venv (editable installs), `mrfactory.__path__` shows
  `'__editable__.mrfactory_adspower-0.3.0.finder.__path_hook__'` instead
  of real folders: the editable-install hook (§6) stands in for them and
  points to the source folders.

**How `import` uses it** (step 3 of §4): for `import a.b.c`, Python
imports `a`, then searches `a.__path__` for `b`, then `a.b.__path__`
for `c`. Only **top-level** names (`a`) are searched on `sys.path`.

| | What it is | Who has it |
| --- | --- | --- |
| `sys.path` | folders to search for **top-level** imports | the whole process |
| `package.__path__` | folders to search for **that package's** submodules | each package |
| `module.__file__` | the one file a module was loaded from | modules and regular packages |

**Using it yourself:** `pkgutil.iter_modules(package.__path__)` lists
what's inside a package without importing it. Real output for adspower:
`['__main__', 'api', 'cli', 'client', 'errors', 'launcher', 'matching', 'models']`.
Plugin systems use this to discover modules in a folder. (This
workspace's plugins use entry points instead; see mouse-ext.)

**Don't modify `__path__`** in normal code. Old code did
(`__path__ = pkgutil.extend_path(__path__, __name__)` in an `__init__.py`)
to fake namespace packages before PEP 420 (Python 3.3). Today, leaving
out `__init__.py` does that properly.

### Subpackages

Packages nest: `mrfactory` → `adspower` → `cli` → `app`. Each level is a
folder; each import name is the folder path with dots:

```text
packages/adspower/src/mrfactory/adspower/cli/app.py
                      └────────── mrfactory.adspower.cli.app ─┘
```

### Namespace packages (PEP 420)

A folder **without** `__init__.py` is a *namespace package*. Python
doesn't stop at the first one it finds; it **merges every folder with
that name** found on the search path. That's how two separately
installed distributions both contribute to `mrfactory`:

```text
packages/mouse-ext/src/mrfactory/mouse_ext/   ┐
packages/adspower/src/mrfactory/adspower/     ┘──▶  import mrfactory.mouse_ext
                                                    import mrfactory.adspower
```

Real output: `mrfactory` has no file, a special loader, and a `__path__`
listing both source folders (see "`__path__`" above):

```text
mrfactory loader:  NamespaceLoader     mrfactory.__file__:  None
```

The rule that makes this work: **no package may add
`src/mrfactory/__init__.py`.** The first one found would turn
`mrfactory` into a regular package and hide all the others.

---

## 4. How `import` finds and runs code

`import mrfactory.adspower.client` does this:

1. **Check the cache.** `sys.modules` is a dict of every module already
   imported. If `"mrfactory.adspower.client"` is in it, Python returns
   that object immediately. **A module's code runs only once per
   process**, however many files import it.
2. **Import the parents first**: `mrfactory`, then `mrfactory.adspower`
   (running its `__init__.py`).
3. **Find** the module: search the parent package's `__path__` (for a
   top-level name, search `sys.path`, the list of folders Python looks in).
4. **Load and run** it: create a module object, put it in `sys.modules`
   (*before* running, which matters for circular imports, §5), then
   execute the file. Compiled bytecode is cached in `__pycache__/*.pyc`
   to make the next start faster.
5. **Bind the name** in the importing module.

`sys.path` normally contains: the folder of the script you ran (or the
current folder for `-m`), the standard library, and `site-packages` of
the active environment (your venv). See it with:

```powershell
python -c "import sys; print(*sys.path, sep='\n')"
```

This explains several things in this workspace:

- **The tests run without installing** because `tests/__init__.py`
  inserts `src/` at the front of `sys.path`.
- **`scripts/test_all.py` runs each package in its own process**
  because every package has a top-level package called `tests`. Once
  `tests` is in `sys.modules`, a second, different `tests` can't be
  imported in the same process.
- **Name your files carefully.** A file called `logging.py` in your
  script's folder is found *before* the standard library's `logging`
  and hides it. The `mrfactory.` prefix protects our packages from this.

---

## 5. Imports in practice: styles, public API, and pitfalls

### Absolute vs relative imports

```python
from mrfactory.adspower.models import Profile   # absolute: full path from the top
from .models import Profile                      # relative: "models, next to me"
from ..client import AdsPower                    # relative: "client, one package up"
```

Inside a package this codebase uses **relative** imports: they keep
working if the package is renamed or moved, and they make internal
imports obvious at a glance. Tests and other packages use **absolute**
imports, because they're outside.

### `import module` vs `from module import name`

```python
from . import prompts          # binds the MODULE; prompts.is_interactive looked up at call time
from .prompts import confirm   # binds the FUNCTION object, copied into this module now
```

The difference matters when something is **replaced later**, as tests
do with `mock.patch`. `cli/commands.py` imports the module (`from . import
prompts`) so a test that patches `prompts.is_interactive` is seen there.
With `from .prompts import is_interactive`, `commands` would keep its
own reference to the original function. This is the "**patch where
it's looked up**" rule.

### The public API: `_private` names and `__all__`

- A leading underscore (`_exact_profile`, `_request`, `_read_all_pages`)
  means "internal: may change without notice". Python doesn't enforce
  it; it's a promise between people.
- `__all__` in `__init__.py` lists the **public** names. It controls
  `from mrfactory.adspower import *`, and it documents what the package
  promises to keep stable across versions. That is exactly what a
  version number makes promises about (§7).

### Pitfalls

| Pitfall | Symptom | Fix |
| --- | --- | --- |
| **Circular import**: `a` imports `b`, `b` imports `a` | `ImportError: cannot import name 'x' from partially initialized module 'a' (most likely due to a circular import)`; Python 3.14 words it as `cannot import name 'x' from 'a' (consider renaming ...)`. Either way, `a` is in `sys.modules` but only half-run | Dependencies point one way (this workspace's rule); move shared code to a third module (like `matching.py`) |
| **Shadowing**: your file has a standard library name | `AttributeError: module 'logging' has no attribute 'getLogger'` | Rename it; use a package prefix |
| **Running a package file by path** | `attempted relative import with no known parent package` | `python -m package.module` |
| **Import-time side effects**: code at module top level that does work | importing is slow, or does something (opens files, makes requests) | Do work in functions; keep top level to definitions and constants |
| **Stale state after editing** | an edited module doesn't change in a running Python | It ran once and is cached in `sys.modules`; restart the process |
| **Two `tests` packages** | the wrong tests run | one process per package (`test_all.py`) |

---

## 6. Distribution packages: what `pip` installs

An import package is just a folder. To *install* it (into any
environment, on any machine) it's bundled into a **distribution** with
metadata. `pyproject.toml` describes that distribution; see
[ARCHITECTURE.md §3](ARCHITECTURE.md#3-packaging-pyprojecttoml-line-by-line)
for it line by line.

### Distribution name vs import name

| | Example | Used by |
| --- | --- | --- |
| Distribution name | `mrfactory-adspower` | `pip install/uninstall/show`, `importlib.metadata.version(...)`, PyPI |
| Import name | `mrfactory.adspower` | `import` statements |

They're independent: `pip install opencv-python` gives `import cv2`;
`pip install pillow` gives `import PIL`. This workspace derives both
from one short name so they're predictable
([CONVENTIONS.md §2](CONVENTIONS.md#2-naming)).

### Build formats: sdist and wheel

```powershell
pip install build
python -m build packages/adspower      # creates packages/adspower/dist/
```

| Format | File | What's inside |
| --- | --- | --- |
| **sdist** (source distribution) | `mrfactory_adspower-0.3.0.tar.gz` | the project's source + `pyproject.toml`; must be *built* on install |
| **wheel** | `mrfactory_adspower-0.3.0-py3-none-any.whl` | ready-to-install files (a zip); installing is just unpacking |

The wheel name is a label: `py3` = any Python 3, `none` = no compiled
C ABI needed, `any` = any OS. Packages with compiled code (OpenCV,
NumPy) publish one wheel per OS/Python combination instead. `dist/` and
`build/` are in `.gitignore`: they're generated.

### What an install leaves behind

In the venv's `Lib\site-packages\` (real listing for our editable install):

```text
mrfactory_adspower-0.3.0.dist-info/              the metadata: name, version, dependencies,
                                                 entry points, Requires-Python, file list
__editable__.mrfactory_adspower-0.3.0.pth        run at startup: installs the import hook
__editable___mrfactory_adspower_0_3_0_finder.py  the hook: maps "mrfactory.adspower" → packages/adspower/src
```

and in `venv\Scripts\`: `adspower.exe`, generated from the entry point.

- A **normal** install copies the code into `site-packages`: a snapshot.
- An **editable** install (`-e`) leaves the code where it is, so
  imports read your working files. Edits are live; changes to
  `pyproject.toml` (dependencies, entry points, metadata) need a
  re-install. *How* it points at your files varies: setuptools may use a
  `.pth` file that adds a folder to `sys.path`, a folder of links, or
  (as here) an import-finder hook, and its docs say it "offers no
  guarantee of which technique will be used". So don't write code that
  depends on the mechanism.

### Reading metadata at runtime

```python
from importlib.metadata import version, distribution
version("mrfactory-adspower")                        # '0.3.0'
distribution("mrfactory-adspower").entry_points      # console_scripts: adspower = mrfactory.adspower.cli:main
distribution("mrfactory-adspower").metadata["Requires-Python"]   # '>=3.10'
```

`PluginManager.load_entry_points()` in mouse-ext uses the same metadata
to discover plugins from *other* installed distributions.

### Where distributions come from

`pip install name` downloads from **PyPI** (pypi.org) by default.
`pip install -e path` or `pip install path` installs from a folder.
This workspace's packages aren't published, so they're installed from
folders, and they deliberately don't list each other (or `natural_mouse`)
as dependencies: pip would look for those names on PyPI, where anyone
could have published something malicious under them (**dependency
confusion**).

---

## 7. Versions

### Which "version"?

| Version of... | Where it's set | Where you see it |
| --- | --- | --- |
| **your package** | `version = "0.3.0"` in `pyproject.toml` | `pip show mrfactory-adspower`, `adspower --version`, `mrfactory.adspower.__version__` |
| **Python** your package needs | `requires-python = ">=3.10"` | pip refuses to install on 3.9 |
| **dependencies** your package needs | `dependencies = ["numpy>=1.26"]` | pip picks a matching version (§8) |
| **the Python you're running** | the interpreter | `python --version`, `sys.version_info` |
| **an external tool/API** | not yours | AdsPower's `/api/v1/` vs `/api/v2/` endpoints |

### Semantic Versioning: MAJOR.MINOR.PATCH

[SemVer](https://semver.org/) makes the version number a **promise
about compatibility** of the public API (the names in `__all__`, the
commands and their options):

| Bump | When | Example |
| --- | --- | --- |
| **PATCH** `0.3.0 → 0.3.1` | bug fixes only; nothing users rely on changes | fixing a wrong error message |
| **MINOR** `0.3.1 → 0.4.0` | new features; existing code keeps working | adding `set-proxy` |
| **MAJOR** `0.4.0 → 1.0.0` | something existing changed or was removed | renaming `find_profile`, removing a command option |

**Before 1.0.0, anything may change.** `0.x` says "still taking shape".
By convention, in `0.x` a MINOR bump may also contain breaking changes.
adspower's own history shows that:

| Version | Change | Why that bump |
| --- | --- | --- |
| 0.1.0 | `open-adspower` became `adspower` with subcommands | first real API (breaking, but 0.x) |
| 0.2.0 | tags, open/close/create profiles, safe exit | new features |
| 0.3.0 | `set-proxy`; CLI split into `cli/`; faster lookups | new feature; the refactor kept `adspower` and `mrfactory.adspower.cli:main` unchanged |

Going 1.0.0 is a decision: "the public API is stable now; breaking it
will need 2.0.0".

### Python's version format (PEP 440)

pip understands more than three numbers:

| Version | Meaning |
| --- | --- |
| `0.4.0.dev1` | a development snapshot before 0.4.0 |
| `0.4.0a1`, `0.4.0b1`, `0.4.0rc1` | alpha, beta, release candidate. Pre-releases are excluded from version matching **unless** already installed, explicitly requested (`pip install --pre`, or a specifier naming one), or the only version that matches |
| `0.4.0` | the release |
| `0.4.0.post1` | a re-release with no code change (e.g. fixed metadata) |
| `0+unknown` | a *local* version label; our fallback when the package isn't installed |

Ordering: `0.4.0.dev1 < 0.4.0a1 < 0.4.0rc1 < 0.4.0 < 0.4.0.post1 < 0.4.1`.

### One source of truth for the version

The version is written **once**, in `pyproject.toml`. pip copies it into
the installed metadata, and the package reads it back:

```python
# mrfactory/adspower/__init__.py
try:
    __version__ = version("mrfactory-adspower")
except PackageNotFoundError:     # running from src/ without installing (the tests do)
    __version__ = "0+unknown"
```

`adspower --version` prints it (argparse's `action="version"`). Writing
the number in two places (pyproject *and* a `__version__ = "0.3.0"`
line) works until the day someone updates one and forgets the other.

Remember: since the version is **metadata**, bumping it in
`pyproject.toml` needs `pip install -e packages/adspower` before
`adspower --version` shows the new number.

### The release routine

1. Decide the bump (table above) from what changed for *users*.
2. Update `version` in `pyproject.toml`.
3. Add a `CHANGELOG.md` entry: Added / Changed / Fixed, in user terms
   ([Keep a Changelog](https://keepachangelog.com/)).
4. `ruff check .` and `python scripts/test_all.py`; commit ("adspower: Release 0.4.0" or as part of the feature commit).
5. Optional: tag the commit so the exact code of each version is easy to
   find later: `git tag adspower-v0.4.0` then `git push --tags`. In a
   monorepo the tag includes the package name, because each package has
   its own version.

### Python versions

`requires-python = ">=3.10"` is a promise that the code works on 3.10+,
so the code may only use features that exist in 3.10. Examples used
here: `X | None` in annotations, `zip(..., strict=True)`, and
`importlib.metadata.entry_points(group=...)`. `ruff.toml` sets
`target-version = "py310"` so the linter suggests only syntax 3.10
supports. Check the running version in code with
`sys.version_info >= (3, 10)`.

---

## 8. Dependencies and their versions

`dependencies` in `pyproject.toml` lists what pip must install with
your package, as **version specifiers**:

| Specifier | Means | Good for |
| --- | --- | --- |
| `numpy>=1.26` | 1.26 or newer | **libraries** (what mouse-ext uses): accept anything compatible, so it can coexist with other packages |
| `numpy>=1.26,<3` | at least 1.26, below 3 | excluding a known future breaking MAJOR |
| `numpy~=1.26` | `>=1.26, ==1.*` ("compatible release") | allowing minor updates only |
| `numpy==1.26.4` | exactly this | **applications/lock files**, not library metadata |

**Libraries use ranges; applications pin.** A library that pins
`numpy==1.26.4` can't be installed next to another library that needs
1.26.5. An *application* you deploy wants the opposite: the exact same
versions everywhere, recorded in a **lock file**:

```powershell
pip freeze > requirements.lock.txt         # record every installed version
pip install -r requirements.lock.txt       # reproduce them elsewhere
```

(Tools like `uv` and `pip-tools` manage lock files properly.) This
workspace doesn't lock yet; see
[ARCHITECTURE.md §11](ARCHITECTURE.md#11-trade-offs-and-whats-not-done-yet).

**Optional dependencies ("extras")** group dependencies only some users
need:

```toml
[project.optional-dependencies]
dev = ["ruff"]
```

`pip install -e "packages/adspower[dev]"` would then install Ruff too.
(Here Ruff is installed once for the whole workspace instead, as the
README's setup shows.)

---

## 9. Organizing code: when to split

| Situation | Move |
| --- | --- |
| A function is used by several modules and belongs to none of them | its own module (`matching.py` came from helpers at the bottom of `client.py`) |
| A module has several unrelated reasons to change, or can't be described without "and" | split it into a **subpackage** with one module per job (`cli.py` → `cli/app.py`, `commands.py`, `prompts.py`, `output.py`) |
| A group of modules is useful on its own, with its own dependencies and users | its own **distribution** (`adspower` and `mouse-ext` are separate: installing one doesn't drag in the other's OpenCV) |
| Two modules import each other | move the shared part to a third module; dependencies point one way |

**Refactor without breaking users.** When `cli.py` became `cli/`,
`cli/__init__.py` re-exported `main`, so `mrfactory.adspower.cli:main`
(used by `pyproject.toml` and `__main__.py`) still worked, and the tests
proved behaviour didn't change. A package's `__init__.py` keeps its public
names stable while the files behind it move. That's why the change was
a MINOR bump, not a MAJOR one.

**The layout of one package in this workspace**, labelled:

```text
packages/adspower/                    project (pyproject.toml lives here)
└── src/
    └── mrfactory/                    namespace package (no __init__.py; shared with mouse-ext)
        └── adspower/                 regular package: mrfactory.adspower
            ├── __init__.py           its front door: re-exports, __version__, __all__
            ├── __main__.py           run by `python -m mrfactory.adspower`
            ├── client.py             module: mrfactory.adspower.client
            ├── api.py, models.py, matching.py, errors.py, launcher.py   modules
            └── cli/                  subpackage: mrfactory.adspower.cli
                ├── __init__.py       re-exports main
                └── app.py, commands.py, prompts.py, output.py   modules
```

---

## 10. Cheat sheet

```powershell
python -m package.module                 # run a module by import name (relative imports work)
python -c "import sys; print(sys.path)"  # where Python looks for imports
python -c "import mrfactory.adspower as m; print(m.__file__)"   # which file was imported
pip install -e packages/adspower         # editable install (re-run after pyproject changes)
pip show mrfactory-adspower              # version, location, dependencies
pip list                                 # everything installed in this environment
pip uninstall mrfactory-adspower         # uses the DISTRIBUTION name
python -m build packages/adspower        # build sdist + wheel into dist/
adspower --version                       # the installed version
git tag adspower-v0.3.0                  # mark a release (then: git push --tags)
```

```python
import importlib.metadata as md
md.version("mrfactory-adspower")         # installed version
hasattr(module, "__path__")              # True → package, False → plain module
import sys; sorted(sys.modules)          # everything imported so far
```

---

## 11. Exercises

1. **Module or package?** For each of `mrfactory`, `mrfactory.adspower`,
   `mrfactory.adspower.cli`, `mrfactory.adspower.cli.app`, print
   `hasattr(x, "__path__")` and `getattr(x, "__file__", None)`. Explain
   why `mrfactory` has no `__file__`. Then print `mrfactory.__path__`
   twice: once in the venv, and once with
   `$env:PYTHONPATH="packages/adspower/src;packages/mouse-ext/src;../Natural/src"`
   using your system Python. Why do the two outputs differ?
2. **`__init__.py` order.** Temporarily add `print("adspower init")` to
   `adspower/__init__.py` and `print("cli init")` to `cli/__init__.py`.
   Run `python -c "import mrfactory.adspower.matching"`. Why does
   `adspower init` appear even though you only imported `matching`? Why
   does `cli init` *not* appear? Now run `adspower --version`: which
   prints appear now, and why? Remove the prints afterwards.
3. **Import runs once.** Create `demo.py` with `print("loading demo")`
   at the top. In one Python session, `import demo` twice. How many
   prints, and why? Then look at `sys.modules["demo"]`.
4. **`__name__`.** Add `print(__name__)` to `demo.py`. Run
   `python demo.py`, then `python -c "import demo"`. Compare.
5. **Relative import failure.** Run
   `python packages/adspower/src/mrfactory/adspower/cli/app.py` and
   read the error. Then run `python -m mrfactory.adspower --help` and
   explain the difference.
6. **Circular import.** Make `a.py` with `from b import y; x = 1` and
   `b.py` with `from a import x; y = 2`. Run `python -c "import a"`.
   Read the error, then fix it by moving `x` into `c.py`.
7. **Version bump.** Change adspower's version to `0.3.1.dev1`. Run
   `adspower --version` (unchanged: why?). Re-install with `pip install -e`,
   run it again. Put it back to `0.3.0` and re-install.
8. **Build a wheel.** `pip install build`, `python -m build packages/adspower`.
   Open the `.whl` as a zip (rename to `.zip`): find the `dist-info`
   folder and the `entry_points.txt` inside. Delete `dist/` afterwards.
9. **Design.** Your `hello` package from LEARNING_PATH Stage 1 grows a
   CLI and a web client. Sketch its folder layout as modules and
   subpackages, and say which names `__init__.py` would re-export.

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

### §1 Vocabulary

- **Official:** Python glossary (module, package, namespace package, ...): <https://docs.python.org/3/glossary.html>
- **Official:** PyPA glossary: <https://packaging.python.org/en/latest/glossary/>
- **Official:** PyPA, "Distribution package vs. import package": <https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/>

### §2 Modules

- **Official:** Python tutorial, modules: <https://docs.python.org/3/tutorial/modules.html>
- **Official:** data model, module attributes (`__name__`, `__file__`, `__path__`, `__spec__`, ...): <https://docs.python.org/3/reference/datamodel.html>
- **Official:** `__main__` and `if __name__ == "__main__"`: <https://docs.python.org/3/library/__main__.html>
- **Official:** `python -m`: <https://docs.python.org/3/using/cmdline.html> · PEP 366 (`__package__` for `-m`): <https://peps.python.org/pep-0366/>

### §3 Packages, `__init__.py`, `__path__`, namespace packages

- **Official:** import system reference ✔ (`__path__` makes a module a package; `__init__.py` runs on import; namespace `__path__` re-searches when `sys.path` changes): <https://docs.python.org/3/reference/import.html> · `__path__`: <https://docs.python.org/3/reference/import.html#module-path>
- **Official:** PEP 420, implicit namespace packages: <https://peps.python.org/pep-0420/>
- **Official:** PyPA, packaging namespace packages: <https://packaging.python.org/en/latest/guides/packaging-namespace-packages/>
- **Official:** `pkgutil` (`iter_modules`, legacy `extend_path`): <https://docs.python.org/3/library/pkgutil.html>
- Real Python, "Python Modules and Packages – An Introduction": <https://realpython.com/python-modules-packages/>
- Real Python, "What's a Python Namespace Package": <https://realpython.com/python-namespace-package/>

### §4 How `import` finds and runs code

- **Official:** import system ✔ (a module is put in `sys.modules` *before* its code runs; `a.b.c` imports `a`, then `a.b`): <https://docs.python.org/3/reference/import.html>
- **Official:** `sys.path`: <https://docs.python.org/3/library/sys.html#sys.path> · `importlib`: <https://docs.python.org/3/library/importlib.html> · `site` (`.pth` files): <https://docs.python.org/3/library/site.html>
- **Official:** PEP 451, module specs: <https://peps.python.org/pep-0451/>
- Real Python, "Python import: Advanced Techniques and Tips": <https://realpython.com/python-import/>

### §5 Imports in practice and pitfalls

- **Official:** PEP 328, absolute/relative imports: <https://peps.python.org/pep-0328/> · PEP 8, imports: <https://peps.python.org/pep-0008/#imports>
- **Official:** `typing.TYPE_CHECKING`: <https://docs.python.org/3/library/typing.html#typing.TYPE_CHECKING>
- **Official:** `unittest.mock`, where to patch: <https://docs.python.org/3/library/unittest.mock.html#where-to-patch>
- Real Python, "Python Circular Imports": <https://realpython.com/python-circular-imports/>

### §6 Distribution packages

- **Official:** PyPA, packaging projects tutorial: <https://packaging.python.org/en/latest/tutorials/packaging-projects/>
- **Official:** wheel format: <https://packaging.python.org/en/latest/specifications/binary-distribution-format/> · PEP 427: <https://peps.python.org/pep-0427/>
- **Official:** setuptools development mode ✔ ("offers no guarantee of which technique will be used"): <https://setuptools.pypa.io/en/latest/userguide/development_mode.html> · PEP 660: <https://peps.python.org/pep-0660/>
- **Official:** `importlib.metadata`: <https://docs.python.org/3/library/importlib.metadata.html> · entry points spec: <https://packaging.python.org/en/latest/specifications/entry-points/>
- Real Python, "What Are Python Wheels": <https://realpython.com/python-wheels/> · "How to Publish an Open-Source Python Package to PyPI": <https://realpython.com/pypi-publish-python-package/>
- Supply chain attacks: <https://en.wikipedia.org/wiki/Supply_chain_attack>
- Alex Birsan, "Dependency Confusion" (2021), the original disclosure: <https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610> (Medium blocks automated link checks; open it in a browser)

### §7 Versions

- **Official:** PEP 440: <https://peps.python.org/pep-0440/> · version specifiers ✔ (`.devN < aN < bN < rcN < release < .postN`; local labels like `0+unknown`; pre-release exclusion rules): <https://packaging.python.org/en/latest/specifications/version-specifiers/>
- **Official:** PyPA, versioning discussion: <https://packaging.python.org/en/latest/discussions/versioning/>
- Semantic Versioning 2.0.0: <https://semver.org/>
- Keep a Changelog: <https://keepachangelog.com/en/1.1.0/>
- Git tagging: <https://git-scm.com/book/en/v2/Git-Basics-Tagging>

### §8 Dependencies

- **Official:** version specifiers ✔ (`~= 1.26` ≈ `>= 1.26, == 1.*`): <https://packaging.python.org/en/latest/specifications/version-specifiers/>
- **Official:** `pyproject.toml` spec (`dependencies`, `optional-dependencies`): <https://packaging.python.org/en/latest/specifications/pyproject-toml/>
- **Official:** pip repeatable installs: <https://pip.pypa.io/en/stable/topics/repeatable-installs/> · `pip freeze`: <https://pip.pypa.io/en/stable/cli/pip_freeze/>
- PyPA, install_requires vs requirements files: <https://packaging.python.org/en/latest/discussions/install-requires-vs-requirements/>

### §9 Organizing code

- *The Hitchhiker's Guide to Python*, structure: <https://docs.python-guide.org/writing/structure/>
- Martin Fowler, *Refactoring* (2nd ed.): <https://refactoring.com/>
