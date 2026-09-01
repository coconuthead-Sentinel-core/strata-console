"""Find the largest widget scaling that still draws every control.

The arithmetic in ``strata_tools/layout.py`` estimates chrome height from
a measured constant, and that estimate keeps coming in low because the
packer's inter-row padding is not in it. Rather than keep tuning a
constant against reality, this asks reality directly: build the console
at a given scaling, count what Tk actually mapped, and report.

    py -3 tools/fit_sweep.py 0.95 0.90 0.85 0.80 0.75

One scaling per process -- CustomTkinter holds global scaling state and
leaves `after` callbacks bound to destroyed roots, so several in one
interpreter gives both wrong numbers and a wall of Tcl noise. This
script re-invokes itself per value.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

# The transcript must stay usable, not merely non-zero.
MIN_TRANSCRIPT = 100


def measure_one(scaling):
    """Build the console pinned to one scaling; print a one-line result."""
    import customtkinter as ctk
    from strata_tools import layout

    layout.plan_widget_scaling = lambda *a, **k: scaling

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    strata_console.DB_PATH = tmp.name
    app = strata_console.StrataConsole()
    root = app.root

    def walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from walk(child)

    kinds = {"CTkButton", "CTkCheckBox", "CTkOptionMenu", "CTkEntry",
             "CTkTextbox"}

    def report():
        root.update_idletasks()
        root.update()
        hidden = [w for w in walk(root)
                  if type(w).__name__ in kinds and not w.winfo_ismapped()]
        transcript = app.output_box.winfo_height()
        buttons = [w for w in walk(root)
                   if type(w).__name__ == "CTkButton" and w.winfo_ismapped()]
        height = max((b.winfo_height() for b in buttons), default=0)
        ok = not hidden and transcript >= MIN_TRANSCRIPT
        print(f"RESULT scaling={scaling} hidden={len(hidden)} "
              f"transcript={transcript} button_h={height} "
              f"{'OK' if ok else 'NO'}")
        root.destroy()

    root.after(1400, report)
    root.mainloop()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--one":
        measure_one(float(args[1]))
        return 0
    values = [float(a) for a in args] or [0.95, 0.90, 0.85, 0.80, 0.75, 0.70]
    print(f"Largest scaling that draws everything and leaves the "
          f"transcript >= {MIN_TRANSCRIPT}px\n")
    best = None
    for value in values:
        out = subprocess.run(
            [sys.executable, "-X", "utf8", os.path.abspath(__file__),
             "--one", str(value)],
            capture_output=True, text=True)
        line = next((l for l in out.stdout.splitlines()
                     if l.startswith("RESULT")), None)
        if line is None:
            print(f"  scaling={value}  measurement failed")
            continue
        print("  " + line[len("RESULT "):])
        if line.endswith("OK") and best is None:
            best = value
    print()
    print(f"  Largest safe scaling: {best}" if best else
          "  Nothing in this range fits. The layout needs fewer rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
