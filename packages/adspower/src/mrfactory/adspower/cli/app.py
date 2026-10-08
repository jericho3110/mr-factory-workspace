"""The entry point: build the argument parser, run one command, and make
sure every way it can end produces a clear message and exit code.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from .. import __version__
from ..api import LocalApi
from ..client import AdsPower
from ..errors import AdsPowerError
from . import commands

EXAMPLES = """\
examples:
  adspower open --wait 60               start AdsPower and wait until it's ready
  adspower groups -n acm                groups whose name contains "acm"
  adspower tags                         every profile tag
  adspower profiles -g Acme          profiles in the "Acme" group
  adspower profiles -t acme          profiles tagged "acme"
  adspower search shop -g Acme       profiles in "Acme" whose name/remark/serial/ID contains "shop"
  adspower open-profile 1234            open profile #1234 (stays open after the command ends)
  adspower open-profile shop -g Acme search, then open; asks which one if several match
  adspower close-profile 1234           close its browser
  adspower proxies -t Acme --unused  proxies tagged "Acme" that no profile uses yet
  adspower set-proxy 1234 --proxy auto  give #1234 an unused proxy with the profile's tag (asks first)
  adspower set-proxy 1234 --proxy 4322  ...or that specific proxy (it must carry the tag)
  adspower set-proxy 1234 --no-proxy    remove its proxy
  adspower create "Shop 8" -g Acme -t acme
                                        new profile in group "Acme", tagged "acme", no proxy
  adspower create "Shop 8" -g Acme -t acme --proxy auto
                                        ...equipped with an unused proxy tagged "acme"
  adspower groups --json                machine-readable output (any command)

Group, tag, and profile names are matched ignoring upper/lower case.
AdsPower must be open for every command except "open".
If API security verification is on in AdsPower, pass --api-key or set
ADSPOWER_API_KEY.
"""

# Unexpected crashes are written here, so the full details aren't lost.
CRASH_LOG = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "mrfactory" / "adspower-crash.log"

# Options whose values must never be written anywhere (logs, crash reports).
SECRET_OPTIONS = ("--api-key",)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its exit code. Every way the command
    can end is handled here (an *exception boundary*), so it always
    exits cleanly with a message:

    - 0    success
    - 1    a known problem (AdsPower closed, group not found, ...)
    - 1    an unexpected bug: short message, details saved to CRASH_LOG
    - 130  cancelled with Ctrl+C (the usual code for "interrupted")

    Profiles already opened stay open in every case, because AdsPower
    owns their browsers, not this program.
    """
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        ads = AdsPower(LocalApi(base_url=args.api_url, api_key=args.api_key))
        return args.run(ads, args)
    except KeyboardInterrupt:  # a BaseException, so `except Exception` wouldn't catch it
        print("\nCancelled.", file=sys.stderr)
        return 130
    except (AdsPowerError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # a bug: don't show a raw traceback, but don't lose it either
        where = save_crash_report(argv)
        print(f"unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"Full details saved to {where}" if where else traceback.format_exc(), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    # Options every command accepts, so they can go after the command name.
    # allow_abbrev=False everywhere: argparse would otherwise also accept
    # prefixes like --api-k, which redact() below wouldn't recognize.
    common = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    common.add_argument("--json", action="store_true", help="print JSON instead of a table")
    common.add_argument("--api-url", metavar="URL",
                        help="Local API address (default: ADSPOWER_API_URL or http://127.0.0.1:50325)")
    common.add_argument("--api-key", metavar="KEY",
                        help="Local API key, if security verification is on (default: ADSPOWER_API_KEY)")

    parser = argparse.ArgumentParser(
        prog="adspower",
        allow_abbrev=False,
        description="Open AdsPower; look up groups, tags, profiles, and proxies; open, create, and re-proxy profiles.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", title="commands", metavar="<command>")

    def command(name: str, run: Callable, help: str) -> argparse.ArgumentParser:
        sub = subcommands.add_parser(name, parents=[common], help=help, allow_abbrev=False,
                                     description=help[0].upper() + help[1:] + ".")
        sub.set_defaults(run=run)
        return sub

    def profile_argument(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("profile", help="serial number, ID, or text from its name/remark")
        sub.add_argument("-g", "--group", metavar="GROUP", help="only look in this group (name or ID)")

    # The app
    open_ = command("open", commands.cmd_open, "start the AdsPower app")
    open_.add_argument("--path", help="AdsPower executable, if not in the default install location")
    open_.add_argument("--wait", type=float, default=0, metavar="SECONDS",
                       help="also wait up to SECONDS for AdsPower to be ready")
    command("status", commands.cmd_status, "check whether AdsPower is running")

    # Looking things up
    groups = command("groups", commands.cmd_groups, "list groups")
    groups.add_argument("-n", "--name", metavar="TEXT", help="only groups whose name contains TEXT")

    tags = command("tags", commands.cmd_tags, "list profile tags")
    tags.add_argument("-n", "--name", metavar="TEXT", help="only tags whose name contains TEXT")

    profiles = command("profiles", commands.cmd_profiles, "list profiles, optionally by group and/or tag")
    profiles.add_argument("-g", "--group", metavar="GROUP", help="only this group (name or ID)")
    profiles.add_argument("-t", "--tag", metavar="TAG", help="only profiles with this tag (name or ID)")

    search = command("search", commands.cmd_search, "find profiles by name, remark, serial number, or ID")
    search.add_argument("text", help="text to look for (case-insensitive)")
    search.add_argument("-g", "--group", metavar="GROUP", help="only search this group (name or ID)")
    search.add_argument("-t", "--tag", metavar="TAG", help="only search profiles with this tag")

    proxies = command("proxies", commands.cmd_proxies, "list proxies, optionally by tag")
    proxies.add_argument("-t", "--tag", metavar="TAG", help="only proxies with this tag")
    proxies.add_argument("--unused", action="store_true", help="only proxies no profile uses yet")

    # A profile's browser
    profile_argument(command("open-profile", commands.cmd_open_profile, "open a profile's browser"))
    profile_argument(command("close-profile", commands.cmd_close_profile, "close a profile's browser"))

    # Changing things
    set_proxy = command("set-proxy", commands.cmd_set_proxy, "change the proxy of an existing profile")
    profile_argument(set_proxy)
    choice = set_proxy.add_mutually_exclusive_group(required=True)
    choice.add_argument("--proxy", metavar="auto|ID",
                        help="'auto' = first unused proxy with the proxy tag, or a proxy ID that has the tag")
    choice.add_argument("--no-proxy", action="store_true", help="remove the profile's proxy")
    set_proxy.add_argument("--proxy-tag", metavar="TAG",
                           help="tag the proxy must have (default: the profile's tag, if it has exactly one)")
    set_proxy.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")

    create = command("create", commands.cmd_create, "create a profile in a group, with a tag")
    create.add_argument("name", help="the new profile's name")
    create.add_argument("-g", "--group", required=True, metavar="GROUP", help="group to put it in (must exist)")
    create.add_argument("-t", "--tag", required=True, metavar="TAG", help="profile tag to give it (must exist)")
    create.add_argument("--proxy", metavar="auto|ID",
                        help="equip a proxy: 'auto' = first unused one with the proxy tag, "
                             "or a proxy ID (default: no proxy)")
    create.add_argument("--proxy-tag", metavar="TAG", help="tag the proxy must have (default: same as --tag)")
    create.add_argument("--remark", default="", help="remark for the new profile")

    return parser


def save_crash_report(argv: Sequence[str]) -> Path | None:
    """Append the current exception's traceback to CRASH_LOG. Returns
    the path, or None if even that failed."""
    try:
        CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with CRASH_LOG.open("a", encoding="utf-8") as log:
            log.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S}  adspower {' '.join(redact(argv))}\n")
            log.write(traceback.format_exc())
        return CRASH_LOG
    except OSError:
        return None


def redact(argv: Sequence[str]) -> list[str]:
    """A copy of `argv` safe to write to a log: the values of secret
    options are replaced, in both `--api-key VALUE` and `--api-key=VALUE`
    form. The real key must never end up in a file on disk."""
    safe: list[str] = []
    hide_next = False
    for arg in argv:
        if hide_next:
            safe.append("***")
            hide_next = False
            continue
        name, has_value, _ = arg.partition("=")
        if name in SECRET_OPTIONS:
            safe.append(f"{name}=***" if has_value else arg)
            hide_next = not has_value
        else:
            safe.append(arg)
    return safe
