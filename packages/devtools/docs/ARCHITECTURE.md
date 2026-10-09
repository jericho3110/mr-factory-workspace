# devtools: architecture

Contents:

1. [Why one package](#1-why-one-package)
2. [The shape](#2-the-shape)
3. [Reuse instead of copy: devtools ← gitship](#3-reuse-instead-of-copy-devtools--gitship)
4. [Which files: git's view](#4-which-files-gits-view)
5. [Pattern scanning: what it can and can't do](#5-pattern-scanning-what-it-can-and-cant-do)
6. [Link extraction](#6-link-extraction)
7. [Testing a scanner](#7-testing-a-scanner)
8. [Principles used](#8-principles-used)
9. [Trade-offs and known limits](#9-trade-offs-and-known-limits)
10. [Exercises](#10-exercises)
11. [References](#references)

---

## 1. Why one package

**DRY ("don't repeat yourself")** is usually explained as saving typing. Here
the reason is safety. Seven copies of a link checker means a bug fixed in one
(parenthesised Wikipedia links reported as dead) stays broken in six. Six
copies of a security scanner means a new secret pattern protects one project.
The same thing happened with the AdsPower clients: a security fix existed in
one copy and not another. A shared package turns "fix it 7 times" into "fix it
once and update".

## 2. The shape

| Module | Job | I/O |
| --- | --- | --- |
| `codescan.py` | regex rules per language; `scan_text(path, text)` | none (pure) |
| `config.py` | read and validate `.devtools.json` | reads one file |
| `files.py` | list project files | runs `git ls-files` |
| `security.py` | codescan + gitship's `scan_file` for every file | reads files |
| `links.py` | extract and check links | reads files; HTTP (injectable opener) |
| `cli.py` | arguments, printing, exit codes | console |

The same **functional core, imperative shell** layout as gitship: the rules
are pure functions over text, so they're tested without files or network,
and the I/O sits in thin outer modules.

## 3. Reuse instead of copy: devtools ← gitship

`security.py` imports `mrfactory.gitship.scan.scan_file` and
`personal_patterns`. Dependencies between workspace packages follow
CONVENTIONS §4:

- **One direction only:** devtools uses gitship, and gitship never imports devtools.
- **Through the public module only** (`scan.py`), never private helpers.
- **Not listed in `pyproject.toml` dependencies.** gitship isn't on PyPI, so pip
  would look for `mrfactory-gitship` there and could install a stranger's
  package of that name (dependency confusion). The README tells you to
  install both from the workspace, and `tests/__init__.py` puts both `src/`
  folders on the path.

## 4. Which files: git's view

`git ls-files -z --cached --others --exclude-standard` gives tracked files
plus new, not-ignored files. That's what git *would* commit, which is exactly
what a pre-commit scan cares about:

| File | Scanned? | Why |
| --- | --- | --- |
| tracked `app.py` | yes | it's in the repo |
| new `notes.md`, not yet staged | yes | one `git add .` away from the repo |
| `.env` listed in `.gitignore` | no | can't be committed by accident |
| `venv/`, `node_modules/` | no | `skip_dirs` |

`-z` separates names with NUL bytes, so names with spaces or newlines are
read correctly. Outside a git repo the folder is walked instead.

## 5. Pattern scanning: what it can and can't do

This is **SAST** (static application security testing) at its simplest:
looking for known-dangerous constructs in source text.

- **It catches the classics cheaply:** `shell=True`, `eval`, SQL built with
  f-strings, `innerHTML =`, `strcpy`. These are the root of most injection and
  RCE bugs ([CWE-78](https://cwe.mitre.org/data/definitions/78.html),
  [CWE-89](https://cwe.mitre.org/data/definitions/89.html),
  [CWE-95](https://cwe.mitre.org/data/definitions/95.html)).
- **It can't follow data.** It doesn't know whether a variable passed to
  `subprocess.run` came from a user. A real taint-tracking tool (CodeQL,
  Semgrep) can. That's why the README pairs it with tests and review.
- **False positives are handled visibly:** a trailing `security-scan: allow
  (reason)` comment on the line. It's a reviewed exception, never a silent one.
- **Comment lines are skipped,** because a comment *describing* `eval(` isn't a
  use of it. The catch: a dangerous call written after code on the same line
  as a comment is still caught, while one hidden in a multi-line string is not.

## 6. Link extraction

```python
MD_LINK = re.compile(r"\]\(\s*<?((?:[^()\s<>]|\([^()\s]*\))+)>?(?:\s+\"[^\"]*\")?\s*\)")
```

Read it as: after `](`, take characters that are not parentheses or spaces,
**or** a parenthesised group with no nested parentheses, repeated; then an
optional `"title"`; then `)`. CommonMark allows balanced parentheses in link
destinations, which is how `.../Plug-in_(computing)` stays whole. The old
checkers used `[^)]` and stopped at the first `)`.

Code blocks are removed first (`FENCE`, `INLINE_CODE`), because URLs inside
code are examples. Web checks run in a `ThreadPoolExecutor`: checking links
is mostly *waiting* on the network, and threads overlap the waits.

## 7. Testing a scanner

A scanner that finds nothing looks exactly like a broken one. So every rule
has a **planted bad line** that must be found and a **safe twin** that must not.
The planted lines are assembled at run time (`"ev" + "al(x)"`), so the test file
itself passes the real scan. The project-level tests run in temporary git
repos, to prove `.gitignore` behaviour with a real `git`.

## 8. Principles used

| Principle | Where |
| --- | --- |
| DRY for safety | the reason the package exists (§1) |
| Reuse through a public API | `security.py` → `gitship.scan` |
| Acyclic dependencies | devtools → gitship, never back |
| Functional core, imperative shell | `codescan.py`, `links.extract` are pure |
| Dependency injection | `check_url(..., opener=)` for tests |
| Fail loud | exit 1 on any finding, 2 on a bad config |
| Configuration over code | project rules live in `.devtools.json`, not forks |

## 9. Trade-offs and known limits

- **Regex rules, not a parser:** fast and dependency-free, but blind to data
  flow, and multi-line constructs can slip through.
- **Dependency scanners** (npm audit, cargo audit, govulncheck, pip-audit) are
  not included: they need each ecosystem's tools. Projects that use them
  (Teto) keep calling them in their own check gate.
- **The web link check is network-dependent.** Use `--offline` in commit gates.

## 10. Exercises

1. Add a rule for Python's `tempfile.mktemp(` (insecure, use `mkstemp`), with a planted line and a safe twin.
2. Write a `.devtools.json` for Disk_Cleanup that reproduces its "only two files may delete" rule.
3. Find a Markdown link that the `MD_LINK` regex still gets wrong. (Hint: nested parentheses.)

**Self-check:** why is gitship not listed under `dependencies` in `pyproject.toml`?

## References

**Official**
- [git-ls-files](https://git-scm.com/docs/git-ls-files), [CommonMark 0.31.2: link destinations](https://spec.commonmark.org/0.31.2/#link-destination)
- Python: [re](https://docs.python.org/3/library/re.html), [concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html), [urllib.request](https://docs.python.org/3/library/urllib.request.html), [fnmatch](https://docs.python.org/3/library/fnmatch.html)
- [OWASP: Static Code Analysis](https://owasp.org/www-community/controls/Static_Code_Analysis)

**Other**
- [Semgrep](https://semgrep.dev/docs/) and [CodeQL](https://codeql.github.com/docs/): what full SAST adds (data flow)
- [Acyclic dependencies principle](https://en.wikipedia.org/wiki/Acyclic_dependencies_principle)

### Further learning
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
