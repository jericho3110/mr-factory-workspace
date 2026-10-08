import contextlib
import io
import unittest

from mrfactory.gitship.cli import build_parser, main

from .repos import TempRepos


class ParserTests(unittest.TestCase):
    def test_ship_needs_a_message(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["ship", "a.py"])

    def test_ship_arguments(self):
        a = build_parser().parse_args(["ship", "-m", "Add x", "a.py", "b.py", "--no-push", "-y"])
        self.assertEqual((a.message, a.paths, a.no_push, a.yes), ("Add x", ["a.py", "b.py"], True, True))

    def test_release_assets_repeat(self):
        a = build_parser().parse_args(["release", "0.2.0", "--asset", "x.exe", "--asset", "y.zip", "--dry-run"])
        self.assertEqual([p.name for p in a.asset], ["x.exe", "y.zip"])


class MainTests(unittest.TestCase):
    def test_where_inside_a_repo(self):
        repos = TempRepos(with_remote=False)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["-C", str(repos.work), "where"]), 0)
            self.assertIn("inside a repo", out.getvalue())
        finally:
            repos.cleanup()

    def test_errors_become_exit_code_1_with_a_message(self):
        repos = TempRepos(with_remote=False)
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = main(["-C", str(repos.work), "ship", "-m", "Added x", "--no-checks", "-y"])
            self.assertEqual(code, 1)
            self.assertIn("past tense", err.getvalue())
        finally:
            repos.cleanup()


if __name__ == "__main__":
    unittest.main()
