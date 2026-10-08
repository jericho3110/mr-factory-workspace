"""Commit message rules (pure functions, no I/O).

The rules, from docs/CONVENTIONS.md section 7:

    Add proxy picker                       <- summary: imperative, <= 72 chars, no period
                                           <- blank line
    Why the change was made ...            <- body
    - related change                       <- bullets
    Verified: tests pass                   <- how it was verified
                                           <- blank line
    Co-Authored-By: ...                    <- trailer(s), if any

A package prefix ("adspower: Add x") is fine; a Conventional-Commits
type prefix ("feat: add x") is not, because the workspace doesn't use them.
"""

from __future__ import annotations

import re

MAX_SUMMARY = 72
CONVENTIONAL_TYPES = {"feat", "fix", "chore", "docs", "refactor", "test", "tests", "style", "perf", "build", "ci"}
_PREFIX = re.compile(r"^(?P<prefix>[\w.-]+)(\([^)]*\))?!?:\s+(?P<rest>.*)$")
_PAST_TENSE = re.compile(r"^(added|fixed|updated|changed|removed|refactored|improved|created|deleted)\b", re.I)


def split_prefix(summary: str) -> tuple[str | None, str]:
    """'adspower: Add x' -> ('adspower', 'Add x'); 'Add x' -> (None, 'Add x')."""
    m = _PREFIX.match(summary)
    if not m:
        return None, summary
    return m.group("prefix"), m.group("rest")


def problems(message: str) -> list[str]:
    """Everything wrong with `message`. An empty list means it's good."""
    lines = message.strip("\n").splitlines()
    if not lines or not lines[0].strip():
        return ["the message is empty"]
    summary = lines[0]
    found = []
    if len(summary) > MAX_SUMMARY:
        found.append(f"summary is {len(summary)} characters; keep it at {MAX_SUMMARY} or fewer")
    if summary.rstrip().endswith("."):
        found.append("summary ends with a period; drop it")
    prefix, rest = split_prefix(summary)
    if prefix and prefix.lower() in CONVENTIONAL_TYPES:
        found.append(f"'{prefix}:' is a Conventional Commits prefix; write 'Add x', or 'package: Add x'")
    if _PAST_TENSE.match(rest):
        found.append("summary is in the past tense; use the imperative ('Add', not 'Added')")
    if rest[:1].islower():
        found.append("summary should start with a capital letter")
    if len(lines) > 1 and lines[1].strip():
        found.append("put a blank line between the summary and the body")
    return found


def with_trailer(message: str, trailer: str | None) -> str:
    """Append `trailer` (e.g. a Co-Authored-By line) once, after a blank line."""
    message = message.rstrip("\n")
    if not trailer or trailer in message:
        return message + "\n"
    return f"{message}\n\n{trailer}\n"
