# Architecture styles: what this codebase uses, and what it doesn't

> **2026-10-09:** `mouse-ext` (`mrfactory.mouse_ext`) has moved into its own library,
> [natural-mouse](https://github.com/jericho3110/natural-mouse) (`natural_mouse.extensions`, `natural_mouse.plugins`). The
> lessons below still apply; where they name `packages/mouse-ext/...`, the code now
> lives in that repo (`src/natural_mouse/`, `tests/ext_fakes.py`, `docs/EXTENSIONS_AND_PLUGINS.md`).

"Which architecture is this?" has a different answer at each level of
the codebase, and two separate questions hide inside it:

- **Architecture style**: how the parts *depend on each other* (who
  calls whom, who knows about whom).
- **Packaging style**: how the parts are *grouped into folders*.

This doc names the style used at each level, explains the well-known
styles (Layered, Hexagonal, Clean/Onion, Package by Layer vs by Feature,
Modular Monolith, Microkernel, and more), compares each one honestly
with this code, and says when it would be worth changing.

Contents:

1. [The short answer](#1-the-short-answer)
2. [Layered architecture (what adspower uses)](#2-layered-architecture-what-adspower-uses)
3. [Hexagonal architecture / Ports and Adapters](#3-hexagonal-architecture--ports-and-adapters)
4. [Clean Architecture and Onion Architecture](#4-clean-architecture-and-onion-architecture)
5. [Package by layer vs package by feature](#5-package-by-layer-vs-package-by-feature)
6. [Modular monolith (and microservices, and this monorepo)](#6-modular-monolith-and-microservices-and-this-monorepo)
7. [Microkernel / plugin architecture (what mouse-ext uses)](#7-microkernel--plugin-architecture-what-mouse-ext-uses)
8. [Other names you'll meet](#8-other-names-youll-meet)
9. [Why not the "bigger" styles yet](#9-why-not-the-bigger-styles-yet)
10. [Exercises](#10-exercises)
11. [References](#references)

---

## 1. The short answer

| Level | Architecture style | Packaging style |
| --- | --- | --- |
| **Workspace** (`Modules/`) | **Monorepo of independently installable libraries**: one git repo, several packages, each with its own `pyproject.toml` and version, dependencies pointing one way. It is **not** a modular monolith (§6) | **By feature/capability** at the top: `adspower/`, `mouse-ext/` |
| **`adspower` package** | **Layered architecture** (§2) with **dependency injection at the edges**: interface → facade → transport/OS. It borrows ideas from **Hexagonal** (§3) but isn't fully hexagonal | **By layer** (§5): `cli/`, `client.py`, `api.py`, `models.py` |
| **`mouse-ext` package** | **Microkernel / plugin architecture** (§7) plus **Decorators** around a Strategy-based core (`natural_mouse`) | **By role**: `plugins/`, `extensions/` |

None of these are "wrong" or "beginner" choices. They match the size of
the code (adspower ~1,500 lines, mouse-ext ~800, one developer). §9 explains
why, and each section says what would justify moving to something bigger.

---

## 2. Layered architecture (what adspower uses)

**The idea:** stack the code in layers. Each layer only calls the layer
below it, never above.

```text
  ┌──────────────────────────────────────────┐
  │ Presentation    cli/   (argparse, prompts, tables)
  ├──────────────────────────────────────────┤
  │ Application     client.py  AdsPower: use cases + rules
  ├──────────────────────────────────────────┤
  │ Domain          models.py, matching.py, errors.py
  ├──────────────────────────────────────────┤
  │ Infrastructure  api.py (HTTP), launcher.py (OS processes)
  └──────────────────────────────────────────┘
```

**Where you see it:** `cli/` imports `client`, `client` imports `api`,
`api` never imports `client` or `cli`. Nothing below `client.py` knows a
command line exists, which is why `AdsPower` works the same from Python
code. (Map and import diagram: [adspower ARCHITECTURE §2](../packages/adspower/docs/ARCHITECTURE.md#2-module-map).)

**Strengths:** simple and familiar; each kind of change lands in one
layer; easy to explain.

**Weakness (the classic one):** the upper layers depend on the lower
ones, ultimately on infrastructure. In adspower, `client.py` imports the
concrete `LocalApi` class, and the domain models know AdsPower's JSON
field names (`Profile.from_api` reads `"profile_no"`). If AdsPower's API
changed, the "domain" would change too. Hexagonal architecture exists to
fix exactly that.

---

## 3. Hexagonal architecture / Ports and Adapters

**The idea** (Alistair Cockburn, 2005): put the **core** (the business
rules) in the middle and make it depend on **nothing outside**. The
core defines **ports**: interfaces describing what it needs ("something
that can list profiles") or offers ("open a profile"). The outside world
plugs in through **adapters** that implement those ports.

```text
        driving adapters                          driven adapters
     (they call the core)                     (the core calls them)

   CLI ─┐                                        ┌─▶ AdsPower Local API (HTTP)
   GUI ─┼─▶ [ inbound port ] ─▶  CORE  ─▶ [ outbound port ] ─┼─▶ fake API (tests)
 tests ─┘                     rules, models                  └─▶ AdsPower cloud API (someday)
```

The key rule: **dependencies point inward.** Adapters import the core;
the core never imports an adapter. The core describes the port as an
interface, and the adapter is *given* to it (dependency injection).

### How close is adspower?

| Hexagonal ingredient | In adspower? |
| --- | --- |
| A core with the rules, usable without any UI | ✅ `AdsPower` in `client.py` |
| Driving adapter separate from the core | ✅ `cli/` only calls `AdsPower`; a GUI could replace it |
| Driven adapter injected into the core | ✅ `AdsPower(api=...)`; tests inject `FakeApi` |
| **Port defined by the core as an interface** | ❌ No explicit port. `client.py` imports the concrete `LocalApi`, and `FakeApi` matches it only by duck typing |
| **Core free of outside formats** | ❌ `models.py` (core) parses AdsPower's JSON in `from_api`; endpoint paths live in `client.py` |

So adspower is **layered, with hexagonal ideas at the edges**: the
driving side is clean, and the driven side is injectable but not formally
a port.

### What fully hexagonal adspower would look like

```text
mrfactory/adspower/
├── core/
│   ├── models.py        Group, Profile... (no from_api; pure data)
│   ├── rules.py         choose_proxy rules, matching
│   ├── ports.py         AdsPowerPort (Protocol): list_profiles(), start_browser(), ...
│   └── service.py       AdsPower(port: AdsPowerPort): the use cases
└── adapters/
    ├── local_api.py     LocalApiAdapter(AdsPowerPort): HTTP + JSON → core models
    └── cli/             the command line (driving adapter)
```

```python
# core/ports.py: the core says what it needs, in its own terms
class AdsPowerPort(Protocol):
    def list_profiles(self, group_id: str | None, tag_ids: list[str] | None) -> list[Profile]: ...
    def start_browser(self, profile_id: str) -> OpenedBrowser: ...
    def update_proxy(self, profile_id: str, proxy_id: str | None) -> None: ...
```

Then `"profile_no"`, `/api/v2/...`, and paging would live only in
`adapters/local_api.py`, and a second backend (AdsPower's cloud API, or
a different anti-detect browser) would be a second adapter with **no**
change to the core.

**When it's worth it:** when there's a *second* driven adapter for real
(another backend), or the core rules grow large enough that you want
them provably independent of AdsPower's JSON. Until then, the extra
layer of translation is cost without benefit (§9). The step that's
already cheap: define the port as a `Protocol` (§10, exercise 2).

---

## 4. Clean Architecture and Onion Architecture

Two close relatives of Hexagonal, drawn as **circles** instead of a
hexagon:

```text
   ┌──────────── frameworks, UI, DB, web, devices ────────────┐
   │   ┌──────────── interface adapters ────────────┐         │
   │   │   ┌───────── use cases (application) ───┐  │         │
   │   │   │      ┌──── entities (domain) ───┐   │  │         │
   │   │   │      └──────────────────────────┘   │  │         │
   │   │   └─────────────────────────────────────┘  │         │
   │   └────────────────────────────────────────────┘         │
   └──────────────────────────────────────────────────────────┘
          The Dependency Rule: source code dependencies point only inward.
```

- **Onion Architecture** (Jeffrey Palermo, 2008): domain model in the
  middle, then domain services, application services, and infrastructure/UI outside.
- **Clean Architecture** (Robert C. Martin, 2012): entities → use cases
  → interface adapters → frameworks, with the **Dependency Rule** above.

All three (Hexagonal, Onion, Clean) share one idea: **the business rules
don't depend on the database, the web, the UI, or an external API.**
Mapped onto adspower: `models.py` + `matching.py` ≈ entities;
`client.py` ≈ use cases; `cli/` and `api.py` ≈ interface adapters. The
same gap as in §3 applies: the inner circle still knows the API's JSON.

---

## 5. Package by layer vs package by feature

This is the *folder* question, and it's independent of the
architecture question.

**Package by layer** groups code by technical role. **This is adspower:**

```text
adspower/
├── api.py        all HTTP, for every feature
├── models.py     all data classes, for every feature
├── client.py     all use cases, for every feature
└── cli/          all commands, for every feature
```

**Package by feature** groups code by what it's *about*, and each folder
contains its own layers:

```text
adspower/
├── groups/       model, api calls, rules, commands for groups
├── profiles/     ...for profiles (find, open, close, create)
├── proxies/      ...for proxies (list, choose, set_proxy)
└── shared/       the HTTP client, errors, matching
```

| | By layer | By feature |
| --- | --- | --- |
| To change one feature, you touch | one file in *each* layer (`set-proxy` touched `models`, `client`, `cli/app`, `cli/commands`) | one folder |
| Easy to see | how the system is built | what the system *does* |
| Works best when | few features, small code (adspower today: ~1,500 lines, `client.py` ~330) | many features, growing independently, or several people each owning one |
| Risk | layer files grow huge as features pile up | duplication between features; unclear home for shared code |

**What this workspace does:** both, at different levels. The
**workspace** is packaged **by feature** (`adspower/` and `mouse-ext/`
are capabilities), and each **package** inside is organized **by layer**.
That combination is common and sensible.

**When adspower should switch:** when a layer file becomes hard to work
with because of features that have nothing to do with each other (say
`client.py` passes ~600 lines, or commands for a new area like "cookies"
or "extensions" arrive). The first move would be splitting `client.py`
by feature (`profiles.py`, `proxies.py`), keeping `AdsPower` as the
facade that delegates to them.

---

## 6. Modular monolith (and microservices, and this monorepo)

These names are about **how many deployable programs** you have, and
**how strictly the inside is divided**.

| Style | Deployed as | Inside | Example |
| --- | --- | --- | --- |
| **Monolith** ("big ball of mud" when it goes wrong) | one program | no enforced boundaries; anything calls anything | many legacy apps |
| **Modular monolith** | **one** program | **strict modules** (often by feature), each with a public API; other modules may only use that API | Shopify's core app is the famous example |
| **Microservices** | **many** programs, each with its own process (often its own database), talking over the network | one service per business capability | large companies with many teams |
| **This workspace** | **no single program at all**: several *libraries*, each installable alone, and the `adspower` command | strict boundaries between packages (public APIs, one-way dependencies) | a monorepo of libraries |

**Is this workspace a modular monolith?** Not quite. A modular monolith
is one application that ships as one unit. This workspace is a set of
**independent libraries** that share a repo. It *shares the good part*
of a modular monolith, though: strict boundaries (packages talk only
through public imports, dependencies point one way,
[CONVENTIONS.md §4](CONVENTIONS.md#4-dependencies-between-packages)).

**It would become one** the day you build a single application, say
`mrfactory-app`, that imports both `mrfactory.adspower` and
`mrfactory.mouse_ext` and ships as one program. Then the packages are
the modules of a modular monolith, and the existing rules are exactly
the ones a modular monolith needs.

**Why not microservices?** They solve organizational problems (many
teams deploying independently) at the cost of network calls, deployment,
monitoring, and data consistency. One developer automating a desktop app
has none of those problems. A well-divided monolith is the recommended
starting point; services are split off only when there's a concrete reason.

---

## 7. Microkernel / plugin architecture (what mouse-ext uses)

**The idea:** a small **core** that does the essential job, plus
**plugins** that add features through defined extension points, without
changing the core. Browsers, code editors (VS Code), and pytest are all
built this way.

In mouse-ext:

- **The core:** `PluggableAutomator` (a `natural_mouse.UIAutomator`).
- **Extension point 1 (hooks):** plugins (`LoggingPlugin`, `StatsPlugin`,
  `RegionGuardPlugin`...) are called at `before_action`, `after_locate`,
  `before_input`, `after_action`, `on_error`.
- **Extension point 2 (strategies):** extensions wrap the core's three
  strategy interfaces as **Decorators** (`RetryLocator`, `FailSafeExecutor`...).
- **Discovery:** other installed packages can add plugins through
  **entry points**, so the core doesn't even need to know they exist.

Details: [mouse-ext ARCHITECTURE](https://github.com/jericho3110/natural-mouse/blob/main/docs/EXTENSIONS_AND_PLUGINS.md).
Note that the strategy interfaces of `natural_mouse` (`ScreenLocator`,
`PathGenerator`, `InputExecutor`) are themselves **ports** in the
hexagonal sense: the core defines them, and implementations are plugged
in. mouse-ext is the most "hexagonal" code in the workspace.

---

## 8. Other names you'll meet

| Name | One-line idea | Here? |
| --- | --- | --- |
| **MVC** (Model–View–Controller) | split UI apps into data (model), display (view), input handling (controller) | loosely: `models.py` / `cli/output.py` / `cli/commands.py` |
| **Pipe and filter** | data flows through a chain of small steps | `FallbackLocator` chains locators; Unix pipes |
| **Event-driven** | parts communicate by publishing and reacting to events | mouse-ext's hooks are a small, synchronous version |
| **CQRS** | separate the code that reads from the code that changes | hinted at: lookups vs `set_proxy`/`create_profile` with confirmation |
| **Repository pattern** | one object per kind of stored thing, hiding where it's stored | `AdsPower.groups()/profiles()/proxies()` play that role through one facade |
| **Service layer** | one layer exposing the application's use cases | `client.py` |
| **Domain-Driven Design (DDD)** | model the code on the business's own language and boundaries | the vocabulary (group, tag, profile, proxy) mirrors AdsPower's own |

---

## 9. Why not the "bigger" styles yet

Every architecture trades **flexibility later** for **complexity now**.
More layers, ports, and adapters mean more files, more translation code,
and more to understand before you can change anything.

The guidelines this codebase follows:

- **YAGNI** ("You Aren't Gonna Need It"): don't build for a second
  backend that doesn't exist. Make it *possible* cheaply (dependency
  injection already does) and build it when needed.
- **Keep the seams where change is likely.** The things most likely to
  change are AdsPower's API (isolated in `api.py` + endpoint constants)
  and the interface (isolated in `cli/`). Those seams exist today.
- **Let tests drive the boundaries.** `FakeApi` exists because tests
  needed it, and it's the same seam a second backend would use.
- **Evolve when it hurts.** Signals that it's time:

| Signal | Move to |
| --- | --- |
| A second backend or a GUI is actually being built | explicit ports (§3) |
| `client.py` or `cli/commands.py` grows hard to navigate | split by feature (§5) |
| You ship one app combining several packages | the packages become modules of a modular monolith (§6) |
| Several people or teams deploy parts on different schedules | consider services (§6), only then |

---

## 10. Exercises

1. **Name the layers.** For each module in `adspower` (`cli/app.py`,
   `cli/commands.py`, `client.py`, `matching.py`, `models.py`, `api.py`,
   `launcher.py`, `errors.py`), say which layer of §2 it belongs to, and
   check its `import` lines: does any module import a layer *above* it?
2. **Define a port.** Write a `Protocol` (see `matching.Named` for the
   syntax) called `ApiPort` with the methods `client.py` actually calls
   on `self.api` (`get`, `post`, `get_all`, `post_all`, `is_running`).
   Annotate `AdsPower.__init__(self, api: ApiPort | None = None)`. Which
   two classes now "implement" the port without inheriting from it?
3. **Find the leak.** List every place where AdsPower's JSON field names
   (`"profile_no"`, `"proxy_tags"`, ...) appear outside `api.py`. In a
   fully hexagonal design, where would each move?
4. **Package by feature, on paper.** Sketch the folder tree if
   adspower were packaged by feature. Where would `choose_proxy` go?
   Where would `matching.py` go? What would `__init__.py` re-export so
   `from mrfactory.adspower import AdsPower` still works?
5. **Spot the plugin architecture.** In mouse-ext, list the extension
   points and, for each, one built-in implementation. Then explain how a
   plugin from a *different* package would be found.

---

---

## References

Every link below was checked and resolved on 2026-10-07. **Official**
sources (Python docs, PEPs, PyPA specifications, vendor docs) are the
authority; **further reading** explains the same ideas another way.
Claims in this doc marked ✔ were re-checked against the cited source.
If a link has moved, search the title on the same site.

### §2 Layered architecture

- Multitier (layered) architecture: <https://en.wikipedia.org/wiki/Multitier_architecture>
- Martin Fowler, "Presentation Domain Data Layering": <https://martinfowler.com/bliki/PresentationDomainDataLayering.html>
- Martin Fowler, Service Layer: <https://martinfowler.com/eaaCatalog/serviceLayer.html>

### §3 Hexagonal / Ports and Adapters

- Alistair Cockburn, "Hexagonal Architecture" (the original): <https://alistair.cockburn.us/hexagonal-architecture/>
- Hexagonal architecture overview: <https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)>
- *Architecture Patterns with Python* (Percival & Gregory), free online: <https://www.cosmicpython.com/>; repository pattern: <https://www.cosmicpython.com/book/chapter_02_repository.html>; service layer: <https://www.cosmicpython.com/book/chapter_04_service_layer.html>
- **Official:** `typing.Protocol` (for writing a port): <https://docs.python.org/3/library/typing.html#typing.Protocol> · PEP 544: <https://peps.python.org/pep-0544/>

### §4 Clean and Onion Architecture

- Robert C. Martin, "The Clean Architecture" (2012): <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
- Jeffrey Palermo, "The Onion Architecture, part 1" (2008): <https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/>

### §5 Package by layer vs by feature

- Simon Brown, "Package by component and architecturally-aligned testing": <https://www.codingthearchitecture.com/2015/03/08/package_by_component_and_architecturally_aligned_testing.html>
- *The Hitchhiker's Guide to Python*, structure: <https://docs.python-guide.org/writing/structure/>

### §6 Modular monolith, microservices, monorepo

- Shopify Engineering, "Deconstructing the Monolith": <https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity>
- Martin Fowler, "MonolithFirst": <https://martinfowler.com/bliki/MonolithFirst.html>
- Lewis & Fowler, "Microservices": <https://martinfowler.com/articles/microservices.html>
- Monorepo: <https://en.wikipedia.org/wiki/Monorepo>

### §7 Microkernel / plugin architecture

- Plug-in (computing): <https://en.wikipedia.org/wiki/Plug-in_(computing)>
- Microkernel (the operating-system origin of the name): <https://en.wikipedia.org/wiki/Microkernel>
- **Official:** PyPA, creating and discovering plugins (entry points): <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/>

### §8 Other names

- Martin Fowler: [Repository](https://martinfowler.com/eaaCatalog/repository.html) · [Data Transfer Object](https://martinfowler.com/eaaCatalog/dataTransferObject.html) · [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html) · [Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- Refactoring Guru, design patterns catalogue: <https://refactoring.guru/design-patterns>

### §9 Why not bigger styles yet

- Martin Fowler, "Yagni": <https://martinfowler.com/bliki/Yagni.html>
- Martin Fowler, dependency injection: <https://martinfowler.com/articles/injection.html>
- Mark Richards, *Software Architecture Patterns* (O'Reilly report, book): layered, microkernel, event-driven, microservices
