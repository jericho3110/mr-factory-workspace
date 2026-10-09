"""Whole-project behaviour: config, file selection, the scan, and the CLI, in temp git repos."""

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mrfactory.devtools import config
from mrfactory.devtools.cli import main
from mrfactory.devtools.security import scan_project

GIT = shutil.which("git") or "git"
FAKE_KEY = "sk-" + "ant-" + "z" * 30


class Repo:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmp.name)
        subprocess.run([GIT, "init", "-q"], cwd=self.root, check=True)  # noqa: S603

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def cleanup(self):
        self._tmp.cleanup()


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.cleanup()

    def test_missing_file_gives_defaults(self):
        cfg = config.load(self.repo.root)
        self.assertIn("node_modules", cfg.skip_dirs)
        self.assertEqual(cfg.rules, ())

    def test_bad_values_are_rejected(self):
        for bad in ('{"scan": {"rules": [{"description": "x", "pattern": "("}]}}',  # invalid regex
                    '{"links": {"ignore": "not-a-list"}}', "[1, 2]", "{oops"):
            self.repo.write(".devtools.json", bad)
            with self.assertRaises(config.ConfigError, msg=bad):
                config.load(self.repo.root)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.cleanup()

    def scan(self):
        return scan_project(self.repo.root, config.load(self.repo.root), env={"USERNAME": "alice"})

    def test_clean_project(self):
        self.repo.write("app.py", "print('hi')\n")
        self.assertEqual(self.scan(), [])

    def test_secret_code_pattern_and_home_path_are_found(self):
        self.repo.write("settings.py", f"KEY = '{FAKE_KEY}'\n")
        self.repo.write("run.py", "import os\nos." + "system(cmd)\n")
        self.repo.write("notes.md", "see C:\\Users\\alice\\Desktop\n")
        found = " | ".join(self.scan())
        for expected in ("Anthropic API key", "shell execution", "home folder"):
            self.assertIn(expected, found)

    def test_gitignored_secret_is_not_a_finding(self):
        self.repo.write(".gitignore", ".env\n")
        self.repo.write(".env", f"KEY={FAKE_KEY}\n")
        self.assertEqual(self.scan(), [])

    def test_project_rule_and_allow_paths(self):
        self.repo.write(".devtools.json", json.dumps({"scan": {
            "allow_paths": ["tests/fixtures/*"],
            "rules": [{"description": "delete outside the cleaner", "globs": ["*.py"],
                       "pattern": r"shutil\.rmtree", "except_paths": ["src/clean.py"]}]}}))
        self.repo.write("src/clean.py", "shutil.rmtree(p)\n")
        self.repo.write("src/sizes.py", "shutil.rmtree(p)\n")
        self.repo.write("tests/fixtures/leak.py", f"K = '{FAKE_KEY}'\n")
        found = self.scan()
        self.assertEqual(len(found), 1)
        self.assertIn("src/sizes.py", found[0])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.cleanup()

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["-C", str(self.repo.root), *args])
        return code, out.getvalue()

    def test_exit_codes(self):
        self.repo.write("README.md", "[ok](docs/A.md)\n")
        self.repo.write("docs/A.md", "x\n")
        self.assertEqual(self.run_cli("check", "--offline")[0], 0)
        self.repo.write("docs/B.md", "[gone](MISSING.md)\n")
        code, out = self.run_cli("links", "--offline")
        self.assertEqual(code, 1)
        self.assertIn("MISSING.md", out)

    def test_bad_config_is_exit_2(self):
        self.repo.write(".devtools.json", "{oops")
        self.assertEqual(self.run_cli("scan")[0], 2)


if __name__ == "__main__":
    unittest.main()
