"""Bench check for the window-geometry path -- does the console FIT?

The console's oldest UI trap: CustomTkinter multiplies requested
geometry by the display scaling factor, so a naive ``geometry("1000x700")``
became 1750x1225 physical and pushed the bottom controls off the owner's
~1097x617 effective display. The console compensates by dividing the
scaling back out, and ``strata_tools/window_fit.py`` now holds that rule
as a tested kernel.

This bench measures the REAL window against the REAL screen and passes
only if the window fits with its bottom edge on screen.

    py -3 tools/dpi_check.py            # the shipped path
    py -3 tools/dpi_check.py --aware    # reproduce the DPI-awareness trial

MEASURED 2026-09-01, and the reason Sentinel Forge's ``platform_dpi``
was NOT ported. Declaring per-monitor-v2 awareness makes Windows report
the true 1920x1080 instead of the virtualized 1097x617. The window stays
999 px wide in Tk coordinates, so it falls from **91% of screen width to
52%** -- half the size, with the accessibility fonts shrinking to match.
Crisper text, materially smaller window. The console is to be left as
designed, so awareness stays off and this bench records why.

Requires a display; it is a bench tool, not a CI test. The pure sizing
rule it exercises is unit-tested headlessly in tests/test_window_fit.py.
"""

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

# Taskbar and title-bar allowance: the window must clear the bottom of the
# work area, not merely the raw screen height.
BOTTOM_ALLOWANCE = 0


def measure(enable_awareness):
    status = "not attempted"
    if enable_awareness:
        # Declared inline, NOT imported from strata_tools: the console
        # deliberately does not ship DPI awareness (see the module
        # docstring), and an unwired module in the package would be dead
        # code pretending to be a feature. This flag exists only so the
        # measurement behind that decision stays reproducible.
        import ctypes
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(-4))
            status = "per-monitor-v2"
        except Exception as e:
            status = f"unavailable ({type(e).__name__})"

    # Point the console at a throwaway DB before importing it.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    import strata_core
    strata_core.DB_PATH = tmp.name

    app = strata_console.StrataConsole()
    root = app.root
    # winfo_width() reports Tk's 200x200 default until the window is
    # actually mapped, so force a real update -- otherwise this bench
    # measures nothing and passes, which is worse than failing.
    root.update_idletasks()
    root.update()
    root.deiconify()
    root.update()
    data = {
        "awareness": status,
        "screen_w": root.winfo_screenwidth(),
        "screen_h": root.winfo_screenheight(),
        "win_w": root.winfo_width(),
        "win_h": root.winfo_height(),
        "requested": root.winfo_geometry(),
        "win_x": root.winfo_x(),
        "win_y": root.winfo_y(),
    }
    try:
        import customtkinter as ctk
        data["ctk_scaling"] = ctk.ScalingTracker.get_window_scaling(root)
    except Exception as e:
        data["ctk_scaling"] = f"unavailable ({type(e).__name__})"
    root.destroy()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)
    return data


def report(d):
    right = d["win_x"] + d["win_w"]
    bottom = d["win_y"] + d["win_h"]
    print(f"  DPI awareness   : {d['awareness']}")
    print(f"  CTk scaling     : {d['ctk_scaling']}")
    print(f"  Screen          : {d['screen_w']} x {d['screen_h']}")
    print(f"  Window          : {d['win_w']} x {d['win_h']} "
          f"at +{d['win_x']}+{d['win_y']}")
    print(f"  wm geometry     : {d['requested']}")
    print(f"  Width as % of screen : "
          f"{100.0 * d['win_w'] / d['screen_w']:.0f}%")
    print(f"  Right edge      : {right}  (screen {d['screen_w']})")
    print(f"  Bottom edge     : {bottom}  (screen {d['screen_h']})")

    fits_x = right <= d["screen_w"]
    fits_y = bottom <= d["screen_h"] - BOTTOM_ALLOWANCE
    for label, ok in (("fits horizontally", fits_x), ("fits vertically", fits_y)):
        print(f"  {'PASS' if ok else 'FAIL'}: {label}")
    if not (fits_x and fits_y):
        print("\n  The bottom controls would be off-screen. This is the "
              "trap the scaling compensation exists to prevent.")
    return 0 if (fits_x and fits_y) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aware", action="store_true",
                    help="reproduce the DPI-awareness trial "
                         "(not the shipped behaviour)")
    args = ap.parse_args(argv)
    mode = "ON (trial)" if args.aware else "OFF (shipped)"
    print(f"Window geometry check -- DPI awareness {mode}\n")
    return report(measure(args.aware))


if __name__ == "__main__":
    raise SystemExit(main())
