"""Makes `mrfactory.adspower` importable from the tests without
installing it (same approach as packages/mouse-ext/tests)."""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
