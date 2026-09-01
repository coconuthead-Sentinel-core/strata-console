r"""Window sizing that keeps the bottom controls on screen. Pure.

This is the console's oldest UI trap, extracted from inline arithmetic
into a kernel that can be graded without a display.

CustomTkinter multiplies whatever you pass to ``geometry()`` by the
display scaling factor. On the owner's laptop that factor is 1.75, so a
plain ``geometry("1000x700")`` became 1750x1225 physical -- and the
bottom row of controls, the send button among them, sat off the bottom
of a 1097x617 effective display. A control you cannot reach is a control
that does nothing, which is a defect.

The fix is to compute the size in real pixels, cap it to the screen, and
divide the scaling back out so CustomTkinter's multiplication lands on
the number actually wanted. That arithmetic used to live inline in
``StrataConsole.__init__`` with a comment; it now lives here with tests,
including the owner's real display and the case that originally broke.

Deliberately NOT solved by declaring Windows DPI awareness. Measured
2026-09-01: awareness makes Windows report the true 1920x1080 instead of
the virtualized 1097x617, and the same 999-pixel window falls from 91%
of screen width to 52% -- along with the accessibility fonts. See
``tools/dpi_check.py``, which reproduces both measurements.
"""

# Target size in real pixels, before the screen cap.
WANT_W = 1000
WANT_H = 700

# Margins kept clear: side chrome, and room for the Windows taskbar.
SIDE_MARGIN = 80
BOTTOM_MARGIN = 130

# Where the window is placed.
ORIGIN_X = 30
ORIGIN_Y = 20

# The smallest the owner can drag it before the layout stops working.
MIN_W = 640
MIN_H = 460


def _safe_scaling(scaling):
    """A usable scaling factor. Pure.

    CustomTkinter has returned 0, None and occasionally a string from
    ``get_window_scaling`` on odd display configurations. Dividing by any
    of those either raises or produces a window of size zero, so anything
    unusable falls back to 1.0 -- an unscaled window is survivable; a
    zero-sized one is not.
    """
    try:
        value = float(scaling)
    except (TypeError, ValueError):
        return 1.0
    if value <= 0 or value != value:      # non-positive, or NaN
        return 1.0
    return value


def target_pixels(screen_w, screen_h):
    """The size we want in REAL pixels, capped to the screen. Pure."""
    return (min(WANT_W, max(1, int(screen_w) - SIDE_MARGIN)),
            min(WANT_H, max(1, int(screen_h) - BOTTOM_MARGIN)))


def plan_geometry(screen_w, screen_h, scaling):
    """``(geometry_string, min_w, min_h)`` for a screen and scaling factor.

    The returned geometry is pre-divided by the scaling factor, because
    CustomTkinter multiplies it straight back. Feed it to
    ``root.geometry()`` and the window lands at ``target_pixels``.
    """
    factor = _safe_scaling(scaling)
    want_w, want_h = target_pixels(screen_w, screen_h)
    geometry = (f"{int(want_w / factor)}x{int(want_h / factor)}"
                f"+{ORIGIN_X}+{ORIGIN_Y}")
    return (geometry, int(MIN_W / factor), int(MIN_H / factor))


def fits_on_screen(screen_w, screen_h):
    """Would the planned window sit fully on screen? Pure.

    Given the caps in :func:`target_pixels`, this is provably always
    True -- ``ORIGIN + (screen - MARGIN)`` is smaller than ``screen``
    whenever the margin exceeds the origin, which both of ours do. It is
    kept as an explicit, testable statement of that invariant rather
    than a runtime guard, because a check that cannot fail is not a
    check. ``tests/test_window_fit.py`` proves it across a sweep of
    screen sizes instead of asserting it once.

    The invariant is what stops the original defect returning: any future
    edit that raises WANT_W/WANT_H past a margin, or drops a cap, breaks
    the sweep.
    """
    want_w, want_h = target_pixels(screen_w, screen_h)
    return (ORIGIN_X + want_w <= int(screen_w)
            and ORIGIN_Y + want_h <= int(screen_h))


def margins_cover_origin():
    """The precondition the fit invariant rests on. Pure."""
    return SIDE_MARGIN >= ORIGIN_X and BOTTOM_MARGIN >= ORIGIN_Y
