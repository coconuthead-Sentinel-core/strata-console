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


class ReadAlongTests(unittest.TestCase):
    """Following the words while hearing them.

    The alignment rule: the page splits what is DISPLAYED, Python returns
    the spoken form of each piece plus whether the two are identical.
    Word-level highlighting uses the speech engine's character offsets,
    which only index the displayed string when they are.
    """

    def setUp(self):
        from strata_tools import speech
        self.speech = speech

    def test_a_plain_sentence_is_spoken_as_written(self):
        text = "The console is ready."
        self.assertEqual(self.speech.speakable(text), text)

    def test_an_expanded_sentence_is_not(self):
        # "$32" -> "thirty-two dollars": the offsets no longer line up,
        # which is exactly what the matches flag exists to report.
        text = "It cost $32 today."
        self.assertNotEqual(self.speech.speakable(text), text)

    def test_the_page_asks_for_word_highlighting_only_when_safe(self):
        js = open(JS_PATH, encoding="utf-8").read()
        self.assertIn("item.matches", js)
        # onboundary must be bound behind the matches check, not always.
        head = js[:js.index("utter.onboundary")]
        self.assertIn("if (item.matches)", head)

    def test_code_blocks_are_never_read_aloud(self):
        js = open(JS_PATH, encoding="utf-8").read()
        self.assertIn("closest('pre')", js)

    def test_a_sentence_is_tracked_by_index_not_by_element(self):
        # A sentence can run across inline markup and so be several
        # spans; they must share one index or half of it lights up.
        js = open(JS_PATH, encoding="utf-8").read()
        self.assertIn("span.dataset.i = String(index)", js)
        self.assertIn("spans[index].push(span)", js)

    def test_stopping_clears_the_highlight(self):
        js = open(JS_PATH, encoding="utf-8").read()
        stop = js[js.index("function stopReading("):]
        self.assertIn("clearHighlight()", stop[:400])

    def test_the_highlights_are_declared_in_the_stylesheet(self):
        css = open(CSS_PATH, encoding="utf-8").read()
        self.assertIn(".s.reading", css)
        self.assertIn(".w.now", css)

    def test_both_highlights_keep_the_text_readable(self):
        # A highlight that makes its own text harder to read has
        # defeated itself. Measured, not assumed.
        props = custom_properties()
        css = open(CSS_PATH, encoding="utf-8").read()
        for marker in (".s.reading", ".w.now"):
            block = css[css.index(marker):css.index(marker) + 260]
            colour = re.search(r"background:\s*(#[0-9A-Fa-f]{6})", block)
            self.assertIsNotNone(colour, marker)
            with self.subTest(marker=marker):
                self.assertTrue(meets_aa(contrast_ratio(props["--ink"],
                                                        colour.group(1))))

    def test_the_word_marker_is_not_colour_alone(self):
        # WCAG 1.4.1 applies to a reading aid as much as to a button.
        css = open(CSS_PATH, encoding="utf-8").read()
        block = css[css.index(".w.now"):css.index(".w.now") + 260]
        self.assertIn("underline", block)


class ContextSourceTests(unittest.TestCase):
    """🌐 web, ☁ OneDrive and 📎 upload, present and wired.

    The desktop shell has had these since it shipped; the web shell went
    out without them. Each assertion here answers "is the control real,
    and does pressing it reach Python" -- a button that renders and does
    nothing is the defect this project names first.
    """

    def setUp(self):
        self.html = open(HTML_PATH, encoding="utf-8").read()
        self.js = open(JS_PATH, encoding="utf-8").read()

    def test_all_three_controls_exist(self):
        for element_id in ('id="src-web"', 'id="src-onedrive"',
                           'id="upload"'):
            with self.subTest(element_id=element_id):
                self.assertIn(element_id, self.html)

    def test_the_two_sources_are_real_checkboxes(self):
        """Not styled divs -- the keyboard has to reach them."""
        for element_id in ("src-web", "src-onedrive"):
            with self.subTest(element_id=element_id):
                self.assertIn(f'type="checkbox" id="{element_id}"',
                              self.html)

    def test_each_source_control_is_labelled(self):
        for element_id in ("src-web", "src-onedrive"):
            with self.subTest(element_id=element_id):
                self.assertIn(f'for="{element_id}"', self.html)

    def test_the_attachment_line_announces_itself(self):
        """A file attaching without a screen reader saying so is silent
        success -- the same class of defect as silent failure."""
        block = self.html[self.html.index('id="attached"'):
                          self.html.index('id="attached"') + 120]
        self.assertIn("aria-live", block)

    def test_every_control_reaches_the_bridge(self):
        for call in ("api.set_source(", "api.upload_document(",
                     "api.clear_attachment(", "api.poll_notes(",
                     "api.busy_for("):
            with self.subTest(call=call):
                self.assertIn(call, self.js)

    def test_the_notes_queue_is_actually_drained(self):
        """poll_notes replaced a bridge method no page ever called. If
        the timer goes away, the note channel is dead again."""
        self.assertIn("setInterval(pollNotes", self.js)

    def test_the_page_never_holds_the_uploaded_text(self):
        """Only name and label cross the bridge; the body can be two
        million characters and belongs in Python."""
        self.assertNotIn("attachment.text", self.js)

    def test_the_answer_reports_what_it_read(self):
        self.assertIn("r.used", self.js)


class BridgeSurfaceTests(unittest.TestCase):
    """The page calls these by name. Import the module and look.

    Imported rather than grepped: a method that exists in the file but
    not on the class -- indented one level wrong -- greps clean and
    fails at runtime as a rejected promise, which the page shows as
    nothing happening.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import strata_web
        except Exception as e:            # pragma: no cover - env-dependent
            raise unittest.SkipTest(f"strata_web not importable: {e}")
        cls.web = strata_web

    def test_every_method_the_page_calls_exists_on_the_bridge(self):
        js = open(JS_PATH, encoding="utf-8").read()
        called = set(re.findall(r"api\.([a-z_]+)\(", js))
        for name in sorted(called):
            with self.subTest(method=name):
                self.assertTrue(
                    callable(getattr(self.web.Api, name, None)),
                    f"app.js calls api.{name}() and the bridge has no "
                    f"such method")

    def test_the_upload_filter_is_what_the_indexer_can_read(self):
        from strata_tools import context_sources, doc_index
        self.assertEqual(set(context_sources.UPLOAD_EXTENSIONS),
                         set(doc_index.SUPPORTED))


if __name__ == "__main__":
    unittest.main()
