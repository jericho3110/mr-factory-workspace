"""The flows: ship (check -> scan -> commit -> push) and publish (create the GitHub repo).

Each flow is a list of gates. Any gate that fails raises `ShipError`, and
nothing after it runs. The order is deliberate: everything that only
LOOKS (message rules, scan, checks) comes before anything that CHANGES
history (commit) or other people's view of it (push, publish).

`ask` and `out` are injected (default: input / print), so the tests can
answer prompts and capture output without a keyboard.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from . import config as config_mod
from .commitmsg import problems as message_problems
from .commitmsg import with_trailer
from .git import Git
from .runner import Runner, run
from .scan import Finding, personal_patterns, scan_file

Ask = Callable[[str], str]
Out = Callable[[str], None]


class ShipError(Exception):
    """A gate failed. The message says what, and what to do next."""


# ---- reusable gates ------------------------------------------------------

def find_repo(cwd: Path, runner: Runner) -> tuple[Git, Path]:
    top = Git(cwd, runner).toplevel()
    if top is None:
        raise ShipError("not inside a git repository. Run `gitship where` to see where this change belongs.")
    return Git(top, runner), top


def scan_staged(git: Git, cfg: config_mod.Config, env: Mapping[str, str]) -> list[Finding]:
    """Scan the STAGED version of every added/changed file (what will actually be committed)."""
    personal = personal_patterns(env.get("USERNAME") or env.get("USER"), git.config_get("user.email"))
    findings: list[Finding] = []
    for path in git.staged_paths():
        findings += scan_file(path, git.staged_size(path), git.staged_text(path), personal, cfg.allow)
    return findings


def run_checks(cfg: config_mod.Config, root: Path, runner: Runner, out: Out) -> None:
    """Run every configured check in order. Only the exit code counts, never the output text."""
    for argv in cfg.checks:
        out(f"  check: {' '.join(argv)}")
        result = runner(list(argv), root)
        if not result.ok:
            raise ShipError(f"check failed (exit {result.returncode}): {' '.join(argv)}\n{result.tail()}")


def confirm(question: str, ask: Ask) -> bool:
    """Default No: only 'y' or 'yes' counts."""
    return ask(f"{question} [y/N] ").strip().lower() in {"y", "yes"}


# ---- ship ------------------------------------------------------------------

def ship(cwd: Path, message: str, paths: Sequence[str] = (), *, stage_all: bool = False, push: bool = True,
         yes: bool = False, allow_unchecked: bool = False, runner: Runner = run, ask: Ask = input,
         out: Out = print, env: Mapping[str, str] | None = None) -> str:
    """Stage -> message rules -> scan -> checks -> confirm -> commit -> push. Returns the new commit's hash."""
    env = os.environ if env is None else env
    git, root = find_repo(cwd, runner)
    cfg = config_mod.load(root)

    bad = message_problems(message)
    if bad:
        raise ShipError("commit message:\n  - " + "\n  - ".join(bad))

    if paths:
        git.add(list(paths))
    elif stage_all:
        git("add", "--all")
    staged = git("diff", "--cached", "--name-status").strip()
    if not staged:
        raise ShipError("nothing is staged. Pass the files to commit, or --all for every change.")
    left_out = [p for code, p in git.status() if code[0] in " ?"]  # changed or untracked, but not staged
    if left_out:
        out(f"  not included (left as they are): {', '.join(left_out[:10])}{' …' if len(left_out) > 10 else ''}")

    findings = scan_staged(git, cfg, env)
    if findings:
        raise ShipError("the scan found something that shouldn't be committed:\n  - "
                        + "\n  - ".join(map(str, findings))
                        + "\nNothing was committed. Fix it, or unstage with: git restore --staged <file>")

    if cfg.checks:
        run_checks(cfg, root, runner, out)
    elif not allow_unchecked:
        raise ShipError(f"no checks configured. Add them to {config_mod.FILE_NAME} "
                        '(e.g. {"checks": [["python", "-m", "unittest"]]}), or pass --no-checks.')

    branch = git.branch() if git.has_commits() else "(first commit)"
    out(f"  repo: {root}\n  branch: {branch}\n  files:\n" + "\n".join(f"    {line}" for line in staged.splitlines()))
    out(f"  message: {message.splitlines()[0]}")
    if not yes and not confirm("Commit" + (" and push" if push else "") + "?", ask):
        raise ShipError("cancelled; nothing was committed (the files stay staged).")

    full = with_trailer(message, cfg.trailer)
    # A file instead of -m: multi-line messages survive every shell and OS unchanged.
    with tempfile.TemporaryDirectory() as tmp:
        msg_file = Path(tmp) / "COMMIT_MSG"
        msg_file.write_text(full, encoding="utf-8")
        git("commit", "--quiet", "--file", str(msg_file))
    sha = git("rev-parse", "--short", "HEAD").strip()
    out(f"  committed {sha}")
    if push:
        push_branch(git, out)
    return sha


def push_branch(git: Git, out: Out) -> None:
    """Push the current branch. Never forces: a rejected push is reported, not overwritten."""
    if "origin" not in git.remotes():
        raise ShipError("no 'origin' remote yet. Run `gitship publish` to create the GitHub repo (private).")
    branch = git.branch()
    has_upstream = git.ahead_behind() is not None
    result = git.raw("push", "origin", branch) if has_upstream else git.raw("push", "--set-upstream", "origin", branch)
    if result.ok:
        out(f"  pushed {branch} -> origin")
        return
    git.raw("fetch", "origin")
    counts = git.ahead_behind()
    detail = f" (local is {counts[0]} ahead, {counts[1]} behind origin)" if counts else ""
    raise ShipError(f"push was rejected{detail}. NOT forcing: that would erase commits on GitHub.\n"
                    "Bring them in first:  git pull --rebase  (then run `gitship push`).\n" + result.tail())


# ---- publish ---------------------------------------------------------------

def repo_name(folder: str) -> str:
    """Folder name -> GitHub repo name in kebab-case: 'Mr_Factory' -> 'mr-factory', 'TetoDesktop' -> 'teto-desktop'."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", folder)
    s = re.sub(r"[^A-Za-z0-9.]+", "-", s)
    return s.strip("-.").lower()


_NAME_OK = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def scan_history(git: Git, env: Mapping[str, str]) -> list[str]:
    """Secrets / personal data in ANY version of ANY file ever committed (for going public)."""
    personal = personal_patterns(env.get("USERNAME") or env.get("USER"), git.config_get("user.email"))
    added = "\n".join(line[1:] for line in git("log", "-p", "--all", "--no-color").splitlines()
                      if line.startswith("+") and not line.startswith("+++"))
    return [f.reason for f in scan_file("(history)", 0, added, personal)]


def publish(cwd: Path, name: str | None = None, *, public: bool = False, description: str = "", yes: bool = False,
            runner: Runner = run, ask: Ask = input, out: Out = print, env: Mapping[str, str] | None = None) -> str:
    """Create the GitHub repo (PRIVATE unless public=True) and push. Returns 'owner/name'."""
    env = os.environ if env is None else env
    git, root = find_repo(cwd, runner)
    if not git.has_commits():
        raise ShipError("make the first commit before publishing (gitship ship ...).")
    if "origin" in git.remotes():
        raise ShipError(f"this repo already has an 'origin' remote: {git.remotes()['origin']}")
    name = name or repo_name(root.name)
    if not _NAME_OK.match(name):
        raise ShipError(f"'{name}' isn't a valid GitHub repository name.")

    login = runner(["gh", "api", "user", "--jq", ".login"], root)
    if not login.ok:
        raise ShipError("GitHub CLI isn't logged in. Run: gh auth login\n" + login.tail())
    full = f"{login.stdout.strip()}/{name}"
    if runner(["gh", "repo", "view", full, "--json", "name"], root).ok:
        raise ShipError(f"{full} already exists on GitHub. Pick another --name; gitship never reuses a repo.")

    if public:
        hits = scan_history(git, env)
        if hits:
            raise ShipError("history contains: " + "; ".join(sorted(set(hits)))
                            + ". Don't publish this history; see the docs on publishing a clean copy.")
        out(f"  history scan: clean. {full} will be PUBLIC: anyone can read every commit.")
        if ask(f"Type the repo name ({name}) to make it public: ").strip() != name:
            raise ShipError("cancelled; nothing was created.")
    else:
        out(f"  will create PRIVATE repo {full} and push {git.branch()}")
        if not yes and not confirm("Create it?", ask):
            raise ShipError("cancelled; nothing was created.")

    argv = ["gh", "repo", "create", name, "--public" if public else "--private",
            "--source", ".", "--remote", "origin", "--push"]
    if description:
        argv += ["--description", description]
    result = runner(argv, root)
    if not result.ok:
        raise ShipError("gh repo create failed:\n" + result.tail())
    out(f"  created https://github.com/{full}")
    return full
