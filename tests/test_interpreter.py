"""Which interpreter carries the voice packages.

The microphone defect of 2026-08-31 was not audio at all: the launcher
started the Store Python while sounddevice and faster_whisper lived in
the per-user Python. Every function that decides this is pure -- the
filesystem arrives as an ``exists`` probe -- so the whole rule is graded
here without a second Python install, a microphone, or a model.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.interpreter import (VOICE_DEPS, dep_present, explain_missing,
                                      has_voice_deps, install_command,
                                      missing_deps, rank_candidates,
                                      site_packages)

# The two interpreters that were actually on the laptop.
STORE = ("C:\\Program Files\\WindowsApps"
         "\\PythonSoftwareFoundation.Python.3.13_3.13.3824.0_x64__qbz5n2kfra8p0")
USER = "C:\\Users\\sbrya\\AppData\\Local\\Programs\\Python\\Python313"


def fake_fs(*present):
    """An ``exists`` probe over a fixed set of paths."""
    have = set(present)
    return lambda path: path in have


def sp(py_dir, leaf):
    return os.path.join(site_packages(py_dir), leaf)


class DepPresenceTests(unittest.TestCase):
    def test_single_module_file_counts_as_installed(self):
        # sounddevice ships as sounddevice.py, not a package directory.
        exists = fake_fs(sp(USER, "sounddevice.py"))
        self.assertTrue(dep_present(USER, "sounddevice", exists))

    def test_package_directory_counts_as_installed(self):
        exists = fake_fs(sp(USER, "faster_whisper"))
        self.assertTrue(dep_present(USER, "faster_whisper", exists))

    def test_absent_dependency_is_absent(self):
        self.assertFalse(dep_present(USER, "sounddevice", fake_fs()))

    def test_dependency_in_another_interpreter_does_not_count(self):
        # The whole defect in one assertion: installed over there is not
        # installed over here.
        exists = fake_fs(sp(USER, "sounddevice.py"))
        self.assertFalse(dep_present(STORE, "sounddevice", exists))


class VoiceCapabilityTests(unittest.TestCase):
    def test_the_laptop_as_it_actually_was(self):
        exists = fake_fs(sp(USER, "sounddevice.py"),
                         sp(USER, "faster_whisper"))
        self.assertTrue(has_voice_deps(USER, exists))
        self.assertFalse(has_voice_deps(STORE, exists))
        self.assertEqual(missing_deps(STORE, exists), list(VOICE_DEPS))

    def test_half_installed_is_not_capable(self):
        # Only sounddevice present: recording would start and then die at
        # transcription, which is what reads as a broken microphone.
        exists = fake_fs(sp(USER, "sounddevice.py"))
        self.assertFalse(has_voice_deps(USER, exists))
        self.assertEqual(missing_deps(USER, exists), ["faster_whisper"])


class RankingTests(unittest.TestCase):
    def test_voice_capable_interpreter_wins_even_when_listed_last(self):
        exists = fake_fs(sp(USER, "sounddevice.py"),
                         sp(USER, "faster_whisper"))
        self.assertEqual(rank_candidates([STORE, USER], exists)[0], USER)

    def test_no_candidate_is_dropped(self):
        exists = fake_fs(sp(USER, "sounddevice.py"),
                         sp(USER, "faster_whisper"))
        self.assertCountEqual(rank_candidates([STORE, USER], exists),
                              [STORE, USER])

    def test_order_is_preserved_when_nothing_is_capable(self):
        self.assertEqual(rank_candidates([STORE, USER], fake_fs()),
                         [STORE, USER])


class OwnerFacingAdviceTests(unittest.TestCase):
    def test_install_command_is_pinned_to_this_interpreter(self):
        # A bare "pip install sounddevice" resolved to the OTHER Python,
        # answered "Requirement already satisfied", and changed nothing.
        cmd = install_command(STORE + "\\python.exe", ["sounddevice"])
        self.assertIn(STORE, cmd)
        self.assertIn("-m pip install sounddevice", cmd)

    def test_explanation_names_the_interpreter_and_the_trap(self):
        msg = explain_missing(STORE + "\\python.exe", list(VOICE_DEPS))
        self.assertIn(STORE, msg)
        for dep in VOICE_DEPS:
            self.assertIn(dep, msg)
        self.assertIn("Another Python", msg)

    def test_explanation_quotes_the_path_so_spaces_survive(self):
        # "C:\\Program Files\\..." unquoted would split at the space.
        msg = explain_missing(STORE + "\\python.exe", ["sounddevice"])
        self.assertIn('"' + STORE + '\\python.exe"', msg)


if __name__ == "__main__":
    unittest.main()
