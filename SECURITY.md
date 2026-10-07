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
- **`mouse-ext`** can load plugins named in a string
  (`PluginManager.load_path`) or advertised by installed packages
  (`load_entry_points`). Both **run that code**, so only load plugins
  from sources you trust, as with any Python package you install.

## How this repository is protected

- No secrets in the code or history: checked before publishing, and
  GitHub secret scanning with push protection is enabled.
- `ruff check .` includes security rules (flake8-bandit) and runs in CI
  on every push; Dependabot watches dependencies and GitHub Actions.
