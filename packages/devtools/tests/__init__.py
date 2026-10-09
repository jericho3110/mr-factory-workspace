"""Makes `mrfactory.devtools` (and `mrfactory.gitship`, whose scanner it reuses)
importable from the tests without installing them."""

import sys
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parent.parent.parent
for src in (_PACKAGES / "devtools" / "src", _PACKAGES / "gitship" / "src"):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
