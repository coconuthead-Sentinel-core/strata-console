"""Dump the console's real layout from inside a live mainloop.

Measuring a Tk window that has never been through a real event loop
reports nonsense -- unmapped children, heights of 1. This builds the
console the way a double-click does, lets it run for a moment on the
actual desktop, then writes what the layout REALLY is and quits.

    py -3 tools/layout_probe.py [seconds]

Writes tools/layout_report.txt. Uses a throwaway database.
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

REPORT = os.path.join(HERE, "layout_report.txt")


def walk(widget, depth=0):
    yield widget, depth
    for child in widget.winfo_children():
        yield from walk(child, depth + 1)


def main(argv=None):
    delay_ms = int(float((argv or sys.argv[1:] or ["2.5"])[0]) * 1000)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    strata_console.DB_PATH = tmp.name
    app = strata_console.StrataConsole()
    root = app.root

    def dump():
        lines = []
        lines.append(f"window {root.winfo_width()}x{root.winfo_height()} "
                     f"screen {root.winfo_screenwidth()}x"
                     f"{root.winfo_screenheight()}")
        lines.append("")
        lines.append("TOP-LEVEL STACK (what the owner can actually see)")
        for child in root.winfo_children():
            lines.append(
                f"  {type(child).__name__:<12} mapped={child.winfo_ismapped()} "
                f"y={child.winfo_y():>4} h={child.winfo_height():>4}")
        lines.append("")
        lines.append("CONTROLS")
        kinds = {"CTkButton", "CTkCheckBox", "CTkOptionMenu", "CTkEntry",
                 "CTkTextbox"}
        hidden = 0
        for widget, _ in walk(root):
            if type(widget).__name__ not in kinds:
                continue
            try:
                label = str(widget.cget("text"))[:22]
            except Exception:
                label = ""
            label = label or type(widget).__name__
            visible = widget.winfo_ismapped()
            if not visible:
                hidden += 1
            lines.append(f"  {label:<24} visible={visible} "
                         f"{widget.winfo_width()}x{widget.winfo_height()}")
        lines.append("")
        lines.append(f"HIDDEN CONTROLS: {hidden}")
        text = "\n".join(lines)
        with open(REPORT, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(text)
        root.destroy()

    root.after(delay_ms, dump)
    root.mainloop()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
