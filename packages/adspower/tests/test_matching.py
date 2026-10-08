"""matching.py is pure (no I/O), so its tests need no fakes at all:
inputs in, answer out."""

import unittest

from mrfactory.adspower.matching import (
    contains,
    find_by_name_or_id,
    looks_like_profile_id,
    names,
    serial_order,
)
from mrfactory.adspower.models import Group


class TestMatching(unittest.TestCase):
    def test_contains_ignores_case_and_none_means_no_filter(self):
        self.assertTrue(contains("Acme", "ACM"))
        self.assertFalse(contains("Acme", "x"))
        self.assertTrue(contains("anything", None))

    def test_find_by_name_or_id(self):
        groups = [Group("1", "Acme"), Group("2", "Jetty")]
        self.assertEqual(find_by_name_or_id(groups, "acme").id, "1")
        self.assertEqual(find_by_name_or_id(groups, " 2 ").name, "Jetty")
        self.assertIsNone(find_by_name_or_id(groups, "acm"))  # exact names only, not parts

    def test_names(self):
        self.assertEqual(names([Group("1", "a"), Group("2", "b")]), "a, b")
        self.assertEqual(names([]), "(none)")

    def test_serial_order_is_numeric_then_text(self):
        serials = ["10", "x", "2", "a", "100"]
        self.assertEqual(sorted(serials, key=serial_order), ["2", "10", "100", "a", "x"])

    def test_looks_like_profile_id(self):
        self.assertTrue(looks_like_profile_id("k1abc2de"))
        self.assertFalse(looks_like_profile_id("1234"))       # a serial number
        self.assertFalse(looks_like_profile_id("shop"))       # plain text
        self.assertFalse(looks_like_profile_id("shop 7"))     # spaces


if __name__ == "__main__":
    unittest.main()
