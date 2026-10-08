import hashlib
import shutil
import unittest
from pathlib import Path

from mrfactory.gitship.release import ReleaseError, changelog_section, plan, publish, verify
from mrfactory.gitship.runner import Completed

from .repos import OK, FakeGh, TempRepos, git

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-10-08

### Added
- Quit button.

## [0.1.0] - 2026-10-01

### Added
- First version.
"""


class ChangelogTests(unittest.TestCase):
    def test_extracts_one_section(self):
        self.assertEqual(changelog_section(CHANGELOG, "0.2.0"), "### Added\n- Quit button.")
        self.assertEqual(changelog_section(CHANGELOG, "0.1.0"), "### Added\n- First version.")
        self.assertIsNone(changelog_section(CHANGELOG, "9.9.9"))

    def test_dots_are_literal(self):
        self.assertIsNone(changelog_section("## [0x2x0]\nx", "0.2.0"))


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.repos = TempRepos()
        self.repos.write("CHANGELOG.md", CHANGELOG)
        self.asset = self.repos.write("dist/app.bin", "binary-ish payload")
        (self.repos.work / ".gitignore").write_text("dist/\n", encoding="utf-8")
        self.repos.commit_all("Add changelog")
        git(self.repos.work, "push", "-q", "-u", "origin", "main")

    def tearDown(self):
        self.repos.cleanup()

    def plan(self, version="0.2.0", assets=None, runner=None):
        kw = {"runner": runner} if runner else {}
        return plan(self.repos.work, version, [self.asset] if assets is None else assets, **kw)

    def test_plan_has_tag_notes_and_hash(self):
        p = self.plan()
        self.assertEqual(p.tag, "v0.2.0")
        self.assertIn("Quit button", p.notes)
        self.assertEqual(p.assets[0].sha256, hashlib.sha256(b"binary-ish payload").hexdigest())
        self.assertEqual(p.sums_text(), f"{p.assets[0].sha256}  app.bin\n")

    def test_gates(self):
        with self.assertRaisesRegex(ReleaseError, "SemVer"):
            self.plan("v0.2")
        with self.assertRaisesRegex(ReleaseError, "no '## \\[0.3.0\\]'"):
            self.plan("0.3.0")
        with self.assertRaisesRegex(ReleaseError, "asset not found"):
            self.plan(assets=[Path("nope.exe")])
        git(self.repos.work, "tag", "v0.2.0")
        with self.assertRaisesRegex(ReleaseError, "already exists"):
            self.plan()

    def test_uncommitted_or_unpushed_work_blocks(self):
        self.repos.write("CHANGELOG.md", CHANGELOG + "\nedit")
        with self.assertRaisesRegex(ReleaseError, "uncommitted"):
            self.plan()
        self.repos.commit_all("Edit changelog")
        with self.assertRaisesRegex(ReleaseError, "1 ahead"):
            self.plan()

    def test_publish_uploads_assets_and_sums(self):
        gh = FakeGh({("gh", "release", "create"): Completed(0, "https://github.com/a/b/releases/tag/v0.2.0\n", "")})
        url = publish(self.plan(), self.repos.work, runner=gh)
        self.assertTrue(url.endswith("v0.2.0"))
        call = gh.calls[0]
        self.assertEqual(call[:4], ["gh", "release", "create", "v0.2.0"])
        self.assertTrue(any(a.endswith("app.bin") for a in call))
        self.assertTrue(any(a.endswith("SHA256SUMS") for a in call))
        self.assertIn("--notes-file", call)

    def test_verify_private_repo_compares_hashes(self):
        p = self.plan()

        def fake_download(good: bool):
            def answer(argv, cwd):
                if argv[:3] == ["gh", "repo", "view"]:
                    return Completed(0, "alice/app PRIVATE\n", "")
                if argv[:3] == ["gh", "release", "download"]:
                    out_dir = Path(argv[argv.index("--dir") + 1])
                    if good:
                        shutil.copy(self.asset, out_dir / "app.bin")
                    else:
                        (out_dir / "app.bin").write_text("tampered", encoding="utf-8")
                    return OK
                return Completed(1, "", "unexpected")
            return answer

        self.assertEqual(verify(p, self.repos.work, runner=fake_download(True)), [])
        self.assertIn("doesn't match", verify(p, self.repos.work, runner=fake_download(False))[0])


if __name__ == "__main__":
    unittest.main()
