"""The project's `.devtools.json`. Every key is optional.

    {
      "skip_dirs": ["node_modules", "dist", "target"],
      "links": {"ignore": ["https://github.com/me/private-repo"]},
      "scan": {
        "allow_paths": ["tests/fixtures/*"],
        "rules": [
          {"description": "delete call outside the cleaner", "globs": ["*.py"],
           "pattern": "shutil\\\\.rmtree", "except_paths": ["src/clean.py"]}
        ]
      }
    }

`rules` are extra, project-specific patterns, such as Disk_Cleanup's
"only two files may delete" rule. JSON is used because the workspace
supports Python 3.10, which has no TOML reader in the standard library.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

FILE_NAME = ".devtools.json"
DEFAULT_SKIP_DIRS = ("node_modules", "dist", "build", "target", "venv", ".venv", "__pycache__", ".git",
                     "graphify-out")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    description: str
    globs: tuple[str, ...]
    pattern: re.Pattern[str]
    except_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    skip_dirs: tuple[str, ...] = DEFAULT_SKIP_DIRS
    link_ignore: tuple[str, ...] = ()
    allow_paths: tuple[str, ...] = ()
    rules: tuple[Rule, ...] = field(default_factory=tuple)


def _strings(value: object, where: str) -> tuple[str, ...]:
    if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
        raise ConfigError(f"{FILE_NAME}: {where} must be a list of strings")
    return tuple(value)


def load(root: Path) -> Config:
    path = root / FILE_NAME
    if not path.is_file():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"{FILE_NAME}: not valid JSON ({e})") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{FILE_NAME}: the top level must be an object")
    links, scan = data.get("links", {}), data.get("scan", {})
    rules = []
    for i, r in enumerate(scan.get("rules", [])):
        if not (isinstance(r, dict) and isinstance(r.get("pattern"), str) and isinstance(r.get("description"), str)):
            raise ConfigError(f"{FILE_NAME}: scan.rules[{i}] needs a string 'description' and 'pattern'")
        try:
            rx = re.compile(r["pattern"])
        except re.error as e:
            raise ConfigError(f"{FILE_NAME}: scan.rules[{i}].pattern is not a valid regex ({e})") from e
        rules.append(Rule(r["description"], _strings(r.get("globs", ["*"]), f"scan.rules[{i}].globs"), rx,
                          _strings(r.get("except_paths", []), f"scan.rules[{i}].except_paths")))
    skip = data.get("skip_dirs")
    return Config(
        skip_dirs=DEFAULT_SKIP_DIRS + (_strings(skip, "skip_dirs") if skip is not None else ()),
        link_ignore=_strings(links.get("ignore", []), "links.ignore"),
        allow_paths=_strings(scan.get("allow_paths", []), "scan.allow_paths"),
        rules=tuple(rules),
    )
