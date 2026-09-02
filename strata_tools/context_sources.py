"""strata_tools/context_sources.py -- deciding what the model gets to read.

The console reaches the web, the owner's OneDrive and an uploaded file;
the model never does. It is handed text that was already gathered. This
module owns the part of that job which is pure -- deciding whether a
message asked for a search, ranking the passages, and composing the
context block -- so both shells share one rule instead of one each.

That sharing is the reason this file exists. The logic shipped inside
``strata_console.py`` as UI code: untested, and about to be copied into
``strata_web.py``. Two copies of a rule is two rules, and the second
shell would have drifted from the first on its first edit. Everything
here is standard library and side-effect free, which is what lets the
suite check it without a screen.

What stays OUT of this module, deliberately: the network call, the
directory walk, and the file dialog. Those are the shells' work, and
keeping them out is what makes the rest testable.
"""
from __future__ import annotations

from .retrieval import retrieve_from_index, retrieve_from_text

# Asking Strata to search should simply work. The owner types "look this
# up" far more often than he reaches for a checkbox, and a request that
# is understood but not acted on reads as the app ignoring him.
TRIGGER_PHRASES = (
    "search the web", "search the internet", "search online",
    "web search", "look online", "look this up", "look up online",
    "check the internet", "check online", "google ", "on the internet",
    # Widened 2026-09-02 after the owner asked to search in words the
    # list did not cover and the model answered "I can't browse". These
    # are the phrasings a person actually uses; a search that was asked
    # for and not run is the app ignoring him.
    "search for", "do a search", "look up", "find out", "latest news",
    "current news", "what's the latest", "browse the web", "web browse",
)

# One upload is held in memory for the life of the session. Two million
# characters is roughly a 400-page book -- past the point where the cap
# protects the process rather than limiting the owner.
MAX_ATTACHMENT_CHARS = 2_000_000

# What the file dialog offers. Mirrors doc_index.SUPPORTED; each shell
# spells the filter in its own syntax, so the list itself lives here.
UPLOAD_EXTENSIONS = (".txt", ".md", ".docx", ".pdf", ".html", ".htm",
                     ".xlsx", ".xlsm", ".csv")

INDEXING_NOTE = ("NOTE: the user's OneDrive files are still being "
                 "indexed. Tell the user the file index is still "
                 "building and to ask again in a few minutes.")


def wants_web(user_input: str, checked: bool = False) -> bool:
    """Did this turn ask for a web search? Pure.

    True when the box is ticked, or when the message says so in plain
    English. Phrasing is matched case-insensitively on the raw text.
    """
    if checked:
        return True
    low = (user_input or "").lower()
    return any(phrase in low for phrase in TRIGGER_PHRASES)


def attachment_context(query: str, attachment) -> str:
    """The passages of the uploaded file that bear on the question.

    ``attachment`` is ``{"name": str, "text": str}`` or None. Ranking a
    long document beats truncating it: the local model's context window
    is small enough that the opening pages of a spreadsheet would crowd
    out the row the owner actually asked about.
    """
    if not attachment:
        return ""
    body = retrieve_from_text(query, attachment.get("text", "") or "")
    if not body:
        return ""
    name = attachment.get("name", "file")
    return f"From the attached file '{name}':\n" + body


def onedrive_context(query: str, index) -> str:
    """Passages from the owner's indexed OneDrive files.

    ``index`` is [(name, text), ...] when ready, ``[]`` when the walk
    found nothing, and ``None`` while it is still building. The three
    are genuinely different answers and the middle one must not be
    reported as the last: silence during a slow first index is the
    failure that makes an owner think the feature is broken.
    """
    if index is None:
        return INDEXING_NOTE
    if not index:
        return ""
    return retrieve_from_index(query, index)


def gather(query: str, attachment=None, onedrive_index=None,
           use_onedrive: bool = False, web_text: str = "") -> str:
    """Compose one turn's grounding text. Pure.

    ``web_text`` arrives already fetched -- this module does not touch
    the network. Sources are joined in the order the owner would rank
    them: the file he just handed over, then his own documents, then
    the open web. Empty sources vanish rather than announcing
    themselves, so an unticked box costs the context window nothing.
    """
    parts = [attachment_context(query, attachment)]
    if use_onedrive:
        parts.append(onedrive_context(query, onedrive_index))
    parts.append(web_text or "")
    return "\n\n".join(p for p in parts if p)


def attachment_label(name: str, n_chars: int) -> str:
    """The 'currently attached' line. Same words in both shells."""
    kb = max(1, int(n_chars) // 1024)
    return f"📎 {name} ({kb} KB) — attached; click here to remove"


def attachment_greeting(name: str) -> str:
    """What the console says when a file lands. Same words in both."""
    return (f"📎 Attached {name}. Ask me about it — I'll read the "
            f"relevant parts. It stays attached until you remove it.")


def unreadable_note(name: str) -> str:
    """Honest refusal when extraction produced nothing."""
    return f"📎 Couldn't read {name} — unsupported format or empty file."


MODEL_LOADING_LABEL = ("loading the local model — first message, "
                       "about 20 seconds")


def busy_label(use_web: bool, use_onedrive: bool, has_attachment: bool,
               model_loading: bool = False) -> str:
    """Status text while the turn runs. Pure.

    Searching, loading and thinking take visibly different amounts of
    time, and saying which one is happening is the difference between a
    wait and a hang.

    ``model_loading`` wins over the others because it is the longest by
    an order of magnitude: measured at ~20s cold against ~3s warm on
    this laptop. A twenty-second wait labelled "thinking" reads as a
    broken application; the same wait labelled with its cause and its
    length reads as a machine doing work.
    """
    if model_loading:
        return MODEL_LOADING_LABEL + "…"
    if use_web or use_onedrive or has_attachment:
        return "🔎 searching…"
    return "thinking (local model)…"
