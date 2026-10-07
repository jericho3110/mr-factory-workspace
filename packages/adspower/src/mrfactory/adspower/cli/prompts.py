"""Asking the user things: is there someone to ask, pick one from a
list, yes/no confirmation.

All questions go through `ask(prompt)`, which defaults to `input()`, so
tests can supply answers and a GUI could supply its own dialog.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")

MAX_CHOICES = 20


def is_interactive() -> bool:
    """True if a person is at a terminal to answer questions; False for
    scripts, scheduled tasks, piped or redirected input.

    `isatty()` alone isn't enough on Windows: the NUL device (`< NUL`)
    also claims to be a terminal. There, a real console is one whose
    console mode can be read."""
    stdin = sys.stdin
    if stdin is None or not stdin.isatty():
        return False
    if sys.platform == "win32":
        return _is_windows_console(stdin)
    return True


def _is_windows_console(stream) -> bool:
    import ctypes
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(stream.fileno())
    except (OSError, ValueError):
        return False
    mode = ctypes.c_uint32()
    return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))


def choose(items: Sequence[T], describe: Callable[[T], str], prompt: str,
           ask: Callable[[str], str] | None = None) -> T | None:
    """Show a numbered list and return the chosen item, or None if the
    user just presses Enter. Shows at most MAX_CHOICES."""
    # Not `ask=input` in the signature: defaults are evaluated once, when
    # the function is defined, so a patched/replaced input() would be missed.
    ask = ask or input
    shown = items[:MAX_CHOICES]
    for number, item in enumerate(shown, start=1):
        print(f"  {number:>2}. {describe(item)}")
    if len(items) > len(shown):
        print(f"  ... and {len(items) - len(shown)} more; narrow the search to see them.")

    while True:
        answer = _ask(ask, f"{prompt} [1-{len(shown)}, Enter to cancel]: ")
        if not answer:
            print("Cancelled.")
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            return shown[int(answer) - 1]
        print(f"Please enter a number from 1 to {len(shown)}.")


def confirm(question: str, ask: Callable[[str], str] | None = None) -> bool:
    """Ask a yes/no question; only "y" or "yes" means yes. The default
    (just Enter) is no: a change only happens if it was clearly asked for."""
    answer = _ask(ask or input, f"{question} [y/N]: ")
    return answer.lower() in ("y", "yes")


def _ask(ask: Callable[[str], str], prompt: str) -> str:
    try:
        return ask(prompt).strip()
    except EOFError:  # input closed (Ctrl+Z / Ctrl+D): treat as "no answer"
        print()
        return ""
