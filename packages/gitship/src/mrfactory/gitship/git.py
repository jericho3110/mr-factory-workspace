"""A small, typed wrapper around the git commands gitship needs.

Each method is one git command. `-z` output (entries separated by NUL
characters) is used wherever file names come back, because names can
contain spaces, quotes, or even newlines, and only NUL can't appear in one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runner import Completed, Runner, run

TEXT_LIMIT = 1024 * 1024  # files bigger than this aren't read for the content scan


class GitError(Exception):
    """A git command failed. The message includes git's own output."""


@dataclass
class Git:
    cwd: Path
    runner: Runner = run

    def raw(self, *args: str) -> Completed:
        return self.runner(["git", *args], self.cwd)

    def __call__(self, *args: str) -> str:
        """Run git and return stdout; raise GitError on a non-zero exit."""
        r = self.raw(*args)
        if not r.ok:
            raise GitError(f"git {' '.join(args)} failed:\n{r.tail()}")
        return r.stdout

    # ---- where are we ------------------------------------------------------
    def toplevel(self) -> Path | None:
        r = self.raw("rev-parse", "--show-toplevel")
        return Path(r.stdout.strip()) if r.ok else None

    def branch(self) -> str:
        return self("rev-parse", "--abbrev-ref", "HEAD").strip()

    def has_commits(self) -> bool:
        return self.raw("rev-parse", "--verify", "--quiet", "HEAD").ok

    def remotes(self) -> dict[str, str]:
        out = self.raw("remote", "-v").stdout
        return {line.split()[0]: line.split()[1] for line in out.splitlines() if line.endswith("(push)")}

    def config_get(self, key: str) -> str | None:
        r = self.raw("config", "--get", key)
        return r.stdout.strip() if r.ok else None

    def tags(self) -> set[str]:
        return set(self("tag", "--list").split())

    # ---- what changed --------------------------------------------------------
    def status(self) -> list[tuple[str, str]]:
        """(two-letter status, path) for every changed or untracked file."""
        out = self("status", "--porcelain=v1", "-z", "--untracked-files=all")
        entries, items = [], out.split("\0")
        i = 0
        while i < len(items):
            item = items[i]
            if len(item) > 3:
                code, path = item[:2], item[3:]
                entries.append((code, path))
                if code[0] in "RC":  # a rename/copy is followed by its old path: skip it
                    i += 1
            i += 1
        return entries

    def staged_paths(self) -> list[str]:
        """Files added or modified in the index (deletions have no content to scan)."""
        out = self("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
        return [p for p in out.split("\0") if p]

    def staged_size(self, path: str) -> int:
        return int(self("cat-file", "-s", f":{path}").strip())

    def staged_text(self, path: str) -> str | None:
        """The staged version of `path` as text, or None if binary or too large to scan."""
        if self.staged_size(path) > TEXT_LIMIT:
            return None
        text = self("show", f":{path}")
        return None if "\0" in text else text  # a NUL byte means binary

    def add(self, paths: list[str]) -> None:
        self("add", "--", *paths)  # "--": a file named "-f" stays a file name

    def ahead_behind(self) -> tuple[int, int] | None:
        """(commits only here, commits only on the upstream), or None without an upstream."""
        r = self.raw("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        if not r.ok:
            return None
        ahead, behind = r.stdout.split()
        return int(ahead), int(behind)
