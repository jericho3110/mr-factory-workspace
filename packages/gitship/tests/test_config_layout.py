import tempfile
import unittest
from pathlib import Path

from mrfactory.gitship import config
from mrfactory.gitship.layout import Kind, locate

from .repos import TempRepos, git


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text):
        (self.root / config.FILE_NAME).write_text(text, encoding="utf-8")

    def test_missing_file_means_no_checks(self):
        self.assertEqual(config.load(self.root).checks, ())

    def test_reads_checks_trailer_allow(self):
        self.write('{"checks": [["ruff", "check", "."]], "trailer": "T", "allow": ["x/*"]}')
        cfg = config.load(self.root)
        self.assertEqual(cfg.checks, (("ruff", "check", "."),))
        self.assertEqual((cfg.trailer, cfg.allow), ("T", ("x/*",)))

    def test_a_shell_string_is_rejected(self):
        # a single string would need a shell to run; only argument lists are allowed
        self.write('{"checks": ["ruff check . && del /s *"]}')
        with self.assertRaises(config.ConfigError):
            config.load(self.root)

    def test_bad_json(self):
        self.write("{nope")
        with self.assertRaises(config.ConfigError):
            config.load(self.root)


class LayoutTests(unittest.TestCase):
    def test_inside_a_repo(self):
        repos = TempRepos(with_remote=False)
        try:
            (repos.work / "sub").mkdir()
            loc = locate(repos.work / "sub")
            self.assertIs(loc.kind, Kind.INSIDE)
            self.assertEqual(loc.repo.resolve(), repos.work.resolve())
        finally:
            repos.cleanup()

    def test_parent_of_repos_and_empty_folder(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            (base / "empty").mkdir()
            self.assertIs(locate(base / "empty").kind, Kind.NONE)
            for name in ("ProjA", "group/ProjB"):
                (base / name).mkdir(parents=True)
                git(base / name, "init", "-q")
            (base / "venv/lib/x").mkdir(parents=True)
            git(base / "venv/lib/x", "init", "-q")  # inside a skipped folder: ignored
            loc = locate(base)
            self.assertIs(loc.kind, Kind.PARENT)
            # sorted by name here: Windows compares paths case-insensitively, Linux doesn't
            self.assertEqual(sorted(p.name for p in loc.subrepos), ["ProjA", "ProjB"])
            self.assertIn("do NOT `git init`", loc.advice())


if __name__ == "__main__":
    unittest.main()
