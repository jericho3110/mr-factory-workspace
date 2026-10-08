"""Throwaway git repositories for the tests.

Real `git` runs against temp folders, so the tests exercise real commits
and real pushes. The "GitHub" remote is a local *bare* repository (a repo
with no working files, exactly what a server stores), so nothing touches
the network. `gh` (GitHub's CLI) is faked: see FakeGh.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from mrfactory.gitship.runner import Completed, run

GIT = shutil.which("git") or "git"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout  # noqa: S603


class TempRepos:
    """A working repo `work` whose 'origin' is a bare repo `remote`. Call cleanup() when done."""

    def __init__(self, with_remote: bool = True) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # git makes object files read-only
        base = Path(self._tmp.name)
        self.work = base / "work"
        self.remote = base / "remote.git"
        self.work.mkdir()
        git(self.work, "init", "-q", "-b", "main")
        git(self.work, "config", "user.name", "Test User")
        git(self.work, "config", "user.email", "test@users.noreply.github.com")
        git(self.work, "config", "core.autocrlf", "false")
        if with_remote:
            git(base, "init", "-q", "--bare", "-b", "main", str(self.remote))
            git(self.work, "remote", "add", "origin", str(self.remote))

    def write(self, rel: str, text: str) -> Path:
        path = self.work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit_all(self, message: str = "Add files") -> None:
        git(self.work, "add", "--all")
        git(self.work, "commit", "-q", "-m", message)

    def remote_log(self) -> str:
        return git(self.remote, "log", "--oneline", "--all") if self.remote.exists() else ""

    def cleanup(self) -> None:
        self._tmp.cleanup()


class FakeGh:
    """A Runner: real git, recorded-and-answered gh. `answers` maps an argv prefix to a Completed."""

    def __init__(self, answers: dict[tuple[str, ...], Completed] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.answers = answers or {}

    def __call__(self, argv: Sequence[str], cwd: Path) -> Completed:
        if argv[0] != "gh":
            return run(argv, cwd)
        self.calls.append(list(argv))
        for prefix, answer in sorted(self.answers.items(), key=lambda kv: -len(kv[0])):
            if tuple(argv[: len(prefix)]) == prefix:
                return answer
        return Completed(1, "", "FakeGh: no answer configured")


OK = Completed(0, "", "")
