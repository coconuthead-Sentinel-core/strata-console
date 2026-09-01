"""The read-aloud front end -- 🔊 was speaking raw markdown.

Pure transforms, graded without a speaker.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.speech import (FENCE_SPOKEN, normalize_for_speech, speakable,
                                 strip_markdown)


class MarkdownTests(unittest.TestCase):
    """What a local model actually emits."""

    def test_bold_and_italic_markers_are_not_spoken(self):
        self.assertEqual(strip_markdown("this is **important** here"),
                         "this is important here")
        self.assertEqual(strip_markdown("a _quiet_ word"), "a quiet word")

    def test_bold_italic_unwraps_fully(self):
        self.assertEqual(strip_markdown("***very***"), "very")

    def test_headings_lose_their_hashes(self):
        self.assertEqual(strip_markdown("## Next steps"), "Next steps")

    def test_bullets_lose_their_markers_but_keep_the_text(self):
        self.assertEqual(strip_markdown("- first\n- second"),
                         "first\nsecond")

    def test_links_are_read_as_their_text_not_their_url(self):
        self.assertEqual(
            strip_markdown("see [the docs](https://example.com/x) now"),
            "see the docs now")

    def test_images_are_read_as_their_alt_text(self):
        self.assertEqual(strip_markdown("![a chart](chart.png)"), "a chart")

    def test_a_fenced_code_block_is_announced_not_recited(self):
        # Silence would hide that the reply contained code; reciting it
        # character by character is unusable.
        out = strip_markdown("Try this:\n```python\nx = 1024\n```\ndone")
        self.assertIn(FENCE_SPOKEN, out)
        self.assertNotIn("x = 1024", out)

    def test_an_unterminated_fence_still_terminates(self):
        # Streaming replies get cut off mid-block.
        out = strip_markdown("Here:\n```python\nx = 1\n")
        self.assertIn(FENCE_SPOKEN, out)
        self.assertNotIn("```", out)

    def test_blockquotes_and_horizontal_rules_go_quiet(self):
        self.assertEqual(strip_markdown("> quoted line"), "quoted line")
        self.assertEqual(strip_markdown("before\n\n---\n\nafter"),
                         "before\n\nafter")

    def test_a_table_is_read_as_rows_not_pipes(self):
        table = "| Name | Lines |\n| --- | --- |\n| speech | 200 |"
        out = strip_markdown(table)
        self.assertNotIn("|", out)
        self.assertIn("Name Lines", out)
        self.assertIn("speech 200", out)

    def test_inline_code_keeps_its_backticks_for_the_next_stage(self):
        # strip_markdown must NOT eat them -- normalize needs them to
        # know what to exempt.
        self.assertIn("`", strip_markdown("run `pip install x` now"))

    def test_plain_prose_is_untouched(self):
        plain = "The microphone works and the console is ready."
        self.assertEqual(strip_markdown(plain), plain)


class NormalizeTests(unittest.TestCase):
    def test_money_is_spoken_as_money(self):
        self.assertEqual(normalize_for_speech("it costs $32"),
                         "it costs thirty-two dollars")

    def test_money_with_cents(self):
        self.assertIn("and fifty cents", normalize_for_speech("$1.50"))

    def test_one_dollar_is_singular(self):
        self.assertEqual(normalize_for_speech("$1"), "one dollar")

    def test_percent_is_expanded(self):
        self.assertEqual(normalize_for_speech("50% done"),
                         "fifty percent done")

    def test_ordinals(self):
        self.assertEqual(normalize_for_speech("the 1st and 3rd"),
                         "the first and third")

    def test_years_read_naturally_not_as_cardinals(self):
        self.assertEqual(normalize_for_speech("in 1999"),
                         "in nineteen ninety-nine")
        self.assertEqual(normalize_for_speech("in 2007"),
                         "in two thousand seven")

    def test_abbreviations_expand(self):
        self.assertEqual(normalize_for_speech("Dr. Who vs. time"),
                         "Doctor Who versus time")

    def test_decimals_are_read_digit_by_digit_after_the_point(self):
        self.assertEqual(normalize_for_speech("pi is 3.14"),
                         "pi is three point one four")

    def test_code_spans_are_exempt_from_english_rules(self):
        # The point of the exemption: 1024 inside backticks must not
        # become "one thousand twenty-four" inside a file path.
        out = normalize_for_speech("open `buffer_1024/read.py` now")
        self.assertNotIn("thousand", out)
        self.assertIn("underscore", out)
        self.assertIn("slash", out)


class SpeakableTests(unittest.TestCase):
    """Both stages, in the order the console uses."""

    def test_a_realistic_model_reply(self):
        reply = ("## Result\n\n"
                 "The build is **97%** complete as of 2026.\n\n"
                 "- run `make test`\n"
                 "- see [the plan](docs/BUILD_PLAN.md)\n")
        out = speakable(reply)
        for noise in ("#", "**", "](", "- "):
            self.assertNotIn(noise, out)
        self.assertIn("ninety-seven percent", out)
        self.assertIn("twenty twenty-six", out)
        self.assertIn("the plan", out)

    def test_code_inside_markdown_survives_both_stages_unexpanded(self):
        self.assertNotIn("thousand", speakable("use `port_8080`"))

    def test_empty_and_none_are_safe(self):
        for value in ("", None):
            self.assertEqual(speakable(value), "")

    def test_a_non_string_returns_unchanged_instead_of_raising(self):
        sentinel = object()
        self.assertIs(speakable(sentinel), sentinel)

    def test_a_reply_that_is_only_a_code_block_still_says_something(self):
        # Must never hand the engine an empty string and look broken.
        out = speakable("```\nx = 1\n```")
        self.assertTrue(out.strip())
        self.assertIn("code block", out)


if __name__ == "__main__":
    unittest.main()
