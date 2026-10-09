"""Dangerous code patterns, per language (pure: text in, findings out).

Each rule is a construct that classically leads to code injection, remote
code execution (RCE), memory bugs or data leaks. Collected from the six
project scanners this package replaces.

A line opts out of the rules with a trailing comment containing
`security-scan: allow` and a reason, so every exception is visible in review.
Comment lines are skipped: a comment describing `eval(` isn't a use of it.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from dataclasses import dataclass

ALLOW = "security-scan: allow"
COMMENT_STARTS = ("#", "//", "*", "/*", "<#", "rem ", "REM ", "::", "--")

PY = ("*.py",)
JS = ("*.js", "*.mjs", "*.cjs", "*.ts", "*.tsx", "*.jsx")
C = ("*.c", "*.h", "*.cpp", "*.hpp", "*.cc")
ANY_CODE = PY + JS + C + ("*.go", "*.rs", "*.java", "*.cs")

# (description, file globs, regex)
RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("shell execution (command injection)", PY, r"shell\s*=\s*True|os\.system\(|os\.popen\("),
    ("dynamic code evaluation", PY, r"(?<![\w.])eval\(|(?<![\w.])exec\("),
    ("unsafe deserialization", PY, r"pickle\.loads?\(|marshal\.loads?\(|yaml\.load\((?!.*SafeLoader)"),
    ("SQL built from a string (use placeholders)", PY,
     r"\.execute(many|script)?\(\s*(f[\"']|[\"'][^\"']*[\"']\s*(%|\+|\.format))"),
    ("TLS verification disabled", PY + ("*.go", "*.cs", "*.java", "*.rs") + JS,
     r"verify\s*=\s*False|InsecureSkipVerify:\s*true|ServerCertificateCustomValidationCallback"
     r"|danger_accept_invalid|rejectUnauthorized:\s*false"),
    ("HTML injection sink (use textContent)", JS, r"\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML|document\.write\("),
    ("dynamic code evaluation", JS, r"(?<![\w.])eval\(|new Function\("),
    ("shell execution", ("*.go",), r"exec\.Command\(\s*\"(sh|bash|cmd|cmd\.exe|powershell|pwsh)\""),
    ("shell execution", ("*.rs",), r"Command::new\(\s*\"(sh|bash|cmd|cmd\.exe|powershell|pwsh)\""),
    ("shell execution", ("*.java",), r"Runtime\.getRuntime\(\)\.exec"),
    ("shell execution", ("*.cs",), r"UseShellExecute\s*=\s*true"),
    ("unsafe deserialization", ("*.java",), r"ObjectInputStream|XMLDecoder"),
    ("unsafe deserialization", ("*.cs",), r"BinaryFormatter|NetDataContractSerializer|SoapFormatter|TypeNameHandling"),
    ("unbounded C string copy", C, r"\b(strcpy|strcat|sprintf|vsprintf|gets|wcscpy|wcscat|swprintf|lstrcpy\w*)\s*\("),
    ("unchecked number parsing", C, r"\b(atoi|atol|_wtoi)\s*\("),
    ("shell execution from C/C++", C, r"\b(system|_wsystem|popen|_popen|WinExec)\s*\("),
    ("dynamic code evaluation", ("*.ps1",), r"Invoke-Expression|(?<![\w-])iex\b|\.DownloadString\("),
    ("download piped into a shell", ("*.sh", "*.bash"), r"(curl|wget)[^|]*\|\s*(ba)?sh\b"),
    ("listener on all network interfaces", ANY_CODE, r"[\"']0\.0\.0\.0[\"']|ListenAndServe\(\":"),
)
_COMPILED = [(d, g, re.compile(p)) for d, g, p in RULES]


@dataclass(frozen=True)
class CodeFinding:
    path: str
    line: int
    description: str
    text: str

    def __str__(self) -> str:
        return f"{self.description}: {self.path}:{self.line}: {self.text}"


def matches(path: str, globs: Iterable[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, g) or fnmatch.fnmatch(path, g) for g in globs)


def scan_text(path: str, text: str,
              extra: Iterable[tuple[str, tuple[str, ...], re.Pattern[str], tuple[str, ...]]] = ()) -> list[CodeFinding]:
    """Findings for one file. `extra` adds project rules: (description, globs, regex, except_paths)."""
    rules = [(d, g, rx) for d, g, rx in _COMPILED if matches(path, g)]
    rules += [(d, g, rx) for d, g, rx, exc in extra if matches(path, g) and not matches(path, exc)]
    if not rules:
        return []
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if ALLOW in line or stripped.startswith(COMMENT_STARTS):
            continue
        for desc, _globs, rx in rules:
            if rx.search(line):
                found.append(CodeFinding(path, n, desc, stripped[:120]))
    return found
