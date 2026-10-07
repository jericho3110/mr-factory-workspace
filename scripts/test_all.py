"""Run every package's test suite, each in its own process.

    python scripts/test_all.py            # all packages
    python scripts/test_all.py adspower   # just the named package(s)

Each package runs separately, from its own folder, because every package
has a top-level `tests` package of its own. Running them in a single
process would make those names collide.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGES = Path(__file__).resolve().parent.parent / "packages"


def main(names: list[str]) -> int:
    packages = sorted(p for p in PACKAGES.iterdir() if (p / "tests").is_dir())
    if names:
        unknown = set(names) - {p.name for p in packages}
        if unknown:
            print(f"Unknown package(s): {', '.join(sorted(unknown))}")
            return 2
        packages = [p for p in packages if p.name in names]

    failed = []
    for package in packages:
        print(f"\n=== {package.name} ===", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=package,
        )
        if result.returncode != 0:
            failed.append(package.name)

    print(f"\n{len(packages) - len(failed)}/{len(packages)} packages passed"
          + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
