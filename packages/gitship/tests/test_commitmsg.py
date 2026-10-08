import unittest

from mrfactory.gitship.commitmsg import problems, split_prefix, with_trailer


class ProblemsTests(unittest.TestCase):
    def test_good_messages_pass(self):
        for msg in ("Add proxy picker", "adspower: Add --path option", "Fix crash on empty list\n\nWhy: ...\n"):
            self.assertEqual(problems(msg), [], msg)

    def test_each_rule(self):
        cases = {
            "": "empty",
            "A" * 73: "characters",
            "Add proxy picker.": "period",
            "feat: add proxy picker": "Conventional",
            "Added proxy picker": "past tense",
            "adspower: added option": "past tense",
            "add proxy picker": "capital",
            "Add proxy picker\nbody right away": "blank line",
        }
        for msg, expected in cases.items():
            found = " ".join(problems(msg))
            self.assertIn(expected, found, msg)

    def test_split_prefix(self):
        self.assertEqual(split_prefix("adspower: Add x"), ("adspower", "Add x"))
        self.assertEqual(split_prefix("Add x"), (None, "Add x"))


class TrailerTests(unittest.TestCase):
    def test_added_once_after_a_blank_line(self):
        t = "Co-Authored-By: A <a@example.com>"
        once = with_trailer("Add x\n\nBody", t)
        self.assertEqual(once, f"Add x\n\nBody\n\n{t}\n")
        self.assertEqual(with_trailer(once, t), once)

    def test_no_trailer(self):
        self.assertEqual(with_trailer("Add x", None), "Add x\n")


if __name__ == "__main__":
    unittest.main()
