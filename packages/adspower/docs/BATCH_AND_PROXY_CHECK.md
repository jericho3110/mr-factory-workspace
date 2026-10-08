# Many profiles at once, and checking proxies

Two features any project can reuse, instead of rebuilding them:

- **Batch creation** (`batch.py`): create many profiles in one go, each
  in a chosen group with a chosen tag, and each with **its own unused
  proxy**.
- **Proxy check** (`proxycheck.py`): open a profile, load a "what is my
  IP?" page through its proxy, close it, and get `ok (exit IP)` or
  Chrome's error.

Both are on the `AdsPower` class (one call each) and on the `adspower`
command.

## Contents

- [1. Quick start: Python](#1-quick-start-python)
- [2. Quick start: command line](#2-quick-start-command-line)
- [3. Batch creation: the rules](#3-batch-creation-the-rules)
- [4. Proxy check: how it works](#4-proxy-check-how-it-works)
- [5. The building blocks](#5-the-building-blocks)
- [6. Design decisions](#6-design-decisions)
- [7. Testing](#7-testing)
- [8. Found live](#8-found-live)
- [9. Exercises](#9-exercises)
- [References](#references)

## 1. Quick start: Python

```python
from mrfactory.adspower import AdsPower, results_text

ads = AdsPower()

# 1. Plan: creates nothing. Group and tag must exist (else GroupNotFound / TagNotFound).
batch = ads.plan_batch(["Shop 8", "Shop 9"], group="Acme", tag="acme",
                       proxy_tag="Acme",        # default: the tag's own name
                       remark="batch 1")        # optional, on every profile
print(batch.summary())                         # 2 of 2 ready; 14 free proxies tagged 'Acme'.
for item in batch.planned:
    print(item.name, item.status.value, item.proxy.address if item.proxy else "")

# 2. Create: one at a time; a failure doesn't stop the rest.
results = ads.create_batch(batch, on_result=lambda r: print(r.name, r.outcome.value))
print(results_text(results))                   # tab-separated: pastes into a spreadsheet

# 3. Check each new profile's proxy (needs Playwright, see §4).
for r in results:
    if r.profile:
        print(r.name, ads.check_proxy(r.profile).text)   # ok (198.51.100.7) / failed: ERR_...
```

`check_proxy` also works on any existing profile: `ads.check_proxy("1234")`.

## 2. Quick start: command line

```powershell
adspower create-many "Shop 8" "Shop 9" -g Acme -t acme
adspower create-many --from-file names.txt -g Acme -t acme --proxy-tag Acme --remark "batch 1" --check
adspower check-proxy 1234
```

| Option | Meaning |
| --- | --- |
| `names` | the new profiles' names (any number) |
| `--from-file FILE` | also read names from FILE, one per line; blank lines and `#` comments are skipped |
| `-g/--group`, `-t/--tag` | where they go (both must exist) |
| `--proxy-tag TAG` | proxies must carry this tag (default: same as `--tag`) |
| `--remark TEXT` | remark on every new profile |
| `--check` | afterwards, check every new profile's proxy |
| `-y/--yes` | don't ask; required when there's no terminal to ask in |
| `--json` | machine-readable output: plan, results, proxy checks |

`create-many` prints the plan table and `N of M ready; K free proxies`,
then asks `Create N profile(s)? [y/N]` (default No). It exits with 0 if
everything was created (and every checked proxy works), and 1 otherwise.
`check-proxy` exits with 0 when the proxy works and 1 when it doesn't,
so scripts can branch on it.

## 3. Batch creation: the rules

| Plan status | When | Created? |
| --- | --- | --- |
| `ready` | new name, and a free proxy was reserved for it | yes |
| `already exists` | a profile with that name exists (ignoring upper/lower case) | no |
| `repeated` | the name appeared earlier in the list | no (created once) |
| `name too long` | over 100 characters, AdsPower's limit | no |
| `no free proxy` | free tagged proxies ran out before this name | no |

- **One unused proxy each.** Free = AdsPower says no profile uses it
  (`Proxy.in_use` is False) **and** this batch hasn't handed it out.
  Proxies are never shared.
- **Re-checked at creation.** `BatchCreator.run` re-reads the proxy list
  once before it starts. A planned proxy that was used in the meantime
  is swapped for another free one, and never for one reserved for a
  later name. With none left, that name is skipped with a message.
- **Idempotent.** Existing names are skipped, so running the same list
  twice creates nothing new.
- **Errors carry on.** An AdsPower error marks that name `failed` with
  AdsPower's message, and the rest continue.

## 4. Proxy check: how it works

```text
ads.check_proxy(profile)
  was it open already? ── remember
  ads.open_profile(profile) ─► OpenedBrowser (.puppeteer = ws:// address)
  check_browser(browser)
     fetch(ws, "https://api.ipify.org?format=json")   ← through the profile's proxy
        loaded  → parse_ip('{"ip": "..."}') → ProxyCheck(ok=True, ip=...)
        error   → error_code("net::ERR_...") → ProxyCheck(ok=False, error="ERR_...")
        other   → ProxyCheck(ok=False, error="unexpected answer")
  close it (only if this call opened it), wait until AdsPower says it's gone
```

- **Through the browser, not from Python.** The library never keeps
  proxy passwords (`Proxy` leaves them out on purpose), and the
  profile's browser is what actually uses the proxy. So the check runs
  inside that browser.
- **Playwright is optional.** It's the only part of the package that
  isn't standard library: `pip install "mrfactory-adspower[browser]"`.
  Without it, `check_proxy` raises `ProxyCheckUnavailable`, which names
  that command. You can also pass your own `fetch(ws, url) -> text`.
- **Only a real IP counts.** `parse_ip` uses `ipaddress.ip_address`, so
  a proxy's block page can't pass as working.
- **Third-party page.** ipify sees the proxy's IP, as every site does.
  Pass `url=` for a different page that answers `{"ip": "..."}`.

| `.text` | Means |
| --- | --- |
| `ok (198.51.100.7)` | it works; that's the exit IP |
| `failed: ERR_PROXY_CONNECTION_FAILED`, `ERR_TUNNEL_CONNECTION_FAILED`, ... | Chrome's network error: the proxy refused or didn't answer |
| `failed: unexpected answer` | something loaded, but not an IP |

## 5. The building blocks

For finer control (a Stop button, your own progress display):

| Name | Kind | Job |
| --- | --- | --- |
| `plan(names, existing, free)` | pure function | the plan, no API calls |
| `free_proxies(proxies)` | pure function | the unused ones |
| `BatchSettings(group, tag, proxy_tag, remark)` | frozen dataclass | where the profiles go |
| `Batch(settings, planned, free_count)` | frozen dataclass | `.ready`, `.summary()` |
| `BatchCreator(ads, on_result)` | class | `.run(planned, settings)`, `.stop()` (between profiles; safe from any thread) |
| `Created`, `Outcome`, `Planned`, `PlanStatus` | values | results; `.row()` for one table line |
| `results_text`, `summarize` | pure functions | table text; `"2 created, 1 skipped"` |
| `check_browser(browser, fetch=None, url=CHECK_URL)` | function | check an already-open browser |
| `ProxyCheck(ok, ip, error, profile)` | frozen dataclass | `.text` |
| `parse_ip`, `error_code` | pure functions | the parsing rules |

A program that opens profiles itself, such as Profile Runner's runner,
uses `check_browser` on the browser it already has, rather than
`check_proxy`, which opens and closes the profile by itself.

## 6. Design decisions

| Decision | Alternatives | Why | Cost |
| --- | --- | --- | --- |
| Pick proxies ourselves | AdsPower's `proxyid: "random"` | "random" may pick a used proxy; we need *unused* and *tagged* | two proxy-list reads per batch |
| Plan, then create | create directly | the caller sees every name's fate first; the CLI asks (default No) | an extra step |
| Pure `plan()` | logic inside `create_batch` | testable without AdsPower; reusable by any front end | the plan can go stale, hence the re-check |
| Playwright as an *optional extra* | a required dependency; a raw DevTools-protocol client | the rest of the package stays standard-library only; Playwright is well tested | one extra install for the check |
| Close only what we opened | always close | checking a profile you're using mustn't close it under you | one extra "is it open?" request |

## 7. Testing

| File | Covers | Stand-in |
| --- | --- | --- |
| `tests/test_batch.py` | plan statuses, proxy hand-out, swap-not-steal, failures, stop, `plan_batch` / `create_batch` request bodies | small `FakeAds`; `FakeApi` |
| `tests/test_proxycheck.py` | `parse_ip`, `error_code`, ok / error / block page, no-Playwright message, `check_proxy` opens and closes (and leaves an already-open profile open, and closes on a crash) | a fake `fetch`; `FakeApi` |
| `tests/test_cli.py` | `create-many` (plan shown, asks, `--yes`, `--from-file`, no terminal), `check-proxy` exit codes | `FakeApi`, patched `playwright_fetch` |

```powershell
python -m unittest discover -s tests -t .     # from packages/adspower
```

## 8. Found live

Run against the real AdsPower on 2026-10-09 with three new profiles
(names, IDs and IPs deliberately left out):

- Plan → create → check worked end to end. Each proxy check's exit IP
  matched the proxy assigned to that profile, every profile was closed
  afterwards, and AdsPower then showed all three proxies as in use, as
  the rules expect.
- A profile tag's spelling can differ from what you type (`acme` vs
  `Acme`). Lookups ignore case, and `BatchSettings.tag.name` keeps
  AdsPower's own spelling.

## 9. Exercises

1. Add `--names-only` to `create-many` that prints the plan and stops
   (a "dry run"). Which existing function already does all the work?
2. Make `check_proxy` also report how long the page took to load. Where
   would you measure it so that a fake `fetch` can still test it?
3. Write a test: two batches planned at the same time from the same free
   proxies, then created one after the other. What does the second one do?

**Self-check:** why is the proxy check done inside the profile's
browser instead of with `urllib` and the proxy's address?

## References

**Official**

- §3: AdsPower Local API, [New Profile V2](https://localapi-doc-en.adspower.com/docs/New-Profile-V2) (name ≤ 100 characters; `proxyid` or `user_proxy_config`; `"random"`) ✔
- §4: Playwright for Python, [`BrowserType.connect_over_cdp`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
- §4: Python docs, [`ipaddress.ip_address`](https://docs.python.org/3/library/ipaddress.html#ipaddress.ip_address)
- §4: [ipify API](https://www.ipify.org/) (`?format=json` → `{"ip": "..."}`; checked on 2026-10-09) ✔
- §4, §6: Python Packaging User Guide, [optional dependencies (extras)](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements)
- §5: Python docs, [`dataclasses`](https://docs.python.org/3/library/dataclasses.html), [`threading.Event`](https://docs.python.org/3/library/threading.html#event-objects)

**Other explanations**

- §3: Wikipedia, [Idempotence](https://en.wikipedia.org/wiki/Idempotence)
- §6: Martin Fowler, [Dependency Injection](https://martinfowler.com/articles/injection.html)

### Further learning

- Real Python, [Python's `ipaddress` module](https://realpython.com/python-ipaddress-module/)
- [Exercism Python track](https://exercism.org/tracks/python)
