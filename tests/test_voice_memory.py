"""Giving the voice model's memory back. Pure policy, graded headlessly.

Field report, 2026-09-02: dictation refused with "even Fast needs about
470 MB and only 406 MB is free". The guard behaved correctly -- it
declined instead of dying inside MKL, which is what it exists for -- but
the console was itself holding a model nobody was using.

Measured that day on the owner's 8 GB laptop:
    loading base.en          -134 MB free
    model + runtime resident  ~174 MB
    releasing the model       +221 MB free
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.voice_budget import (IDLE_RELEASE_SECONDS, LOW_RAM_MB,
                                       TIER_LOAD_SECONDS, plan_tier,
                                       release_reason, should_release,
                                       shortfall_advice, tier_cost)


class ReleasePolicyTests(unittest.TestCase):
    def test_a_model_in_active_use_is_kept(self):
        # Mid-session, plenty of room: reloading would cost 2.5s for
        # nothing.
        self.assertFalse(should_release(10, 3000))

    def test_an_idle_model_is_released(self):
        self.assertTrue(should_release(IDLE_RELEASE_SECONDS, 3000))

    def test_low_memory_releases_even_when_recently_used(self):
        # Somebody else needs it more than a warm cache does.
        self.assertTrue(should_release(1, LOW_RAM_MB - 1))

    def test_nothing_loaded_is_never_released(self):
        self.assertFalse(should_release(9999, 10, loaded=False))

    def test_garbage_inputs_do_not_release(self):
        # A clock or a memory read that failed must not silently throw
        # the model away.
        self.assertFalse(should_release(None, 3000))
        self.assertFalse(should_release(10, "lots"))

    def test_the_owners_reported_condition_would_release(self):
        # 406 MB free is what he actually saw.
        self.assertTrue(should_release(1, 406))

    def test_the_threshold_sits_above_the_smallest_tier(self):
        # Releasing must kick in BEFORE free RAM drops under what Fast
        # needs, or it only ever fires after dictation has already
        # failed.
        self.assertGreater(LOW_RAM_MB, tier_cost("Fast"))


class ReleaseMessageTests(unittest.TestCase):
    """A background action that changes how long the next dictation takes
    should not be a surprise."""

    def test_low_memory_release_says_why(self):
        msg = release_reason(1, 400)
        self.assertIn("400", msg)
        self.assertIn("free", msg)

    def test_idle_release_says_it_will_come_back(self):
        msg = release_reason(IDLE_RELEASE_SECONDS, 3000)
        self.assertIn("idle", msg)
        self.assertIn(str(TIER_LOAD_SECONDS["Fast"]), msg)

    def test_a_broken_memory_read_still_produces_a_sentence(self):
        self.assertTrue(release_reason(10, None).strip())


class ShortfallAdviceTests(unittest.TestCase):
    """The old text sent the owner to close Ollama, which was holding
    13 MB. Advice that cannot work is a defect -- it is what kept FB-002
    alive for weeks."""

    def test_it_names_the_actual_gap(self):
        # 470 needed, 406 free -> 64 short.
        self.assertIn("64", shortfall_advice(406))

    def test_it_no_longer_singles_out_ollama(self):
        advice = shortfall_advice(406)
        self.assertNotIn("close Ollama", advice)

    def test_it_mentions_the_lever_that_returns_the_most(self):
        self.assertIn("window", shortfall_advice(406))

    def test_it_tells_the_owner_strata_frees_its_own(self):
        self.assertIn("releases", shortfall_advice(406))

    def test_the_full_stop_message_carries_the_advice(self):
        tier, note = plan_tier(406, "Fast")
        self.assertIsNone(tier)
        self.assertIn("64 MB short", note)

    def test_no_shortfall_is_reported_as_zero_not_negative(self):
        self.assertIn("0 MB short", shortfall_advice(5000))


if __name__ == "__main__":
    unittest.main()
