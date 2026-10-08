"""GitHub releases: plan -> publish -> verify.

A release is a git TAG (a name like v0.1.1 pinned to one commit) plus a
page on GitHub with notes and downloadable files ("assets"). The flow:

1. plan     read-only: version is SemVer, tag is new, everything is
            committed and pushed, CHANGELOG has a section for it, assets
            exist; compute each asset's SHA-256.
2. publish  `gh release create` with the assets + a SHA256SUMS file;
            GitHub creates the tag on the pushed commit.
3. verify   download the assets again (anonymously for public repos,
            exactly what a stranger gets) and compare the hashes.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .git import Git
from .runner import Runner, run

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SUMS_NAME = "SHA256SUMS"


class ReleaseError(Exception):
    """A release gate failed."""


@dataclass(frozen=True)
class Asset:
    path: Path
    sha256: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class ReleasePlan:
    version: str
    tag: str
    title: str
    notes: str
    branch: str
    assets: tuple[Asset, ...]

    def sums_text(self) -> str:
        """The SHA256SUMS file: '<hash>  <name>' per line, the format `sha256sum -c` reads."""
        return "".join(f"{a.sha256}  {a.name}\n" for a in self.assets)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):  # 1 MB at a time: any file size, little memory
            h.update(block)
    return h.hexdigest()


def changelog_section(text: str, version: str) -> str | None:
    """The body under '## [version]' (or '## version') up to the next '## ' heading."""
    head = re.compile(rf"^##\s+\[?{re.escape(version)}\]?.*$", re.M)
    m = head.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[: nxt.start() if nxt else len(rest)].strip()


def plan(cwd: Path, version: str, asset_paths: list[Path], *, title: str | None = None,
         changelog: str = "CHANGELOG.md", runner: Runner = run) -> ReleasePlan:
    git = Git(cwd, runner)
    root = git.toplevel()
    if root is None:
        raise ReleaseError("not inside a git repository.")
    git = Git(root, runner)
    if not SEMVER.match(version):
        raise ReleaseError(f"'{version}' isn't a SemVer version (MAJOR.MINOR.PATCH, e.g. 0.1.1).")
    tag = f"v{version}"
    if tag in git.tags() or git.raw("ls-remote", "--exit-code", "--tags", "origin", tag).ok:
        raise ReleaseError(f"tag {tag} already exists. Releases are never replaced; bump the version.")
    dirty = [p for code, p in git.status() if code != "??"]
    if dirty:
        raise ReleaseError(f"uncommitted changes: {', '.join(dirty[:5])}. Commit (gitship ship) first.")
    counts = git.ahead_behind()
    if counts is None:
        raise ReleaseError("this branch has no upstream on GitHub yet. Push it (gitship push) first.")
    if counts != (0, 0):
        raise ReleaseError(f"local and GitHub differ ({counts[0]} ahead, {counts[1]} behind). Push/pull first.")
    log = root / changelog
    notes = changelog_section(log.read_text(encoding="utf-8"), version) if log.is_file() else None
    if not notes:
        raise ReleaseError(f"{changelog} has no '## [{version}]' section. Write the release notes there first.")
    assets = []
    for p in asset_paths:
        if not p.is_file():
            raise ReleaseError(f"asset not found: {p}")
        assets.append(Asset(p.resolve(), sha256(p)))
    if len({a.name for a in assets}) != len(assets) or any(a.name == SUMS_NAME for a in assets):
        raise ReleaseError(f"asset names must be unique and not '{SUMS_NAME}'.")
    return ReleasePlan(version, tag, title or f"{root.name} {version}", notes, git.branch(), tuple(assets))


def publish(p: ReleasePlan, cwd: Path, runner: Runner = run) -> str:
    """Create the release on GitHub. Returns its URL."""
    with tempfile.TemporaryDirectory() as tmp:
        sums = Path(tmp) / SUMS_NAME
        sums.write_text(p.sums_text(), encoding="utf-8", newline="\n")
        notes = Path(tmp) / "NOTES.md"
        checks = "\n".join(f"    {a.sha256}  {a.name}" for a in p.assets)
        verify = f"\n\n### Verify your download\n\nSHA-256:\n\n{checks}\n" if p.assets else ""
        notes.write_text(p.notes + verify, encoding="utf-8")
        argv = ["gh", "release", "create", p.tag, *[str(a.path) for a in p.assets]]
        if p.assets:
            argv.append(str(sums))
        argv += ["--target", p.branch, "--title", p.title, "--notes-file", str(notes)]
        result = runner(argv, cwd)
    if not result.ok:
        raise ReleaseError("gh release create failed:\n" + result.tail())
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def _download_anonymously(url: str, dest: Path) -> None:
    if not url.startswith("https://github.com/"):
        raise ReleaseError(f"refusing to download from {url}")
    with urllib.request.urlopen(url, timeout=60) as r, dest.open("wb") as f:  # noqa: S310 - https://github.com only
        while block := r.read(1024 * 1024):
            f.write(block)


def verify(p: ReleasePlan, cwd: Path, runner: Runner = run) -> list[str]:
    """Download every asset again and compare hashes. Returns problems (empty = verified)."""
    info = runner(["gh", "repo", "view", "--json", "nameWithOwner,visibility",
                   "--jq", '.nameWithOwner + " " + .visibility'], cwd)
    if not info.ok:
        return ["could not read the repo's name: " + info.tail()]
    repo, visibility = info.stdout.split()
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        if visibility.upper() == "PUBLIC":
            for a in p.assets:  # no login: proves strangers get the same bytes
                _download_anonymously(f"https://github.com/{repo}/releases/download/{p.tag}/{a.name}", out_dir / a.name)
        else:
            r = runner(["gh", "release", "download", p.tag, "--dir", str(out_dir)], cwd)
            if not r.ok:
                return ["gh release download failed: " + r.tail()]
        for a in p.assets:
            got = out_dir / a.name
            if not got.is_file():
                problems.append(f"{a.name}: not in the release")
            elif sha256(got) != a.sha256:
                problems.append(f"{a.name}: downloaded file's SHA-256 doesn't match")
    return problems
