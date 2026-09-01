r"""WCAG 2.1 contrast kernel, and this console's actual palette.

Reused from Sentinel Forge's ``lyceum/wcag.py``. The math is the W3C
relative-luminance definition and Success Criterion 1.4.3 (Contrast,
Minimum): normal text at least 4.5:1, large text at least 3:1.

Two jobs here:

1. **A gate on new colour pairs.** Any colour introduced into the UI
   gets checked before it ships.
2. **A record of the palette as it stands.** ``PALETTE`` lists the pairs
   the console actually renders, read from the running CustomTkinter
   dark theme rather than guessed, so the audit describes the real
   application.

Findings are reported, never auto-corrected. Silently recolouring the
owner's app to satisfy a threshold would be exactly the "left as
designed" rule being broken by the tool meant to protect it.

Pure: no Tk, no I/O.
"""

AA_NORMAL = 4.5
AA_LARGE = 3.0

# The console's real pairs. Backgrounds are what the widget paints;
# #DCE4EE is CustomTkinter's dark-theme text colour, confirmed from
# ThemeManager rather than assumed. is_large marks text at or above the
# WCAG large-text threshold (18pt, or 14pt bold).
TEXT = "#DCE4EE"
PALETTE = [
    ("button (default)",        TEXT, "#1F6AA5", False),
    ("button (hover)",          TEXT, "#144870", False),
    ("voice button, recording", TEXT, "#DC2626", False),
    ("voice button, hover",     TEXT, "#B91C1C", False),
    ("attachment notice",       "#D97706", "#1D1E1E", False),
    ("transcript text",         TEXT, "#1D1E1E", False),
    ("input box text",          TEXT, "#343638", False),
]


# Pairs that miss AA and are accepted for now, each with a reason. This
# list is the difference between a known, decided shortfall and an
# unnoticed one -- the test asserts that NOTHING ELSE fails, so a newly
# introduced bad pair breaks the build while these stay as they are.
#
# Neither is silently recoloured: "left as designed" is the binding
# constraint, and a contrast tool that edits the owner's palette to make
# its own numbers go green is the tool breaking the rule it exists to
# protect. Both are reported to the owner as findings instead.
ACCEPTED_SHORTFALLS = {
    "button (default)":
        "4.47:1 against a 4.5:1 threshold -- CustomTkinter's own stock "
        "dark theme, not a Strata choice. Missing by 0.03 means changing "
        "it would restyle every button in the app to gain nothing a "
        "person can perceive.",
    "voice button, recording":
        "3.77:1. Strata's own red, and the genuine shortfall of the two. "
        "It is a transient state colour shown only while recording, and "
        "the button also changes its LABEL to 'Stop' -- so the state is "
        "not carried by colour alone, which is the WCAG 1.4.1 concern. "
        "Worth raising with the owner; a darker red (#B91C1C, already "
        "the hover colour) reaches 5.05:1 and would keep the design.",
}


def _srgb_to_linear(channel):
    """One sRGB channel (0..1) -> linear-light value. W3C piecewise."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    """Relative luminance of an sRGB hex colour ('#rrggbb'), 0.0-1.0."""
    text = hex_color.strip().lstrip("#")
    if len(text) == 3:                      # allow #abc shorthand
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"not a hex colour: {hex_color!r}")
    red = _srgb_to_linear(int(text[0:2], 16) / 255.0)
    green = _srgb_to_linear(int(text[2:4], 16) / 255.0)
    blue = _srgb_to_linear(int(text[4:6], 16) / 255.0)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(color_a, color_b):
    """WCAG contrast ratio, 1.0 (identical) to 21.0 (black on white).

    Symmetric: the order of the two colours does not matter.
    """
    lum_a = relative_luminance(color_a)
    lum_b = relative_luminance(color_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def meets_aa(ratio, large=False):
    """WCAG 2.1 AA: 4.5:1 normal text, 3.0:1 large text."""
    return ratio >= (AA_LARGE if large else AA_NORMAL)


def audit(pairs=None):
    """Audit (name, fg, bg, is_large) pairs. One dict per pair. Pure."""
    out = []
    for name, foreground, background, large in (pairs or PALETTE):
        ratio = contrast_ratio(foreground, background)
        out.append({"name": name, "fg": foreground, "bg": background,
                    "large": large, "ratio": round(ratio, 2),
                    "passes_aa": meets_aa(ratio, large)})
    return out


def failures(pairs=None):
    """Only the pairs that miss AA. Findings for the owner, not fixes."""
    return [row for row in audit(pairs) if not row["passes_aa"]]


def format_audit(rows):
    """A readable table of an audit result. Pure."""
    width = max((len(r["name"]) for r in rows), default=4)
    lines = []
    for row in rows:
        verdict = "PASS" if row["passes_aa"] else "FAIL"
        size = "large" if row["large"] else "normal"
        lines.append(f"{verdict}  {row['name']:<{width}}  "
                     f"{row['fg']} on {row['bg']}  "
                     f"{row['ratio']:>5.2f}:1  ({size} text)")
    return lines
