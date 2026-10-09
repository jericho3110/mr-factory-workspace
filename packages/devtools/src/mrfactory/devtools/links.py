"""Markdown link checker: local links must point at existing files, web links must load.

Improvements over the seven copies it replaces (each found live):
- Link targets may contain parentheses, as Wikipedia's do:
  `[x](https://en.wikipedia.org/wiki/Plug-in_(computing))`.
- Links inside code blocks and `inline code` are examples, not links.
- `ignore` prefixes skip links that can't be checked by a script, such as
  your own private repos (404 to anyone not logged in).
- 403/429 answers mean "blocks scripts", not "dead": reported, not failed.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
# [text](target "title"): the target may hold one level of balanced parentheses.
MD_LINK = re.compile(r"\]\(\s*<?((?:[^()\s<>]|\([^()\s]*\))+)>?(?:\s+\"[^\"]*\")?\s*\)")
AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
BARE_URL = re.compile(r"(?<![(<\[\"'=])\bhttps?://[^\s<>\"'`\]\)]+")
HEADERS = {"User-Agent": "Mozilla/5.0 (devtools link checker)"}
Opener = Callable[..., object]


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: str  # "ok 200", "blocked 403", "DEAD 404", "DEAD URLError"
    sources: tuple[str, ...]

    @property
    def dead(self) -> bool:
        return self.status.startswith("DEAD")


def prose(markdown: str) -> str:
    """The text with code blocks and inline code removed."""
    return INLINE_CODE.sub("", FENCE.sub("", markdown))


def extract(markdown: str) -> tuple[list[str], list[str]]:
    """(web URLs, local targets) in a Markdown text."""
    text = prose(markdown)
    web, local = [], []
    for target in MD_LINK.findall(text):
        if target.startswith(("http://", "https://")):
            web.append(target)
        elif not target.startswith(("#", "mailto:", "tel:")):
            local.append(target.split("#", 1)[0])
    web += AUTOLINK.findall(text)
    web += [u.rstrip(".,;:") for u in BARE_URL.findall(MD_LINK.sub("", AUTOLINK.sub("", text)))]
    return web, [t for t in local if t]


def check_local(markdown_files: Iterable[Path], root: Path) -> list[str]:
    broken = []
    for md in markdown_files:
        _, local = extract(md.read_text(encoding="utf-8", errors="replace"))
        for target in local:
            if not (md.parent / target.replace("%20", " ")).exists():
                broken.append(f"BROKEN local link {target}  ({md.relative_to(root).as_posix()})")
    return broken


def check_url(url: str, opener: Opener = urllib.request.urlopen, timeout: float = 20) -> str:
    if not url.startswith(("http://", "https://")):
        return "DEAD not-http"
    for method in ("HEAD", "GET"):  # some servers reject HEAD
        try:
            req = urllib.request.Request(url, method=method, headers=HEADERS)  # noqa: S310 - http(s) checked above
            with opener(req, timeout=timeout) as r:
                return f"ok {r.status}"
        except urllib.error.HTTPError as e:
            e.close()  # an HTTPError is also the open response: close it, or it leaks until garbage collection
            if method == "GET":
                return f"blocked {e.code}" if e.code in (403, 429) else f"DEAD {e.code}"
        except Exception as e:  # DNS, TLS, timeouts, dropped connections
            if method == "GET":
                return f"DEAD {type(e).__name__}"
    return "DEAD"


def check_web(markdown_files: Iterable[Path], root: Path, ignore: Iterable[str] = (),
              opener: Opener = urllib.request.urlopen, workers: int = 8) -> list[LinkResult]:
    sources: dict[str, set[str]] = {}
    ignore = tuple(ignore)
    for md in markdown_files:
        web, _ = extract(md.read_text(encoding="utf-8", errors="replace"))
        for url in web:
            if "localhost" in url or "127.0.0.1" in url or url.startswith(ignore):
                continue
            sources.setdefault(url, set()).add(md.relative_to(root).as_posix())
    with ThreadPoolExecutor(max_workers=workers) as pool:  # network waits overlap
        statuses = list(pool.map(lambda u: check_url(u, opener), sorted(sources)))
    return [LinkResult(u, s, tuple(sorted(sources[u]))) for u, s in zip(sorted(sources), statuses, strict=True)]
