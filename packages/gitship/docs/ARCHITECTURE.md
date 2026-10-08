# gitship: architecture

Why gitship is built the way it is. For *how to use it*, see the
[README](../README.md). For the workflow it automates, see
[docs/GITHUB_WORKFLOW.md](../../../docs/GITHUB_WORKFLOW.md).

Contents:

1. [The shape](#1-the-shape)
2. [One command, end to end](#2-one-command-end-to-end)
3. [Gates: look first, change last](#3-gates-look-first-change-last)
4. [The runner: the only door to other programs](#4-the-runner-the-only-door-to-other-programs)
5. [Why scan the staged version](#5-why-scan-the-staged-version)
6. [Parsing git output safely](#6-parsing-git-output-safely)
7. [Releases and checksums](#7-releases-and-checksums)
8. [Testing with real git and a fake GitHub](#8-testing-with-real-git-and-a-fake-github)
9. [Security review](#9-security-review)
10. [Principles used, and where](#10-principles-used-and-where)
11. [Trade-offs and known limits](#11-trade-offs-and-known-limits)
12. [Exercises](#12-exercises)
13. [References](#references)

---

## 1. The shape

**Layered, with a functional core and an imperative shell:**

| Layer | Modules | Does I/O? |
| --- | --- | --- |
| interface | `cli.py` | arguments, printing, exit codes |
| application | `workflow.py`, `release.py` | the flows: which step, in which order, with which gate |
| infrastructure | `git.py`, `runner.py`, `layout.py`, `config.py` | runs programs, reads files |
| domain (pure) | `commitmsg.py`, `scan.py` | none: text in, findings out |

The pure modules hold the *rules* (what makes a message good, what looks
like a secret). They need no git, no files and no network, so they are
trivial to test and to read. The shell around them does the I/O.

## 2. One command, end to end

`gitship ship -F msg.txt src/a.py`:

```text
cli.main            parse args → workflow.ship(cwd, message, ["src/a.py"])
workflow.ship
  find_repo           git rev-parse --show-toplevel           (not a repo → stop)
  config.load         .gitship.json → checks, trailer, allow
  commitmsg.problems  "Added x." → stop before touching anything
  git.add             git add -- src/a.py                      (only the named file)
  git diff --cached   nothing staged → stop
  git.status          report changed files that were NOT included
  scan_staged         for each staged file: git cat-file -s :path, git show :path → scan_file
  run_checks          each argv in config.checks; non-zero exit → stop
  confirm             "Commit and push? [y/N]"                  (unless --yes)
  git commit --file   message + trailer, written to a temp file (UTF-8, no BOM)
  push_branch         git push [--set-upstream] origin main
                      rejected → git fetch → "ahead 1, behind 2" → stop (never --force)
```

## 3. Gates: look first, change last

Every step that only **looks** (message rules, scan, checks) runs before
the first step that **changes history** (commit), and that runs before
the one that changes **other people's view** (push / publish). A failed
gate raises `ShipError`, and the steps after it never run. This is the
**fail-fast** principle. It's also why the message is checked before
staging: a typo in the message shouldn't leave files half-staged.

Default answers are always the safe ones:

| Question | Default |
| --- | --- |
| `Commit and push? [y/N]` | No |
| `publish` visibility | private |
| `publish --public` | you must type the repo name; "yes" is not enough |
| push rejected | report, don't force |
| no checks configured | refuse, unless `--no-checks` |

## 4. The runner: the only door to other programs

All git, gh and check commands go through one function type:

```python
Runner = Callable[[Sequence[str], Path], Completed]
```

- **No shell.** Arguments are a list passed straight to the program, so a
  file named `x; rm -rf ~` stays a file name (command-injection safe,
  CWE-78). `.gitship.json` checks must be lists too: a string like
  `"ruff check . && del *"` is rejected when the config is loaded.
- **`shutil.which`** turns `gh` into `gh.exe` on Windows before running.
- **Dependency injection.** Every flow takes `runner=`, so the tests pass
  `FakeGh` and production code passes the real `run`. No mocking
  library, and no "if testing" branches in the code.

## 5. Why scan the staged version

What gets committed is the **index**, not your working file. You can
`git add` a file and then edit it, so the working file and the committed
version differ. `git show :path` reads the staged blob, which is exactly
what the commit will contain. `git cat-file -s :path` gives its size
first, so a 2 GB file isn't loaded into memory just to be scanned.

`publish --public` goes further and scans **every added line in all of
history** (`git log -p --all`), because a public repo exposes old
commits too. A test commits a home path, "deletes" it in a later commit,
and checks that publishing is still refused.

## 6. Parsing git output safely

File names can contain spaces, quotes and even newlines, so splitting
git's output on lines or spaces breaks on unusual names. gitship uses
`-z` (entries separated by NUL, `\0`, the one byte a file name can't
contain) for `status --porcelain=v1` and `diff --name-only`. `--porcelain`
asks for the stable, script-friendly format, which doesn't change with
your language or git version.

## 7. Releases and checksums

`release.plan` is read-only and checks everything a release depends on:
a valid SemVer version; a tag that exists neither locally nor on GitHub
(`git ls-remote --tags`); no uncommitted changes; local equal to GitHub
(`rev-list --left-right --count HEAD...@{upstream}` = `0 0`); a CHANGELOG
section; existing, uniquely named assets.

**SHA-256** is a cryptographic hash: any change to a file changes its
64-hex-digit fingerprint. Publishing the hashes lets anyone check that
their download is exactly what you built. `sha256()` reads 1 MB at a
time, so a 2 GB installer doesn't need 2 GB of RAM.

**Verify like a stranger:** for a public repo, assets are downloaded
again with plain `urllib` and **no login**, which is what any visitor
gets. Only `https://github.com/` URLs are opened. For private repos,
`gh release download` (logged in) is used instead.

## 8. Testing with real git and a fake GitHub

| Thing | In tests | Why |
| --- | --- | --- |
| git | **real**, in `TemporaryDirectory` repos | the flows are about git's real behaviour |
| GitHub remote | a local **bare** repo (`git init --bare`) | real pushes and real rejections, no network |
| a rejected push | a second clone pushes first | proves "never force" against the real thing |
| `gh` | `FakeGh` records argv and returns canned answers | no network, no accidental repos |
| prompts | `ask=lambda _q: "n"` | no keyboard |

## 9. Security review

| Risk | Defense | Test |
| --- | --- | --- |
| command injection via file names / config | argv lists, no shell; config must be lists | `test_a_shell_string_is_rejected` |
| committing secrets / personal data | staged-file scan before commit | `test_secret_blocks_the_commit`, `test_home_path_blocks_the_commit` |
| exposing old secrets when going public | full-history scan + typed name | `test_public_refused_when_history_has_personal_data` |
| destroying others' commits | never `--force`; fetch and report | `test_rejected_push_is_never_forced` |
| sweeping up unrelated work | only named files (or explicit `--all`); leftovers reported | `test_commits_and_pushes_only_the_named_files` |
| pushing into someone else's repo | `gh repo view` must fail first | `test_existing_repo_is_never_reused` |
| replacing a published release | existing tag → stop | `test_gates` |
| a download from an unexpected host | only `https://github.com/` | code review |

The scanner's test plants fake secrets assembled at run time
(`"sk-" + "ant-" + …`), so the test file itself never contains a real-looking
key and stays committable.

## 10. Principles used, and where

| Principle | Where |
| --- | --- |
| Single responsibility | one job per module (§1) |
| Functional core, imperative shell | `commitmsg.py`, `scan.py` are pure |
| Dependency injection | `runner=`, `ask=`, `out=`, `env=` parameters |
| Fail fast / fail closed | gates raise `ShipError`; unknown or missing config → refuse |
| Least privilege / safe defaults | private by default; `--yes` and `--public` are explicit |
| Command–query separation | `release.plan` (query) vs `release.publish` (command) |
| Value objects | `@dataclass(frozen=True)` `Completed`, `Finding`, `Config`, `ReleasePlan` |
| YAGNI | no plugin system, no TOML (3.10 support), no GitHub API client: `gh` already does it |

## 11. Trade-offs and known limits

- **Regex scanning has false positives and negatives.** It catches common
  key formats and your own identifiers, not every possible secret. GitHub's
  push protection (on public repos) is a second net.
- **`gh` is required** for publish and release. Calling GitHub's REST API
  directly would avoid it, but would mean handling tokens ourselves. `gh`
  already stores them securely.
- **One remote, `origin`**, and the current branch only. Enough for these
  projects.
- **Windows PowerShell quoting** is avoided rather than solved: pass
  messages with `-F file`.

## 12. Exercises

1. Add a gate that refuses commits on a branch named `release/*` unless `--yes` is given. Write the test first.
2. Make `scan_file` also flag Windows paths containing `\Desktop\`. Which existing docs would trip it?
3. Change `push_branch` to print the commits GitHub has that you don't (`git log HEAD..@{upstream} --oneline`).

**Self-check:** why does `ship` check the message *before* staging files?

## References

**Official**
- Git: [git-status `--porcelain` and `-z`](https://git-scm.com/docs/git-status#_porcelain_format_version_1), [git-show (`:path` = index)](https://git-scm.com/docs/gitrevisions#Documentation/gitrevisions.txt-emltngtltpathgtemegem0READMEememREADMEem), [git-cat-file](https://git-scm.com/docs/git-cat-file), [git-rev-list `--left-right --count`](https://git-scm.com/docs/git-rev-list), [git-ls-remote](https://git-scm.com/docs/git-ls-remote), [git-init `--bare`](https://git-scm.com/docs/git-init)
- GitHub CLI: [gh release create](https://cli.github.com/manual/gh_release_create), [gh repo create](https://cli.github.com/manual/gh_repo_create)
- Python: [`subprocess` security considerations](https://docs.python.org/3/library/subprocess.html#security-considerations), [`hashlib`](https://docs.python.org/3/library/hashlib.html), [`shutil.which`](https://docs.python.org/3/library/shutil.html#shutil.which), [`tempfile`](https://docs.python.org/3/library/tempfile.html), [`fnmatch`](https://docs.python.org/3/library/fnmatch.html)
- MITRE: [CWE-78 OS command injection](https://cwe.mitre.org/data/definitions/78.html), [CWE-540 Sensitive information in source code](https://cwe.mitre.org/data/definitions/540.html)
- NIST: [FIPS 180-4 Secure Hash Standard (SHA-256)](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)

**Other**
- Gary Bernhardt: [Functional Core, Imperative Shell](https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell)
- Martin Fowler: [CommandQuerySeparation](https://martinfowler.com/bliki/CommandQuerySeparation.html)

### Further learning
- [Pro Git, ch. 10 "Git Internals"](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain): what the index and blobs really are
