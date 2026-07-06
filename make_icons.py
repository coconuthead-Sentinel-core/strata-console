"""Generate two bright, distinct desktop icons for Quantum Nexus Forge + Turbo."""
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


def make(path, bg, accent, top, bottom):
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded tile
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=46, fill=bg, outline=accent, width=8)
    centered(d, (0, 28, S, 168), top, font(150), accent)        # big glyph/letter
    centered(d, (0, 170, S, 236), bottom, font(40), (255, 255, 255, 255))  # label
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(path, sizes=sizes)
    print("wrote", path)


# Quantum Nexus Forge — deep violet tile, cyan accent
make(os.path.join(HERE, "qnf_icon.ico"), (30, 16, 54, 255), (0, 229, 255, 255), "⚡", "NEXUS FORGE")
# Turbo — black tile, lime-green accent
make(os.path.join(HERE, "turbo_icon.ico"), (12, 12, 12, 255), (124, 252, 0, 255), "T", "TURBO")
