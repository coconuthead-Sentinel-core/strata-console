"""Controls visible as shapes -- WCAG 1.4.11 Non-text Contrast, AA.

The audit before this one checked the TEXT on the buttons and never the
button against what it sits on. These re-measure both, so the gap cannot
reopen quietly.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.modes import MODES
from strata_tools.theme import (BUTTON_MIN_HEIGHT, FILLS, FRAME, NON_TEXT_MIN,
                                OUTLINE, OUTLINE_WIDTH, SELECTED_OUTLINE,
                                SELECTED_OUTLINE_WIDTH, TEXT, outline_kwargs,
                                surfaces_to_check)
from strata_tools.wcag import contrast_ratio, meets_aa


class OutlineContrastTests(unittest.TestCase):
    def test_the_outline_clears_three_to_one_everywhere(self):
        failures = [f"{name} {contrast_ratio(a, b):.2f}:1"
                    for name, (a, b) in surfaces_to_check().items()
                    if contrast_ratio(a, b) < NON_TEXT_MIN]
        self.assertEqual(failures, [],
                         f"outline {OUTLINE} is invisible on: "
                         + ", ".join(failures))

    def test_the_selected_outline_also_clears_everywhere(self):
        failures = [name for name, (_, bg) in surfaces_to_check().items()
                    if contrast_ratio(SELECTED_OUTLINE, bg) < NON_TEXT_MIN]
        self.assertEqual(failures, [])

    def test_the_outline_has_margin_over_the_rejected_candidate(self):
        # #B3BECA passed, but by 3.04:1 on the blue fill -- one nudge from
        # failing. This records why it was not chosen.
        worst_rejected = min(contrast_ratio("#B3BECA", bg)
                             for _, bg in surfaces_to_check().values())
        worst_chosen = min(contrast_ratio(OUTLINE, bg)
                           for _, bg in surfaces_to_check().values())
        self.assertGreater(worst_chosen, worst_rejected)


class TheDefectItselfTests(unittest.TestCase):
    """These assert the problem was real. If someone 'simplifies' the
    outline away, the fills alone still fail and these say so."""

    def test_the_customtkinter_default_blue_fails_unaided(self):
        self.assertLess(contrast_ratio("#1F6AA5", FRAME), NON_TEXT_MIN)

    def test_every_inactive_mode_fill_fails_unaided(self):
        for key, spec in MODES.items():
            with self.subTest(mode=key):
                self.assertLess(contrast_ratio(spec["inactive"], FRAME),
                                NON_TEXT_MIN)

    def test_the_worst_inactive_fill_was_essentially_invisible(self):
        worst = min(contrast_ratio(s["inactive"], FRAME)
                    for s in MODES.values())
        self.assertLess(worst, 1.1)


class TextStillPassesTests(unittest.TestCase):
    """The outline must not be bought by losing 1.4.3 on the labels."""

    def test_every_fill_still_carries_the_label_at_aa(self):
        for name, fill in FILLS.items():
            with self.subTest(fill=name):
                self.assertTrue(meets_aa(contrast_ratio(TEXT, fill)))


class OutlineKwargsTests(unittest.TestCase):
    def test_unselected_controls_get_the_quiet_outline(self):
        kw = outline_kwargs(False)
        self.assertEqual(kw["border_color"], OUTLINE)
        self.assertEqual(kw["border_width"], OUTLINE_WIDTH)

    def test_selected_controls_get_a_brighter_thicker_one(self):
        kw = outline_kwargs(True)
        self.assertEqual(kw["border_color"], SELECTED_OUTLINE)
        self.assertGreater(kw["border_width"], OUTLINE_WIDTH)

    def test_every_control_gets_a_visible_border(self):
        # Zero would put the shape back under 3:1.
        self.assertGreaterEqual(OUTLINE_WIDTH, 1)


class ButtonSizeTests(unittest.TestCase):
    def test_the_height_floor_clears_the_wcag_target_minimum(self):
        # WCAG 2.2 SC 2.5.8 asks 24x24; the owner asked for bigger than
        # that, having found 24-ish too small to use comfortably.
        self.assertGreaterEqual(BUTTON_MIN_HEIGHT, 24)
        self.assertGreater(BUTTON_MIN_HEIGHT, 24)

    def test_every_fill_in_the_console_is_registered(self):
        # A fill missing from FILLS is a fill the outline was never
        # measured against.
        for spec in MODES.values():
            for state in ("active", "inactive"):
                self.assertIn(spec[state], FILLS.values())


if __name__ == "__main__":
    unittest.main()
