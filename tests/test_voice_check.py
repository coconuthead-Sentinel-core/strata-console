"""Thresholds and RAM budgeting for the voice-path bench check.

Both graded functions are pure, so the verdicts the owner will read can
be checked without a microphone and without loading a Whisper model.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from voice_check import (HEADROOM_MB, SILENCE_FLOOR, SPEECH_FLOOR,
                         TIER_COST_MB, tier_plan, verdict)


class CaptureVerdictTests(unittest.TestCase):
    def test_measured_quiet_room_floor_reads_dead(self):
        # Bench measurement, Realtek array, nobody speaking.
        label, why = verdict(0.00046)
        self.assertEqual(label, "DEAD")
        self.assertIn("not you", why)

    def test_hard_zero_reads_dead(self):
        self.assertEqual(verdict(0.0)[0], "DEAD")

    def test_exactly_on_the_silence_floor_reads_dead(self):
        self.assertEqual(verdict(SILENCE_FLOOR)[0], "DEAD")

    def test_between_the_floors_reads_weak(self):
        self.assertEqual(verdict(0.005)[0], "WEAK")

    def test_measured_spoken_sentence_reads_good(self):
        # Bench measurement: 0.076 peak on a synthesised sentence.
        self.assertEqual(verdict(0.076)[0], "GOOD")

    def test_floors_are_ordered(self):
        self.assertLess(SILENCE_FLOOR, SPEECH_FLOOR)


class TierBudgetTests(unittest.TestCase):
    def test_plenty_of_ram_keeps_the_requested_tier(self):
        tier, note = tier_plan(6000, "Best")
        self.assertEqual(tier, "Best")
        self.assertEqual(note, "fits")

    def test_measured_free_ram_cannot_hold_best(self):
        # Bench measurement: 7.7 GB total, 1.6 GB free, 79% load.
        tier, note = tier_plan(1638, "Best")
        self.assertEqual(tier, "Accurate")
        self.assertIn("falling back", note)

    def test_falls_all_the_way_to_fast_when_tight(self):
        tier, _ = tier_plan(TIER_COST_MB["Fast"] + HEADROOM_MB, "Best")
        self.assertEqual(tier, "Fast")

    def test_no_tier_fits_is_a_stop_not_a_fallback(self):
        tier, note = tier_plan(100, "Best")
        self.assertIsNone(tier)
        self.assertIn("close Ollama", note)

    def test_exact_fit_is_accepted(self):
        need = TIER_COST_MB["Accurate"] + HEADROOM_MB
        self.assertEqual(tier_plan(need, "Accurate")[0], "Accurate")

    def test_one_byte_short_falls_back(self):
        need = TIER_COST_MB["Accurate"] + HEADROOM_MB
        self.assertEqual(tier_plan(need - 1, "Accurate")[0], "Fast")

    def test_fast_never_falls_back_to_anything_larger(self):
        self.assertEqual(tier_plan(6000, "Fast")[0], "Fast")

    def test_tier_costs_are_ordered(self):
        self.assertLess(TIER_COST_MB["Fast"], TIER_COST_MB["Accurate"])
        self.assertLess(TIER_COST_MB["Accurate"], TIER_COST_MB["Best"])


if __name__ == "__main__":
    unittest.main()
