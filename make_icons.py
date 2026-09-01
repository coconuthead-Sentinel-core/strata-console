"""Generate the distinct desktop icons for this project.

Distinct is the point, not decoration. There are now two shells over one
engine and their shortcuts sit next to each other on the desktop; two
near-identical tiles differing only by a word in the filename is a poor
way to tell them apart, especially for a reader who has to parse the
label rather than recognise the shape. So the shells differ by COLOUR
and by GLYPH as well as by name -- the same rule the mode buttons follow.

Running this rewrites EVERY icon it defines. To add or refresh one
without disturbing the others, import make() and call it for that file.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))


def font(size):
    for name in ("arialbd.ttf", "arial.ttf", "segoeuib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def centered(draw, box, text, fnt, fill):
    x0, y0, x1, y1 = box
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    w, h = r - l, b - t
    draw.text((x0 + (x1 - x0 - w) / 2 - l, y0 + (y1 - y0 - h) / 2 - t), text, font=fnt, fill=fill)


def fit(draw, text, box_w, start=40, floor=18):
    """Largest label font that fits inside the tile. Pure enough.

    A fixed size clipped "STRATA WEB" to "TRATA WE" -- a label that runs
    off its own tile is worse than a smaller one, and an icon is exactly
    the place where nobody notices the difference until they are looking
    for the right shortcut.
    """
    for size in range(start, floor - 1, -2):
        f = font(size)
        l, _t, r, _b = draw.textbbox((0, 0), text, font=f)
        if (r - l) <= box_w:
            return f
    return font(floor)


def make(path, bg, accent, top, bottom):
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded tile
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=46, fill=bg, outline=accent, width=8)
    centered(d, (0, 28, S, 168), top, font(150), accent)        # big glyph/letter
    centered(d, (0, 170, S, 236), bottom, fit(d, bottom, S - 48),
             (255, 255, 255, 255))                              # label
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(path, sizes=sizes)
    print("wrote", path)


def make_wordmark(path, bg, fg, word):
    """A tile that is just the word, as large as it will go.

    For the Start menu, where the entries sit in a plain alphabetical
    list and the icon is small. A glyph-plus-caption tile turns to mush
    at 32px; one word filling the tile stays legible, and the colour
    then carries which of the two shells it is.

    The word is auto-fitted rather than set at a fixed size, for the
    same reason the caption is: a label that runs off its own tile is
    worse than a smaller one.
    """
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, S - 6, S - 6], radius=44, fill=bg,
                        outline=fg, width=6)
    centered(d, (0, 0, S, S), word, fit(d, word, S - 56, start=96, floor=24),
             fg)
    img.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48),
                          (32, 32), (16, 16)])
    print("wrote", path)


# Quantum Nexus Forge — deep violet tile, cyan accent
make(os.path.join(HERE, "qnf_icon.ico"), (30, 16, 54, 255), (0, 229, 255, 255), "⚡", "NEXUS FORGE")
# Turbo — black tile, lime-green accent
make(os.path.join(HERE, "turbo_icon.ico"), (12, 12, 12, 255), (124, 252, 0, 255), "T", "TURBO")
# Strata web shell — the console's own dark ground (#12161A) and a
# lightened steel blue, both traceable to strata_tools/theme.py, so the
# icon and the window it opens are recognisably the same thing. Reads as
# a sibling of the desktop shell rather than a different application.
make(os.path.join(HERE, "strata_web_icon.ico"), (18, 22, 26, 255),
     (95, 165, 214, 255), "W", "STRATA WEB")

# Start-menu wordmarks. Both black; the LETTERING is what separates them,
# because in the Start menu's alphabetical list the two entries sit
# directly on top of each other under S and the name alone is a slow way
# to tell them apart.
#   white -> the desktop console (the original)
#   gold  -> the web shell
# Colour is the fast cue, not the only one: the shortcut names still say
# which is which, so the pair does not depend on distinguishing white
# from gold at 32 pixels.
make_wordmark(os.path.join(HERE, "strata_start_desktop.ico"),
              (0, 0, 0, 255), (255, 255, 255, 255), "STRATA")
make_wordmark(os.path.join(HERE, "strata_start_web.ico"),
              (0, 0, 0, 255), (212, 175, 55, 255), "STRATA")
