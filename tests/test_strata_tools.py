"""Tests for strata_tools — the console's context tools (ported from
Imprint/Sentinel Forge): cached file indexing incl. Excel, and pure RAG
retrieval."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strata_tools import doc_index
from strata_tools.retrieval import (chunk_text, retrieve_from_index,
                                    retrieve_from_text)


class DocIndexTest(unittest.TestCase):
    def _tree(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "Paperwork"))
        os.makedirs(os.path.join(d, ".git"))
        with open(os.path.join(d, "Paperwork", "lease.md"), "w",
                  encoding="utf-8") as f:
            f.write("the monthly rent is due on the first")
        with open(os.path.join(d, ".git", "x.md"), "w",
                  encoding="utf-8") as f:
            f.write("never index git internals")
        return d

    def test_excludes_and_relative_labels(self):
        d = self._tree()
        idx = doc_index.build_index_over(d, os.path.join(d, "c.json"))
        self.assertEqual([lbl for lbl, _ in idx],
                         [os.path.join("Paperwork", "lease.md")])

    def test_cache_reused(self):
        d = self._tree()
        cache = os.path.join(d, "c.json")
        doc_index.build_index_over(d, cache)
        idx2 = doc_index.build_index_over(d, cache)
        self.assertIn("rent", idx2[0][1])

    @unittest.skipIf(doc_index._openpyxl is None, "openpyxl not installed")
    def test_xlsx_extraction(self):
        import openpyxl
        d = tempfile.mkdtemp()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Budget"
        ws.append(["Item", "Amount"])
        ws.append(["Hosting", 60])
        p = os.path.join(d, "b.xlsx")
        wb.save(p)
        text = doc_index.extract_text(p)
        self.assertIn("Sheet: Budget", text)
        self.assertIn("Hosting | 60", text)

    def test_cache_dir_is_strata(self):
        self.assertTrue(doc_index.cache_dir().endswith("Strata"))


class RetrievalTest(unittest.TestCase):
    def test_retrieve_from_index_ranks(self):
        docs = [("a.md", "cats and dogs"),
                ("b.md", "the monthly rent is 900 dollars rent rent")]
        hits = retrieve_from_index("how much is my rent", docs)
        self.assertIn("b.md", hits)
        self.assertIn("900", hits)

    def test_retrieve_from_text_falls_back_to_opening(self):
        self.assertTrue(retrieve_from_text("zzz", "short doc").startswith(
            "short doc"))

    def test_chunking_overlap(self):
        chunks = chunk_text("abcdefghij" * 200, chunk_chars=500, overlap=100)
        self.assertGreater(len(chunks), 3)


if __name__ == "__main__":
    unittest.main()
