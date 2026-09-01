"""Clearing the window: the pure floor rules, and the DB that honours them.

The kernel is pure, so the rules are graded without Tk. The database
half runs against a temp file -- never the live quantum_nexus_forge.db.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.session import (STATE_KEY, clear_report, hidden_count,
                                  is_visible, next_floor, parse_floor)


class ParseFloorTests(unittest.TestCase):
    def test_missing_state_is_no_floor(self):
        self.assertEqual(parse_floor(None), 0)

    def test_text_digits_parse(self):
        # system_state stores TEXT, so the floor arrives as a string.
        self.assertEqual(parse_floor("12"), 12)
        self.assertEqual(parse_floor("  7 "), 7)

    def test_garbage_does_not_crash_the_console(self):
        # A hand-edited row must not take the app down at startup.
        for bad in ("", "abc", "3.5", [], {}):
            self.assertEqual(parse_floor(bad), 0)

    def test_negative_floor_is_treated_as_none(self):
        self.assertEqual(parse_floor("-4"), 0)


class NextFloorTests(unittest.TestCase):
    def test_clear_raises_the_floor_to_the_latest_thread(self):
        self.assertEqual(next_floor(0, 9), 9)

    def test_floor_is_monotonic_on_an_empty_database(self):
        # Clearing twice, second time with nothing logged, must not
        # un-hide the first batch.
        self.assertEqual(next_floor(9, 0), 9)

    def test_floor_never_moves_backwards(self):
        self.assertEqual(next_floor(20, 5), 20)

    def test_none_inputs_are_tolerated(self):
        self.assertEqual(next_floor(None, None), 0)


class VisibilityTests(unittest.TestCase):
    def test_threads_above_the_floor_are_visible(self):
        self.assertTrue(is_visible(10, 9))

    def test_the_floor_itself_is_hidden(self):
        self.assertFalse(is_visible(9, 9))

    def test_hidden_count_never_goes_negative(self):
        self.assertEqual(hidden_count(3, 5), 0)
        self.assertEqual(hidden_count(10, 4), 6)


class ClearReportTests(unittest.TestCase):
    def test_report_says_archived_not_deleted(self):
        msg = clear_report(3, 12)
        self.assertIn("3 turns", msg)
        self.assertIn("12", msg)
        self.assertIn("Nothing was deleted", msg)

    def test_single_turn_is_not_pluralised(self):
        self.assertIn("1 turn archived", clear_report(1, 1))

    def test_clearing_an_empty_window_says_so(self):
        self.assertIn("nothing was archived", clear_report(0, 0))


class DatabaseFloorTests(unittest.TestCase):
    """The floor as the console actually uses it -- on a temp DB."""

    def setUp(self):
        import strata_console
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = strata_console.StrataDB(path=self.tmp.name)

    def tearDown(self):
        self.db.conn.close()
        os.unlink(self.tmp.name)

    def add(self, n):
        for i in range(n):
            self.db.add_thread("2026-08-31", f"turn {i}", "GREEN")

    def test_clearing_hides_recall_but_deletes_nothing(self):
        self.add(4)
        self.assertEqual(len(self.db.recent_threads(10)), 4)
        cleared = self.db.raise_memory_floor()
        self.assertEqual(cleared, 4)
        # The model can no longer see them...
        self.assertEqual(self.db.recent_threads(10), [])
        self.assertEqual(self.db.thread_count(), 0)
        # ...but they are still on disk.
        self.assertEqual(self.db.archived_thread_count(), 4)

    def test_new_turns_after_a_clear_are_recalled_again(self):
        self.add(2)
        self.db.raise_memory_floor()
        self.add(1)
        recent = self.db.recent_threads(10)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["input"], "turn 0")

    def test_clearing_twice_in_a_row_is_harmless(self):
        self.add(2)
        self.assertEqual(self.db.raise_memory_floor(), 2)
        self.assertEqual(self.db.raise_memory_floor(), 0)
        self.assertEqual(self.db.archived_thread_count(), 2)

    def test_the_floor_survives_a_reopen(self):
        import strata_console
        self.add(3)
        self.db.raise_memory_floor()
        self.db.conn.close()
        reopened = strata_console.StrataDB(path=self.tmp.name)
        try:
            self.assertEqual(reopened.recent_threads(10), [])
            self.assertEqual(reopened.get_state(STATE_KEY), "3")
        finally:
            reopened.conn.close()
            self.db = reopened


class DatabasePathBindingTests(unittest.TestCase):
    """DB_PATH must be resolved when a connection is made, not when the
    class is defined -- and it must live in exactly ONE module.

    After the engine was split out of the shell, the shell deliberately
    does not re-export DB_PATH. A re-export would be a second name that
    tools could set while nothing read it: the same silent redirect
    failure as before, wearing a different hat.

    The original `def __init__(self, path=DB_PATH)` captured the module
    constant at import time, so a tool that set strata_core.DB_PATH to
    a throwaway file was silently ignored and wrote to the owner's real
    database. The accessibility probes did exactly that on 2026-09-01 and
    pressed A+ against the live store, changing a saved font size.
    """

    def test_setting_db_path_after_import_is_honoured(self):
        import strata_core
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        original = strata_core.DB_PATH
        strata_core.DB_PATH = tmp.name
        try:
            db = strata_core.StrataDB()
            self.assertEqual(db.path, tmp.name)
            db.conn.close()
        finally:
            strata_core.DB_PATH = original
            os.unlink(tmp.name)

    def test_an_explicit_path_still_wins(self):
        import strata_core
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            db = strata_core.StrataDB(path=tmp.name)
            self.assertEqual(db.path, tmp.name)
            db.conn.close()
        finally:
            os.unlink(tmp.name)


    def test_the_shell_does_not_shadow_the_setting(self):
        # A re-exported DB_PATH in the shell would be a name tools could
        # set while StrataDB reads the core's copy -- NM-005 again.
        import strata_console
        self.assertFalse(hasattr(strata_console, "DB_PATH"),
                         "strata_console must not define DB_PATH; the "
                         "engine owns it (see strata_core docstring)")


if __name__ == "__main__":
    unittest.main()
