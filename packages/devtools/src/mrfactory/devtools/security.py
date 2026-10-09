"""The security scan: code patterns (codescan.py) + gitship's file scan.

gitship's `scan_file` already knows secrets (API keys, tokens, private
keys), personal data (your home path, your email), real IP addresses,
files that must never be committed (.env, *.pem, browser Cookies) and
build output. It is reused here, not copied, so a new secret pattern
added there protects every project. gitship applies it to what is
*staged*; devtools applies it to *every project file*.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from mrfactory.gitship.scan import personal_patterns, scan_file

from .codescan import matches, scan_text
from .config import Config
from .files import project_files

TEXT_LIMIT = 1024 * 1024
SELF = ("*/mrfactory/devtools/codescan.py",)  # the scanner contains every pattern by definition


def _git_email(root: Path) -> str | None:
    try:
        r = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True)  # noqa: S603,S607
    except OSError:
        return None
    return r.stdout.strip() or None


def _read_text(path: Path) -> str | None:
    if path.stat().st_size > TEXT_LIMIT:
        return None
    data = path.read_bytes()
    return None if b"\0" in data else data.decode("utf-8", errors="replace")


def scan_project(root: Path, cfg: Config, env: Mapping[str, str] | None = None,
                 personal: bool = True) -> list[str]:
    """Every finding in the project, as readable lines. An empty list means clean."""
    env = os.environ if env is None else env
    patterns = personal_patterns(env.get("USERNAME") or env.get("USER"), _git_email(root)) if personal else []
    extra = [(r.description, r.globs, r.pattern, r.except_paths) for r in cfg.rules]
    findings: list[str] = []
    for path in project_files(root, cfg.skip_dirs):
        rel = path.relative_to(root).as_posix()
        if matches(rel, cfg.allow_paths):
            continue
        text = _read_text(path)
        findings += [str(f) for f in scan_file(rel, path.stat().st_size, text, patterns, cfg.allow_paths)]
        if text is not None and not matches(rel, SELF):
            findings += [str(f) for f in scan_text(rel, text, extra)]
    return findings
