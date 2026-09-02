"""Generate the distinct desktop icons for this project.

Distinct is the point, not decoration. Several projects live side by
side in this folder and their shortcuts sit next to each other on the
desktop; near-identical tiles differing only by a word in the filename
is a poor way to tell them apart, especially for a reader who has to
parse the label rather than recognise the shape. So they differ by
COLOUR and by GLYPH as well as by name -- the mode buttons' rule.

Strata needed a PAIR of icons while it ran two shells. It does not any
more: the CustomTkinter console was retired on 2026-09-01 and there is
one Strata icon, ``strata_start_desktop.ico``. The web-shell tile and
its gold wordmark were deleted with the shell they pointed at, because
an icon for an application that no longer exists is worse than no icon
-- it is a shortcut that opens nothing.

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
# Strata — the one Start-menu wordmark. Black tile, white lettering.
# There was a second, gold one while a second shell existed; it went
# with that shell. Both shortcuts that matter -- desktop and Start menu
# -- point at launch_strata.vbs and wear this file.
make_wordmark(os.path.join(HERE, "strata_start_desktop.ico"),
              (0, 0, 0, 255), (255, 255, 255, 255), "STRATA")
