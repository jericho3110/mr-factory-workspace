"""One function per subcommand.

Every command has the same shape, `cmd_x(ads, args) -> exit code`:
take the parsed arguments, call `AdsPower`, print the result, return
0 on success. Errors are *raised*, not printed; `app.main()` turns them
into messages and exit codes in one place.

`prompts` is imported as a module (`prompts.is_interactive()`), not as
names (`from .prompts import is_interactive`), so a test can replace
`prompts.is_interactive` once and every caller sees the replacement.
"""

from __future__ import annotations

import argparse

from ..client import AdsPower
from ..errors import AdsPowerError, AmbiguousProfile
from ..models import Profile
from . import prompts
from .output import (
    describe_profile,
    describe_proxy,
    print_groups,
    print_json,
    print_profiles,
    print_proxies,
    print_tags,
)

# --- the app ----------------------------------------------------------------


def cmd_open(ads: AdsPower, args: argparse.Namespace) -> int:
    exe = ads.open(args.path, wait=args.wait)
    print(f"Opened {exe}" + (" (ready)" if args.wait else ""))
    return 0


def cmd_status(ads: AdsPower, args: argparse.Namespace) -> int:
    running = ads.is_running()
    if args.json:
        print_json({"running": running, "api_url": ads.api.base_url})
    else:
        print(f"AdsPower is {'running' if running else 'not running'} ({ads.api.base_url})")
    return 0 if running else 1


# --- looking things up ------------------------------------------------------


def cmd_groups(ads: AdsPower, args: argparse.Namespace) -> int:
    print_groups(ads.groups(name=args.name), as_json=args.json)
    return 0


def cmd_tags(ads: AdsPower, args: argparse.Namespace) -> int:
    print_tags(ads.tags(name=args.name), as_json=args.json)
    return 0


def cmd_profiles(ads: AdsPower, args: argparse.Namespace) -> int:
    print_profiles(ads.profiles(group=args.group, tag=args.tag), as_json=args.json)
    return 0


def cmd_search(ads: AdsPower, args: argparse.Namespace) -> int:
    print_profiles(ads.search_profiles(args.text, group=args.group, tag=args.tag), as_json=args.json)
    return 0


def cmd_proxies(ads: AdsPower, args: argparse.Namespace) -> int:
    print_proxies(ads.proxies(tag=args.tag, unused=args.unused), as_json=args.json)
    return 0


# --- a profile's browser ----------------------------------------------------


def cmd_open_profile(ads: AdsPower, args: argparse.Namespace) -> int:
    profile = resolve_profile(ads, args)
    if profile is None:
        return 1
    browser = ads.open_profile(profile)
    if args.json:
        print_json({"profile": profile, "browser": browser})
    else:
        print(f"Opened {describe_profile(profile)}.")
        print("It stays open after this command ends. Close it in AdsPower, or with:")
        print(f"  adspower close-profile {profile.serial_number}")
    return 0


def cmd_close_profile(ads: AdsPower, args: argparse.Namespace) -> int:
    profile = resolve_profile(ads, args)
    if profile is None:
        return 1
    ads.close_profile(profile)
    if args.json:
        print_json({"closed": profile})
    else:
        print(f"Closed {describe_profile(profile)}.")
    return 0


# --- changing things --------------------------------------------------------


def cmd_set_proxy(ads: AdsPower, args: argparse.Namespace) -> int:
    """Look up everything, show the planned change, confirm, then make
    exactly one change request."""
    profile = resolve_profile(ads, args)
    if profile is None:
        return 1

    if args.no_proxy:
        new = None
    else:
        tag = args.proxy_tag or _only_tag(profile)
        new = ads.choose_proxy(tag=tag, proxy_id=_proxy_id(args.proxy))

    current = profile.proxy or "no proxy"
    planned = describe_proxy(new)
    if (new.url if new else "") == profile.proxy:
        print(f"{describe_profile(profile)} already uses {current}. Nothing to change.")
        return 0

    print(f"Profile: {describe_profile(profile)}")
    print(f"Proxy:   {current}  ->  {planned}")
    if not args.yes:
        if not prompts.is_interactive():
            raise AdsPowerError("Not changed: confirm with --yes when not running in a terminal.")
        if not prompts.confirm("Change it?"):
            print("Cancelled. Nothing was changed.")
            return 1

    ads.set_proxy(profile, new)
    if args.json:
        print_json({"profile": profile, "old_proxy": profile.proxy, "new_proxy": new})
    else:
        print(f"Done. {describe_profile(profile)} now uses {planned}.")
        if ads.is_profile_open(profile):
            print("Its browser is open: close and reopen it to use the new proxy.")
    return 0


def cmd_create(ads: AdsPower, args: argparse.Namespace) -> int:
    proxy = None
    if args.proxy:
        proxy_tag = args.proxy_tag or args.tag
        proxy = ads.choose_proxy(tag=proxy_tag, proxy_id=_proxy_id(args.proxy))

    profile = ads.create_profile(args.name, group=args.group, tag=args.tag, proxy=proxy, remark=args.remark)
    if args.json:
        print_json({"profile": profile, "proxy": proxy})
    else:
        print(f"Created {describe_profile(profile)}, tagged {', '.join(profile.tags)}.")
        print(f"Proxy: {describe_proxy(proxy)}")
    return 0


# --- shared helpers ---------------------------------------------------------


def resolve_profile(ads: AdsPower, args: argparse.Namespace) -> Profile | None:
    """The profile the user meant (`args.profile`, within `args.group`).

    If several match: in a terminal, ask which one; otherwise (a script,
    redirected input) list them and fail, so nothing waits forever for
    an answer that can't come. None means the user cancelled."""
    try:
        return ads.find_profile(args.profile, group=args.group)
    except AmbiguousProfile as e:
        if not prompts.is_interactive():
            print_profiles(e.matches[: prompts.MAX_CHOICES])
            raise
        return prompts.choose(e.matches, describe_profile, prompt="Which profile?")


def _only_tag(profile: Profile) -> str:
    """The proxy tag to use when none is given: the profile's own tag,
    if it has exactly one. Otherwise it's unclear, so ask for it."""
    if len(profile.tags) == 1:
        return profile.tags[0]
    have = ", ".join(profile.tags) or "no tags"
    raise AdsPowerError(
        f"{describe_profile(profile)} has {have}: pass --proxy-tag to say which proxies are allowed."
    )


def _proxy_id(choice: str) -> str | None:
    """--proxy takes 'auto' (pick one: None) or a proxy ID."""
    return None if choice.lower() == "auto" else choice
