"""Tests for the language model's RAM budget.

The two measurements that motivate this file: 2.9 s per reply with
978 MB free, 103.5 s per reply with 475 MB free, identical code. The
kernel's job is to notice the second case and say so in numbers.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools import model_budget as mb

LLAMA_3B_BYTES = 2_324_546_189      # what Ollama reports for llama3.2:3b


class NeedTests(unittest.TestCase):
    def test_the_measured_model_needs_its_size_plus_margin(self):
        need = mb.model_need_mb(LLAMA_3B_BYTES)
        self.assertGreater(need, 2_200)
        self.assertLess(need, 2_700)

    def test_garbage_size_does_not_raise(self):
        self.assertEqual(mb.model_need_mb(None), mb.SAFETY_MB)
        self.assertEqual(mb.model_need_mb("x"), mb.SAFETY_MB)


class PlanTests(unittest.TestCase):
    def test_the_good_day_warms_quietly(self):
        """978 MB free was fine at 2.9 s? No -- 978 < 2,500, so even
        the 'good' measurement was already starved; it just had not
        tipped into the pagefile. The plan must say so."""
        p = mb.plan(978, LLAMA_3B_BYTES, "llama3.2:3b")
        self.assertTrue(p["starved"])

    def test_plenty_of_room_warms_without_comment(self):
        p = mb.plan(4_000, LLAMA_3B_BYTES, "llama3.2:3b")
        self.assertTrue(p["warm"])
        self.assertFalse(p["starved"])
        self.assertEqual(p["note"], "")

    def test_the_bad_day_is_named_in_numbers(self):
        """475 MB free is the measurement that produced a 103 s reply."""
        p = mb.plan(475, LLAMA_3B_BYTES, "llama3.2:3b")
        self.assertFalse(p["warm"])
        self.assertTrue(p["starved"])
        self.assertIn("475", p["note"])
        self.assertIn("llama3.2:3b", p["note"])
        self.assertIn("short", p["note"])

    def test_a_starved_machine_is_not_warmed(self):
        """Loading 2.3 GB into 475 MB of free RAM does not speed the
        first reply; it freezes the window while it is still drawing."""
        self.assertFalse(mb.plan(475, LLAMA_3B_BYTES)["warm"])

    def test_the_note_offers_two_actions(self):
        note = mb.plan(475, LLAMA_3B_BYTES, "llama3.2:3b")["note"]
        self.assertIn("Close other programs", note)
        self.assertIn(mb.LIGHTER_MODEL, note)

    def test_the_note_carries_both_measurements(self):
        """The owner asked whether RAM was the problem. The note answers
        with the evidence, not a verdict."""
        note = mb.plan(475, LLAMA_3B_BYTES)["note"]
        self.assertIn("3 s", note)
        self.assertIn("100 s", note)

    def test_unknown_model_size_does_not_block_warming(self):
        p = mb.plan(475, None)
        self.assertTrue(p["warm"])
        self.assertFalse(p["starved"])

    def test_garbage_free_ram_is_treated_as_zero(self):
        p = mb.plan("lots", LLAMA_3B_BYTES)
        self.assertTrue(p["starved"])


class StatusTests(unittest.TestCase):
    def test_the_figure_is_formatted_for_reading(self):
        self.assertEqual(mb.status_fragment(4123), "RAM 4,123 MB free")

    def test_unknown_is_a_question_mark_not_a_crash(self):
        self.assertEqual(mb.status_fragment(None), "RAM ?")


if __name__ == "__main__":
    unittest.main()
