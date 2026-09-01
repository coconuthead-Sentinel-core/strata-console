r"""Making the content fit the window. Pure.

``window_fit.py`` makes the window fit the SCREEN. This makes the
content fit the WINDOW, and the distinction is the whole defect.

FB-001 was recorded as fixed because the window measured 999x486 inside
a 1097x617 screen — true, and irrelevant. CustomTkinter multiplies every
widget by a display-scaling factor of 1.75 here, so the console's chrome
needed **919 pixels** of the 486 available. Tk's packer does not
complain; it simply stops mapping children once it runs out of room, in
reverse order of packing. Thirteen controls, the transcript among them,
were never drawn at all.

Measured 2026-09-01 on the owner's display, one scaling per process
(``tools/_one_scaling.py``):

    scaling 1.75 -> chrome 919      1.4 -> 740
    scaling 1.20 -> chrome 634      1.0 -> 529

The relationship is linear, which is what lets this be arithmetic rather
than a search: chrome(s) = CHROME_AT_1 * s.

Two levers, and both are needed, because at 1.75 the chrome overflows a
617-pixel screen even with no transcript at all:

  1. **Fewer stacked rows.** The console had seven. The shop's own
     design law caps a screen at five major choices for exactly this
     reason (ADHD executive load), so consolidating is what the standard
     asks for, not a liberty taken with it.
  2. **A widget scaling that fits**, chosen from the real screen height
     rather than inherited from the display.

The transcript gets a floor rather than the leftovers. It is the point
of the application; a console that renders its own chrome and clips its
output has its priorities inverted.
"""

# Chrome height (everything except the transcript) at widget scaling
# 1.0, measured after the title row was removed and status merged into
# the top row. Re-derive with: py -3 tools/_one_scaling.py 1.0
CHROME_AT_1 = 431

# The transcript never gets less than this, in real pixels.
MIN_TRANSCRIPT = 180

# CustomTkinter renders below about 0.7 with visible artefacts, and
# above 1.75 there is no display here that needs it.
MIN_SCALING = 0.7
MAX_SCALING = 1.75


def chrome_height(scaling, chrome_at_1=CHROME_AT_1):
    """Pixels the non-transcript rows need at this scaling. Pure."""
    return chrome_at_1 * float(scaling)


def content_fits(window_h, scaling, chrome_at_1=CHROME_AT_1,
                 min_transcript=MIN_TRANSCRIPT):
    """Would every row render, with a usable transcript? Pure.

    This is the check FB-001 never made.
    """
    return chrome_height(scaling, chrome_at_1) + min_transcript <= window_h


def plan_widget_scaling(window_h, chrome_at_1=CHROME_AT_1,
                        min_transcript=MIN_TRANSCRIPT):
    """The largest widget scaling whose content fits ``window_h``. Pure.

    Clamped to a sane range. When even MIN_SCALING will not fit — a
    genuinely tiny screen — it returns MIN_SCALING rather than something
    unusable, and :func:`content_fits` will report False so the caller
    can say so out loud instead of silently clipping.
    """
    if chrome_at_1 <= 0:
        return MAX_SCALING
    available = float(window_h) - min_transcript
    if available <= 0:
        return MIN_SCALING
    ideal = available / float(chrome_at_1)
    return max(MIN_SCALING, min(MAX_SCALING, round(ideal, 2)))


def transcript_height(window_h, scaling, chrome_at_1=CHROME_AT_1):
    """Pixels left for the transcript at this scaling. Pure."""
    return int(float(window_h) - chrome_height(scaling, chrome_at_1))


def describe(window_h, scaling, chrome_at_1=CHROME_AT_1,
             min_transcript=MIN_TRANSCRIPT):
    """One owner-facing line about the fit. Pure."""
    chrome = int(chrome_height(scaling, chrome_at_1))
    left = transcript_height(window_h, scaling, chrome_at_1)
    if content_fits(window_h, scaling, chrome_at_1, min_transcript):
        return (f"Layout fits: chrome {chrome}px, transcript {left}px "
                f"in a {int(window_h)}px window at scaling {scaling}.")
    return (f"Layout does NOT fit: chrome {chrome}px leaves {left}px for "
            f"the transcript in a {int(window_h)}px window at scaling "
            f"{scaling}; {min_transcript}px is the minimum. Controls "
            f"will be clipped.")


# --- interface text ------------------------------------------------------
#
# WCAG 1.4.4 Resize Text (AA) asks for text scalable to 200% without loss
# of content or functionality. Those last four words are the constraint:
# on a 617-pixel screen, growing the CHROME without limit re-creates the
# defect this module exists to fix -- controls stop being drawn.
#
# So the two kinds of text scale differently, on purpose:
#
#   * The reading surfaces -- transcript and message box -- scale
#     without a ceiling beyond the app's own 10-36pt range. That is
#     where the owner actually reads, and it is what the A+/A- buttons
#     are for.
#   * The chrome -- button labels, menus, the status line -- scales with
#     them but is capped, because past the cap the row heights push
#     controls off the window and "without loss of functionality" fails.
#
# The cap was measured, not guessed. Sweeping chrome font sizes at the
# maximum reading size of 36pt and counting controls that stop being
# mapped:
#
#     9,10,11,12 -> 0 hidden
#     13, 14     -> 1 hidden  ("Mode: Red")
#     15         -> 2 hidden  ("Tour", "Mode: Red")
#
# So 12 is the honest ceiling. Note WHAT is lost first and why: the
# bottom row carries seven controls, and past 12pt their combined width
# exceeds the row. This is a HORIZONTAL limit, not a vertical one, and
# it is the shop design law speaking again -- a row of seven major
# choices is over the five the law allows, and the cost of that shows up
# here as a chrome font that cannot grow past 12pt.
#
# Consolidating that row would raise this cap. Until then the number is
# reported honestly rather than set to what would look better: the
# reading surfaces still scale to 36pt uncapped, which is where the
# dyslexia support actually matters.
UI_FONT_MIN = 10
UI_FONT_MAX = 12


def ui_font_size(reading_size):
    """Chrome text size for a given reading size. Pure and clamped.

    Follows the reading size so the interface does not stay tiny while
    the transcript grows, but stops at UI_FONT_MAX so the rows still fit.
    """
    try:
        size = int(reading_size)
    except (TypeError, ValueError):
        return UI_FONT_MIN
    return max(UI_FONT_MIN, min(UI_FONT_MAX, size))


def ui_font_is_capped(reading_size):
    """Is the chrome no longer following the reading size? Pure.

    Worth surfacing: the owner should know the interface stopped growing
    on purpose rather than assume the button is broken.
    """
    try:
        return int(reading_size) > UI_FONT_MAX
    except (TypeError, ValueError):
        return False
