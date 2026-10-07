import contextlib
import io
import unittest
from unittest import mock

from mrfactory.adspower.cli import prompts


def answers(*replies):
    """An `ask` function that returns the given replies in order."""
    queue = list(replies)
    return lambda prompt: queue.pop(0)


def closed_input(prompt):
    raise EOFError


class TestChoose(unittest.TestCase):
    def choose(self, items, ask):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result = prompts.choose(items, str, "Which?", ask=ask)
        return result, out.getvalue()

    def test_picks_by_number_and_retries_bad_input(self):
        result, out = self.choose(["a", "b"], answers("x", "3", "2"))
        self.assertEqual(result, "b")
        self.assertEqual(out.count("Please enter a number"), 2)

    def test_enter_or_closed_input_cancels(self):
        self.assertIsNone(self.choose(["a"], answers(""))[0])
        self.assertIsNone(self.choose(["a"], closed_input)[0])

    def test_shows_at_most_max_choices(self):
        items = [str(n) for n in range(prompts.MAX_CHOICES + 5)]
        _, out = self.choose(items, answers(""))
        self.assertIn("... and 5 more", out)


class TestConfirm(unittest.TestCase):
    def test_only_yes_means_yes(self):
        for reply, expected in [("y", True), ("YES", True), ("", False), ("n", False), ("yep", False)]:
            self.assertEqual(prompts.confirm("Sure?", ask=answers(reply)), expected, reply)

    def test_closed_input_means_no(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(prompts.confirm("Sure?", ask=closed_input))


class TestIsInteractive(unittest.TestCase):
    def test_redirected_input_is_not_interactive(self):
        with mock.patch("sys.stdin", io.StringIO("")):  # StringIO.isatty() is False
            self.assertFalse(prompts.is_interactive())

    def test_no_stdin_is_not_interactive(self):  # e.g. pythonw.exe
        with mock.patch("sys.stdin", None):
            self.assertFalse(prompts.is_interactive())

    def test_windows_nul_is_not_a_console(self):
        # NUL says isatty() is True; the console-mode check must say no.
        with open("NUL" if prompts.sys.platform == "win32" else "/dev/null") as nul, \
                mock.patch("sys.stdin", nul):
            self.assertFalse(prompts.is_interactive())


if __name__ == "__main__":
    unittest.main()
