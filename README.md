# mr-factory workspace

A workspace of small, focused Python packages. Each package does one job,
lives in its own folder under `packages/`, and installs into the shared
`mrfactory` import namespace.

## Packages

| Package | Import | What it does |
| --- | --- | --- |
| [`packages/adspower`](packages/adspower/) | `mrfactory.adspower` | Opens AdsPower; finds groups, tags, profiles, and proxies; opens, creates, and re-proxies profiles (`adspower --help`) |
| [`packages/gitship`](packages/gitship/) | `mrfactory.gitship` | Checks, scans, commits, pushes, publishes (private by default) and releases a git repo safely (`gitship --help`) |

### Linked library: natural-mouse

The human-like mouse library (curves, easing, jitter, Fitts's law,
extensions and plugins) is developed in its **own repository**,
[natural-mouse](https://github.com/jericho3110/natural-mouse), in the `Natural/` folder next to this one. It
used to be split: `natural_mouse` there and `packages/mouse-ext` here;
since 2026-10-09 it's all one library (`from natural_mouse import ...`).
The workspace links to it rather than keeping a copy: install it with
`pip install -e ../Natural`.

**New here and want to learn from it?** Start with
[docs/LEARNING_PATH.md](docs/LEARNING_PATH.md).

## Setup

One virtual environment for the whole workspace, created at the
workspace root:

```powershell
python -m venv venv
venv\Scripts\activate

pip install -e packages/adspower

# optional: the linked mouse library, developed in ../Natural (its own repo)
pip install -e ../Natural

pip install ruff        # the linter (development only)
```

`-e` (editable) installs point at the live source, so edits take effect
without reinstalling. Re-run `pip install -e` only after a package's
`pyproject.toml` changes (new command, dependency, or version). Install
only the packages you need.

## Before every commit

The same checks also run automatically on GitHub for every push
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

```powershell
ruff check .                            # lint every package (config: ruff.toml)
python scripts/test_all.py              # test every package
python scripts/test_all.py adspower     # ...or just one
```

## Documentation

| Doc | What's in it |
| --- | --- |
| [docs/LEARNING_PATH.md](docs/LEARNING_PATH.md) | **start here to learn**: a reading order through the code and docs, with exercises |
| [docs/ARCHITECTURE_STYLES.md](docs/ARCHITECTURE_STYLES.md) | which architecture styles this code uses (Layered, plugin) vs others (Hexagonal, Clean, by-feature, modular monolith), and when to switch |
| [docs/LIBRARIES_AND_BUILTINS.md](docs/LIBRARIES_AND_BUILTINS.md) | every standard-library module, built-in, dunder method, decorator, and external library used: where, and why |
| [docs/MODULES_AND_PACKAGES.md](docs/MODULES_AND_PACKAGES.md) | modules vs packages, how `import` works, distributions, versions, dependencies |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the *why* of the workspace: principles, `pyproject.toml`, `src/` layout, every command, testing, linting |
| [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md) | commit, push, publish a repo, make a release: every step, why, and the commands (automated by `gitship`) |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | the rules: layout, naming, namespace package, dependencies, commits |
| `packages/<name>/README.md` | how to use each package |
| `packages/<name>/docs/ARCHITECTURE.md` | how each package is designed, and why |
| `packages/<name>/CHANGELOG.md` | what changed in each version |

## Layout

```text
README.md              this file
SECURITY.md            how to report vulnerabilities; how secrets are handled
LICENSE                MIT
.github/               CI workflow (lint + tests) and Dependabot config
ruff.toml              linter settings for the whole workspace
docs/
  LEARNING_PATH.md     guided route through the workspace
  ARCHITECTURE.md      why the workspace is built this way
  MODULES_AND_PACKAGES.md  modules, packages, imports, distributions, versions
  ARCHITECTURE_STYLES.md   Layered, Hexagonal, by-feature, modular monolith... and ours
  LIBRARIES_AND_BUILTINS.md  stdlib, built-ins, dunders, decorators, external libraries
  CONVENTIONS.md       layout, naming, dependency, and commit rules
scripts/test_all.py    runs each package's tests in its own process
packages/
  adspower/            mrfactory-adspower
```

## Security

See [SECURITY.md](SECURITY.md): how to report a problem privately, and
how the code handles API keys, URLs, and plugins.

## License

[MIT](LICENSE): free to use, copy, and modify, with attribution and no
warranty. See <https://choosealicense.com/licenses/mit/>.
