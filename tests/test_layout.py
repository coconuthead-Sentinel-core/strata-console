"""Content fitting the window -- the check FB-001 never made.

Pure arithmetic, graded without a display. The empirical half lives in
tools/layout_probe.py, which counts controls Tk actually mapped.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.layout import (CHROME_AT_1, MAX_SCALING, MIN_SCALING,
                                 MIN_TRANSCRIPT, UI_FONT_MAX, UI_FONT_MIN,
                                 chrome_height, content_fits, describe,
                                 plan_widget_scaling, transcript_height,
                                 ui_font_is_capped, ui_font_size)

OWNER_WINDOW = 487        # what window_fit yields on a 617px screen


class ChromeTests(unittest.TestCase):
    def test_chrome_scales_linearly_as_measured(self):
        # Measured: 529 at 1.0 and 919 at 1.75, a ratio of 1.737.
        self.assertAlmostEqual(chrome_height(1.75) / chrome_height(1.0),
                               1.75, places=6)

    def test_the_defect_configuration_does_not_fit(self):
        # The console as it shipped: inherited 1.75 scaling in a 486px
        # window. This must report False, or the kernel is useless.
        self.assertFalse(content_fits(486, 1.75))

    def test_the_chosen_configuration_fits(self):
        scaling = plan_widget_scaling(OWNER_WINDOW)
        self.assertTrue(content_fits(OWNER_WINDOW, scaling))


class ScalingTests(unittest.TestCase):
    def test_the_owner_display_gets_a_scaling_that_fits(self):
        scaling = plan_widget_scaling(OWNER_WINDOW)
        self.assertGreaterEqual(scaling, MIN_SCALING)
        self.assertLessEqual(scaling, MAX_SCALING)
        self.assertGreaterEqual(
            transcript_height(OWNER_WINDOW, scaling), MIN_TRANSCRIPT - 1)

    def test_a_tall_screen_is_not_scaled_past_the_ceiling(self):
        self.assertEqual(plan_widget_scaling(4000), MAX_SCALING)

    def test_a_tiny_window_clamps_instead_of_returning_nonsense(self):
        self.assertEqual(plan_widget_scaling(10), MIN_SCALING)

    def test_a_window_smaller_than_the_transcript_floor_clamps(self):
        self.assertEqual(plan_widget_scaling(MIN_TRANSCRIPT - 1),
                         MIN_SCALING)

    def test_zero_chrome_does_not_divide_by_zero(self):
        self.assertEqual(plan_widget_scaling(500, chrome_at_1=0),
                         MAX_SCALING)

    def test_bigger_windows_never_get_smaller_scaling(self):
        previous = 0
        for height in (300, 400, 500, 700, 900, 1200):
            scaling = plan_widget_scaling(height)
            self.assertGreaterEqual(scaling, previous)
            previous = scaling


class DescribeTests(unittest.TestCase):
    def test_a_fitting_layout_says_so_with_numbers(self):
        note = describe(OWNER_WINDOW, plan_widget_scaling(OWNER_WINDOW))
        self.assertIn("fits", note)
        self.assertIn("transcript", note)

    def test_a_clipped_layout_says_controls_will_be_clipped(self):
        note = describe(486, 1.75)
        self.assertIn("does NOT fit", note)
        self.assertIn("clipped", note)


class UiFontTests(unittest.TestCase):
    """WCAG 1.4.4 asks for resize WITHOUT loss of functionality. The cap
    is where those two halves meet, and it was measured."""

    def test_the_cap_is_the_measured_value(self):
        # Sweeping chrome sizes at 36pt reading size: 12 lost nothing,
        # 13 lost the "Mode: Red" button to horizontal overflow.
        self.assertEqual(UI_FONT_MAX, 12)

    def test_the_chrome_follows_the_reading_size_below_the_cap(self):
        self.assertEqual(ui_font_size(11), 11)

    def test_the_chrome_stops_at_the_cap(self):
        self.assertEqual(ui_font_size(36), UI_FONT_MAX)

    def test_the_chrome_never_goes_below_the_floor(self):
        self.assertEqual(ui_font_size(4), UI_FONT_MIN)

    def test_garbage_is_survivable(self):
        self.assertEqual(ui_font_size(None), UI_FONT_MIN)
        self.assertEqual(ui_font_size("big"), UI_FONT_MIN)
        self.assertFalse(ui_font_is_capped("big"))

    def test_the_owner_is_told_when_the_cap_binds(self):
        # A control that silently stops responding reads as broken.
        self.assertFalse(ui_font_is_capped(UI_FONT_MAX))
        self.assertTrue(ui_font_is_capped(UI_FONT_MAX + 1))


if __name__ == "__main__":
    unittest.main()
