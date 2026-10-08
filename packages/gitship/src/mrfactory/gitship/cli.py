"""The `gitship` command. Run `gitship --help` or `gitship <command> --help`.

The CLI only turns arguments into calls on workflow.py / release.py and
their errors into messages and exit codes; everything can also be done
from Python.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, config, release, workflow
from .layout import locate
from .runner import run

EPILOG = """examples:
  gitship where                                   which repo does this folder belong to?
  gitship check                                   run the checks + scan what's staged
  gitship ship -F msg.txt src/a.py docs/a.md      stage these, check, scan, commit, push
  gitship ship -m "Add proxy picker" --all        the same for every change (asks first)
  gitship push                                    push the current branch (never forces)
  gitship publish                                 create a PRIVATE GitHub repo and push
  gitship release 0.2.0 --asset dist/app.exe      tag, upload with SHA256SUMS, verify the download
"""


def _message(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.message


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gitship", description="Check, scan, commit, push, publish and release safely.",
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"gitship {__version__}")
    p.add_argument("-C", dest="cwd", default=".", help="run as if started in this folder (default: here)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("where", help="say which repo this folder belongs to (or that it's a parent folder)")
    sub.add_parser("check", help="run the configured checks and scan what's staged; commits nothing")

    s = sub.add_parser("ship", help="stage -> message rules -> scan -> checks -> commit -> push")
    msg = s.add_mutually_exclusive_group(required=True)
    msg.add_argument("-m", "--message", help="commit message (summary line; use -F for a body)")
    msg.add_argument("-F", "--file", help="read the commit message from this file")
    s.add_argument("paths", nargs="*", help="files to stage (default: only what's already staged)")
    s.add_argument("--all", action="store_true", help="stage every change, including new files")
    s.add_argument("--no-push", action="store_true", help="commit only")
    s.add_argument("--no-checks", action="store_true", help="allow committing when no checks are configured")
    s.add_argument("-y", "--yes", action="store_true", help="don't ask before committing")

    sub.add_parser("push", help="push the current branch; on rejection fetch and explain (never forces)")

    pub = sub.add_parser("publish", help="create the GitHub repo (PRIVATE by default) and push")
    pub.add_argument("--name", help="repo name (default: the folder name in kebab-case)")
    pub.add_argument("--public", action="store_true", help="make it public (scans all history; asks for the name)")
    pub.add_argument("--description", default="", help="one-line description shown on GitHub")
    pub.add_argument("-y", "--yes", action="store_true", help="don't ask (private repos only)")

    r = sub.add_parser("release", help="tag a version, upload assets + SHA256SUMS, verify the download")
    r.add_argument("version", help="SemVer version without the v, e.g. 0.2.0")
    r.add_argument("--asset", action="append", default=[], type=Path, help="file to attach (repeatable)")
    r.add_argument("--title", help="release title (default: '<repo folder> <version>')")
    r.add_argument("--dry-run", action="store_true", help="show the plan; create nothing")
    r.add_argument("-y", "--yes", action="store_true", help="don't ask before publishing")
    return p


def _release(args: argparse.Namespace, cwd: Path) -> int:
    top = workflow.find_repo(cwd, run)[1]
    cfg = config.load(top)
    plan = release.plan(cwd, args.version, args.asset, title=args.title, changelog=cfg.changelog)
    print(f"  tag: {plan.tag} on {plan.branch}\n  title: {plan.title}")
    for a in plan.assets:
        print(f"  asset: {a.name}  sha256 {a.sha256}")
    print("  notes:\n" + "\n".join(f"    {line}" for line in plan.notes.splitlines()))
    if args.dry_run:
        print("dry run: nothing created.")
        return 0
    if not args.yes and not workflow.confirm(f"Publish release {plan.tag}?", input):
        print("cancelled; nothing created.")
        return 1
    url = release.publish(plan, top)
    print(f"  released {url}")
    problems = release.verify(plan, top)
    for problem in problems:
        print(f"  VERIFY FAILED: {problem}")
    if not problems:
        print(f"  verified: {len(plan.assets)} asset(s) re-downloaded, hashes match")
    return 1 if problems else 0


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    args = build_parser().parse_args(argv)
    cwd = Path(args.cwd).resolve()
    try:
        if args.command == "where":
            loc = locate(cwd)
            print(f"{cwd} is {loc.kind.value}: {loc.advice()}")
        elif args.command == "check":
            git, root = workflow.find_repo(cwd, run)
            cfg = config.load(root)
            workflow.run_checks(cfg, root, run, print)
            findings = workflow.scan_staged(git, cfg, os.environ)
            for f in findings:
                print(f"  FINDING: {f}")
            print(f"  {len(cfg.checks)} check(s) passed; scan: {len(findings)} finding(s)")
            return 1 if findings else 0
        elif args.command == "ship":
            workflow.ship(cwd, _message(args), args.paths, stage_all=args.all, push=not args.no_push,
                          yes=args.yes, allow_unchecked=args.no_checks)
        elif args.command == "push":
            git, _root = workflow.find_repo(cwd, run)
            workflow.push_branch(git, print)
        elif args.command == "publish":
            workflow.publish(cwd, args.name, public=args.public, description=args.description, yes=args.yes)
        elif args.command == "release":
            return _release(args, cwd)
    except (workflow.ShipError, release.ReleaseError, config.ConfigError) as e:
        print(f"gitship: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ngitship: interrupted", file=sys.stderr)
        return 130
    return 0
