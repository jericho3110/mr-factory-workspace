# The GitHub workflow: commit, push, publish, release

How every change in these projects goes from your editor to GitHub, why
each step exists, and the commands behind it. The
[`gitship`](../packages/gitship/) package automates exactly these steps.
This guide is the manual version, so you know what the tool does for you.

Contents:

1. [The big picture](#1-the-big-picture)
2. [Which repository? (before the first commit)](#2-which-repository-before-the-first-commit)
3. [Before every commit: checks and the scan](#3-before-every-commit-checks-and-the-scan)
4. [Commit](#4-commit)
5. [Push (and what to do when it's rejected)](#5-push-and-what-to-do-when-its-rejected)
6. [Publishing a new repository](#6-publishing-a-new-repository)
7. [Going public](#7-going-public)
8. [Releases](#8-releases)
9. [The same flow with gitship](#9-the-same-flow-with-gitship)
10. [Things that went wrong for real](#10-things-that-went-wrong-for-real)
11. [Exercises](#11-exercises)
12. [References](#references)

---

## 1. The big picture

```text
edit ──► checks pass? ──► scan staged files ──► commit ──► push ──► (first time) publish repo
                                                                └──► (a version is done) release
```

| Word | Meaning |
| --- | --- |
| **working tree** | the files in your folder, as you edit them |
| **index / staging area** | the snapshot you're preparing: `git add` puts a file's *current* content there |
| **commit** | a saved snapshot of the index, with a message, author and parent commit |
| **branch** | a movable name for the latest commit of a line of work (`main`) |
| **remote** | another copy of the repo, usually on GitHub, named `origin` |
| **push / fetch** | send your commits to the remote / download its commits |
| **tag** | a fixed name for one commit, like `v0.2.0` |
| **release** | a GitHub page for a tag, with notes and downloadable files (assets) |

## 2. Which repository? (before the first commit)

```powershell
git rev-parse --show-toplevel   # prints the repo's top folder, or fails if not in a repo
```

1. **Inside a repo:** commit there. Never `git init` inside another repo
   (a **nested repo**: the outer one would see the inner one as a single
   strange entry).
2. **Not inside one, but sub-folders are repos:** you're in a **parent
   folder** (like `Coding_Proj/`). Never `git init` it. Commit inside the
   sub-repo that holds the change.
3. **No repo anywhere:** `git init -b main` in the project's top folder.

`gitship where` makes this decision for you.

## 3. Before every commit: checks and the scan

**Checks** are the project's tests and linters. In this workspace:

```powershell
ruff check .                  # lint: style and likely bugs, incl. security rules (S)
python scripts/test_all.py    # every package's tests
```

Gate the commit on their **exit codes** (0 means success), never on
their printed text. `tests | grep OK && git commit` commits even when
tests fail, because a pipeline's exit code is that of its *last* command
(`grep`).

**The scan.** Look at what's staged before committing, because **git
history is permanent**: deleting a key in a later commit leaves it
readable in the older one.

| Look for | Example | Why |
| --- | --- | --- |
| secrets | API keys, tokens, private keys, passwords | anyone with the repo can use them |
| secret files | `.env`, `*.pem`, `*.key`, browser `Cookies` | same |
| personal data | `C:\Users\<you>\…`, your private email, real IPs, account IDs | privacy; use `<you>`, `203.0.113.x` (RFC 5737) |
| generated files | `*.exe`, `*.pyc`, `__pycache__/`, `node_modules/` | rebuilt anyway; bloat history forever |
| huge files | videos, datasets | GitHub limits files to 100 MB; history keeps every version |

```powershell
git status                       # what changed; what's staged
git diff --cached --name-only    # the staged file list
git diff --cached                # the staged content
```

**Don't sweep up other changes.** `git add -A` stages *everything*,
including half-finished work you didn't mean to commit. Name the files
instead: `git add -- src/a.py docs/a.md`. The `--` means "only file names
after this", so a file called `-f` can't be read as an option.

## 4. Commit

The message format (see [CONVENTIONS.md §7](CONVENTIONS.md#7-commit-messages)):

```text
adspower: Add --path option                  <- imperative, ≤ 72 chars, package prefix

Why the change was needed, in a few lines.   <- body: the WHY (the diff shows the what)
- related change
- docs updated

Verified: ruff check . and scripts/test_all.py pass.

Co-Authored-By: Name <noreply@example.com>   <- trailer(s)
```

Write multi-line messages to a **file** and use `git commit -F file`.
Quoting a multi-line `-m` differs between PowerShell, cmd and bash, and
it broke here once (§10).

**Your email in commits.** Every commit records an author email, and on
a public repo anyone can read it. Use GitHub's private address:

```powershell
git config --global user.email "<id>+<username>@users.noreply.github.com"
```

(GitHub → Settings → Emails shows yours. "Block command line pushes that
expose my email" makes GitHub refuse pushes with the real one.)

## 5. Push (and what to do when it's rejected)

```powershell
git push                          # after the first time
git push --set-upstream origin main   # first push of a branch: also remembers origin/main as its "upstream"
```

A push is **rejected** when GitHub has commits you don't have, for
example from another PC. **Never** `git push --force`: it replaces
GitHub's history with yours and deletes their commits. Instead:

```powershell
git fetch origin                  # download, change nothing
git status                        # "ahead 1, behind 2"
git pull --rebase                 # replay your commits on top of theirs
git push
```

## 6. Publishing a new repository

```powershell
gh repo view <you>/<name>         # must FAIL: the name must be free
gh repo create <name> --private --source . --remote origin --push
```

| Flag | Meaning |
| --- | --- |
| `--private` | only you (and people you invite) can see it. **The default for everything here.** |
| `--source .` | use this local repo |
| `--remote origin` | add GitHub as the remote named `origin` |
| `--push` | push the current branch right away |

Name it after the folder in kebab-case (`Disk_Cleanup` → `disk-cleanup`).
If the name is taken, stop. Never push into an existing repo that isn't
this project's.

## 7. Going public

Making a repo public publishes **every commit ever made**, not just the
current files. Before that:

1. **Scan the full history**, not just the files:
   `git log -p --all | Select-String "sk-ant-|PRIVATE KEY|Users\\<you>"`
2. If the history isn't clean, **don't rewrite it in place**. Publish a
   fresh repo from the clean files, and keep the old one private as an
   archive. That is how this public workspace started: its first commit
   is a fresh copy, and the older history stays in a private archive.
3. Add a `LICENSE`, then turn on Dependabot alerts, secret scanning and
   push protection (Settings → Code security). On a free private repo,
   GitHub doesn't offer secret scanning; your own scan does that job.

## 8. Releases

A **release** turns "the code at some commit" into something people
download. These projects follow these steps:

1. **Pick the version (SemVer).** `MAJOR.MINOR.PATCH`: bump PATCH for
   fixes (0.1.0 → 0.1.1), MINOR for new features, MAJOR for breaking
   changes. While MAJOR is 0, anything may change.
2. **Write the notes** in `CHANGELOG.md` under `## [0.1.1] - YYYY-MM-DD`
   ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/)), and bump the
   version in `pyproject.toml` / `Cargo.toml` / `tauri.conf.json`.
3. **Commit and push** everything. A release must point at a commit
   that is on GitHub.
4. **Build the assets** (installer, zip) **outside** synced folders, and
   check they don't contain local paths (Teto's `assert_no_local_paths`).
5. **Checksums.** Compute SHA-256 for every asset:
   ```powershell
   (Get-FileHash dist\app.exe -Algorithm SHA256).Hash.ToLower()
   ```
   Write them to `SHA256SUMS` as `<hash>  <file name>` lines, the format
   `sha256sum -c SHA256SUMS` checks on Linux.
6. **Create the release**:
   ```powershell
   gh release create v0.1.1 dist\app.exe SHA256SUMS --target main --title "App 0.1.1" --notes-file notes.md
   ```
   `gh` creates the tag `v0.1.1` on `main`'s latest commit, uploads the
   files and publishes the page. `--latest` marks it as the newest release.
7. **Verify like a stranger.** Download the asset again **without being
   logged in** and compare its hash to the one you published. This
   catches truncated uploads and wrong files. It was done for Teto v0.1.0
   and v0.1.1.
8. **Never replace a release's files.** People may already have the old
   ones, and their checksums would stop matching. Fix it in a new version.

## 9. The same flow with gitship

```powershell
pip install -e packages/gitship

gitship where                                        # §2
gitship check                                        # §3 checks + scan of what's staged
gitship ship -F msg.txt src/a.py docs/a.md           # §3 → §5: stage, rules, scan, checks, commit, push
gitship publish                                      # §6: private repo, name from the folder
gitship publish --public                             # §7: history scan + type the name to confirm
gitship release 0.2.0 --asset dist/app.exe           # §8: plan, upload with SHA256SUMS, verify
gitship release 0.2.0 --asset dist/app.exe --dry-run # only print the plan
```

A repo tells gitship its checks in `.gitship.json` (this workspace's:
[`../.gitship.json`](../.gitship.json)). How it's built:
[packages/gitship/docs/ARCHITECTURE.md](../packages/gitship/docs/ARCHITECTURE.md).

## 10. Things that went wrong for real

| What happened | Lesson | Now handled by |
| --- | --- | --- |
| A multi-line `git commit -F - @'...'@` in Windows PowerShell 5.1 passed the message as file names, so nothing was committed | write the message to a file first | `ship` always writes the file itself |
| A message file written with PowerShell 5.1's `Set-Content -Encoding utf8` started with an invisible BOM, which ended up in commit `94136d9`'s summary | 5.1's "utf8" means UTF-8 *with* BOM | `ship` writes UTF-8 without BOM |
| Old commits in the workspace contained a personal Gmail address | history is forever; publish a fresh repo, archive the old one privately | `publish --public` scans history first |
| Tests used real public IPs (one was Cloudflare's public DNS server) and a real group name | use RFC 5737 addresses and neutral names | the staged-file scan flags public IPs; it even stopped gitship's own first commit, whose docs quoted that IP |

## 11. Exercises

1. In a scratch repo, commit a file, change it, commit again. Then run `git log -p` and find the first version. What does this tell you about "deleting" a secret?
2. Make two clones of a bare repo (`git init --bare r.git`), push from both, and resolve the rejected push with `git pull --rebase`, without forcing.
3. Run `gitship release 0.0.1 --dry-run` in a repo without a CHANGELOG section. What stops it?

**Self-check:** why does a release need the commit to be pushed *before* `gh release create`?

## References

**Official**
- §1 Git: [Pro Git book](https://git-scm.com/book/en/v2), [Git basics: recording changes](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository), [git-push](https://git-scm.com/docs/git-push), [git-commit](https://git-scm.com/docs/git-commit), [git-rev-parse](https://git-scm.com/docs/git-rev-parse)
- §5 [git-pull `--rebase`](https://git-scm.com/docs/git-pull), [git-fetch](https://git-scm.com/docs/git-fetch)
- §4 GitHub: [Setting your commit email address](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-email-preferences/setting-your-commit-email-address)
- §6 GitHub CLI: [gh repo create](https://cli.github.com/manual/gh_repo_create), [gh repo view](https://cli.github.com/manual/gh_repo_view)
- §7 GitHub: [Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository), [Secret scanning](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning), [About large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- §8 [Semantic Versioning](https://semver.org/), [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), [gh release create](https://cli.github.com/manual/gh_release_create), [gh release download](https://cli.github.com/manual/gh_release_download), [About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [Get-FileHash](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-filehash)
- IETF: [RFC 5737, IPv4 addresses reserved for documentation](https://www.rfc-editor.org/rfc/rfc5737)

**Other**
- [How to Write a Git Commit Message](https://cbea.ms/git-commit/)
- Atlassian: [Merging vs. rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing)

### Further learning
- [Learn Git Branching](https://learngitbranching.js.org/) (interactive)
- [Oh Shit, Git!?!](https://ohshitgit.com/): getting out of common messes
- GitHub Skills: [Introduction to GitHub](https://github.com/skills/introduction-to-github)
