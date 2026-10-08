"""Create many profiles at once, each with its own unused proxy.

The easy way is through `AdsPower` (client.py):

    batch = ads.plan_batch(["Shop 8", "Shop 9"], group="Acme", tag="acme")
    print(batch.summary())                  # look before you change anything
    results = ads.create_batch(batch)       # one profile at a time
    print(results_text(results))            # a table that pastes into a sheet

The pieces, for finer control:

- `plan()` is a *pure function*: names + existing profiles + free proxies
  in, one `Planned` per name out. No API calls, so it's instant and you
  can show the plan and ask before anything changes.
- `BatchCreator` carries a plan out. Just before it starts it re-reads
  the proxy list: a planned proxy that got used in the meantime is
  swapped for another free one (never one reserved for a later name), so
  a proxy is never shared.

Rules:

- Every new profile gets **its own unused proxy** with the proxy tag:
  unused = no profile uses it (`Proxy.in_use` is False) and this batch
  hasn't handed it out. When proxies run out, the remaining names are
  *not* created.
- A name that **already exists** (ignoring upper/lower case) is skipped,
  so running the same list twice creates nothing new. A name repeated in
  the list is created once. Names over 100 characters are refused
  (AdsPower's limit).
- One failure doesn't stop the batch; `stop()` takes effect between
  profiles, never in the middle of one.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from .errors import AdsPowerError
from .models import Group, Profile, Proxy, Tag

# "no more than 100 characters": AdsPower Local API docs, New Profile V2.
NAME_MAX = 100


class PlanStatus(Enum):
    """What will happen to one name. `.value` is readable text for tables."""

    READY = "ready"
    EXISTS = "already exists"
    REPEATED = "repeated"
    TOO_LONG = "name too long"
    NO_PROXY = "no free proxy"


@dataclass(frozen=True)
class Planned:
    name: str
    status: PlanStatus
    proxy: Proxy | None = None      # set when READY

    @property
    def ready(self) -> bool:
        return self.status is PlanStatus.READY


@dataclass(frozen=True)
class BatchSettings:
    """Where the new profiles go. Group and tag are already looked up, so
    a typo fails before anything is created. The proxy tag is a name:
    proxy tags are a separate list in AdsPower."""

    group: Group
    tag: Tag
    proxy_tag: str
    remark: str = ""        # written into every new profile (optional)


@dataclass(frozen=True)
class Batch:
    """A plan plus its settings: what `AdsPower.plan_batch` returns and
    `AdsPower.create_batch` takes."""

    settings: BatchSettings
    planned: tuple[Planned, ...]
    free_count: int         # free proxies with the tag when planned

    @property
    def ready(self) -> list[Planned]:
        return [p for p in self.planned if p.ready]

    def summary(self) -> str:
        """'2 of 3 ready; 5 free proxies tagged 'acme'.', for a prompt or a log."""
        return (f"{len(self.ready)} of {len(self.planned)} ready; {self.free_count} free "
                f"prox{'y' if self.free_count == 1 else 'ies'} tagged {self.settings.proxy_tag!r}.")


def free_proxies(proxies: Iterable[Proxy]) -> list[Proxy]:
    """The proxies no profile uses yet, in AdsPower's order."""
    return [proxy for proxy in proxies if not proxy.in_use]


def plan(names: Sequence[str], existing: Sequence[Profile], free: Sequence[Proxy]) -> list[Planned]:
    """Decide every name's fate and hand out one free proxy per new
    profile, in list order. Pure: no AdsPower calls."""
    taken = {profile.name.strip().casefold() for profile in existing}
    seen: set[str] = set()
    proxies = iter(free)
    result = []
    for name in names:
        key = name.casefold()
        if len(name) > NAME_MAX:
            result.append(Planned(name, PlanStatus.TOO_LONG))
        elif key in seen:
            result.append(Planned(name, PlanStatus.REPEATED))
        elif key in taken:
            result.append(Planned(name, PlanStatus.EXISTS))
        else:
            seen.add(key)
            proxy = next(proxies, None)
            result.append(Planned(name, PlanStatus.READY if proxy else PlanStatus.NO_PROXY, proxy))
    return result


# --- carrying a plan out -------------------------------------------------------


class Outcome(Enum):
    CREATED = "created"
    FAILED = "failed"
    SKIPPED = "skipped"     # not READY in the plan, or no free proxy left at creation time
    NOT_RUN = "not run"     # stop() was called before its turn


@dataclass(frozen=True)
class Created:
    """One name's result; also what `on_result` receives after each name."""

    index: int                      # position in the plan
    name: str
    outcome: Outcome
    message: str = ""
    profile: Profile | None = None  # set when CREATED
    proxy: Proxy | None = None

    def row(self) -> tuple[str, str, str, str, str]:
        """Name, serial, profile ID, proxy address, result: one table line."""
        profile = self.profile
        return (self.name, profile.serial_number if profile else "", profile.id if profile else "",
                self.proxy.address if self.proxy and profile else "", self.message or self.outcome.value)


class BatchCreator:
    """Creates the READY names of a plan, one at a time.

    `ads` is an `AdsPower` (or anything with `proxies(tag=)` and
    `create_profile(...)`). `on_result(Created)` is called after each
    name, from the thread that called `run`. `stop()` is safe from any
    thread."""

    def __init__(self, ads, on_result: Callable[[Created], None] = lambda created: None):
        self.ads = ads
        self.on_result = on_result
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def run(self, planned: Sequence[Planned], settings: BatchSettings) -> list[Created]:
        still_free = {p.id: p for p in free_proxies(self.ads.proxies(tag=settings.proxy_tag))}
        given_out = {p.proxy.id for p in planned if p.ready and p.proxy.id in still_free}
        results = []
        for index, item in enumerate(planned):
            if self._stop.is_set():
                result = Created(index, item.name, Outcome.NOT_RUN)
            elif not item.ready:
                result = Created(index, item.name, Outcome.SKIPPED, item.status.value)
            else:
                proxy = _proxy_for(item, still_free, given_out)
                if proxy is None:
                    result = Created(index, item.name, Outcome.SKIPPED,
                                     f"no free proxy tagged {settings.proxy_tag!r} left")
                else:
                    result = self._create(index, item.name, settings, proxy)
            results.append(result)
            self.on_result(result)
        return results

    def _create(self, index: int, name: str, settings: BatchSettings, proxy: Proxy) -> Created:
        try:
            profile = self.ads.create_profile(name, group=settings.group, tag=settings.tag, proxy=proxy,
                                              remark=settings.remark)
        except AdsPowerError as e:
            return Created(index, name, Outcome.FAILED, str(e), proxy=proxy)
        return Created(index, name, Outcome.CREATED, profile=profile, proxy=proxy)


def _proxy_for(item: Planned, still_free: dict[str, Proxy], given_out: set[str]) -> Proxy | None:
    """The planned proxy if it's still free; otherwise another free one
    nobody in this batch has. Marks the choice as used."""
    if item.proxy.id in still_free:
        proxy = item.proxy
    else:
        proxy = next((p for pid, p in still_free.items() if pid not in given_out), None)
        if proxy is None:
            return None
        given_out.add(proxy.id)
    del still_free[proxy.id]
    return proxy


def summarize(results: Iterable[Created]) -> str:
    """'2 created, 1 skipped', counting only outcomes that occurred."""
    results = list(results)
    counts = {o: sum(r.outcome is o for r in results) for o in Outcome}
    return ", ".join(f"{n} {o.value}" for o, n in counts.items() if n) or "nothing to do"


def results_text(results: Iterable[Created]) -> str:
    """Tab-separated with a header: pastes into Excel or a sheet as a table."""
    lines = ["Name\tSerial\tProfile ID\tProxy\tResult"]
    lines += ["\t".join(result.row()) for result in results]
    return "\n".join(lines)
