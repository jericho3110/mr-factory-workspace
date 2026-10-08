# gitship

Check, scan, commit, push, publish and release a git repository the
same safe way every time. It is the workflow from
[docs/GITHUB_WORKFLOW.md](../../docs/GITHUB_WORKFLOW.md), turned into a command.

```powershell
pip install -e packages/gitship       # from the workspace root; installs the `gitship` command
gitship --help
```

Needs `git` and, for `publish`/`release`, the [GitHub CLI](https://cli.github.com/)
logged in (`gh auth login`). There are no Python dependencies.

## Usage

| Command | What it does | Changes anything? |
| --- | --- | --- |
| `gitship where` | inside a repo / a parent folder of repos / no repo, and what to do | no |
| `gitship check` | runs the checks in `.gitship.json`, scans what's staged | no |
| `gitship ship -m "Add x" a.py b.md` | stage these files → message rules → scan → checks → `[y/N]` → commit → push | yes |
| `gitship ship -F msg.txt --all` | the same with a message file, staging every change | yes |
| `gitship push` | push; on rejection fetch and explain; **never forces** | yes |
| `gitship publish [--name N] [--description D]` | create a **private** GitHub repo, push | yes |
| `gitship publish --public` | scan all history, ask you to type the name, then create it public | yes |
| `gitship release 0.2.0 --asset dist/app.exe [--dry-run]` | check, tag, upload assets + `SHA256SUMS`, re-download and compare hashes | yes |

`-y` / `--yes` skips the confirmation question (for when you've already
reviewed the change). `-C DIR` runs as if started in `DIR`.

### `.gitship.json`

At the repo root:

```json
{
  "checks": [["ruff", "check", "."], ["python", "scripts/test_all.py"]],
  "trailer": "Co-Authored-By: Name <noreply@example.com>",
  "allow": ["tests/fixtures/*"],
  "changelog": "CHANGELOG.md"
}
```

| Key | Meaning |
| --- | --- |
| `checks` | argument lists, run in order without a shell; every one must exit 0 |
| `trailer` | a line appended to every commit message (once) |
| `allow` | path patterns the scan skips (for deliberate test fixtures) |
| `changelog` | where `release` finds the `## [version]` notes |

## What ship refuses to commit

| Gate | Example |
| --- | --- |
| message rules | `feat: added x.` → past tense, a Conventional prefix, a period |
| secrets | API keys, GitHub tokens, AWS keys, private keys, `password = "..."` |
| secret files | `.env`, `*.pem`, `*.key`, `Cookies`, `Login Data` |
| personal data | your home path (`C:\Users\<you>`), your git email (unless it's GitHub's noreply) |
| real IPs | anything outside RFC 5737 / private / loopback ranges |
| generated files | `*.exe`, `*.pyc`, `__pycache__/`, `node_modules/` |
| large files | over 5 MB |
| failing checks | any check with a non-zero exit code |

Nothing is committed when a gate fails, and files you didn't name are
never staged.

## Layout

```text
src/mrfactory/gitship/
  commitmsg.py   message rules (pure)
  scan.py        secret / personal-data scan (pure)
  config.py      .gitship.json
  runner.py      the only place that starts programs (no shell)
  git.py         typed git wrapper
  layout.py      which repo does this folder belong to?
  workflow.py    ship, push, publish
  release.py     plan, publish, verify a release
  cli.py         the command
tests/           45 tests: real temp repos with a local bare "GitHub"; gh is faked
```

Design and reasoning: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```powershell
cd packages/gitship
python -m unittest discover -s tests -t .
```

The tests run real `git` in temp folders. The "GitHub" remote is a local
*bare* repository, so pushes and rejected pushes are real. `gh` is replaced
by a fake that records its commands, so nothing touches the network.

## References

**Official**
- [git documentation](https://git-scm.com/docs), [GitHub CLI manual](https://cli.github.com/manual/)

### Further learning
- [Pro Git book](https://git-scm.com/book/en/v2)
