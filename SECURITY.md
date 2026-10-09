# Security policy

## Reporting a vulnerability

Please **don't open a public issue** for a security problem. Use
GitHub's private reporting instead: the **Security** tab of this
repository → **Report a vulnerability**. You'll get a reply there.

Only the latest version on `main` is maintained.

## What this code handles

- **`adspower`** talks to the AdsPower Local API on this machine
  (`http://127.0.0.1:50325` by default). If API security verification is
  on, it sends the API key as a `Bearer` header.
  - Prefer the `ADSPOWER_API_KEY` environment variable over `--api-key`:
    command-line arguments can appear in shell history and process lists.
  - The key is never written to the crash log (it's redacted), and proxy
    passwords from the API are never loaded into memory objects or output.
  - Only `http://` and `https://` API URLs are accepted. If you point
    `--api-url` at another machine, use `https://`; over plain `http://`
    the key travels unencrypted.
- The plugin loading that used to live in `mouse-ext` is now in
  [natural-mouse](https://github.com/jericho3110/natural-mouse), with its own SECURITY.md.

## How this repository is protected

- No secrets in the code or history: checked before publishing, and
  GitHub secret scanning with push protection is enabled.
- `ruff check .` includes security rules (flake8-bandit) and runs in CI
  on every push; Dependabot watches dependencies and GitHub Actions.
