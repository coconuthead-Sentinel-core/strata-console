"""Capture thresholds and Whisper RAM budgeting.

Both graded functions are pure, so the verdict and the tier decision the
owner will actually see can be checked without a microphone attached and
without loading a model.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from strata_tools.voice_budget import (SAFETY_MB, TIER_LOAD_SECONDS,
                                       TIER_MODELS, TIER_ORDER, TIER_PEAK_MB,
                                       plan_tier, tier_cost)
from voice_check import SILENCE_FLOOR, SPEECH_FLOOR, verdict


class CaptureVerdictTests(unittest.TestCase):
    def test_measured_quiet_room_floor_reads_dead(self):
        # Bench measurement: Realtek array, nobody speaking.
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
        # Bench measurement: 0.076 peak on a spoken sentence at 16 kHz.
        self.assertEqual(verdict(0.076)[0], "GOOD")

    def test_floors_are_ordered(self):
        self.assertLess(SILENCE_FLOOR, SPEECH_FLOOR)


class TierBudgetTests(unittest.TestCase):
    def test_cost_is_measured_peak_plus_safety(self):
        self.assertEqual(tier_cost("Best"), TIER_PEAK_MB["Best"] + SAFETY_MB)

    def test_costs_are_ordered(self):
        costs = [tier_cost(t) for t in reversed(TIER_ORDER)]
        self.assertEqual(costs, sorted(costs))

    def test_best_fits_the_measured_free_ram(self):
        # medium.en was observed loading alone with 1638 MB free, so the
        # budget must not refuse it there.
        tier, note = plan_tier(1638, "Best")
        self.assertEqual(tier, "Best")
        self.assertEqual(note, "fits")

    def test_tight_ram_falls_back_to_fast_not_a_crash(self):
        # Measured a second time later in the session: 527 MB free.
        tier, note = plan_tier(527, "Best")
        self.assertEqual(tier, "Fast")
        self.assertIn("using Fast instead", note)

    def test_middling_ram_falls_back_to_accurate(self):
        self.assertEqual(plan_tier(900, "Best")[0], "Accurate")

    def test_no_tier_fits_is_a_stop_not_a_silent_downgrade(self):
        tier, note = plan_tier(200, "Best")
        self.assertIsNone(tier)
        # UPDATED 2026-09-02. This used to assert the note contained
        # "close Ollama" -- which pinned in place advice that could not
        # work. Measured on the owner's machine while he was hitting this
        # very stop: Ollama was holding 13 MB because its model was not
        # loaded, so closing it would have recovered nothing against a
        # 270 MB shortfall.
        #
        # A test that asserts exact wording locks the wording in, defect
        # and all. So this now checks what the message must ACHIEVE: name
        # the size of the gap, and offer something that would close it.
        self.assertIn("270 MB short", note)
        self.assertRegex(note, r"window|releases")

    def test_exact_fit_is_accepted(self):
        self.assertEqual(plan_tier(tier_cost("Accurate"), "Accurate")[0],
                         "Accurate")

    def test_one_megabyte_short_falls_back(self):
        self.assertEqual(plan_tier(tier_cost("Accurate") - 1,
                                   "Accurate")[0], "Fast")

    def test_fast_never_falls_back_to_anything_larger(self):
        self.assertEqual(plan_tier(6000, "Fast")[0], "Fast")

    def test_fast_below_its_own_cost_is_a_stop(self):
        self.assertIsNone(plan_tier(tier_cost("Fast") - 1, "Fast")[0])

    def test_every_tier_has_a_model_cost_and_load_estimate(self):
        for tier in TIER_ORDER:
            self.assertIn(tier, TIER_MODELS)
            self.assertIn(tier, TIER_PEAK_MB)
            self.assertIn(tier, TIER_LOAD_SECONDS)


if __name__ == "__main__":
    unittest.main()
