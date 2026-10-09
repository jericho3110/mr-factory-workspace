# devtools

One **security scanner** and one **Markdown link checker** for every project.
A code graph of these workspaces found a link checker copied into 7 projects
and a security scanner into 6 (see [docs/CODE_GRAPH.md](../../docs/CODE_GRAPH.md)).
Every copy had to be fixed separately. This package is the single copy.

```powershell
pip install -e packages/gitship -e packages/devtools   # devtools reuses gitship's file scanner
devtools scan                # code patterns, secrets, personal data, never-commit files
devtools links               # local links exist, web links load
devtools links --offline     # local links only (fast, no network)
devtools check               # both; exit code 0 only if both pass
devtools -C ..\OtherProject scan
```

## What `scan` looks for

| Layer | Examples | From |
| --- | --- | --- |
| code patterns | `shell=True`, `eval(`, `pickle.loads`, SQL built with f-strings, `innerHTML =`, `strcpy`, `atoi`, `Invoke-Expression`, `curl … \| sh`, `0.0.0.0` listeners, disabled TLS checks | `codescan.py` |
| secrets | Anthropic / GitHub / AWS / Slack tokens, private keys, `password = "…"` | gitship `scan.py` |
| personal data | your home path (`C:\Users\<you>`), your git email (GitHub's noreply address is fine), real IPs (use RFC 5737 `203.0.113.x`) | gitship `scan.py` |
| files | `.env`, `*.pem`, `*.key`, browser `Cookies`, build output, files over 5 MB | gitship `scan.py` |

It scans what git would commit: tracked files plus new files that
`.gitignore` doesn't exclude. A secret in an ignored `.env` is safe; one in a
new, unstaged file is about to leak.

Opt a line out with a trailing comment containing `security-scan: allow`
and the reason, e.g. `self.conn.execute(f"PRAGMA user_version = {n}")  # security-scan: allow (int only)`.

## `.devtools.json` (optional)

```json
{
  "skip_dirs": ["docs/generated"],
  "links": {"ignore": ["https://github.com/me/my-private-repo"]},
  "scan": {
    "allow_paths": ["tests/fixtures/*"],
    "rules": [
      {"description": "delete call outside the cleaner", "globs": ["*.py"],
       "pattern": "shutil\\.rmtree", "except_paths": ["src/clean.py"]}
    ]
  }
}
```

| Key | Meaning |
| --- | --- |
| `skip_dirs` | folders to skip, in addition to `node_modules`, `dist`, `build`, `target`, `venv`, `graphify-out`, … |
| `links.ignore` | URL prefixes the link checker skips (e.g. private repos, which return 404 to scripts) |
| `scan.allow_paths` | path patterns the scan skips entirely (deliberate test fixtures) |
| `scan.rules` | extra project rules: a regex for files matching `globs`, except `except_paths` |

## Using it in a project

Add it to the project's check gate. With gitship, in `.gitship.json`:

```json
{"checks": [["python", "-m", "unittest"], ["devtools", "scan"], ["devtools", "links", "--offline"]]}
```

The web link check depends on outside websites (a slow site can time out), so
run `devtools links` by hand before a release rather than on every commit.

## Layout

```text
src/mrfactory/devtools/
  files.py     which files belong to the project (git's view)
  config.py    .devtools.json
  codescan.py  dangerous code patterns (pure)
  security.py  codescan + gitship's file scan
  links.py     Markdown link extraction and checking
  cli.py       the command
tests/         18 tests: planted findings + safe twins, fake HTTP opener, temp git repos
```

Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Tests

```powershell
python scripts/test_all.py devtools      # from the workspace root
```

## References

**Official**
- [git-ls-files](https://git-scm.com/docs/git-ls-files) (`--others --exclude-standard`)
- MITRE: [CWE-78](https://cwe.mitre.org/data/definitions/78.html), [CWE-89](https://cwe.mitre.org/data/definitions/89.html), [CWE-95 (eval injection)](https://cwe.mitre.org/data/definitions/95.html), [CWE-502 (unsafe deserialization)](https://cwe.mitre.org/data/definitions/502.html), [CWE-120](https://cwe.mitre.org/data/definitions/120.html), [CWE-79 (XSS)](https://cwe.mitre.org/data/definitions/79.html)
- [CommonMark: links](https://spec.commonmark.org/0.31.2/#links) (why link targets may contain balanced parentheses)

### Further learning
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
