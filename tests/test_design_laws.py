"""The design-law linter, and the gate that runs it over this repository.

Each rule is proved twice: it fires on the shape that caused a real
defect, and it stays quiet on the correct shape sitting right next to it.
A linter that cannot fire is worse than no linter, because it reads as
proof.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.design_laws import (WIDGETS, format_findings, scan_file,
                                      scan_source)


def rules(src):
    return sorted(f.rule for f in scan_source(src))


class RuleATests(unittest.TestCase):
    """Tuple padding in a constructor -- 'bad screen distance'."""

    def test_fires_on_a_customtkinter_constructor(self):
        self.assertEqual(
            rules('ctk.CTkLabel(parent, text="x", pady=(12, 4))'), ["A"])

    def test_fires_on_padx_too(self):
        self.assertEqual(rules('ctk.CTkButton(p, padx=(1, 2))'), ["A"])

    def test_fires_on_plain_tk_widgets(self):
        self.assertEqual(rules('tk.Label(p, pady=(1, 2))'), ["A"])

    def test_quiet_when_the_tuple_is_in_pack(self):
        # The correct shape, and by far the more common one in this file.
        self.assertEqual(rules('w.pack(side="top", pady=(12, 4))'), [])

    def test_quiet_on_a_scalar_pad_in_a_constructor(self):
        self.assertEqual(rules('ctk.CTkLabel(p, pady=6)'), [])

    def test_the_widget_table_covers_customtkinter(self):
        # Sentinel's table was raw Tk only. Ported unchanged it would have
        # matched nothing here and passed silently.
        for name in ("CTkLabel", "CTkButton", "CTkFrame", "CTkTextbox",
                     "CTkEntry", "CTkOptionMenu", "CTkCheckBox"):
            self.assertIn(name, WIDGETS)


class RuleBTests(unittest.TestCase):
    """Hardcoded geometry -- the send button off the bottom of the screen."""

    def test_fires_on_a_literal_size(self):
        self.assertEqual(rules('root.geometry("1000x700")'), ["B"])

    def test_fires_on_a_literal_with_an_offset(self):
        self.assertEqual(rules('win.geometry("820x54+180+120")'), ["B"])

    def test_quiet_on_a_computed_f_string(self):
        # How a real computed size arrives; must not be flagged.
        self.assertEqual(
            rules('root.geometry(f"{w}x{h}+30+20")'), [])

    def test_quiet_on_a_move_only_geometry_call(self):
        # "+x+y" with no size is how the toolbar drags itself around.
        self.assertEqual(rules('win.geometry("+120+80")'), [])

    def test_quiet_on_the_sanctioned_helper(self):
        self.assertEqual(
            rules('root.geometry(window_fit.plan_geometry(w, h, s)[0])'), [])


class RuleCTests(unittest.TestCase):
    """Install advice that cannot work -- earned 2026-08-31."""

    def test_fires_on_a_bare_instruction(self):
        self.assertEqual(
            rules('show("Voice needs it: pip install sounddevice")'), ["C"])

    def test_fires_regardless_of_spacing_or_case(self):
        self.assertEqual(rules('show("PIP  INSTALL numpy")'), ["C"])

    def test_quiet_when_the_interpreter_is_interpolated(self):
        # The corrected shape from strata_tools/interpreter.py.
        self.assertEqual(
            rules('msg = f\'"{executable}" -m pip install {deps}\''), [])

    def test_quiet_inside_a_docstring(self):
        # Documentation explains the trap; it must not trip the rule.
        src = '"""Do not say pip install without naming the Python."""\nx = 1'
        self.assertEqual(rules(src), [])


class ParseTests(unittest.TestCase):
    def test_a_syntax_error_is_reported_not_swallowed(self):
        findings = scan_source("def broken(:\n    pass")
        self.assertEqual(findings[0].rule, "parse")

    def test_an_unreadable_file_yields_no_findings(self):
        self.assertEqual(scan_file(os.path.join(ROOT, "no_such_file.py")), [])

    def test_findings_format_with_file_and_line(self):
        findings = scan_source('ctk.CTkLabel(p, pady=(1, 2))')
        line = format_findings("x.py", findings)[0]
        self.assertTrue(line.startswith("x.py:1: [A]"))


class RepositoryGateTests(unittest.TestCase):
    """The gate itself: this repository must obey its own design laws."""

    def python_files(self):
        # tests/ is excluded on purpose: these files carry deliberate
        # counterexamples as fixtures, which is what makes them tests.
        # Everything the console actually ships is scanned.
        skip = {".git", "__pycache__", ".claude", "tests"}
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(folder, name)

    def test_every_python_file_in_the_repo_is_clean(self):
        offences = []
        scanned = 0
        for path in self.python_files():
            scanned += 1
            findings = scan_file(path)
            if findings:
                offences.extend(
                    format_findings(os.path.relpath(path, ROOT), findings))
        self.assertGreater(scanned, 5, "the walker found almost nothing")
        # Guard the guard: if the walker ever stops reaching the shell
        # itself, this gate would pass while checking nothing. Followed
        # strata_console.py into retirement -- strata_web.py is the
        # shell now, and it is what must always be scanned.
        self.assertIn("strata_web.py",
                      [os.path.basename(p) for p in self.python_files()])
        self.assertEqual(offences, [], "\n" + "\n".join(offences))


if __name__ == "__main__":
    unittest.main()
