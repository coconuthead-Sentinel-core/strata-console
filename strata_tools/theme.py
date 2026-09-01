r"""Making the controls visible as SHAPES. WCAG 1.4.11, Level AA.

**The finding.** The owner tested the console and reported the buttons
were "very small and hard to see". Measuring the second half of that
found something the earlier audit missed entirely: every button in the
application fails WCAG 1.4.11 Non-text Contrast, which requires a user
interface component to reach **3:1 against its background**.

    CustomTkinter default blue #1F6AA5 on the frame  ->  2.47:1  FAIL

That one is original to the app. The colour-coded mode buttons added on
2026-09-01 are far worse, because deep fills that carry near-white text
beautifully are nearly the same luminance as the dark frame behind them:

    GREEN inactive  #16301B on #2B2B2B  ->  1.01:1
    YELLOW inactive #33270A on #2B2B2B  ->  1.03:1
    RED    inactive #3A1414 on #2B2B2B  ->  1.15:1

1.01:1 is not a low-contrast control. It is an invisible one. The
earlier pass verified the *text* on those buttons and never checked the
button against what it sits on — the same class of mistake as checking
that the window fits the screen and not that the content fits the
window. Two different questions, and only one of them was asked.

**The fix is an outline, not a repaint.** Raising the fills would trade
1.4.11 against 1.4.3 — a lighter fill carries the near-white label less
well. A border sidesteps that: the fill keeps doing the text job, the
outline does the shape job. ``OUTLINE`` clears 3:1 against the frame and
against every fill in the console, measured in ``tests/test_theme.py``
rather than asserted here.
"""

# The CustomTkinter dark-theme frame every control sits on.
FRAME = "#2B2B2B"

# Label colour on those controls.
TEXT = "#DCE4EE"

# The console's own button fill. CustomTkinter's default #1F6AA5 carries
# the #DCE4EE label at 4.47:1 -- under the 4.5:1 AA line by a hair, and
# under it nonetheless. This is the nearest blue that clears it (5.68:1)
# so the change is a correction rather than a restyle.
BUTTON_FILL = "#1A5A8C"
BUTTON_HOVER = "#144870"

# Every fill an outline has to work against. A new button colour must be
# added here, or it goes unverified.
FILLS = {
    "button blue": BUTTON_FILL,
    "button hover": BUTTON_HOVER,
    "green active": "#1B5E20",
    "green inactive": "#16301B",
    "yellow active": "#705200",
    "yellow inactive": "#33270A",
    "red active": "#8B1A1A",
    "red inactive": "#3A1414",
}

# Chosen by sweep, not by eye. #B3BECA was the first candidate to pass
# everything and cleared the blue fill by only 3.04:1; this one holds
# 3.45:1 at its worst, which leaves room for a fill to be nudged later
# without silently dropping under the line.
OUTLINE = "#C0CAD5"
OUTLINE_WIDTH = 1

# A control the owner has selected is outlined brighter and thicker, so
# "which mode am I in" survives on a dim screen or at an angle.
SELECTED_OUTLINE = TEXT
SELECTED_OUTLINE_WIDTH = 3

# WCAG 1.4.11 threshold for user interface components.
NON_TEXT_MIN = 3.0

# Minimum drawn height for a primary control, in real pixels. The owner
# reported the buttons as too small after widget scaling was reduced to
# fit every control on a 617px screen; this is the floor that reduction
# is not allowed to cross.
BUTTON_MIN_HEIGHT = 40


def outline_kwargs(selected=False):
    """CustomTkinter border keywords for a control. Pure."""
    if selected:
        return {"border_color": SELECTED_OUTLINE,
                "border_width": SELECTED_OUTLINE_WIDTH}
    return {"border_color": OUTLINE, "border_width": OUTLINE_WIDTH}


def surfaces_to_check(outline=OUTLINE):
    """``{name: (outline, background)}`` every pair that must pass. Pure.

    The frame first, because that is the pair the original defect failed,
    then every fill the outline is drawn on top of.
    """
    pairs = {"frame": (outline, FRAME)}
    for name, fill in FILLS.items():
        pairs[name] = (outline, fill)
    return pairs
