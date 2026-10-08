"""ship / push / publish against real temp repos with a local bare 'GitHub'."""

import subprocess
import sys
import unittest

from mrfactory.gitship.runner import Completed
from mrfactory.gitship.workflow import ShipError, publish, repo_name, ship

from .repos import OK, FakeGh, TempRepos, git

PASSING = f'{{"checks": [["{sys.executable.replace(chr(92), "/")}", "-c", "pass"]]}}'
FAILING = f'{{"checks": [["{sys.executable.replace(chr(92), "/")}", "-c", "raise SystemExit(3)"]]}}'
ENV = {"USERNAME": "alice"}


class ShipTests(unittest.TestCase):
    def setUp(self):
        self.repos = TempRepos()
        self.repos.write(".gitship.json", PASSING)
        self.out: list[str] = []

    def tearDown(self):
        self.repos.cleanup()

    def ship(self, *paths, message="Add readme", **kw):
        kw.setdefault("yes", True)
        return ship(self.repos.work, message, paths, out=self.out.append, env=ENV, **kw)

    def test_commits_and_pushes_only_the_named_files(self):
        self.repos.write("README.md", "hello")
        self.repos.write("notes.txt", "my own unfinished work")
        self.ship("README.md", ".gitship.json")
        self.assertIn("Add readme", self.repos.remote_log())
        tracked = git(self.repos.work, "ls-files").split()
        self.assertNotIn("notes.txt", tracked)  # never swept up
        self.assertTrue(any("notes.txt" in line for line in self.out))

    def test_secret_blocks_the_commit(self):
        self.repos.write("settings.py", "KEY = '" + "sk-" + "ant-" + "x" * 30 + "'")
        with self.assertRaisesRegex(ShipError, "Anthropic"):
            self.ship("settings.py", ".gitship.json")
        with self.assertRaises(subprocess.CalledProcessError):  # no HEAD: nothing was committed
            git(self.repos.work, "rev-parse", "--verify", "HEAD")
        self.assertEqual(self.repos.remote_log(), "")

    def test_home_path_blocks_the_commit(self):
        self.repos.write("doc.md", r"C:\Users\alice\AppData")
        with self.assertRaisesRegex(ShipError, "home folder"):
            self.ship("doc.md", ".gitship.json")

    def test_failing_check_blocks_the_commit(self):
        self.repos.write(".gitship.json", FAILING)
        self.repos.write("a.txt", "a")
        with self.assertRaisesRegex(ShipError, "check failed"):
            self.ship("a.txt", ".gitship.json")
        self.assertEqual(self.repos.remote_log(), "")

    def test_bad_message_blocks_before_anything_else(self):
        self.repos.write("a.txt", "a")
        with self.assertRaisesRegex(ShipError, "past tense"):
            self.ship("a.txt", message="Added a")

    def test_no_checks_configured_needs_explicit_flag(self):
        (self.repos.work / ".gitship.json").unlink()
        self.repos.write("a.txt", "a")
        with self.assertRaisesRegex(ShipError, "no checks configured"):
            self.ship("a.txt")
        self.ship(allow_unchecked=True)  # a.txt is still staged from the first attempt
        self.assertIn("Add readme", self.repos.remote_log())

    def test_answering_no_commits_nothing(self):
        self.repos.write("a.txt", "a")
        with self.assertRaisesRegex(ShipError, "cancelled"):
            self.ship("a.txt", ".gitship.json", yes=False, ask=lambda _q: "")
        self.assertEqual(self.repos.remote_log(), "")

    def test_trailer_is_appended(self):
        self.repos.write(".gitship.json", PASSING[:-1] + ', "trailer": "Co-Authored-By: T <t@example.com>"}')
        self.repos.write("a.txt", "a")
        self.ship("a.txt", ".gitship.json")
        self.assertIn("Co-Authored-By: T", git(self.repos.work, "log", "-1", "--format=%B"))

    def test_rejected_push_is_never_forced(self):
        self.repos.write("a.txt", "a")
        self.ship("a.txt", ".gitship.json")
        # Someone else pushes first: clone, commit, push.
        other = self.repos.work.parent / "other"
        git(self.repos.work.parent, "clone", "-q", str(self.repos.remote), str(other))
        identity = ["-c", "user.name=O", "-c", "user.email=o@example.com"]
        git(other, *identity, "commit", "-q", "--allow-empty", "-m", "Theirs")
        git(other, "push", "-q", "origin", "main")
        self.repos.write("b.txt", "b")
        with self.assertRaisesRegex(ShipError, "NOT forcing"):
            self.ship("b.txt", message="Add b")
        self.assertIn("Theirs", self.repos.remote_log())  # their commit survived


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.repos = TempRepos(with_remote=False)
        self.repos.write("a.txt", "a")
        self.repos.commit_all()

    def tearDown(self):
        self.repos.cleanup()

    def fake(self, exists=False):
        return FakeGh({
            ("gh", "api", "user"): Completed(0, "alice\n", ""),
            ("gh", "repo", "view"): OK if exists else Completed(1, "", "not found"),
            ("gh", "repo", "create"): OK,
        })

    def test_repo_name(self):
        self.assertEqual(repo_name("Mr_Factory"), "mr-factory")
        self.assertEqual(repo_name("Disk_Cleanup"), "disk-cleanup")
        self.assertEqual(repo_name("TetoDesktop"), "teto-desktop")

    def test_private_by_default(self):
        gh = self.fake()
        full = publish(self.repos.work, "my-repo", yes=True, runner=gh, out=lambda _s: None, env=ENV)
        self.assertEqual(full, "alice/my-repo")
        create = [c for c in gh.calls if c[:3] == ["gh", "repo", "create"]][0]
        self.assertIn("--private", create)
        self.assertNotIn("--public", create)

    def test_existing_repo_is_never_reused(self):
        with self.assertRaisesRegex(ShipError, "already exists"):
            publish(self.repos.work, "taken", yes=True, runner=self.fake(exists=True), out=lambda _s: None, env=ENV)

    def test_public_needs_clean_history_and_the_typed_name(self):
        gh = self.fake()
        with self.assertRaisesRegex(ShipError, "cancelled"):
            publish(self.repos.work, "pub", public=True, runner=gh, ask=lambda _q: "yes", out=lambda _s: None, env=ENV)
        publish(self.repos.work, "pub", public=True, runner=gh, ask=lambda _q: "pub", out=lambda _s: None, env=ENV)
        self.assertIn("--public", [c for c in gh.calls if c[:3] == ["gh", "repo", "create"]][0])

    def test_public_refused_when_history_has_personal_data(self):
        self.repos.write("old.md", r"C:\Users\alice\Desktop")
        self.repos.commit_all("Add old notes")
        self.repos.write("old.md", "cleaned")  # deleting it later doesn't clean history
        self.repos.commit_all("Clean notes")
        with self.assertRaisesRegex(ShipError, "history contains"):
            publish(self.repos.work, "pub", public=True, runner=self.fake(), ask=lambda _q: "pub",
                    out=lambda _s: None, env=ENV)


if __name__ == "__main__":
    unittest.main()
