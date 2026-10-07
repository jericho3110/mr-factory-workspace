"""Open desktop applications, starting with AdsPower.

Launching the executable directly is more reliable than finding and
double-clicking its icon: it works whether or not the icon is visible,
and doesn't depend on screen layout or a template image.

The command line (`adspower open`) lives in cli.py.
"""

from __future__ import annotations

import os
from pathlib import Path

ADSPOWER_EXE = Path("AdsPower Global") / "AdsPower Global.exe"


def adspower_candidates() -> list[Path]:
    """Where the AdsPower installer puts the executable: per-machine
    (Program Files) or per-user (AppData\\Local\\Programs)."""
    env = os.environ.get
    roots = [env("ProgramFiles"), env("ProgramFiles(x86)")]
    if env("LOCALAPPDATA"):
        roots.append(str(Path(env("LOCALAPPDATA")) / "Programs"))
    return [Path(root) / ADSPOWER_EXE for root in roots if root]


def find_adspower() -> Path | None:
    return next((p for p in adspower_candidates() if p.is_file()), None)


def open_app(path: str | Path) -> Path:
    """Start the application at `path` (detached; returns immediately)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Application not found: {path}")
    os.startfile(path)
    return path


def open_adspower(path: str | Path | None = None) -> Path:
    """Open AdsPower, from `path` if given, otherwise from its usual
    install location."""
    exe = Path(path) if path else find_adspower()
    if exe is None:
        searched = "\n  ".join(str(p) for p in adspower_candidates())
        raise FileNotFoundError(
            f"AdsPower not found. Looked in:\n  {searched}\n"
            "Pass its path explicitly (--path on the command line)."
        )
    return open_app(exe)

