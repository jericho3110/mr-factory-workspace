# Learning path

A guided route through this workspace for learning the skills it uses,
so you can **rebuild the same kind of project yourself** and then improve
on it. Each step says what to read, what to look for, and a small
exercise to prove you've got it.

The other docs are references (look things up); this one is a course
(read in order):

| Doc | Use it for |
| --- | --- |
| [README.md](../README.md) | setup and the package list |
| [CONVENTIONS.md](CONVENTIONS.md) | the rules: layout, naming, commits |
| [ARCHITECTURE.md](ARCHITECTURE.md) | *why* the workspace is set up this way: packaging, commands, testing, style |
| [ARCHITECTURE_STYLES.md](ARCHITECTURE_STYLES.md) | named architecture styles (Layered, Hexagonal, Clean, by-feature, modular monolith, plugins) and which ones this code uses |
| [LIBRARIES_AND_BUILTINS.md](LIBRARIES_AND_BUILTINS.md) | reference: every stdlib module, built-in, dunder, decorator, and external library used, and why |
| [MODULES_AND_PACKAGES.md](MODULES_AND_PACKAGES.md) | modules vs packages, how `import` works, distributions, versions, dependencies |
| [adspower ARCHITECTURE](../packages/adspower/docs/ARCHITECTURE.md) | a complete small application, layer by layer |
| [mouse-ext ARCHITECTURE](../packages/mouse-ext/docs/ARCHITECTURE.md) | extending a library you don't own: Decorator, plugins/hooks |
| [adspower CHANGELOG](../packages/adspower/CHANGELOG.md) | how the design evolved, version by version |

> **Tip:** read code with the doc open next to it. Every concept below
> names the file where it lives; open it, find the thing, and change
> something small to see what happens. Run the tests after.

---

## Stage 1: The project shell (packaging and tooling)

**Goal:** understand everything around the code.

1. Read workspace [ARCHITECTURE.md](ARCHITECTURE.md) §1–§5 and §7
   (the big picture, `pyproject.toml`, `src/` layout, namespace package,
   every command).
2. Open [packages/adspower/pyproject.toml](../packages/adspower/pyproject.toml)
   and match each line to its explanation.

**Concepts:** virtual environments · `pyproject.toml` (PEP 517/621) ·
build backends · editable installs (`pip install -e`) · console scripts ·
entry points · `src/` layout · namespace packages (PEP 420) · semantic versioning.

**Exercise:** create a third package, `packages/hello/`, following
[CONVENTIONS.md §5](CONVENTIONS.md#5-adding-a-package): a `pyproject.toml`
with a console script `hello` that prints "hello", one test, and a
README. `pip install -e packages/hello`, run `hello`, run
`python scripts/test_all.py hello`. (Then delete it, or keep it as a template.)

**Check yourself:** why did `adspower` need `pip install -e` again after
`[project.scripts]` changed, but not after editing `client.py`?

---

## Stage 1½: Modules, packages, and versions

**Goal:** know exactly what a module, a package, and a distribution are,
how `import` finds code, and what a version number promises.

1. Read [MODULES_AND_PACKAGES.md](MODULES_AND_PACKAGES.md) §1–§5 (vocabulary,
   modules, packages, how `import` works, import styles and pitfalls).
2. Then §6–§9 (distributions, versions, dependencies, when to split).

**Concepts:** module · package · subpackage · regular vs namespace
package · `__init__.py` as the front door · `__main__.py` and `python -m` ·
`if __name__ == "__main__"` · dunder attributes (`__name__`, `__file__`,
`__package__`, `__path__`, `__spec__`) · `sys.path` vs a package's
`__path__` · `sys.modules` · absolute vs
relative imports · `_private` names and `__all__` · circular imports ·
distribution vs import name · sdist and wheel · `dist-info` metadata ·
editable-install hooks · SemVer and PEP 440 · single source of truth for
`__version__` · version specifiers · libraries use ranges, apps pin ·
lock files · extras.

**Exercise:** do exercises 1–6 at the end of that doc (they take a few
minutes each).

**Check yourself:** `adspower` — module or package? `mrfactory` — what
kind of package, and what would break if someone added
`src/mrfactory/__init__.py`? Why did adding `set-proxy` bump 0.2.0 →
0.3.0 rather than 1.0.0 or 0.2.1?

---

## Stage 2: Reading a layered application

**Goal:** follow one command through every layer.

1. Read [adspower ARCHITECTURE](../packages/adspower/docs/ARCHITECTURE.md)
   §1–§3 (what it does, module map, one command end to end).
2. Run `adspower set-proxy --help`, then read `cli/app.py` →
   `cli/commands.py` `cmd_set_proxy` → `client.py` `find_profile` /
   `choose_proxy` / `set_proxy` → `api.py` `post` → `models.py` `Profile.from_api`.

**Concepts:** layered architecture (named and compared in Stage 2½) · single responsibility · facade ·
dependency direction (no import cycles) · separation of library and interface.

**Exercise:** draw the import diagram yourself from the `import` lines
at the top of each module, then compare with §2 of the doc.

**Check yourself:** which single file would change if AdsPower renamed
`profile_no` to `serial` in its JSON? And if you wanted a GUI?

---

## Stage 2½: Naming the architecture

**Goal:** put names on what you just traced, and know the alternatives.

Read [ARCHITECTURE_STYLES.md](ARCHITECTURE_STYLES.md).

**Concepts:** layered architecture · hexagonal (ports and adapters;
driving vs driven adapters) · Clean/Onion and the Dependency Rule ·
package by layer vs by feature · monolith, modular monolith,
microservices, monorepo · microkernel/plugin architecture · YAGNI and
evolving an architecture when it hurts.

**Exercise:** exercises 1 and 2 at the end of that doc (name the layers;
define an `ApiPort` Protocol).

**Check yourself:** adspower is layered with hexagonal ideas, but not
fully hexagonal. Which two ingredients are missing, and what would have
to happen for adding them to be worth it?

---

## Stage 3: Talking to an external API (`api.py`, `models.py`)

1. Read adspower ARCHITECTURE §4–§5.
2. In `api.py`, trace `post_all()` → `_read_all_pages()` → `post()` →
   `_call()` → `_request()`.

**Concepts:** HTTP GET vs POST · JSON envelopes · pagination ·
higher-order functions · rate limiting (throttle + retry) · idempotency ·
translating errors at a boundary · exception chaining (`raise ... from e`) ·
dataclasses · immutability (`frozen=True`) · alternative constructors
(`@classmethod`) · anti-corruption layer · data minimization.

**Exercise:** add `Profile.created_time` (a `datetime | None`, the API
sends Unix seconds in `created_time`). Parse it in `from_api` using the
existing helper, add it to a fake profile in `tests/fakes.py`, and write
one test. Run `ruff check .` and the tests.

**Check yourself:** why is it safe to retry a *create* request after a
"too many requests" refusal, but not after a timeout?

---

## Stage 3½: The toolbox (standard library, built-ins, dunders)

**Goal:** recognize every tool the code reaches for, and know why it was
picked over the alternatives.

Skim [LIBRARIES_AND_BUILTINS.md](LIBRARIES_AND_BUILTINS.md) once, then
keep it open as a reference while reading code: whenever you meet an
unfamiliar import, built-in, `@decorator`, or `__dunder__`, look it up there.

**Concepts:** standard library first · `pathlib` vs strings · `time.monotonic`
vs `perf_counter` · `urllib` vs `requests` · `defaultdict` · dunder methods
as hooks Python calls (`__init__`, `__iter__`, `__len__`, `__call__`) ·
what `@dataclass` generates · `@classmethod`, `@property`, `@staticmethod` ·
`TYPE_CHECKING` · vectorized numpy · choosing and adding a dependency.

**Exercise:** exercises 1–3 at the end of that doc.

**Check yourself:** why does `adspower` have zero external dependencies
while `mouse-ext` has two? What would you check before adding a third?

---

## Stage 4: Rules, matching, and errors (`client.py`, `matching.py`, `errors.py`)

1. Read adspower ARCHITECTURE §6–§8.
2. Read `matching.py` top to bottom (it's short), then `test_matching.py`.

**Concepts:** pure functions · `Protocol` and `TypeVar` (typing by shape) ·
`casefold()` · sort keys · validate first, then change · exact before
fuzzy · pushing filters to the server · exception hierarchies · errors
that carry data (`AmbiguousProfile.matches`) · helpful error messages ·
"explicit is better than implicit".

**Exercise:** add `AdsPower.find_proxy(proxy_id)` that returns the
proxy with that ID or raises `ProxyNotFound` listing how many proxies
exist. Test it with `FakeApi` (both outcomes).

**Check yourself:** why does `find_profile` raise `AmbiguousProfile`
instead of printing a list and asking? Who *should* ask?

---

## Stage 5: Building a good command line (`cli/`)

1. Read adspower ARCHITECTURE §9.
2. Read `cli/prompts.py` and `test_prompts.py`, then `cmd_set_proxy`.

**Concepts:** argparse subcommands · table-driven dispatch
(`set_defaults(run=...)`) · exception boundary and exit codes (0/1/130) ·
crash logs · plan → confirm → apply · safe defaults (`[y/N]`) ·
interactive vs non-interactive (`isatty`, and the Windows `NUL` trap) ·
stdout vs stderr · human and machine output (`--json`) · making
interaction replaceable (`ask=`).

**Exercise:** add `--dry-run` to `set-proxy`: do everything up to
showing the plan, then print "Dry run: nothing changed." and return 0.
Write a test that proves no update request was sent (`api.updates == []`).

**Check yourself:** what exit code does Ctrl+C give, and why does it need
its own `except`?

---

## Stage 6: Testing (all `tests/` folders)

1. Read workspace ARCHITECTURE §8, then adspower ARCHITECTURE §10–§12.
2. Read `tests/fakes.py` (adspower), then any test class in `test_cli.py`.

**Concepts:** fakes vs mocks · stateful fakes · dependency injection for
tests · "patch where it's looked up" · `addCleanup` · arrange/act/assert ·
testing each layer through its own interface · pinning performance with
request counts · live checks on throwaway data with cleanup in `finally`.

**Exercise:** break something on purpose: in `matching.py`, change
`casefold()` to nothing (`return part in text`). Run the tests and read
which ones fail and why. Restore it.

**Check yourself:** why does `FakeApi` deep-copy its data in `__init__`?
What would go wrong without it?

---

## Stage 7: Extending code you don't own (mouse-ext)

Read [mouse-ext ARCHITECTURE](../packages/mouse-ext/docs/ARCHITECTURE.md).

**Concepts:** Open/Closed principle · Decorator (wrappers with the same
interface) · Observer/hooks (plugins) · Liskov substitution · entry-point
plugin discovery · controlling a loop through the iterator it consumes.

**Exercise:** one of the "Extension points" at the end of that doc.

---

## Stage 8: Code quality habits

1. Read workspace ARCHITECTURE §9–§11 and [CONVENTIONS.md §7](CONVENTIONS.md#7-commit-messages).
2. Run `ruff check .`, then read `ruff.toml`.

**Concepts:** PEP 8 · linters (Ruff) and what each rule set catches ·
fixing causes instead of silencing (`# noqa`) · docstrings that explain
*why* · commit messages as documentation · changelogs · refactoring
safely behind tests.

**Exercise:** read `git log` for the last few commits. For one, explain
from the message alone *why* the change was made, then check the diff
(`git show <hash>`).

---

## Replicating this on your own project: a checklist

1. `python -m venv venv`, activate, one venv per project.
2. `pyproject.toml` with `[build-system]`, `[project]`, and a console
   script if it's a tool. `src/<package>/` layout. `pip install -e .`
3. Split by job from the start: **transport** (talks to the outside),
   **models** (typed data), **rules** (facade), **interface** (CLI/GUI).
   Dependencies point one way.
4. Inject the outside world (`api=`, `opener=`, `ask=`) so tests can pass fakes.
5. Errors: one base class, specific subclasses, messages that say what to do.
   One exception boundary at the top of the interface.
6. Anything that changes data: validate first, show the plan, confirm
   (default no), then make one change.
7. Tests per layer from day one; a live check on throwaway data before
   trusting a feature; every surprise becomes a test.
8. `ruff check .` + tests before every commit; commit messages say why.
9. Write the docs as you go: README (how to use), ARCHITECTURE (why),
   CHANGELOG (what changed).

---

## References

Every link was checked and resolved on 2026-10-07. Each stage's own docs
have fuller, section-by-section reference lists; this is the short list
per stage, official sources first.

| Stage | Official | Further reading |
| --- | --- | --- |
| 1 Project shell | [PyPA packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/) · [Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) · [`venv` tutorial](https://docs.python.org/3/tutorial/venv.html) | [Real Python: pyproject.toml](https://realpython.com/python-pyproject-toml/) · [virtual environments](https://realpython.com/python-virtual-environments-a-primer/) |
| 1½ Modules & packages | [Tutorial: modules](https://docs.python.org/3/tutorial/modules.html) · [Import system](https://docs.python.org/3/reference/import.html) · [PEP 420](https://peps.python.org/pep-0420/) · [PEP 440](https://peps.python.org/pep-0440/) | [Real Python: modules and packages](https://realpython.com/python-modules-packages/) · [import](https://realpython.com/python-import/) |
| 2 Layered app | [`argparse` tutorial](https://docs.python.org/3/howto/argparse.html) | [Fowler: layering](https://martinfowler.com/bliki/PresentationDomainDataLayering.html) · [Cosmic Python](https://www.cosmicpython.com/) |
| 2½ Architecture styles | [Cockburn: Hexagonal](https://alistair.cockburn.us/hexagonal-architecture/) · [Martin: Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html) | [Fowler: MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) · [Shopify: modular monolith](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity) |
| 3 External API | [`urllib.request`](https://docs.python.org/3/library/urllib.request.html) · [`dataclasses`](https://docs.python.org/3/library/dataclasses.html) · [`json`](https://docs.python.org/3/library/json.html) | [MDN: idempotent](https://developer.mozilla.org/en-US/docs/Glossary/Idempotent) · [429](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429) · [Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry) · [Anti-corruption layer](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer) |
| 3½ Toolbox | [Built-in functions](https://docs.python.org/3/library/functions.html) · [Data model (dunders)](https://docs.python.org/3/reference/datamodel.html) · [PEP 318 decorators](https://peps.python.org/pep-0318/) | [Real Python: magic methods](https://realpython.com/python-magic-methods/) · [decorators](https://realpython.com/primer-on-python-decorators/) |
| 4 Rules & errors | [`typing.Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol) · [Exceptions](https://docs.python.org/3/library/exceptions.html) · [PEP 20](https://peps.python.org/pep-0020/) | [Pure function](https://en.wikipedia.org/wiki/Pure_function) · [Real Python: exceptions](https://realpython.com/python-exceptions/) |
| 5 Command line | [`argparse`](https://docs.python.org/3/library/argparse.html) | [clig.dev](https://clig.dev/) · [Exit codes](https://tldp.org/LDP/abs/html/exitcodes.html) · [12-factor config](https://12factor.net/config) |
| 6 Testing | [`unittest`](https://docs.python.org/3/library/unittest.html) · [`unittest.mock`, where to patch](https://docs.python.org/3/library/unittest.mock.html#where-to-patch) | [Fowler: TestDouble](https://martinfowler.com/bliki/TestDouble.html) · [Mocks aren't stubs](https://martinfowler.com/articles/mocksArentStubs.html) · [Test pyramid](https://martinfowler.com/articles/practical-test-pyramid.html) |
| 7 Extending (mouse-ext) | [Entry points spec](https://packaging.python.org/en/latest/specifications/entry-points/) · [Plugins guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) | [Refactoring Guru: patterns](https://refactoring.guru/design-patterns) · [Open–closed](https://en.wikipedia.org/wiki/Open%E2%80%93closed_principle) |
| 8 Quality habits | [PEP 8](https://peps.python.org/pep-0008/) · [Ruff rules](https://docs.astral.sh/ruff/rules/) | [Commit messages](https://cbea.ms/git-commit/) · [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · [SemVer](https://semver.org/) |

Books (not online): *Fluent Python* (Luciano Ramalho) for dataclasses,
protocols, iterators, and generators in depth; *Clean Architecture*
(Robert C. Martin); *Architecture Patterns with Python* (Percival &
Gregory, also free at <https://www.cosmicpython.com/>).
