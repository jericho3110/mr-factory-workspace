# Changelog

What changed in each version of `mrfactory-gitship`, newest first.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- `.env.example` (and `.env.sample` / `.env.template`) can be committed: they list
  variable names only. Their contents are still scanned for secrets.

## [0.1.0] - 2026-10-08

### Added

- `gitship where`: inside a repo, a parent folder of repos, or no repo.
- `gitship check`: configured checks + a scan of the staged files.
- `gitship ship`: stage named files (or `--all`) → message rules → scan →
  checks → `[y/N]` → commit (message written to a UTF-8 file, no BOM) → push.
- `gitship push`: on a rejected push, fetch and report ahead/behind; never forces.
- `gitship publish`: private by default; refuses existing names; `--public`
  scans all history and needs the name typed.
- `gitship release`: SemVer, new tag, clean and pushed tree, CHANGELOG
  section, assets + `SHA256SUMS`, then re-download and compare hashes
  (anonymously for public repos).
- `.gitship.json` for checks, commit trailer, scan allow-list, changelog path.
- 45 tests with real temp repos and a local bare remote.
