"""Tests for the local model's readiness reporting.

The defect these exist for was not a crash. The app worked; it took ~20
seconds to answer the first message while Ollama read 2.3 GB into RAM on
a CPU-only laptop, and said nothing but a static "thinking…" the whole
time. The owner read that as an application that had failed to start,
which is a fair reading: a wait with no evidence of progress cannot be
told apart from a hang.

Nothing here needs a running Ollama daemon -- readiness must degrade to
"not loaded" when the answer is unknown, and that is exactly the case a
build machine exercises.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_core import LLMBrain


class UnavailableBrainTests(unittest.TestCase):
    """With no daemon, every answer must be safe and quiet."""

    def setUp(self):
        self.brain = LLMBrain.__new__(LLMBrain)
        self.brain.model = "llama3.2:3b"
        self.brain.available = False
        self.brain.last_error = "daemon not reachable"
        self.brain.num_ctx = 2048
        self.brain.keep_alive = "10m"

    def test_an_unavailable_model_is_never_reported_as_loaded(self):
        self.assertFalse(self.brain.is_loaded())

    def test_warming_an_unavailable_model_fails_quietly(self):
        """Returns False rather than raising: warm-up runs on a
        background thread, and an exception there is invisible."""
        self.assertFalse(self.brain.warm())

    def test_neither_call_raises(self):
        self.brain.is_loaded()
        self.brain.warm()


class UnknownStateTests(unittest.TestCase):
    """When the daemon cannot be asked, the answer is 'not loaded'."""

    def setUp(self):
        self.brain = LLMBrain.__new__(LLMBrain)
        self.brain.model = "llama3.2:3b"
        self.brain.available = True
        self.brain.last_error = None
        self.brain.num_ctx = 2048
        self.brain.keep_alive = "10m"

    def test_a_failing_probe_reports_not_loaded(self):
        """False on doubt. The cost is asymmetric: promising a fast
        reply and delivering twenty seconds is the failure being
        prevented; promising a slow one and being quick is not."""
        import strata_core

        def boom():
            raise OSError("daemon went away")

        original = getattr(strata_core, "ollama", None)
        if original is None:
            self.skipTest("ollama package not importable")
        saved = original.ps
        original.ps = boom
        try:
            self.assertFalse(self.brain.is_loaded())
        finally:
            original.ps = saved

    def test_a_resident_model_is_recognised_by_stem(self):
        """'llama3.2:3b' must match a daemon reporting 'llama3.2:3b' or
        any tag of it -- the tag is not guaranteed to round-trip."""
        import strata_core

        original = getattr(strata_core, "ollama", None)
        if original is None:
            self.skipTest("ollama package not importable")
        saved = original.ps
        original.ps = lambda: {"models": [{"model": "llama3.2:3b"}]}
        try:
            self.assertTrue(self.brain.is_loaded())
        finally:
            original.ps = saved

    def test_a_different_model_being_resident_is_not_ours(self):
        import strata_core

        original = getattr(strata_core, "ollama", None)
        if original is None:
            self.skipTest("ollama package not importable")
        saved = original.ps
        original.ps = lambda: {"models": [{"model": "mistral:7b"}]}
        try:
            self.assertFalse(self.brain.is_loaded())
        finally:
            original.ps = saved

    def test_an_empty_daemon_means_nothing_is_loaded(self):
        import strata_core

        original = getattr(strata_core, "ollama", None)
        if original is None:
            self.skipTest("ollama package not importable")
        saved = original.ps
        original.ps = lambda: {"models": []}
        try:
            self.assertFalse(self.brain.is_loaded())
        finally:
            original.ps = saved


if __name__ == "__main__":
    unittest.main()
