"""strata_tools/commands.py -- the slash-command grammar.

A message beginning with ``/`` is an instruction to the console, not a
question for the model. Getting that wrong is expensive in a way that
is easy to miss: an unrecognised ``/clear`` is not an error message, it
is a prompt sent to the language model, which then answers it as though
the owner had asked something. The console appears to work and quietly
does the wrong thing.

This module owns the grammar and the formatting -- both pure, both
tested headless. Executing a command touches the pipeline and the
database, so that stays in the shell.

Lifted out of ``strata_console.py`` when the web shell became the only
shell: the Tk console had this behaviour, the web shell did not, and
retiring the Tk console without moving the grammar first would have
removed a working feature under cover of a refactor.
"""
from __future__ import annotations

# name -> one-line description, in the order /help should list them.
COMMANDS = {
    "status": "Show the current mode, model and memory depth.",
    "lexicon": "List the operator tokens and what each one does.",
    "mode": "Switch mode: /mode green | yellow | red.",
    "clear": "Clear the window and what the model recalls.",
    "help": "Show this list.",
}

# Spellings the owner may type for the same thing. /zone predates
# /mode and still works; /new is the older name for /clear. Dropping
# either would break muscle memory for no gain.
ALIASES = {
    "zone": "mode",
    "new": "clear",
}


def parse(text):
    """Read one line of input. Pure.

    Returns ``None`` when the text is an ordinary message, so the caller
    can tell "not a command" from "a command I do not know" -- the
    second must be reported, and the first must never be.

    Otherwise returns ``{"name": str, "argument": str, "known": bool}``.
    """
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None

    body = raw[1:].strip()
    if not body:
        return {"name": "", "argument": "", "known": False}

    head, _, tail = body.partition(" ")
    name = head.lower()
    name = ALIASES.get(name, name)
    return {"name": name,
            "argument": tail.strip(),
            "known": name in COMMANDS}


def unknown_message(text):
    """What to say about a command that does not exist."""
    return f"Unknown command: {(text or '').strip()}. Try /help"


def lexicon_text(glyphs):
    """The operator token lexicon as displayable text. Pure.

    ``glyphs`` is a sequence of mappings with 'glyph', 'name' and
    'function' keys -- ``strata_core.ALL_GLYPHS`` or anything shaped
    like it.
    """
    lines = ["### Operator Token Lexicon", ""]
    for g in glyphs or []:
        lines.append(f"- {g['glyph']}  **{g['name']}** — {g['function']}")
    if len(lines) == 2:
        lines.append("_No tokens are defined._")
    return "\n".join(lines)


def help_text():
    """The command list as displayable text. Pure.

    Generated from COMMANDS rather than written out, so a command added
    to the table cannot go undocumented.
    """
    lines = ["### Commands", ""]
    for name, description in COMMANDS.items():
        lines.append(f"- `/{name}` — {description}")
    extra = ", ".join(f"`/{a}`" for a in ALIASES)
    lines += ["", f"Also accepted: {extra}."]
    return "\n".join(lines)
