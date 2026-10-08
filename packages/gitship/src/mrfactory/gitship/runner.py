"""The one place that starts other programs.

Every git, gh and check command goes through a `Runner`: a function that
takes an argument list and a folder and returns a `Completed`. The real
one is `run` below; tests pass a fake, so they can check exactly which
commands would run without touching GitHub (dependency injection).

Arguments are always a list and never pass through a shell, so nothing in
a file name, branch name or commit message can become an extra command.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def tail(self, chars: int = 2000) -> str:
        """The end of the output: where errors usually are."""
        return (self.stdout + self.stderr)[-chars:]


Runner = Callable[[Sequence[str], Path], Completed]


def run(argv: Sequence[str], cwd: Path) -> Completed:
    """Run a program and capture its output. A missing program is exit code 127, like a shell."""
    # shutil.which finds "gh.exe" / "npm.cmd" on Windows, where a bare name may not resolve.
    program = shutil.which(argv[0]) or argv[0]
    try:
        proc = subprocess.run(  # noqa: S603 - argument list, no shell; see the module docstring
            [program, *argv[1:]], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        return Completed(127, "", f"{argv[0]}: not found (is it installed and on PATH?)")
    return Completed(proc.returncode, proc.stdout, proc.stderr)
