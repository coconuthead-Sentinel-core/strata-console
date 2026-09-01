"""Window sizing -- the trap that put the send button off the screen.

Pure rules, so the owner's real display and the configuration that
originally broke are both graded here without opening a window.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.window_fit import (MIN_H, MIN_W, ORIGIN_X, ORIGIN_Y, WANT_H,
                                     WANT_W, fits_on_screen,
                                     margins_cover_origin, plan_geometry,
                                     target_pixels)

# The owner's laptop as Windows reports it without DPI awareness.
OWNER_W, OWNER_H = 1097, 617
OWNER_SCALING = 1.75


def parse(geometry):
    """'999x486+30+20' -> (999, 486, 30, 20)."""
    size, x, y = geometry.split("+")
    w, h = size.split("x")
    return int(w), int(h), int(x), int(y)


class TargetPixelTests(unittest.TestCase):
    def test_owner_display_is_capped_by_height_not_width(self):
        w, h = target_pixels(OWNER_W, OWNER_H)
        self.assertEqual(w, WANT_W)        # 1097 - 80 = 1017, so 1000 wins
        self.assertEqual(h, OWNER_H - 130)  # 487: the screen is the limit

    def test_a_large_screen_gets_the_full_target(self):
        self.assertEqual(target_pixels(2560, 1440), (WANT_W, WANT_H))

    def test_a_tiny_screen_never_produces_a_zero_or_negative_size(self):
        # max(1, ...) exists so a pathological screen cannot yield a
        # zero-sized window, which Tk accepts and then renders invisible.
        w, h = target_pixels(40, 40)
        self.assertGreaterEqual(w, 1)
        self.assertGreaterEqual(h, 1)


class PlanGeometryTests(unittest.TestCase):
    def test_owner_display_matches_the_measured_window(self):
        # Measured 2026-09-01 by tools/dpi_check.py: 999x486+30+20.
        # CustomTkinter multiplies by 1.75, so we pre-divide.
        geometry, _, _ = plan_geometry(OWNER_W, OWNER_H, OWNER_SCALING)
        w, h, x, y = parse(geometry)
        self.assertEqual((int(w * OWNER_SCALING), int(h * OWNER_SCALING)),
                         (999, 486))
        self.assertEqual((x, y), (ORIGIN_X, ORIGIN_Y))

    def test_the_original_bug_would_now_fail_this_test(self):
        # The trap: passing the target straight through. At 1.75 that is
        # 1750x1225 physical on a 1097x617 screen.
        self.assertGreater(WANT_W * OWNER_SCALING, OWNER_W)
        # The kernel must NOT do that.
        geometry, _, _ = plan_geometry(OWNER_W, OWNER_H, OWNER_SCALING)
        w, h, _, _ = parse(geometry)
        self.assertLess(w * OWNER_SCALING, OWNER_W)
        self.assertLess(h * OWNER_SCALING, OWNER_H)

    def test_minimum_size_is_scaled_too(self):
        _, min_w, min_h = plan_geometry(OWNER_W, OWNER_H, OWNER_SCALING)
        self.assertEqual((min_w, min_h),
                         (int(MIN_W / OWNER_SCALING), int(MIN_H / OWNER_SCALING)))

    def test_unscaled_display_is_a_passthrough(self):
        geometry, min_w, min_h = plan_geometry(1920, 1080, 1.0)
        self.assertEqual(geometry, f"{WANT_W}x{WANT_H}+{ORIGIN_X}+{ORIGIN_Y}")
        self.assertEqual((min_w, min_h), (MIN_W, MIN_H))


class BadScalingTests(unittest.TestCase):
    """CustomTkinter has handed back 0, None and strings on odd displays."""

    def test_zero_scaling_does_not_divide_by_zero(self):
        geometry, _, _ = plan_geometry(OWNER_W, OWNER_H, 0)
        w, h, _, _ = parse(geometry)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_none_scaling_falls_back_to_unscaled(self):
        self.assertEqual(plan_geometry(1920, 1080, None)[0],
                         f"{WANT_W}x{WANT_H}+{ORIGIN_X}+{ORIGIN_Y}")

    def test_garbage_scaling_falls_back_to_unscaled(self):
        self.assertEqual(plan_geometry(1920, 1080, "big")[0],
                         f"{WANT_W}x{WANT_H}+{ORIGIN_X}+{ORIGIN_Y}")

    def test_negative_scaling_falls_back_to_unscaled(self):
        self.assertEqual(plan_geometry(1920, 1080, -2)[0],
                         f"{WANT_W}x{WANT_H}+{ORIGIN_X}+{ORIGIN_Y}")


class FitInvariantTests(unittest.TestCase):
    """Fit is guaranteed by construction. These prove it, and would break
    if a future edit removed a cap or outgrew a margin."""

    def test_the_margins_cover_the_origin_offset(self):
        # The precondition the whole invariant rests on.
        self.assertTrue(margins_cover_origin())

    def test_fits_across_a_sweep_of_real_and_absurd_screens(self):
        widths = [200, 640, 800, 1024, OWNER_W, 1280, 1366, 1600, 1920,
                  2560, 3840]
        heights = [150, 480, 600, OWNER_H, 720, 768, 900, 1080, 1440, 2160]
        for w in widths:
            for h in heights:
                with self.subTest(screen=(w, h)):
                    self.assertTrue(fits_on_screen(w, h))

    def test_the_owner_display_fits(self):
        self.assertTrue(fits_on_screen(OWNER_W, OWNER_H))

    def test_planned_window_never_exceeds_the_screen_after_rescaling(self):
        # The round trip that actually matters: we divide, CustomTkinter
        # multiplies back. Truncation may only shrink, never grow.
        for screen in [(OWNER_W, OWNER_H), (1920, 1080), (1366, 768)]:
            for scaling in (1.0, 1.25, 1.5, OWNER_SCALING, 2.0):
                with self.subTest(screen=screen, scaling=scaling):
                    geometry, _, _ = plan_geometry(*screen, scaling)
                    w, h, x, y = parse(geometry)
                    self.assertLessEqual(x + w * scaling, screen[0])
                    self.assertLessEqual(y + h * scaling, screen[1])


if __name__ == "__main__":
    unittest.main()
