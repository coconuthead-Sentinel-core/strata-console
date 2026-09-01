r"""The read-aloud front end -- what 🔊 should actually say.

Two stages, in this order:

1. **Strip markdown** (new here). Sentinel Forge reads *documents*;
   Strata reads *a local language model's replies*, and those arrive as
   markdown. Handed straight to SAPI, the console says "asterisk
   asterisk important asterisk asterisk" and reads fenced code blocks
   character by character. That is the gap this closes -- 🔊 already
   worked, it just was not speaking English.

2. **Normalize for speech** (recycled from Sentinel Forge's
   ``lyceum/text_norm.py``). The text-analysis stage of a standard TTS
   front end: expand numbers, money, percents, ordinals, years and
   common abbreviations, because a voice engine pronounces "$32" and
   "Dr." badly. Inline code spans are treated as ATOMIC and exempted
   from the English rules -- otherwise ``1024`` inside backticks becomes
   "one thousand twenty-four" in the middle of a file path.

Both stages are pure and defensive: any unexpected error returns the
input unchanged, so a reading session can never be broken by this
module. Applied only to the string handed to the engine, never to the
on-screen text.
"""

import re

# ---------------------------------------------------------------- numbers

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven",
         "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
         "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]

# Deliberately small: only abbreviations that are nearly always read the
# same way. An ambiguous expansion is worse than none.
_ABBREV = {
    "Mr.": "Mister", "Mrs.": "Missus", "Ms.": "Miss", "Dr.": "Doctor",
    "Prof.": "Professor", "Jr.": "Junior", "Sr.": "Senior", "St.": "Saint",
    "vs.": "versus", "etc.": "et cetera", "e.g.": "for example",
    "i.e.": "that is", "approx.": "approximately",
}

_ORDINAL_IRREGULAR = {
    "one": "first", "two": "second", "three": "third", "five": "fifth",
    "eight": "eighth", "nine": "ninth", "twelve": "twelfth",
}


def _int_to_words(n):
    """Whole number -> English words (up to the billions). Pure."""
    if n < 0:
        return "negative " + _int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        word = _TENS[n // 10]
        return word + ("-" + _ONES[n % 10] if n % 10 else "")
    parts = []
    for value, name in ((1_000_000_000, "billion"),
                        (1_000_000, "million"),
                        (1_000, "thousand")):
        if n >= value:
            parts.append(_int_to_words(n // value) + " " + name)
            n %= value
    if n >= 100:
        parts.append(_ONES[n // 100] + " hundred")
        n %= 100
    if n:
        parts.append(_int_to_words(n))
    return " ".join(parts)


def _ordinalize(words):
    head, _, last = words.rpartition("-")
    if not last:
        head, last = "", words
    if last in _ORDINAL_IRREGULAR:
        last = _ORDINAL_IRREGULAR[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return (head + "-" + last) if head else last


def _decimal_to_words(token):
    """'3.14' -> 'three point one four'; '12' -> 'twelve'. Pure."""
    token = token.replace(",", "")
    if "." in token:
        whole, frac = token.split(".", 1)
        whole_words = _int_to_words(int(whole)) if whole else "zero"
        digits = " ".join(_ONES[int(d)] for d in frac if d.isdigit())
        return f"{whole_words} point {digits}".strip()
    return _int_to_words(int(token))


def _money(match):
    whole = int(match.group(1).replace(",", ""))
    cents_str = match.group(2)
    dollars = f"{_int_to_words(whole)} {'dollar' if whole == 1 else 'dollars'}"
    if cents_str:
        cents = int(round(float("0" + cents_str) * 100))
        if cents:
            unit = "cent" if cents == 1 else "cents"
            return f"{dollars} and {_int_to_words(cents)} {unit}"
    return dollars


def _year_to_words(year):
    """1999 -> 'nineteen ninety-nine'; 2007 -> 'two thousand seven'. Pure."""
    if 2000 <= year <= 2009:
        return ("two thousand" if year == 2000
                else "two thousand " + _int_to_words(year - 2000))
    hi, lo = year // 100, year % 100
    if lo == 0:
        return _int_to_words(hi) + " hundred"
    if lo < 10:
        return _int_to_words(hi) + " oh " + _ONES[lo]
    return _int_to_words(hi) + " " + _int_to_words(lo)


# --------------------------------------------------------------- markdown

_FENCE = re.compile(r"```[^\n]*\n.*?(?:```|\Z)", re.DOTALL)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_RULE = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$", re.MULTILINE)
_QUOTE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_BULLET = re.compile(r"^(\s*)[-*+]\s+", re.MULTILINE)
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BOLD_ITALIC = re.compile(r"(\*{1,3}|_{1,3})(\S(?:.*?\S)?)\1", re.DOTALL)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$", re.MULTILINE)
_BLANKS = re.compile(r"\n{3,}")

# What a fenced code block becomes. Reading one aloud character by
# character is unusable; silence would hide that the reply contained one.
FENCE_SPOKEN = "(code block)"


def strip_markdown(text):
    """Turn a model's markdown reply into something worth hearing. Pure.

    Inline ``code`` keeps its backticks so the normalizer can treat it as
    an atomic token; everything else becomes plain prose.
    """
    try:
        if not text:
            return text or ""
        out = text
        out = _FENCE.sub(FENCE_SPOKEN + ". ", out)
        out = _TABLE_SEP.sub("", out)
        out = _TABLE_ROW.sub(
            lambda m: " ".join(
                cell.strip() for cell in m.group(0).strip().strip("|").split("|")
            ) + ".", out)
        out = _RULE.sub("", out)
        out = _IMAGE.sub(r"\1", out)
        out = _LINK.sub(r"\1", out)
        out = _HEADING.sub("", out)
        out = _QUOTE.sub("", out)
        out = _BULLET.sub(r"\1", out)
        # Emphasis markers, innermost first so ***x*** unwraps fully.
        for _ in range(3):
            out = _BOLD_ITALIC.sub(r"\2", out)
        out = _BLANKS.sub("\n\n", out)
        return out.strip()
    except Exception:
        return text


# -------------------------------------------------------------- normalize

# Code is not English prose: running the abbreviation, number and year
# rules over `strata_tools/speech.py` or `1024` garbles it. Standard TTS
# practice is to treat code spans as atomic tokens exempt from
# linguistic normalization.
_CODE_SPAN = re.compile(r"`([^`\n]+)`")


def _normalize_code_span(code):
    """Name the separators a listener cannot hear; expand nothing else."""
    return (code.replace("_", " underscore ")
                .replace("/", " slash ")
                .strip())


def _normalize_prose(text):
    out = text
    for abbr, full in _ABBREV.items():
        out = out.replace(abbr, full)
    # Money before bare numbers, or the digits are consumed first.
    out = re.sub(r"\$(\d[\d,]*)(\.\d{1,2})?", _money, out)
    out = re.sub(r"(\d[\d,]*(?:\.\d+)?)\s*%",
                 lambda m: _decimal_to_words(m.group(1)) + " percent", out)
    out = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b",
                 lambda m: _ordinalize(_int_to_words(int(m.group(1)))), out)
    # Calendar years read naturally, bounded 1000-2099 to limit false
    # positives -- a standard normalization trade-off.
    out = re.sub(r"\b(1\d{3}|20\d{2})\b",
                 lambda m: _year_to_words(int(m.group(1))), out)
    out = re.sub(r"\b\d[\d,]*(?:\.\d+)?\b",
                 lambda m: _decimal_to_words(m.group(0)), out)
    return out


def normalize_for_speech(text):
    """Expand numbers, currency, percents, ordinals and abbreviations. Pure."""
    try:
        if not text:
            return text or ""
        # re.split with one capture group alternates prose / code / prose.
        parts = _CODE_SPAN.split(text)
        return "".join(_normalize_code_span(seg) if i % 2
                       else _normalize_prose(seg)
                       for i, seg in enumerate(parts))
    except Exception:
        return text


def speakable(text):
    """Markdown out, numbers spelled out. What 🔊 hands to the engine."""
    try:
        return normalize_for_speech(strip_markdown(text))
    except Exception:
        return text
