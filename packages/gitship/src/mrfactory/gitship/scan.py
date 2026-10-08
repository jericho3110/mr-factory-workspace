"""Does anything about to be committed look like a secret or personal data? (pure)

Git history is permanent: once a key or your home path is pushed, deleting
it later doesn't remove it from older commits. So every staged file is
checked BEFORE the commit. The functions here only look at text and names
they are given; reading the staged files is git.py's job.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_BYTES = 5 * 1024 * 1024  # GitHub warns at 50 MB; anything over 5 MB deserves a second look

SECRET_PATTERNS = {
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "OpenAI-style API key": r"\bsk-[A-Za-z0-9]{32,}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b",
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "Slack token": r"\bxox[abpr]-[A-Za-z0-9-]{10,}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "password in code": r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]",
}
_SECRETS = [(name, re.compile(rx)) for name, rx in SECRET_PATTERNS.items()]

# File names that are secrets or local data by nature, whatever they contain.
FORBIDDEN_NAMES = [".env", ".env.*", "*.pem", "*.key", "*.pfx", "*.p12", "id_rsa", "id_ed25519",
                   "credentials.json", "*.kdbx", "Cookies", "Login Data"]
# Templates that list variable NAMES only; committing them is the convention.
# Their contents are still scanned for secrets like any other file.
TEMPLATES = [".env.example", ".env.sample", ".env.template"]
# Build output and caches: regenerated, so they don't belong in git.
GENERATED = ["*.exe", "*.dll", "*.pyc", "*.pyo", "*.obj", "*.o", "*.pdb", "*.so", "*.dylib",
             "__pycache__/*", "*/__pycache__/*", "node_modules/*", "*/node_modules/*"]
EXAMPLE_IPS = re.compile(r"^(192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|127\.|0\.0\.0\.0$)")  # RFC 5737 + loopback
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def personal_patterns(user: str | None, email: str | None) -> list[tuple[str, re.Pattern[str]]]:
    """Your user name inside a home path, and your git email (unless it's GitHub's noreply address)."""
    found = []
    if user and len(user) >= 3:
        found.append(("your home folder path", re.compile(r"(?i)(users[\\/]+|home/)" + re.escape(user) + r"\b")))
    if email and not email.lower().endswith("users.noreply.github.com"):
        found.append(("your email address", re.compile(re.escape(email), re.I)))
    return found


def _matches(path: str, patterns: Sequence[str]) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in patterns)


def scan_file(path: str, size: int, text: str | None,
              personal: Sequence[tuple[str, re.Pattern[str]]] = (),
              allow: Sequence[str] = ()) -> list[Finding]:
    """Findings for one staged file. `text` is None for binary or very large files."""
    if _matches(path, allow):
        return []
    found = []
    if _matches(path, FORBIDDEN_NAMES) and not _matches(path, TEMPLATES):
        found.append(Finding(path, "secret or private-data file name; add it to .gitignore"))
    if _matches(path, GENERATED):
        found.append(Finding(path, "build output / cache; add it to .gitignore"))
    if size > MAX_BYTES:
        found.append(Finding(path, f"large file ({size / 1024 / 1024:.1f} MB); does it belong in git?"))
    if text is None:
        return found
    for name, rx in _SECRETS:
        if rx.search(text):
            found.append(Finding(path, f"looks like a {name}"))
    for name, rx in personal:
        if rx.search(text):
            found.append(Finding(path, f"contains {name}"))
    real_ips = sorted({ip for ip in _IPV4.findall(text) if _is_real_ip(ip)})
    if real_ips:
        found.append(Finding(path, f"IP address(es) {', '.join(real_ips[:3])}: use RFC 5737 examples (203.0.113.x)"))
    return found


def _is_real_ip(ip: str) -> bool:
    parts = ip.split(".")
    if any(int(p) > 255 for p in parts):
        return False  # a version number like 1.2.3.400, not an IP
    if EXAMPLE_IPS.match(ip) or ip.startswith(("10.", "192.168.", "255.")):
        return False  # documentation ranges, loopback, private LAN ranges, masks
    return parts[0] != "0"
