"""The `devtools` command.

    devtools scan                 security scan: code patterns, secrets, personal data, never-commit files
    devtools links                every Markdown link: local files exist, web links load
    devtools links --offline      local links only (no network)
    devtools check                scan + links; exit code 0 only if both pass
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, config
from .codescan import matches
from .files import project_files
from .links import check_local, check_web
from .security import scan_project


def run_scan(root: Path, cfg: config.Config, personal: bool) -> int:
    findings = scan_project(root, cfg, personal=personal)
    for f in findings:
        print(f"FINDING: {f}")
    print(f"security: {len(findings)} finding(s)")
    return 1 if findings else 0


def run_links(root: Path, cfg: config.Config, offline: bool) -> int:
    md = [p for p in project_files(root, cfg.skip_dirs) if p.suffix.lower() == ".md"
          and not matches(p.relative_to(root).as_posix(), cfg.allow_paths)]
    broken = check_local(md, root)
    for b in broken:
        print(b)
    dead = 0
    checked = 0
    if not offline:
        results = check_web(md, root, cfg.link_ignore)
        checked = len(results)
        for r in results:
            if not r.status.startswith("ok"):
                print(f"{r.status:12} {r.url}  ({', '.join(r.sources)})")
        dead = sum(r.dead for r in results)
    print(f"links: {len(md)} Markdown files, {checked} web links checked, {dead} dead, {len(broken)} broken local")
    return 1 if dead or broken else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="devtools", description="Security scan and link check for any project.")
    p.add_argument("--version", action="version", version=f"devtools {__version__}")
    p.add_argument("-C", dest="root", default=".", help="project folder (default: here)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan", help="code patterns, secrets, personal data, never-commit files")
    s.add_argument("--no-personal", action="store_true", help="skip the user-name / email check")
    lk = sub.add_parser("links", help="check Markdown links")
    lk.add_argument("--offline", action="store_true", help="local links only, no network")
    c = sub.add_parser("check", help="scan + links")
    c.add_argument("--offline", action="store_true", help="local links only, no network")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        cfg = config.load(root)
    except config.ConfigError as e:
        print(f"devtools: {e}", file=sys.stderr)
        return 2
    if args.command == "scan":
        return run_scan(root, cfg, personal=not args.no_personal)
    if args.command == "links":
        return run_links(root, cfg, args.offline)
    scan_code = run_scan(root, cfg, personal=True)
    links_code = run_links(root, cfg, args.offline)
    return 1 if scan_code or links_code else 0
