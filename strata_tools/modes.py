r"""Colour-coded operating modes, with the active one readable without colour.

The console had three Mode buttons — Green, Yellow, Red — rendered in
**identical CustomTkinter blue**, with the current mode stated only in a
line of status text. Measured 2026-09-01 by ``tools/a11y_check.py``.

Two things were wrong with that, and they pull in opposite directions,
which is why this module exists rather than a one-line colour change.

**Colour coding was missing.** Sentinel Forge colour-codes its controls
because a colour-carried category is faster to locate than a word — it
is pre-attentive, so it costs no working memory. That matters for ADHD
in particular, where the executive cost of re-reading a row of
identical buttons is the whole problem.

**Colour alone must never carry the state.** WCAG 1.4.1 Use of Colour
(Level A). Somewhere between 1 in 12 and 1 in 200 people cannot separate
these hues, and the console is also used by someone who may be reading
it tired, on a dim screen, or at an angle.

So the active mode is marked **three** ways: a filled colour, a bullet
in the label, and a raised border. Any one of them alone is enough to
tell which mode is live.

Colours were chosen by measurement, not taste — every pair clears WCAG
AA 4.5:1 against the console's text colour, and the white focus ring
clears 3:1 against every one of them. ``tests/test_modes.py`` re-measures
rather than trusting these comments. They are deliberately deep and
desaturated: the shop design law asks for calm, predictable feedback
(sensory regulation), so these read as *coded*, not as alarms.
"""

# Text colour the console draws button labels in (CustomTkinter dark).
TEXT = "#DCE4EE"

# The marker that carries the active state without colour.
ACTIVE_MARK = "● "          # a filled bullet
INACTIVE_MARK = ""

# Both states carry a border now. Inactive used to be 0, which left the
# fill alone to define the shape -- and the inactive fills measure as low
# as 1.01:1 against the frame, i.e. invisible. See strata_tools/theme.py.
ACTIVE_BORDER = 3
INACTIVE_BORDER = 1

# fg when active / fg when inactive / hover. Active is the brighter of
# each pair, so "live" reads as lit rather than merely different.
MODES = {
    "GREEN": {
        "label": "Green",
        "active": "#1B5E20",
        "inactive": "#16301B",
        "hover": "#247029",
        "meaning": "active",
    },
    "YELLOW": {
        "label": "Yellow",
        "active": "#705200",
        "inactive": "#33270A",
        "hover": "#7D5A00",
        # Yellow is the awkward hue here: it has to stay dark enough to
        # carry near-white text at 4.5:1 while still reading as yellow
        # rather than brown. A brighter #856100 hover measured 4.42:1 and
        # was rejected -- hover states are where this gets forgotten,
        # because nobody screenshots a hover.
        "meaning": "analytical",
    },
    "RED": {
        "label": "Red",
        "active": "#8B1A1A",
        "inactive": "#3A1414",
        "hover": "#A52121",
        "meaning": "archival",
    },
}

ORDER = ["GREEN", "YELLOW", "RED"]


def is_mode(name):
    """Is this a known mode? Pure. Case-insensitive."""
    return str(name).strip().upper() in MODES


def normalise(name):
    """Canonical mode name, or None. Pure."""
    key = str(name).strip().upper()
    return key if key in MODES else None


def label_for(mode, active):
    """Button text. Pure.

    The bullet is the non-colour carrier of the active state, so it is
    part of the label rather than a separate decoration that a screen
    reader would skip.
    """
    key = normalise(mode)
    if key is None:
        return str(mode)
    mark = ACTIVE_MARK if active else INACTIVE_MARK
    return f"{mark}Mode: {MODES[key]['label']}"


def appearance(mode, active):
    """Everything the shell needs to draw one mode button. Pure.

    Returns a dict of CustomTkinter keyword arguments plus the label, so
    the Tk layer stays a thin application of a decision made here.
    """
    key = normalise(mode)
    if key is None:
        return {}
    spec = MODES[key]
    from strata_tools import theme
    return {
        "text": label_for(key, active),
        "fg_color": spec["active"] if active else spec["inactive"],
        "hover_color": spec["hover"],
        "border_width": ACTIVE_BORDER if active else INACTIVE_BORDER,
        "border_color": TEXT if active else theme.OUTLINE,
    }


def describe(mode):
    """One line naming the mode and what it means. Pure.

    Used for the tooltip and the status line, so the colour is never the
    only place the meaning lives.
    """
    key = normalise(mode)
    if key is None:
        return str(mode)
    spec = MODES[key]
    return f"{spec['label']} — {spec['meaning']}"


def all_appearances(current):
    """``{mode: kwargs}`` for every button given the live mode. Pure."""
    return {key: appearance(key, key == normalise(current))
            for key in ORDER}
