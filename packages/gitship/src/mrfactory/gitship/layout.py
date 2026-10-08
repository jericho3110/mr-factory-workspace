"""Which repository does a change in this folder belong to?

The rules (from the global working instructions, section 1.1):

1. Inside a repo?                  -> use that repo; never create one inside it.
2. Not inside, but sub-folders are repos?
                                   -> this is a PARENT folder: never `git init` it;
                                      commit inside the sub-repo that holds the change.
3. No repos anywhere?              -> this folder is one project: init it here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .git import Git
from .runner import Runner, run

SKIP = {"venv", ".venv", "node_modules", "__pycache__", "dist", "build", ".git", "target"}
MAX_DEPTH = 4


class Kind(Enum):
    INSIDE = "inside a repo"
    PARENT = "a parent folder of other repos"
    NONE = "not in any repo"


@dataclass(frozen=True)
class Location:
    kind: Kind
    repo: Path | None             # INSIDE: the repo's top folder
    subrepos: tuple[Path, ...]    # PARENT: repos found below

    def advice(self) -> str:
        if self.kind is Kind.INSIDE:
            return f"commit in {self.repo}"
        if self.kind is Kind.PARENT:
            listed = "\n".join(f"  - {p}" for p in self.subrepos)
            return ("this folder holds other repos: do NOT `git init` it.\n"
                    f"Commit inside the repo that contains your change:\n{listed}")
        return "no repo here or below: `git init -b main`, then `gitship publish` to create a private GitHub repo"


def find_subrepos(start: Path, max_depth: int = MAX_DEPTH) -> list[Path]:
    """Folders below `start` that contain a `.git`, without descending into them."""
    found = []
    base_depth = len(start.parts)
    for folder, dirs, _files in os.walk(start):
        here = Path(folder)
        if here != start and (here / ".git").exists():
            found.append(here)
            dirs[:] = []  # a repo's own sub-folders belong to it
            continue
        if len(here.parts) - base_depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
    return sorted(found)


def locate(start: Path, runner: Runner = run) -> Location:
    top = Git(start, runner).toplevel()
    if top is not None:
        return Location(Kind.INSIDE, top, ())
    subs = find_subrepos(start)
    if subs:
        return Location(Kind.PARENT, None, tuple(subs))
    return Location(Kind.NONE, None, ())
