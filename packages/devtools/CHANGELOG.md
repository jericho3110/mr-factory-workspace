# Changelog

What changed in each version of `mrfactory-devtools`, newest first.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-09

### Added

- `devtools scan`: dangerous code patterns for Python, JS/TS, C/C++, Go, Rust, Java, C#, PowerShell and bash,
  plus gitship's secret, personal-data, IP, never-commit and large-file checks, applied to every project file.
- `devtools links`: local Markdown links must exist, web links must load. Parenthesised targets are supported,
  code is skipped, ignore prefixes are honoured, and 403/429 counts as "blocked", not "dead".
- `devtools check`: both, with one exit code. `.devtools.json` adds skip dirs, ignore prefixes, allowed paths
  and project-specific rules.
- 18 tests.

### Fixed (compared with the copies it replaces)

- Link targets with parentheses (Wikipedia) were cut short and reported as dead.
- Error responses (`HTTPError`) are closed instead of leaking until garbage collection (found by a
  `ResourceWarning` in the tests).
