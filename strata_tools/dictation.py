r"""Spoken punctuation for the dictation path -- hands-free, pure, safe.

Recycled from Sentinel Forge's ``lyceum/dictation_commands.py`` and
``lyceum/dictation_guard.py``, merged into one module because in Strata
they are always used together: one inserts marks, the other resolves
them.

Why this finishes a half-built feature rather than adding a new one.
Strata's microphone works and returns a transcript. Someone dictating
instead of typing dictates *everything*, punctuation included -- and a
raw transcript leaves the spoken word "period" sitting there as the word
"period". Dictation that cannot punctuate is dictation that is not
finished, so this closes a gap rather than widening scope.

The second half exists because Whisper already auto-punctuates from
acoustic pauses. A person who ALSO speaks the punctuation produces
collisions: the recogniser's own "." plus the spoken one, giving
"stable . period" or "stable.." The guard converts what is still spoken
and then collapses duplicates, keeping the strongest terminal mark.

Order matters and is fixed: :func:`apply_commands` (which knows about
capitalisation and brackets) runs first, then :func:`dedup_punctuation`
tidies the collisions. :func:`polish` does both, and is what the console
calls.

Every entry point is pure and defensive -- it returns its input
unchanged on any unexpected error, because a transcription that arrives
slightly wrong is recoverable and one that raises inside a worker thread
loses the words entirely.

Deliberately NOT handled: "scratch that" and "select <x>", which are
stateful edits needing the text widget rather than a string transform;
and phonetic-alphabet spelling, which is too ambiguous in free dictation
(the name "Victor" would become "V").
"""

import re

# Two-word spoken forms -> (output, kind). ``kind`` controls spacing:
#   "close" attaches to the preceding word ("word."), "open" attaches to
#   the following word ("$5"), "break" is a line control character.
_TWO_WORD = {
    ("question", "mark"): ("?", "close"),
    ("exclamation", "mark"): ("!", "close"),
    ("exclamation", "point"): ("!", "close"),
    ("full", "stop"): (".", "close"),
    ("open", "quote"): ('"', "open"),
    ("close", "quote"): ('"', "close"),
    ("open", "paren"): ("(", "open"),
    ("close", "paren"): (")", "close"),
    ("open", "parenthesis"): ("(", "open"),
    ("close", "parenthesis"): (")", "close"),
    ("dollar", "sign"): ("$", "open"),
    ("percent", "sign"): ("%", "close"),
    ("new", "line"): ("\n", "break"),
    ("new", "paragraph"): ("\n\n", "break"),
    ("tab", "key"): ("\t", "break"),
}

_ONE_WORD = {
    "period": (".", "close"),
    "comma": (",", "close"),
    "colon": (":", "close"),
    "semicolon": (";", "close"),
    "ellipsis": ("…", "close"),
}

_MARKS = ".,!?;:"
# Strongest first: terminals outrank clause marks; "!" and "?" outrank ".".
_PRECEDENCE = "!?.;:,"


def _strongest(marks):
    """The strongest mark in a run. Pure."""
    for mark in _PRECEDENCE:
        if mark in marks:
            return mark
    return marks[0] if marks else ""


def apply_commands(text):
    """Turn spoken punctuation, formatting and capitalisation into characters.

    Ordinary prose passes through untouched; only recognised command
    words convert. Returns the input unchanged on any unexpected error.
    """
    try:
        if not text:
            return text or ""
        words = text.split()
        out = []
        need_space = False
        cap_next = False
        caps_mode = None                     # None | "title" | "upper"

        def space_before():
            nonlocal need_space
            if need_space and out:
                out.append(" ")
            need_space = False

        i, n = 0, len(words)
        while i < n:
            lower = words[i].lower()
            two = tuple(w.lower() for w in words[i:i + 2])
            three = [w.lower() for w in words[i:i + 3]]

            # --- capitalisation modes ---
            if three == ["all", "caps", "on"]:
                caps_mode = "upper"; i += 3; continue
            if three == ["all", "caps", "off"]:
                caps_mode = None; i += 3; continue
            if two == ("caps", "on"):
                caps_mode = "title"; i += 2; continue
            if two == ("caps", "off"):
                caps_mode = None; i += 2; continue
            if lower == "cap":
                cap_next = True; i += 1; continue

            # --- punctuation / formatting ---
            spec = _TWO_WORD.get(two) if len(two) == 2 else None
            step = 2
            if spec is None:
                spec = _ONE_WORD.get(lower)
                step = 1
            if spec is not None:
                symbol, kind = spec
                if kind == "open":
                    space_before(); out.append(symbol); need_space = False
                elif kind == "break":
                    out.append(symbol); need_space = False
                else:                        # "close"
                    out.append(symbol); need_space = True
                i += step
                continue

            # --- an ordinary word ---
            word = words[i]
            if cap_next:
                word = word[:1].upper() + word[1:]
                cap_next = False
            elif caps_mode == "title":
                word = word[:1].upper() + word[1:]
            elif caps_mode == "upper":
                word = word.upper()
            space_before(); out.append(word); need_space = True
            i += 1
        return "".join(out)
    except Exception:
        return text


def dedup_punctuation(text):
    """Collapse adjacent or duplicated marks to the strongest, and tidy spacing.

    Preserves numbers (3.14, 1,234) and newlines -- a paragraph break is
    a hard boundary, and a decimal point is not a sentence.
    """
    try:
        if not text:
            return text or ""
        result = text
        # 1) A run of marks (optionally spaced, never across newlines)
        #    collapses to the single strongest mark.
        result = re.sub(
            r"[.,!?;:]+(?:[ \t]*[.,!?;:]+)*",
            lambda m: _strongest("".join(c for c in m.group(0) if c in _MARKS)),
            result,
        )
        # 2) Drop a space sitting before a mark ("word ." -> "word.").
        result = re.sub(r"[ \t]+([.,!?;:])", r"\1", result)
        # 3) Exactly one space after a mark when a word follows -- but not
        #    between digits, so 3.14 and 1,234 survive.
        result = re.sub(r"(?<!\d)([.,!?;:])[ \t]*(?=[^\s\d.,!?;:])",
                        r"\1 ", result)
        return result
    except Exception:
        return text


def polish(text):
    """The whole dictation transform, in the one correct order.

    This is what the console calls on a finished Whisper transcript.
    """
    try:
        return dedup_punctuation(apply_commands(text))
    except Exception:
        return text
