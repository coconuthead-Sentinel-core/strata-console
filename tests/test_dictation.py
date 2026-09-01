"""Spoken punctuation -- the half of dictation the console was missing.

Pure transforms, so every case is graded without a microphone.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.dictation import (apply_commands, dedup_punctuation, polish)


class PunctuationTests(unittest.TestCase):
    def test_period_becomes_a_full_stop_attached_to_the_word(self):
        self.assertEqual(apply_commands("the model is stable period"),
                         "the model is stable.")

    def test_comma_attaches_and_keeps_one_following_space(self):
        self.assertEqual(apply_commands("first comma then second"),
                         "first, then second")

    def test_question_and_exclamation_are_two_word_forms(self):
        self.assertEqual(apply_commands("is it ready question mark"),
                         "is it ready?")
        self.assertEqual(apply_commands("stop exclamation point"), "stop!")

    def test_brackets_and_quotes_attach_to_the_right_side(self):
        self.assertEqual(
            apply_commands("run open paren twice close paren now"),
            "run (twice) now")

    def test_dollar_sign_opens_onto_the_number(self):
        self.assertEqual(apply_commands("it costs dollar sign 5"),
                         "it costs $5")

    def test_ordinary_prose_is_untouched(self):
        plain = "the quick brown fox jumps over the lazy dog"
        self.assertEqual(apply_commands(plain), plain)


class LineBreakTests(unittest.TestCase):
    def test_new_line_and_new_paragraph(self):
        self.assertEqual(apply_commands("one new line two"), "one\ntwo")
        self.assertEqual(apply_commands("one new paragraph two"),
                         "one\n\ntwo")

    def test_a_paragraph_break_is_a_hard_boundary_for_dedup(self):
        # Marks either side of a newline must not be collapsed together.
        self.assertEqual(dedup_punctuation("done.\n\nNext."), "done.\n\nNext.")


class CapitalisationTests(unittest.TestCase):
    def test_cap_raises_only_the_next_word(self):
        self.assertEqual(apply_commands("meet cap shannon today"),
                         "meet Shannon today")

    def test_caps_on_and_off_title_case_a_span(self):
        self.assertEqual(apply_commands("caps on strata console caps off now"),
                         "Strata Console now")

    def test_all_caps_shouts_until_turned_off(self):
        self.assertEqual(apply_commands("all caps on help all caps off me"),
                         "HELP me")


class CollisionTests(unittest.TestCase):
    """Whisper auto-punctuates. Speaking punctuation too causes collisions."""

    def test_recogniser_mark_plus_spoken_word_collapses(self):
        # "stable. period" -- Whisper heard the pause AND the word.
        self.assertEqual(polish("the model is stable. period"),
                         "the model is stable.")

    def test_duplicate_marks_collapse_to_one(self):
        self.assertEqual(dedup_punctuation("done.."), "done.")

    def test_strongest_terminal_wins_a_collision(self):
        self.assertEqual(dedup_punctuation("really?."), "really?")
        self.assertEqual(dedup_punctuation("stop.!"), "stop!")

    def test_space_before_a_mark_is_removed(self):
        self.assertEqual(dedup_punctuation("word ."), "word.")

    def test_exactly_one_space_after_a_mark(self):
        self.assertEqual(dedup_punctuation("one.two"), "one. two")
        self.assertEqual(dedup_punctuation("one.   two"), "one. two")


class NumberSafetyTests(unittest.TestCase):
    """The dedup pass must not damage numbers -- a decimal is not a stop."""

    def test_decimals_survive(self):
        self.assertEqual(dedup_punctuation("pi is 3.14 exactly"),
                         "pi is 3.14 exactly")

    def test_thousands_separators_survive(self):
        self.assertEqual(dedup_punctuation("1,234 lines"), "1,234 lines")

    def test_a_version_number_survives(self):
        self.assertEqual(dedup_punctuation("python 3.13.14"),
                         "python 3.13.14")


class DefensiveTests(unittest.TestCase):
    """A transcript that arrives slightly wrong is recoverable; one that
    raises inside a worker thread loses the words entirely."""

    def test_empty_and_none_are_safe(self):
        for value in ("", None):
            self.assertEqual(apply_commands(value), "")
            self.assertEqual(dedup_punctuation(value), "")
            self.assertEqual(polish(value), "")

    def test_a_non_string_returns_unchanged_instead_of_raising(self):
        sentinel = object()
        self.assertIs(polish(sentinel), sentinel)

    def test_only_command_words_still_produces_output(self):
        self.assertEqual(polish("period"), ".")


class PolishOrderTests(unittest.TestCase):
    def test_polish_applies_commands_before_dedup(self):
        # If dedup ran first it would see no marks and do nothing, leaving
        # the duplicate that the command pass creates.
        self.assertEqual(polish("all set period period"), "all set.")

    def test_a_realistic_dictated_sentence(self):
        spoken = ("cap the console is ready comma and the microphone works "
                  "period new line cap next question mark")
        self.assertEqual(polish(spoken),
                         "The console is ready, and the microphone works.\n"
                         "Next?")


if __name__ == "__main__":
    unittest.main()
