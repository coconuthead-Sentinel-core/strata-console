"""How much vertical room does the console's chrome actually need?

CustomTkinter multiplies every widget's size by a widget-scaling factor
(1.75 on this laptop). The window is sized in real pixels and capped to
the screen, so on a 617-pixel-tall display the window is 486 tall while
the scaled content needs far more -- and pack silently drops whatever
does not fit, starting with the last thing packed.

This measures the requested height of the whole stack at a range of
scaling factors and reports the largest one that still fits.

    py -3 tools/scaling_probe.py

Uses a throwaway database.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

CANDIDATES = [1.75, 1.6, 1.5, 1.4, 1.3, 1.25, 1.2, 1.1, 1.0, 0.9, 0.8]

# The transcript is the point of the app; it must get real room, not the
# few pixels left over.
MIN_TRANSCRIPT = 160


def measure(scaling):
    """Requested height of the console's chrome at one scaling factor."""
    import customtkinter as ctk
    ctk.set_widget_scaling(scaling)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    import strata_core
    strata_core.DB_PATH = tmp.name
    app = strata_console.StrataConsole()
    root = app.root
    root.update_idletasks()

    # Everything except the transcript, which is the elastic one.
    chrome = 0
    for child in root.winfo_children():
        if type(child).__name__ == "CTkTextbox":
            continue
        chrome += child.winfo_reqheight()
    # pack pady between the stacked children, measured generously.
    chrome += 8 * len(root.winfo_children())

    window_h = root.winfo_height()
    screen_h = root.winfo_screenheight()
    root.destroy()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)
    return chrome, window_h, screen_h


def main():
    import strata_console
    from strata_tools import window_fit

    print("Chrome height needed vs window height available\n")
    print(f"  {'scale':>6}  {'chrome':>7}  {'window':>7}  "
          f"{'transcript':>10}  verdict")
    best = None
    for scaling in CANDIDATES:
        try:
            chrome, window_h, screen_h = measure(scaling)
        except Exception as e:
            print(f"  {scaling:>6}  measurement failed: "
                  f"{type(e).__name__}: {e}")
            continue
        left = window_h - chrome
        ok = left >= MIN_TRANSCRIPT
        verdict = "FITS" if ok else "content clipped"
        print(f"  {scaling:>6}  {chrome:>7}  {window_h:>7}  "
              f"{left:>10}  {verdict}")
        if ok and best is None:
            best = scaling
    print()
    if best is None:
        print("  Nothing in the candidate range leaves the transcript "
              f"{MIN_TRANSCRIPT}px. The layout itself needs to shrink.")
    else:
        print(f"  Largest scaling that fits: {best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
