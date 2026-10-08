<!-- Each version repeats the Added/Changed/Fixed headings, as Keep a Changelog does. -->
<!-- markdownlint-disable MD024 -->

# Changelog

What changed in each version of `mrfactory-adspower`, newest first.
The format follows [Keep a Changelog](https://keepachangelog.com/), and
versions follow [Semantic Versioning](https://semver.org/): while the
version is `0.x`, any release may change how things work.

## Unreleased

## 0.5.0 (2026-10-09)

### Added

- **Duplicate scanner**: `name_key()` and `NameIndex`. Besides exact
  names, *similar* names (same apart from case, spaces, `-`, `_`, `.`)
  are now skipped as `similar name exists`, naming the existing profile
  (`Planned.existing`, `Planned.note`). `allow_similar=True` /
  `--allow-similar` restores exact-only matching.
- `BatchCreator.run` re-checks every name against a fresh list of the
  account's profiles right before creating, so running a batch twice, or
  a profile created elsewhere after the plan, never makes a duplicate.

### Changed

- `BatchCreator.run` keeps only proxies that really carry the proxy tag
  (`Proxy.has_tag`), whatever the plan or the API filter returned.
- `create-many`'s plan table shows which profile a duplicate clashes with.

## 0.4.0 (2026-10-09)

### Added

- **Batch creation** (`batch.py`): `AdsPower.plan_batch()` and
  `create_batch()`, plus the building blocks `plan`, `free_proxies`,
  `BatchCreator` (with `stop()`), `BatchSettings`, `Batch`, `Created`,
  `results_text`, `summarize`. Every new profile gets its own unused
  tagged proxy; existing, repeated and too-long names are skipped;
  proxies are re-checked at creation time and never shared.
- **Proxy check** (`proxycheck.py`): `AdsPower.check_proxy()` opens a
  profile, loads `api.ipify.org` through its proxy, and closes it again
  (only if it opened it); `check_browser`, `parse_ip`, `error_code`,
  `ProxyCheck`, `ProxyCheckUnavailable`.
- Commands `adspower create-many` (plan, confirm, create, `--check`,
  `--from-file`, `--remark`) and `adspower check-proxy`.
- Optional extra `[browser]` (Playwright), needed only by the proxy
  check. The rest of the package stays standard-library only.
- docs/BATCH_AND_PROXY_CHECK.md.

### Added

- `adspower --version` and `mrfactory.adspower.__version__`, read from
  the installed metadata so the version lives only in `pyproject.toml`.
- `ConfigError` for invalid settings.

### Security

- The crash log no longer records the API key: `--api-key` values are
  replaced with `***` (both `--api-key X` and `--api-key=X`), and option
  abbreviations (`--api-k`) are rejected so they can't slip past.
- `--api-url` / `ADSPOWER_API_URL` must be `http://` or `https://`;
  `urllib` would otherwise also open `file://` URLs.
- Plain `http://` is accepted only for this machine (`127.0.0.1`,
  `localhost`, `::1`). A remote API must use `https://`, so the API key
  is never sent unencrypted over a network.
- The API key header is no longer forwarded if the server answers with a
  redirect (`add_unredirected_header`).
- Examples and test data use neutral names (`Acme`) and reserved
  documentation IPs (RFC 5737, `203.0.113.x`) instead of real ones.

### Fixed

- Paging stops with an error after 1000 full pages instead of looping
  forever if the API ignored the page number.
- The crash log records the arguments `main()` was given, not `sys.argv`.

## 0.3.0 (2026-10-07)

### Added

- `adspower set-proxy PROFILE (--proxy auto|ID | --no-proxy)` and
  `AdsPower.set_proxy()` change an existing profile's proxy. The new proxy
  must carry the profile's tag (or `--proxy-tag`). The CLI shows
  current → new and asks `[y/N]` (or takes `--yes`; required without a terminal).
- `AdsPower.current_proxy()`, `Profile.proxy` (`type://host:port`, never
  the password), `Proxy.used_by`, `Proxy.url`, `Profile.has_tag()`.
- `matching.py`: the name/text matching rules as pure functions.
- Workspace-wide linting with Ruff (`ruff.toml`).

### Changed

- `find_profile` looks up serial numbers and IDs on AdsPower's side:
  ~0.4 s instead of ~3 s (it used to download every profile).
- The CLI is now a package, `cli/` (`app`, `commands`, `prompts`,
  `output`), instead of one `cli.py`. The `adspower` command and
  `python -m mrfactory.adspower` are unchanged.
- Endpoint paths are constants at the top of `client.py`.

### Fixed

- On Windows, input redirected from `NUL` was treated as a terminal;
  now only a real console counts as interactive.

## 0.2.0 (2026-10-07)

### Added

- `tags`, `open-profile`, `close-profile`, `proxies`, `create` commands
  and the matching `AdsPower` methods.
- `groups -n TEXT`; `profiles`/`search` filter by `-t TAG`.
- Picker when several profiles match (terminal only).
- Safe exit: clear errors, Ctrl+C → exit 130, unexpected errors logged to
  `%LOCALAPPDATA%\mrfactory\adspower-crash.log`.

### Changed

- Profiles come from the v2 list API, which includes tags.

### Fixed

- `open-profile ""` no longer matches every profile.
- A clear hint when a profile can't open because AdsPower is still
  downloading its browser.

## 0.1.0 (2026-10-06)

### Added

- `adspower` command with `open`, `status`, `groups`, `profiles`, `search`;
  `--json` output; rate limiting and retries for the Local API.
- Find and launch the AdsPower app (`adspower open`), replacing the
  earlier single-purpose `open-adspower` command.
