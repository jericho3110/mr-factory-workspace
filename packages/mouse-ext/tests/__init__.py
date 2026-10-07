"""Makes `mrfactory.mouse_ext` importable from the tests without installing
it, the same trick the Natural project's tests use. If `natural_mouse`
itself isn't installed in the active venv either, fall back to the
Natural project's src/ (a sibling of the workspace root) so the tests
still run."""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# packages/mouse-ext -> packages -> workspace root -> its parent, where Natural lives
_NATURAL_SRC = _ROOT.parents[2] / "Natural" / "src"
if importlib.util.find_spec("natural_mouse") is None and _NATURAL_SRC.is_dir():
    sys.path.append(str(_NATURAL_SRC))
