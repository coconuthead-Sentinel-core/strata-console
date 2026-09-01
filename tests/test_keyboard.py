"""Keyboard access -- WCAG 2.1.1 Level A, and the focus ring AA needs.

Policy is pure and the shell is duck-typed, so both grade headlessly
against fakes. The empirical half -- that the real Tab ring actually
grew from 2 widgets to all of them -- is `tools/a11y_check.py`, which
needs a display.
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from strata_tools.keyboard import (ACTIVATION_KEYS, FOCUS_RING,
                                   FOCUS_RING_WIDTH, FOCUS_SURFACES,
                                   activator_names, enable_tree,
                                   enable_widget, find_activator, focus_hosts,
                                   is_control)
from strata_tools.wcag import contrast_ratio


class FakeCanvas:
    def __init__(self):
        self.config = {}
        self.bindings = {}

    def winfo_class(self):
        return "Canvas"

    def configure(self, **kw):
        self.config.update(kw)

    def bind(self, key, fn):
        self.bindings[key] = fn

    def winfo_children(self):
        return []


class FakeLabel(FakeCanvas):
    def winfo_class(self):
        return "Label"


class CTkButton:
    """A CTkButton shape: canvas + label inside, invoke() to activate.

    Named for the real class because enable_tree reads type(w).__name__.
    """

    def __init__(self):
        self.canvas = FakeCanvas()
        self.label = FakeLabel()
        self.invoked = 0
        self.config = {"border_color": "#1F6AA5", "border_width": 0}

    def winfo_children(self):
        return [self.canvas, self.label]

    def invoke(self):
        self.invoked += 1

    def cget(self, key):
        return self.config[key]

    def configure(self, **kw):
        self.config.update(kw)


class CTkCheckBox(CTkButton):
    """No invoke() -- a checkbox is toggled, which is why the activator
    lookup is a fall-through list and not a single method name."""

    def __init__(self):
        super().__init__()
        self.toggled = 0

    invoke = None

    def toggle(self):
        self.toggled += 1


class CTkLabel:
    """Not a control."""

    def winfo_children(self):
        return []


class PolicyTests(unittest.TestCase):
    def test_the_control_families_are_recognised(self):
        for name in ("CTkButton", "CTkCheckBox", "CTkOptionMenu",
                     "CTkSwitch", "CTkComboBox"):
            self.assertTrue(is_control(name), name)

    def test_presentational_widgets_are_not_controls(self):
        self.assertFalse(is_control("CTkLabel"))
        self.assertFalse(is_control("CTkFrame"))

    def test_activators_were_probed_not_guessed(self):
        # Verified against CustomTkinter 5.2.2: a button has invoke(); a
        # checkbox does not, it has toggle().
        self.assertIn("invoke", activator_names("CTkButton"))
        self.assertEqual(activator_names("CTkCheckBox"), ("toggle",))

    def test_both_space_and_return_activate(self):
        # Either habit must work; neither is wrong on Windows.
        self.assertIn("<Return>", ACTIVATION_KEYS)
        self.assertIn("<space>", ACTIVATION_KEYS)


class DuckTypingTests(unittest.TestCase):
    def test_finds_invoke_on_a_button(self):
        self.assertIsNotNone(find_activator(CTkButton()))

    def test_falls_through_to_toggle_on_a_checkbox(self):
        box = CTkCheckBox()
        activate = find_activator(box)
        self.assertIsNotNone(activate)
        activate()
        self.assertEqual(box.toggled, 1)

    def test_an_unknown_widget_has_no_activator(self):
        self.assertIsNone(find_activator(CTkLabel()))

    def test_finds_the_canvas_and_not_the_label(self):
        button = CTkButton()
        hosts = focus_hosts(button)
        self.assertEqual(hosts, [button.canvas])


class EnableTests(unittest.TestCase):
    def test_the_canvas_joins_the_tab_ring(self):
        button = CTkButton()
        self.assertTrue(enable_widget(button))
        self.assertEqual(button.canvas.config.get("takefocus"), 1)

    def test_every_activation_key_is_bound(self):
        button = CTkButton()
        enable_widget(button)
        for key in ACTIVATION_KEYS:
            self.assertIn(key, button.canvas.bindings)

    def test_pressing_return_activates_the_control(self):
        button = CTkButton()
        enable_widget(button)
        result = button.canvas.bindings["<Return>"](None)
        self.assertEqual(button.invoked, 1)
        # "break" stops Tk also treating Return as something else.
        self.assertEqual(result, "break")

    def test_space_activates_too(self):
        button = CTkButton()
        enable_widget(button)
        button.canvas.bindings["<space>"](None)
        self.assertEqual(button.invoked, 1)

    def test_a_non_control_is_left_untouched(self):
        self.assertFalse(enable_widget(CTkLabel()))

    def test_focus_callbacks_fire_for_the_ring(self):
        button = CTkButton()
        seen = []
        enable_widget(button, on_focus=seen.append, on_blur=seen.append)
        button.canvas.bindings["<FocusIn>"](None)
        button.canvas.bindings["<FocusOut>"](None)
        self.assertEqual(seen, [button, button])


class TreeTests(unittest.TestCase):
    def test_counts_what_it_enabled_and_skips_what_it_did_not(self):
        widgets = [CTkButton(), CTkButton(), CTkCheckBox(), CTkLabel()]
        self.assertEqual(enable_tree(None, walk=lambda _r: widgets), 3)

    def test_an_empty_tree_is_zero_not_an_error(self):
        self.assertEqual(enable_tree(None, walk=lambda _r: []), 0)


class FocusRingContrastTests(unittest.TestCase):
    """WCAG 1.4.11 Non-text Contrast, 3:1. The first ring colour failed
    this on the button blue -- exactly where it is most needed."""

    def test_the_ring_clears_three_to_one_on_every_surface(self):
        failures = [f"{name} {contrast_ratio(FOCUS_RING, colour):.2f}:1"
                    for name, colour in FOCUS_SURFACES.items()
                    if contrast_ratio(FOCUS_RING, colour) < 3.0]
        self.assertEqual(failures, [],
                         f"focus ring {FOCUS_RING} is invisible on: "
                         + ", ".join(failures))

    def test_the_rejected_amber_would_have_failed(self):
        # Guards the reasoning, not only the answer: if someone later
        # "tidies" the ring to a brand colour, this records what it cost.
        self.assertLess(contrast_ratio("#F5A524", "#1F6AA5"), 3.0)

    def test_the_ring_is_thick_enough_to_see(self):
        self.assertGreaterEqual(FOCUS_RING_WIDTH, 2)

    def test_every_console_surface_is_covered(self):
        # A new background colour must be added here, or the ring is
        # unverified against it.
        self.assertGreaterEqual(len(FOCUS_SURFACES), 6)


if __name__ == "__main__":
    unittest.main()
