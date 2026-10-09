"""Which files belong to the project: what git would commit.

`git ls-files --cached --others --exclude-standard` lists tracked files
plus new files that .gitignore doesn't exclude. That's exactly what a
scan should look at: a secret in an ignored .env is safe, while a secret
in a new, not-yet-staged file is about to leak. Outside a git repo, the
folder is walked instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def project_files(root: Path, skip_dirs: tuple[str, ...]) -> list[Path]:
    git = shutil.which("git")
    if git:
        r = subprocess.run([git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],  # noqa: S603
                           cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            paths = [root / p for p in r.stdout.split("\0") if p]
            return [p for p in paths if p.is_file() and not set(p.relative_to(root).parts) & set(skip_dirs)]
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        found += [Path(folder) / f for f in files]
    return found
