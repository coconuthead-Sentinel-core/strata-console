"""Select-all -- the control that looked present and did nothing.

Headless: the kernel dispatches on capability, so fakes standing in for
each widget family are a faithful test.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.selection import select_all


class FakeTextbox:
    """The CTkTextbox shape: tag_add / mark_set / see."""

    def __init__(self):
        self.calls = []

    def tag_add(self, *a):
        self.calls.append(("tag_add",) + a)

    def mark_set(self, *a):
        self.calls.append(("mark_set",) + a)

    def see(self, *a):
        self.calls.append(("see",) + a)


class FakeEntry:
    """The CTkEntry shape: select_range / icursor."""

    def __init__(self):
        self.calls = []

    def select_range(self, *a):
        self.calls.append(("select_range",) + a)

    def icursor(self, *a):
        self.calls.append(("icursor",) + a)


class FakeLabel:
    """Neither family -- the case that used to fail invisibly."""


class TextFamilyTests(unittest.TestCase):
    def test_selects_the_whole_buffer(self):
        box = FakeTextbox()
        select_all(box)
        self.assertIn(("tag_add", "sel", "1.0", "end"), box.calls)

    def test_moves_the_view_to_the_top(self):
        box = FakeTextbox()
        select_all(box)
        self.assertIn(("mark_set", "insert", "1.0"), box.calls)
        self.assertIn(("see", "insert"), box.calls)


class EntryFamilyTests(unittest.TestCase):
    def test_selects_the_whole_field(self):
        entry = FakeEntry()
        select_all(entry)
        self.assertIn(("select_range", 0, "end"), entry.calls)

    def test_leaves_the_cursor_at_the_end(self):
        entry = FakeEntry()
        select_all(entry)
        self.assertIn(("icursor", "end"), entry.calls)

    def test_the_entry_path_never_calls_the_text_api(self):
        # The original defect: one API assumed for both species.
        entry = FakeEntry()
        select_all(entry)
        self.assertFalse(any(c[0] == "tag_add" for c in entry.calls))


class UnsupportedWidgetTests(unittest.TestCase):
    def test_raises_rather_than_failing_invisibly(self):
        with self.assertRaises(AttributeError) as caught:
            select_all(FakeLabel())
        self.assertIn("FakeLabel", str(caught.exception))

    def test_the_error_says_what_is_wrong(self):
        with self.assertRaises(AttributeError) as caught:
            select_all(FakeLabel())
        message = str(caught.exception)
        self.assertIn("tag_add", message)
        self.assertIn("select_range", message)


if __name__ == "__main__":
    unittest.main()
