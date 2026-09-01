"""Accessibility bench -- measure the console, do not assume it.

Reports the things a neuro-inclusive audit actually turns on, taken from
the real running widgets rather than from reading the source:

  * keyboard reachability  -- can every control be reached by Tab?
    (WCAG 2.1.1 Keyboard, level A -- the one that, if it fails, makes
    most of the rest moot)
  * target size            -- WCAG 2.2 SC 2.5.8 Target Size (Minimum),
    level AA, 24x24 CSS px
  * text scaling           -- which widgets actually respond to A+/A-
  * line length            -- characters per line on the reading surface
    (British Dyslexia Association style guidance: 60-80)

Run it with a display attached:

    py -3 tools/a11y_check.py

Uses a throwaway database, so the live one is never touched.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

MIN_TARGET = 24          # WCAG 2.2 SC 2.5.8 (Minimum), CSS px
LINE_MIN, LINE_MAX = 60, 80   # BDA reading-width guidance


def walk(widget, depth=0):
    yield widget, depth
    for child in widget.winfo_children():
        yield from walk(child, depth + 1)


def interesting(widget):
    """Widgets a person is meant to operate."""
    name = type(widget).__name__
    return name in {"CTkButton", "CTkEntry", "CTkOptionMenu", "CTkCheckBox",
                    "CTkTextbox", "CTkSegmentedButton", "CTkSlider"}


def label_of(widget):
    for attr in ("cget",):
        try:
            text = widget.cget("text")
            if text:
                return str(text)[:28]
        except Exception:
            pass
    return type(widget).__name__


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    import strata_console
    strata_console.DB_PATH = tmp.name

    app = strata_console.StrataConsole()
    root = app.root
    root.update_idletasks()
    root.update()
    root.deiconify()
    root.update()

    controls = [w for w, _ in walk(root) if interesting(w)]

    print(f"Controls found: {len(controls)}\n")

    # --- target size -----------------------------------------------------
    print(f"[1] TARGET SIZE  (WCAG 2.2 SC 2.5.8 AA, {MIN_TARGET}x{MIN_TARGET} minimum)")
    small = []
    for widget in controls:
        w, h = widget.winfo_width(), widget.winfo_height()
        if w <= 1 or h <= 1:
            continue
        if w < MIN_TARGET or h < MIN_TARGET:
            small.append((label_of(widget), w, h))
    if small:
        for name, w, h in small:
            print(f"    FAIL  {name:<28} {w}x{h}")
    else:
        print(f"    PASS  every control is at least {MIN_TARGET}x{MIN_TARGET}")

    # --- keyboard reachability -------------------------------------------
    print("\n[2] KEYBOARD  (WCAG 2.1.1 level A -- Tab must reach every control)")
    # Walk the REAL tab ring rather than reading takefocus, which is ''
    # (meaning "decide at traversal time") on most widgets and so proves
    # nothing either way.
    ring, seen = [], set()
    node = root
    for _ in range(400):
        try:
            node = node.tk_focusNext()
        except Exception:
            break
        if node is None or str(node) in seen:
            break
        seen.add(str(node))
        ring.append(node)
    reachable = {str(w) for w in ring}
    # A CustomTkinter control is a frame wrapping a real Tk widget, so a
    # control counts as reachable if it or any descendant is in the ring.
    unreachable = []
    for widget in controls:
        names = {str(w) for w, _ in walk(widget)}
        if not (names & reachable):
            unreachable.append((label_of(widget), type(widget).__name__))
    print(f"    tab ring holds {len(ring)} widgets")
    if unreachable:
        for name, kind in unreachable:
            print(f"    FAIL  {name:<28} {kind} is not reachable by Tab")
    else:
        print("    PASS  every control is reachable by Tab")

    # --- text scaling ----------------------------------------------------
    print("\n[3] TEXT SCALING  (WCAG 1.4.4 -- what A+/A- actually resizes)")
    before = {}
    for widget in controls:
        try:
            before[widget] = str(widget.cget("font"))
        except Exception:
            pass
    for _ in range(3):
        app.bigger_text()
    root.update_idletasks()
    changed, fixed = [], []
    for widget, old in before.items():
        try:
            new = str(widget.cget("font"))
        except Exception:
            continue
        (changed if new != old else fixed).append(label_of(widget))
    print(f"    resizes  : {', '.join(changed) or '(none)'}")
    print(f"    FIXED    : {', '.join(fixed) or '(none)'}")

    # --- reading width ---------------------------------------------------
    print(f"\n[4] LINE LENGTH  (BDA guidance {LINE_MIN}-{LINE_MAX} characters)")
    box = app.output_box
    try:
        import tkinter.font as tkfont
        font = tkfont.Font(family=app.font_family, size=app.font_size)
        char_w = max(1, font.measure("0"))
        cols = box.winfo_width() // char_w
        verdict = "PASS" if LINE_MIN <= cols <= LINE_MAX else "FAIL"
        print(f"    {verdict}  ~{cols} characters per line "
              f"({box.winfo_width()}px at {app.font_size}pt)")
    except Exception as e:
        print(f"    could not measure: {type(e).__name__}: {e}")

    # --- mode indication --------------------------------------------------
    print("\n[5] MODE INDICATION  (WCAG 1.4.1 -- state not by colour alone,")
    print("     and the design law: colour-coded, labelled controls)")
    mode_buttons = [w for w in controls
                    if type(w).__name__ == "CTkButton"
                    and "Mode:" in str(label_of(w))]
    colours = {label_of(w): str(w.cget("fg_color")) for w in mode_buttons}
    print(f"    mode buttons : {len(mode_buttons)}")
    for name, colour in colours.items():
        print(f"      {name:<16} fg_color={colour}")
    if len(set(colours.values())) <= 1 and mode_buttons:
        print("    FAIL  every mode button is the same colour, and none "
              "shows which mode is active")
    else:
        print("    PASS  modes are visually distinguished")

    root.destroy()
    try:
        app.pipeline.db.conn.close()
    except Exception:
        pass
    os.unlink(tmp.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
