"""WCAG contrast -- the math, and this console's real palette.

The palette test is a characterisation test, not an aspiration: it pins
the two known shortfalls with their reasons and fails on any NEW one.
Asserting that everything passes AA would fail the build over a design
decision this build is not permitted to make.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.wcag import (AA_LARGE, AA_NORMAL, ACCEPTED_SHORTFALLS,
                               PALETTE, audit, contrast_ratio, failures,
                               format_audit, meets_aa, relative_luminance)


class MathTests(unittest.TestCase):
    """Checked against the W3C's own published values."""

    def test_black_on_white_is_the_maximum(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0,
                               places=2)

    def test_identical_colours_are_one_to_one(self):
        self.assertAlmostEqual(contrast_ratio("#1F6AA5", "#1F6AA5"), 1.0,
                               places=6)

    def test_the_ratio_is_symmetric(self):
        self.assertAlmostEqual(contrast_ratio("#DCE4EE", "#1F6AA5"),
                               contrast_ratio("#1F6AA5", "#DCE4EE"),
                               places=9)

    def test_luminance_endpoints(self):
        self.assertAlmostEqual(relative_luminance("#000000"), 0.0, places=6)
        self.assertAlmostEqual(relative_luminance("#FFFFFF"), 1.0, places=6)

    def test_shorthand_hex_is_accepted(self):
        self.assertAlmostEqual(relative_luminance("#fff"),
                               relative_luminance("#FFFFFF"), places=9)

    def test_a_bad_colour_is_rejected_loudly(self):
        for bad in ("#12345", "not-a-colour", ""):
            with self.assertRaises(ValueError):
                relative_luminance(bad)


class ThresholdTests(unittest.TestCase):
    def test_aa_thresholds_are_the_published_ones(self):
        self.assertEqual((AA_NORMAL, AA_LARGE), (4.5, 3.0))

    def test_exactly_on_the_threshold_passes(self):
        self.assertTrue(meets_aa(4.5))
        self.assertTrue(meets_aa(3.0, large=True))

    def test_just_under_fails(self):
        self.assertFalse(meets_aa(4.49))

    def test_large_text_has_the_lower_bar(self):
        self.assertFalse(meets_aa(3.5))
        self.assertTrue(meets_aa(3.5, large=True))


class PaletteTests(unittest.TestCase):
    def test_no_shortfall_beyond_the_accepted_ones(self):
        unexpected = [row["name"] for row in failures()
                      if row["name"] not in ACCEPTED_SHORTFALLS]
        self.assertEqual(unexpected, [],
                         "new contrast failure(s):\n"
                         + "\n".join(format_audit(failures())))

    def test_every_accepted_shortfall_is_still_real(self):
        # If one gets fixed, this list must shrink -- a stale exception
        # is a hole in the gate.
        failing = {row["name"] for row in failures()}
        for name in ACCEPTED_SHORTFALLS:
            self.assertIn(name, failing,
                          f"{name!r} now passes; remove it from "
                          f"ACCEPTED_SHORTFALLS")

    def test_every_accepted_shortfall_carries_a_reason(self):
        for name, reason in ACCEPTED_SHORTFALLS.items():
            self.assertGreater(len(reason), 60,
                               f"{name!r} needs a real reason, not a note")

    def test_the_reading_surfaces_pass_comfortably(self):
        # The transcript is what the owner actually reads; it must not
        # merely scrape past the threshold.
        rows = {row["name"]: row for row in audit()}
        self.assertGreater(rows["transcript text"]["ratio"], 10.0)
        self.assertGreater(rows["input box text"]["ratio"], 7.0)

    def test_the_palette_describes_the_real_app(self):
        self.assertGreaterEqual(len(PALETTE), 7)
        for name, foreground, background, large in PALETTE:
            self.assertTrue(name and foreground.startswith("#")
                            and background.startswith("#"))
            self.assertIsInstance(large, bool)


if __name__ == "__main__":
    unittest.main()
