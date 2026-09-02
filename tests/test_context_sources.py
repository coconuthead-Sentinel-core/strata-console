"""Tests for the shared context-source kernel.

These rules used to live inside strata_console.py, where nothing could
reach them without a screen. The web shell needed the same behaviour,
and the cheap move -- copying them -- would have produced two rules that
agree today and diverge on the first edit. They were lifted into
strata_tools/context_sources.py instead, and this file is the reason
that lift is safe: it pins the behaviour the desktop shell shipped, so
the port is provably a port and not a rewrite.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools import context_sources as cs


class WantsWebTests(unittest.TestCase):
    """The checkbox is one way in; plain English is the other."""

    def test_the_ticked_box_is_enough_on_its_own(self):
        self.assertTrue(cs.wants_web("what is the capital of Peru",
                                     checked=True))

    def test_an_ordinary_question_does_not_reach_the_network(self):
        self.assertFalse(cs.wants_web("summarise what we discussed"))

    def test_asking_in_plain_english_turns_it_on(self):
        for phrase in ("search the web for tide tables",
                       "look this up for me",
                       "can you check online",
                       "google the part number"):
            with self.subTest(phrase=phrase):
                self.assertTrue(cs.wants_web(phrase))

    def test_the_phrase_is_matched_whatever_the_casing(self):
        self.assertTrue(cs.wants_web("Please SEARCH THE INTERNET for it"))

    def test_every_shipped_phrase_actually_fires(self):
        """A trigger list nobody checks is a list with a dead entry in it."""
        for phrase in cs.TRIGGER_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertTrue(cs.wants_web(f"hey {phrase} thanks"))

    def test_empty_and_none_are_safe(self):
        self.assertFalse(cs.wants_web(""))
        self.assertFalse(cs.wants_web(None))


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.att = {
            "name": "lease.txt",
            "text": ("Tenant obligations are listed below. " * 20
                     + "The monthly rent is 1450 dollars payable on the "
                       "first. " + "Parking is not included. " * 20),
        }

    def test_no_attachment_contributes_nothing(self):
        self.assertEqual(cs.attachment_context("rent", None), "")

    def test_the_file_name_is_named_so_the_model_can_cite_it(self):
        out = cs.attachment_context("what is the monthly rent", self.att)
        self.assertIn("lease.txt", out)

    def test_the_relevant_passage_is_what_comes_back(self):
        out = cs.attachment_context("what is the monthly rent", self.att)
        self.assertIn("1450", out)

    def test_an_empty_file_contributes_nothing(self):
        self.assertEqual(
            cs.attachment_context("rent", {"name": "x.txt", "text": ""}), "")

    def test_a_missing_name_does_not_raise(self):
        out = cs.attachment_context("rent", {"text": "the rent is 900"})
        self.assertIn("900", out)


class OneDriveTests(unittest.TestCase):
    """None, [] and a populated index are three different answers."""

    def test_still_indexing_says_so_rather_than_saying_nothing(self):
        out = cs.onedrive_context("rent", None)
        self.assertEqual(out, cs.INDEXING_NOTE)
        self.assertIn("still being", out)

    def test_an_empty_index_is_silence_not_a_complaint(self):
        self.assertEqual(cs.onedrive_context("rent", []), "")

    def test_a_hit_comes_back_with_its_file_name(self):
        index = [("bills/rent.md", "The rent is 1450 per month."),
                 ("notes/car.md", "The tyres need replacing.")]
        out = cs.onedrive_context("how much is the rent", index)
        self.assertIn("rent.md", out)
        self.assertIn("1450", out)

    def test_a_miss_is_silence(self):
        index = [("notes/car.md", "The tyres need replacing.")]
        self.assertEqual(cs.onedrive_context("photosynthesis", index), "")


class GatherTests(unittest.TestCase):
    def test_nothing_switched_on_produces_nothing(self):
        self.assertEqual(cs.gather("hello"), "")

    def test_an_unticked_onedrive_box_is_not_consulted(self):
        """Even mid-index, an off source must stay silent."""
        out = cs.gather("hello", onedrive_index=None, use_onedrive=False)
        self.assertEqual(out, "")

    def test_the_ticked_box_is_what_lets_the_index_speak(self):
        out = cs.gather("hello", onedrive_index=None, use_onedrive=True)
        self.assertEqual(out, cs.INDEXING_NOTE)

    def test_web_text_passes_through_untouched(self):
        out = cs.gather("tides", web_text="Web search results for: tides")
        self.assertEqual(out, "Web search results for: tides")

    def test_sources_arrive_in_owner_priority_order(self):
        """His file first, then his documents, then the open web."""
        att = {"name": "a.txt", "text": "the rent is 1450"}
        index = [("b.md", "the rent is also mentioned here")]
        out = cs.gather("rent", attachment=att, onedrive_index=index,
                        use_onedrive=True, web_text="WEBBLOCK")
        self.assertLess(out.index("a.txt"), out.index("b.md"))
        self.assertLess(out.index("b.md"), out.index("WEBBLOCK"))

    def test_empty_sources_do_not_pad_the_context_window(self):
        """A blank source must not cost blank lines the model pays for."""
        out = cs.gather("rent", attachment=None, onedrive_index=[],
                        use_onedrive=True, web_text="WEB")
        self.assertEqual(out, "WEB")


class OwnerFacingCopyTests(unittest.TestCase):
    """Both shells say the same words, because they are one product."""

    def test_the_label_reports_size_and_how_to_remove_it(self):
        label = cs.attachment_label("lease.pdf", 40960)
        self.assertIn("lease.pdf", label)
        self.assertIn("40 KB", label)
        self.assertIn("remove", label)

    def test_a_tiny_file_never_reports_zero_kilobytes(self):
        self.assertIn("1 KB", cs.attachment_label("note.txt", 12))

    def test_the_greeting_promises_the_file_stays_attached(self):
        """Ongoing dialogue is the feature; the copy has to say so."""
        self.assertIn("stays attached", cs.attachment_greeting("lease.pdf"))

    def test_an_unreadable_file_is_reported_honestly(self):
        note = cs.unreadable_note("scan.pdf")
        self.assertIn("scan.pdf", note)
        self.assertIn("Couldn't read", note)


class BusyLabelTests(unittest.TestCase):
    def test_plain_thinking_when_no_source_is_on(self):
        self.assertEqual(cs.busy_label(False, False, False),
                         "thinking (local model)…")

    def test_any_source_switches_the_wording_to_searching(self):
        for args in ((True, False, False), (False, True, False),
                     (False, False, True)):
            with self.subTest(args=args):
                self.assertEqual(cs.busy_label(*args), "🔎 searching…")


class UploadFilterTests(unittest.TestCase):
    def test_the_dialog_offers_what_the_indexer_can_actually_read(self):
        """Offering a format the extractor cannot open is a dead control."""
        from strata_tools import doc_index
        self.assertEqual(set(cs.UPLOAD_EXTENSIONS), set(doc_index.SUPPORTED))


if __name__ == "__main__":
    unittest.main()
