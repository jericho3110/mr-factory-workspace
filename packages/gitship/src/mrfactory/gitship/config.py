"""The repo's `.gitship.json`: which checks gate a commit, and a few options.

    {
      "checks": [["ruff", "check", "."], ["python", "scripts/test_all.py"]],
      "trailer": "Co-Authored-By: Name <noreply@example.com>",
      "allow": ["tests/fixtures/*"],
      "changelog": "CHANGELOG.md"
    }

Why JSON and not TOML? The workspace supports Python 3.10, and `tomllib`
(TOML in the standard library) only arrived in 3.11. JSON needs nothing.

Each check is an argument LIST, run without a shell, so a config file
can't smuggle in `&& del ...`. Only exit codes decide pass or fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

FILE_NAME = ".gitship.json"


class ConfigError(Exception):
    """The config file is missing a required shape or has the wrong types."""


@dataclass(frozen=True)
class Config:
    checks: tuple[tuple[str, ...], ...] = ()
    trailer: str | None = None
    allow: tuple[str, ...] = field(default_factory=tuple)
    changelog: str = "CHANGELOG.md"


def load(root: Path) -> Config:
    """Read `.gitship.json` from the repo root; a missing file means "no checks configured"."""
    path = root / FILE_NAME
    if not path.is_file():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{FILE_NAME}: not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{FILE_NAME}: the top level must be an object {{...}}")

    checks = data.get("checks", [])
    if not (isinstance(checks, list)
            and all(isinstance(c, list) and c and all(isinstance(a, str) for a in c) for c in checks)):
        raise ConfigError(f'{FILE_NAME}: "checks" must be a list of argument lists, e.g. [["ruff", "check", "."]]')
    allow = data.get("allow", [])
    if not (isinstance(allow, list) and all(isinstance(a, str) for a in allow)):
        raise ConfigError(f'{FILE_NAME}: "allow" must be a list of path patterns')
    trailer = data.get("trailer")
    if trailer is not None and not isinstance(trailer, str):
        raise ConfigError(f'{FILE_NAME}: "trailer" must be a string')
    changelog = data.get("changelog", "CHANGELOG.md")
    if not isinstance(changelog, str):
        raise ConfigError(f'{FILE_NAME}: "changelog" must be a string')
    return Config(tuple(tuple(c) for c in checks), trailer, tuple(allow), changelog)
