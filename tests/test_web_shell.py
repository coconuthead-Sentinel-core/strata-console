"""The web shell must not drift away from the desktop shell's palette.

Two shells over one engine is only true if they agree. The CSS claims it
carries the SAME measured colours as strata_tools/theme.py and
strata_tools/modes.py -- this reads the stylesheet and checks that claim,
so a colour changed in one place and not the other fails the build
rather than quietly producing two different accessibility stories.

The CSS is parsed rather than imported, which is the point: the test
sees exactly what the browser will.
"""

import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools import theme
from strata_tools.keyboard import FOCUS_RING
from strata_tools.modes import MODES
from strata_tools.wcag import contrast_ratio, meets_aa

CSS_PATH = os.path.join(ROOT, "web", "style.css")
HTML_PATH = os.path.join(ROOT, "web", "index.html")
JS_PATH = os.path.join(ROOT, "web", "app.js")


def custom_properties():
    """``{--name: value}`` from the stylesheet's :root block."""
    css = open(CSS_PATH, encoding="utf-8").read()
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{3,8}|[\w.]+)", css))


class FilesExistTests(unittest.TestCase):
    def test_the_shell_has_all_three_parts(self):
        for path in (CSS_PATH, HTML_PATH, JS_PATH):
            self.assertTrue(os.path.exists(path), path)


class PaletteAgreementTests(unittest.TestCase):
    """Same numbers, both shells."""

    def setUp(self):
        self.props = custom_properties()

    def test_the_outline_matches_the_desktop_shell(self):
        self.assertEqual(self.props["--outline"].upper(),
                         theme.OUTLINE.upper())

    def test_the_button_fill_matches(self):
        self.assertEqual(self.props["--fill"].upper(),
                         theme.BUTTON_FILL.upper())

    def test_the_ink_matches(self):
        self.assertEqual(self.props["--ink"].upper(), theme.TEXT.upper())

    def test_the_focus_ring_matches(self):
        self.assertEqual(self.props["--focus"].upper(), FOCUS_RING.upper())

    def test_every_mode_colour_matches(self):
        for key, css_on, css_off in (("GREEN", "--green", "--green-off"),
                                     ("YELLOW", "--yellow", "--yellow-off"),
                                     ("RED", "--red", "--red-off")):
            with self.subTest(mode=key):
                self.assertEqual(self.props[css_on].upper(),
                                 MODES[key]["active"].upper())
                self.assertEqual(self.props[css_off].upper(),
                                 MODES[key]["inactive"].upper())


class WebPaletteContrastTests(unittest.TestCase):
    """The pairs the desktop shell never had, measured here."""

    def setUp(self):
        self.props = custom_properties()

    def test_body_text_passes_on_the_ground_and_the_surface(self):
        for bg in ("--ground", "--surface"):
            with self.subTest(bg=bg):
                self.assertTrue(meets_aa(contrast_ratio(
                    self.props["--ink"], self.props[bg])))

    def test_muted_text_passes_where_it_is_actually_used(self):
        # On the dark ground and surface only. It is deliberately NOT
        # used on the coloured mode buttons -- see the next test.
        for bg in ("--ground", "--surface"):
            with self.subTest(bg=bg):
                self.assertTrue(meets_aa(contrast_ratio(
                    self.props["--ink-mute"], self.props[bg])))

    def test_muted_text_would_fail_on_the_mode_fills(self):
        # Records why .mode small uses full ink. If someone "tidies" it
        # back to --ink-mute, this states the cost.
        for key in ("--green", "--yellow", "--red"):
            with self.subTest(fill=key):
                self.assertFalse(meets_aa(contrast_ratio(
                    self.props["--ink-mute"], self.props[key])))

    def test_the_mode_caption_uses_full_ink(self):
        css = open(CSS_PATH, encoding="utf-8").read()
        block = css[css.index(".mode small"):css.index(".mode small") + 400]
        self.assertIn("color: var(--ink)", block)
        self.assertNotIn("color: var(--ink-mute)", block)

    def test_ink_passes_on_every_mode_fill(self):
        for key in ("--green", "--green-off", "--yellow", "--yellow-off",
                    "--red", "--red-off", "--fill"):
            with self.subTest(fill=key):
                self.assertTrue(meets_aa(contrast_ratio(
                    self.props["--ink"], self.props[key])))


class MarkupAccessibilityTests(unittest.TestCase):
    """The things HTML gives for free are only free if actually used."""

    def setUp(self):
        self.html = open(HTML_PATH, encoding="utf-8").read()

    def test_controls_are_real_buttons_not_clickable_divs(self):
        # A <div onclick> is how a web UI throws away the keyboard for
        # free behaviour the Tk shell had to be given by hand.
        self.assertNotIn("<div onclick", self.html)
        self.assertGreaterEqual(self.html.count("<button"), 8)

    def test_the_language_is_declared(self):
        self.assertIn('lang="en"', self.html)

    def test_there_is_a_skip_link(self):
        self.assertIn('class="skip"', self.html)

    def test_the_modes_announce_their_state(self):
        self.assertEqual(self.html.count('role="radio"'), 3)
        self.assertIn('aria-checked="true"', self.html)

    def test_status_and_transcript_are_live_regions(self):
        self.assertGreaterEqual(self.html.count("aria-live"), 2)

    def test_the_message_box_is_labelled(self):
        self.assertIn('for="msg"', self.html)


class RenderingSafetyTests(unittest.TestCase):
    """Model output is data, never markup."""

    def test_the_renderer_escapes_before_it_formats(self):
        js = open(JS_PATH, encoding="utf-8").read()
        self.assertIn("function esc(", js)
        # markdown() must escape first; if esc() were applied after the
        # tags were inserted it would escape our own markup instead.
        body = js[js.index("function markdown("):]
        self.assertIn("esc(src)", body)


if __name__ == "__main__":
    unittest.main()
