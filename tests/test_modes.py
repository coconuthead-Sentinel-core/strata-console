"""Mode colour coding, and the rule that colour is never the only cue.

Every colour claim in modes.py is re-measured here rather than trusted,
because a comment saying "this passes AA" is not a passing grade.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.keyboard import FOCUS_RING
from strata_tools.modes import (ACTIVE_BORDER, ACTIVE_MARK, INACTIVE_BORDER,
                                MODES, ORDER, TEXT, all_appearances,
                                appearance, describe, is_mode, label_for,
                                normalise)
from strata_tools.wcag import AA_NORMAL, contrast_ratio, meets_aa


class NamingTests(unittest.TestCase):
    def test_the_three_modes_are_known(self):
        for name in ("GREEN", "YELLOW", "RED"):
            self.assertTrue(is_mode(name))

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(normalise("green"), "GREEN")
        self.assertEqual(normalise("  Red "), "RED")

    def test_an_unknown_mode_is_rejected_not_guessed(self):
        self.assertIsNone(normalise("purple"))
        self.assertFalse(is_mode("purple"))

    def test_order_covers_every_mode(self):
        self.assertEqual(sorted(ORDER), sorted(MODES))


class ColourContrastTests(unittest.TestCase):
    """WCAG 1.4.3 Contrast (Minimum), AA, 4.5:1 for normal text."""

    def test_every_active_colour_passes_aa_against_the_label(self):
        for key, spec in MODES.items():
            ratio = contrast_ratio(TEXT, spec["active"])
            with self.subTest(mode=key, state="active"):
                self.assertTrue(meets_aa(ratio),
                                f"{key} active {spec['active']} "
                                f"{ratio:.2f}:1 < {AA_NORMAL}")

    def test_every_inactive_colour_passes_aa_against_the_label(self):
        for key, spec in MODES.items():
            ratio = contrast_ratio(TEXT, spec["inactive"])
            with self.subTest(mode=key, state="inactive"):
                self.assertTrue(meets_aa(ratio),
                                f"{key} inactive {spec['inactive']} "
                                f"{ratio:.2f}:1 < {AA_NORMAL}")

    def test_every_hover_colour_passes_aa(self):
        for key, spec in MODES.items():
            with self.subTest(mode=key, state="hover"):
                self.assertTrue(meets_aa(contrast_ratio(TEXT,
                                                        spec["hover"])))

    def test_the_focus_ring_is_visible_on_every_mode_colour(self):
        # WCAG 1.4.11, 3:1. A focus ring that vanishes on the coloured
        # buttons would undo the keyboard work.
        for key, spec in MODES.items():
            for state in ("active", "inactive", "hover"):
                with self.subTest(mode=key, state=state):
                    self.assertGreaterEqual(
                        contrast_ratio(FOCUS_RING, spec[state]), 3.0)

    def test_active_and_inactive_are_actually_distinguishable(self):
        # If the two states were near-identical the colour coding would
        # be decorative rather than informative.
        for key, spec in MODES.items():
            with self.subTest(mode=key):
                self.assertGreaterEqual(
                    contrast_ratio(spec["active"], spec["inactive"]), 1.5)

    def test_the_three_modes_are_distinguishable_from_each_other(self):
        actives = [MODES[k]["active"] for k in ORDER]
        for i in range(len(actives)):
            for j in range(i + 1, len(actives)):
                with self.subTest(pair=(actives[i], actives[j])):
                    self.assertNotEqual(actives[i], actives[j])


class NonColourCueTests(unittest.TestCase):
    """WCAG 1.4.1 Use of Colour, Level A -- colour is never the only cue."""

    def test_the_active_label_carries_a_marker(self):
        self.assertTrue(label_for("GREEN", True).startswith(ACTIVE_MARK))

    def test_the_inactive_label_does_not(self):
        self.assertFalse(label_for("GREEN", False).startswith(ACTIVE_MARK))

    def test_the_mode_name_is_always_in_the_label(self):
        # The text, not the hue, is what a screen reader announces.
        for key in ORDER:
            self.assertIn(MODES[key]["label"], label_for(key, False))
            self.assertIn(MODES[key]["label"], label_for(key, True))

    def test_the_active_button_also_carries_a_border(self):
        # A third cue: marker, colour, border. Any one suffices.
        self.assertGreater(ACTIVE_BORDER, INACTIVE_BORDER)
        self.assertEqual(appearance("GREEN", True)["border_width"],
                         ACTIVE_BORDER)
        self.assertEqual(appearance("GREEN", False)["border_width"],
                         INACTIVE_BORDER)

    def test_stripping_colour_still_identifies_the_active_mode(self):
        # The decisive test: given only the labels, can the active mode
        # be found? This is what a monochrome screen shows.
        looks = all_appearances("YELLOW")
        marked = [k for k, kw in looks.items()
                  if kw["text"].startswith(ACTIVE_MARK)]
        self.assertEqual(marked, ["YELLOW"])


class AppearanceTests(unittest.TestCase):
    def test_exactly_one_mode_is_active_at_a_time(self):
        looks = all_appearances("RED")
        active = [k for k, kw in looks.items()
                  if kw["border_width"] == ACTIVE_BORDER]
        self.assertEqual(active, ["RED"])

    def test_an_unknown_current_mode_leaves_all_inactive(self):
        # Better than arbitrarily lighting one up.
        looks = all_appearances("purple")
        self.assertTrue(all(kw["border_width"] == INACTIVE_BORDER
                            for kw in looks.values()))

    def test_appearance_of_an_unknown_mode_is_empty_not_a_crash(self):
        self.assertEqual(appearance("purple", True), {})

    def test_every_mode_gets_an_appearance(self):
        self.assertEqual(sorted(all_appearances("GREEN")), sorted(ORDER))

    def test_the_kwargs_are_what_customtkinter_accepts(self):
        kw = appearance("GREEN", True)
        for key in ("text", "fg_color", "hover_color", "border_width",
                    "border_color"):
            self.assertIn(key, kw)


class DescriptionTests(unittest.TestCase):
    def test_each_mode_explains_itself_in_words(self):
        self.assertIn("active", describe("GREEN"))
        self.assertIn("analytical", describe("YELLOW"))
        self.assertIn("archival", describe("RED"))

    def test_an_unknown_mode_echoes_rather_than_inventing_a_meaning(self):
        self.assertEqual(describe("purple"), "purple")


if __name__ == "__main__":
    unittest.main()
