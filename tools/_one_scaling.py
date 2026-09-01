"""Measure the console's chrome height at ONE widget-scaling factor.

One scaling per process on purpose: CustomTkinter keeps global scaling
state and leaves `after` callbacks bound to destroyed roots, so
measuring several factors in a single interpreter produces both wrong
numbers and a wall of Tcl errors.

    py -3 tools/_one_scaling.py 1.75

Called in a loop by tools/scaling_probe.py.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))


def main():
    scaling = float(sys.argv[1])
    import customtkinter as ctk
    ctk.set_widget_scaling(scaling)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    strata_console.DB_PATH = tmp.name
    app = strata_console.StrataConsole()
    root = app.root
    root.update_idletasks()

    rows = []
    chrome = 0
    for child in root.winfo_children():
        name = type(child).__name__
        height = child.winfo_reqheight()
        rows.append((name, height))
        if name != "CTkTextbox":
            chrome += height

    print(f"SCALING {scaling}")
    for name, height in rows:
        print(f"  {name:<12} {height}")
    print(f"CHROME {chrome}")
    print(f"SCREEN {root.winfo_screenheight()}")
    root.destroy()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
