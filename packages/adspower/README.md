# mrfactory.adspower

Opens the [AdsPower](https://www.adspower.com/) desktop app, looks up its
groups, profile tags, profiles, and proxies, and opens and creates
profiles, through AdsPower's
[Local API](https://localapi-doc-en.adspower.com/). Part of the
[mr-factory workspace](../../README.md): distribution `mrfactory-adspower`,
import `mrfactory.adspower`. No third-party dependencies.

📖 **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** explains how it's
layered and the concepts behind it.

## Setup

From the workspace root, after the shared setup in the
[workspace README](../../README.md#setup):

```powershell
pip install -e packages/adspower
```

Re-run it whenever `pyproject.toml` changes (for example, a new console
command); code changes need no reinstall. See
[why](../../docs/ARCHITECTURE.md#7-every-command-explained).

## Command line

```powershell
adspower --help                     # every command, with examples
adspower <command> --help           # options for one command
adspower --version                  # the installed version
```

| Command | What it does |
| --- | --- |
| `adspower open [--path EXE] [--wait SECONDS]` | Start AdsPower; with `--wait`, also wait until its API is ready |
| `adspower status` | Say whether AdsPower is running (exit code 0 = yes, 1 = no) |
| `adspower groups [-n TEXT]` | List groups, or only those whose name contains TEXT |
| `adspower tags [-n TEXT]` | List profile tags, or only those whose name contains TEXT |
| `adspower profiles [-g GROUP] [-t TAG]` | List profiles, optionally only one group's and/or one tag's |
| `adspower search TEXT [-g GROUP] [-t TAG]` | Profiles whose name, remark, serial number, or ID contains TEXT |
| `adspower open-profile PROFILE [-g GROUP]` | Open a profile's browser. It **stays open** after the command ends |
| `adspower close-profile PROFILE [-g GROUP]` | Close a profile's browser |
| `adspower proxies [-t TAG] [--unused]` | List proxies, optionally only those with a tag and/or not used by any profile |
| `adspower set-proxy PROFILE [-g GROUP] (--proxy auto\|ID \| --no-proxy) [--proxy-tag TAG] [--yes]` | Change an existing profile's proxy, only to one carrying the profile's tag. Shows current → new and asks first |
| `adspower create NAME -g GROUP -t TAG [--proxy auto\|ID] [--proxy-tag TAG] [--remark TEXT]` | Create a profile in a group, with a tag, optionally with a proxy |

`PROFILE` is a serial number, a profile ID, or part of its name or
remark. If several profiles match, you get a numbered list to pick from
(Enter cancels). When there's no terminal to ask in, the matches are
listed and the command fails instead.

Names of groups, tags, and profiles are matched ignoring upper/lower
case (`-t jericho` and `-t Jericho` are the same).

Every command also accepts:

- `--json` prints JSON instead of a table, for scripts.
- `--api-url URL` sets the Local API address (default `http://127.0.0.1:50325`, or `ADSPOWER_API_URL`).
- `--api-key KEY` is only needed if API security verification is on in AdsPower (or set `ADSPOWER_API_KEY`).

Everything except `open` needs AdsPower to be running. `python -m mrfactory.adspower ...`
works the same as `adspower ...` without installing the command.

### Typical flow

```powershell
adspower groups -n jer                         # which groups are there? -> Jericho
adspower tags -n jer                           # which tag? -> jericho
adspower search shop -g Jericho                # find the profile
adspower open-profile shop -g Jericho          # open it (pick from a list if several match)

adspower proxies -t Jericho --unused           # proxies ready to use
adspower create "Shop 8" -g Jericho -t jericho --proxy auto
adspower set-proxy 1234 --proxy auto          # swap #1234's proxy for an unused one with its tag
```

`set-proxy` shows the change first (`Proxy: socks5://old -> socks5://new`)
and asks `Change it? [y/N]`. Only `y` changes anything. In scripts (no
terminal) it refuses unless you add `--yes`. The proxy tag defaults to
the profile's own tag; if the profile has no tag or several, pass
`--proxy-tag`.

## Python

```python
from mrfactory.adspower import AdsPower, AmbiguousProfile

ads = AdsPower()
ads.open(wait=60)                                   # start AdsPower, wait for its API

ads.groups(name="jer")                              # [Group(id=..., name='Jericho'), ...]
ads.tags(name="jer")                                # [Tag(id=..., name='jericho'), ...]
ads.profiles(group="Jericho", tag="jericho")
ads.search_profiles("shop", group="Jericho")

try:
    profile = ads.find_profile("shop", group="Jericho")
except AmbiguousProfile as e:
    profile = e.matches[0]                          # or ask the user
browser = ads.open_profile(profile)                 # stays open after Python exits
browser.puppeteer                                   # ws://... for automation tools later
ads.close_profile(profile)

proxy = ads.choose_proxy(tag="Jericho")             # first unused proxy tagged Jericho
proxy = ads.choose_proxy(tag="Jericho", proxy_id="4322")   # or a specific one (must have the tag)
ads.create_profile("Shop 8", group="Jericho", tag="jericho", proxy=proxy)

profile = ads.find_profile("1234")                 # exact serial: one quick request
profile.proxy                                       # 'socks5://host:port' or '' (never the password)
ads.current_proxy(profile)                          # its Proxy List entry, or None
ads.set_proxy(profile, ads.choose_proxy(tag="jericho"))   # equip another tagged proxy
ads.set_proxy(profile, None)                        # remove the proxy
```

Every `group`, `tag`, and `profile` argument takes the object or its
name/ID. The data classes are `Group`, `Tag`, `Profile` (with `.tags`,
`.proxy`), `Proxy` (with `.tags`, `.in_use`, `.used_by`, `.url`; never
its password), and `OpenedBrowser` (debug port and automation addresses).
`set_proxy` itself doesn't check tags; choosing the proxy with
`choose_proxy(tag=...)` is what enforces the tag rule.

Errors all derive from `AdsPowerError`: `AdsPowerNotRunning`,
`AdsPowerApiError`, `AmbiguousProfile` (`.matches`), and the `NotFound`
family (`GroupNotFound`, `TagNotFound`, `ProfileNotFound`,
`ProxyNotFound`). `open()` raises `FileNotFoundError` if AdsPower isn't
installed where expected.

## Good to know

- **Opened profiles stay open.** The browser is started by the AdsPower
  app, not by this program, so it keeps running when the command ends,
  is cancelled, or crashes. That's the same as opening it by hand.
- **Groups and tags must already exist** for `create`. A misspelled tag
  is an error listing the real ones, never a quietly created new tag.
- **Proxy tags are set in the AdsPower app** (Proxies > Proxy List). The
  Local API can read a proxy's tags but can't set them.
- **Profile tags and proxy tags are separate lists** in AdsPower, even
  when they share a name (`jericho` vs `Jericho`). `create --proxy auto`
  looks for proxies tagged like the profile's tag; use `--proxy-tag` if
  the proxy tag is different.
- **A changed proxy applies the next time the browser opens.** If the
  profile is open, `set-proxy` reminds you to close and reopen it.
- **Questions need a real console.** The picker and `[y/N]` appear in
  PowerShell or Windows Terminal. Git Bash's default terminal counts as
  "no terminal", so use exact serial numbers and `--yes` there.
- **A new profile can take a minute to open the first time** while
  AdsPower downloads the browser version it needs. The error says so; try
  again shortly.
- **Errors never dump a traceback.** Known problems print `error: ...`
  (exit 1); Ctrl+C prints `Cancelled.` (exit 130); an unexpected bug
  prints a one-line message and saves the full details to
  `%LOCALAPPDATA%\mrfactory\adspower-crash.log`.

## How it finds AdsPower

It looks for `AdsPower Global\AdsPower Global.exe` under Program Files,
Program Files (x86), and `%LOCALAPPDATA%\Programs` (per-user installs),
then launches it directly. That's more reliable than finding and clicking
its icon on screen, so this package doesn't use `mrfactory.mouse_ext`.

## Layout

```text
CHANGELOG.md           what changed in each version
docs/ARCHITECTURE.md   module map, one command end to end, concepts, testing, recipe
src/mrfactory/adspower/
  __init__.py     public API
  __main__.py     `python -m mrfactory.adspower`
  client.py       AdsPower: groups, tags, profiles, open/close, proxies, set_proxy, create
  api.py          LocalApi: HTTP GET/POST, paging, rate limiting, retries
  models.py       Group, Tag, Profile, Proxy, OpenedBrowser
  matching.py     name/text matching rules (pure functions)
  errors.py       AdsPowerError and subclasses
  launcher.py     find_adspower, open_adspower, open_app
  cli/            the `adspower` command
    app.py          parser, entry point, safe exit
    commands.py     one cmd_* per subcommand
    prompts.py      picker, [y/N] confirm, terminal detection
    output.py       tables and JSON
tests/            unittest suite: fake API, no AdsPower or network needed
```

## Tests

From this package's folder, or `python scripts/test_all.py` from the workspace root:

```powershell
python -m unittest discover -s tests -t .
```

---

## References

- AdsPower Local API (official): <https://localapi-doc-en.adspower.com/>
- AdsPower's MCP server source (undocumented endpoints): <https://github.com/AdsPower/local-api-mcp-typescript>
- Design concepts and their sources: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#references)
