# Workspace conventions

> **2026-10-09:** `mouse-ext` (`mrfactory.mouse_ext`) has moved into its own library,
> [natural-mouse](https://github.com/jericho3110/natural-mouse) (`natural_mouse.extensions`, `natural_mouse.plugins`). The
> lessons below still apply; where they name `packages/mouse-ext/...`, the code now
> lives in that repo (`src/natural_mouse/`, `tests/ext_fakes.py`, `docs/EXTENSIONS_AND_PLUGINS.md`).

How this workspace is organized and how everything in it is named.
Follow these when adding or changing a package, so the workspace stays
predictable as it grows. The reasoning behind each rule is in
[ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Layout

```text
<workspace root>/
├── README.md            index of every package + shared setup
├── ruff.toml            linter settings, shared by every package
├── docs/                workspace-wide docs (this file, ARCHITECTURE, LEARNING_PATH)
├── scripts/             workspace tooling (test_all.py)
└── packages/
    └── <name>/          one folder per package, all with the same shape:
        ├── pyproject.toml
        ├── README.md    what it does, setup, usage, layout, tests
        ├── CHANGELOG.md what changed in each version (Keep a Changelog)
        ├── src/mrfactory/<module>/
        ├── tests/
        ├── docs/        optional: ARCHITECTURE.md, LEARNING_RESOURCES.md
        └── examples/    optional
```

One package = one job. If you can't describe a package in one sentence
without "and", it's probably two packages.

## 2. Naming

Each package has three names, all derived from one short name:

| What | Style | Example (`mouse-ext`) | Example (`adspower`) |
| --- | --- | --- | --- |
| Folder under `packages/` | kebab-case | `packages/mouse-ext/` | `packages/adspower/` |
| Distribution (`pip install`, `pyproject` `name`) | `mrfactory-` + folder name | `mrfactory-mouse-ext` | `mrfactory-adspower` |
| Import path | `mrfactory.` + snake_case | `mrfactory.mouse_ext` | `mrfactory.adspower` |

Rules:

- **Name it after what it is, not how it's implemented.** `adspower`,
  not `adspower-launcher`: launching is what it does today, but the
  package is about AdsPower and can grow.
- **Short and lowercase.** Folder hyphens become import underscores
  (Python identifiers can't contain `-`).
- **Avoid names that shadow the standard library or popular packages**
  (`logging`, `requests`, `test`, ...). The `mrfactory.` prefix protects
  imports, but a clear name still matters in folder listings.
- Inside a package: modules are `snake_case.py`, classes `PascalCase`,
  functions/variables `snake_case`, constants `UPPER_SNAKE_CASE`.
- A package's command-line tool is one console script
  (`[project.scripts]`) named after the folder, with verb subcommands:
  `adspower open`, `adspower groups`. Every command and option has
  `help=` text, and the top-level `--help` ends with examples.

## 3. The `mrfactory` namespace package

Every package installs into the same top-level import name, `mrfactory`,
using a PEP 420 *namespace package*:

- There is **no** `src/mrfactory/__init__.py` in any package. That's
  what lets several separately installed distributions each contribute
  one subpackage (`mrfactory.mouse_ext`, `mrfactory.adspower`) to the
  same `mrfactory` namespace.
- Each `pyproject.toml` includes only its own subpackage:

  ```toml
  [tool.setuptools.packages.find]
  where = ["src"]
  include = ["mrfactory.<module>*"]
  namespaces = true
  ```

Adding an `mrfactory/__init__.py` to any one package would make that
package "own" `mrfactory` and hide all the others. Don't.

Background: [PEP 420](https://peps.python.org/pep-0420/) and the
[Packaging Guide on namespace packages](https://packaging.python.org/en/latest/guides/packaging-namespace-packages/).

## 4. Dependencies between packages

- A package may depend on another workspace package, but only through
  its public API (`from mrfactory.mouse_ext import ...`), never by
  reaching into private modules or files.
- Dependencies point one way. If two packages need each other, the
  shared part belongs in a third package.
- Code from outside the workspace (like `natural_mouse` in
  `../Natural`) is installed and imported, never copied in.
- Don't list unpublished packages (`natural_mouse`, `mrfactory-*`) under
  `dependencies` in `pyproject.toml`: pip would look for them on PyPI
  and could install a stranger's package with that name ("dependency
  confusion"). Document the install step in the README instead.

## 5. Adding a package

1. Pick the short name (§2). Create `packages/<name>/` with the layout
   from §1.
2. Write `pyproject.toml` with the namespace settings from §3.
3. Add `tests/__init__.py` that puts `src/` on `sys.path` (copy one
   from an existing package), so tests run without installing.
4. Write the package README (what, setup, usage, layout, tests).
5. Add a row to the package table in the workspace README.
6. `ruff check .` and `python scripts/test_all.py` must pass.

## 6. Tests

- Per package, from its folder: `python -m unittest discover -s tests -t .`
- Everything: `python scripts/test_all.py` from the workspace root.
- Tests never touch the real screen, mouse, or launch real apps. Fake or
  mock the boundary (see `packages/mouse-ext/tests/fakes.py` and the
  `os.startfile` mock in `packages/adspower/tests`).

## 7. Commit messages

Before committing: `ruff check .` and `python scripts/test_all.py` pass,
docs touched by the change are updated (README, ARCHITECTURE, and a
CHANGELOG entry for user-visible changes), and a package's version in
`pyproject.toml` is bumped when its behaviour changes.

- Summary line: present tense, imperative, at most 72 characters, no
  prefix ("Add RetryLocator extension", not "feat: added retry").
- When a commit touches one package, name it in the summary line:
  "adspower: Add --path option".
- A blank line, then a body explaining *why* the change was made, not
  just what changed (the diff already shows what). Related changes are
  grouped as "- " bullets, and updated docs are mentioned.
- The body ends with how the change was verified (tests run, manual check).
- One logical change per commit.

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

- §2 Naming: **Official** PEP 8, naming conventions: <https://peps.python.org/pep-0008/#naming-conventions> · PyPA, distribution vs import package: <https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/>
- §3 Namespace package: **Official** PEP 420: <https://peps.python.org/pep-0420/> · PyPA guide: <https://packaging.python.org/en/latest/guides/packaging-namespace-packages/>
- §4 Dependencies: Supply chain attacks: <https://en.wikipedia.org/wiki/Supply_chain_attack>; Acyclic dependencies principle: <https://en.wikipedia.org/wiki/Acyclic_dependencies_principle>
- Alex Birsan, "Dependency Confusion" (2021), the original disclosure: <https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610> (Medium blocks automated link checks; open it in a browser)
- §6 Tests: **Official** `unittest`: <https://docs.python.org/3/library/unittest.html>
- §7 Commits: Chris Beams, "How to Write a Git Commit Message": <https://cbea.ms/git-commit/> · **Official** `git commit`: <https://git-scm.com/docs/git-commit> · Keep a Changelog: <https://keepachangelog.com/en/1.1.0/> · Semantic Versioning: <https://semver.org/> · Ruff: <https://docs.astral.sh/ruff/>
