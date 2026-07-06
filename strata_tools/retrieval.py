"""imprint/retrieval.py — local retrieval (RAG) for Imprint's assistant.

Ported from Sentinel Forge's proven lyceum/local_context.py, minus its
study-database coupling. The local model has a tiny context window, so
instead of "reading everything" we rank the user's documents against the
question and hand the model only the top passages. All functions here
are PURE — no file or network access — so every one is unit-testable.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")


def _terms(query: str) -> list[str]:
    """Content words from the query (drop short stop-ish tokens)."""
    return [w for w in _WORD.findall((query or "").lower()) if len(w) > 2]


def score(text: str, terms: list[str]) -> int:
    """How many term occurrences appear in text. Pure."""
    if not terms:
        return 0
    t = (text or "").lower()
    return sum(t.count(w) for w in terms)


def rank_snippets(query, documents, limit: int = 5, max_chars: int = 1500):
    """Rank (source_label, text) documents against the query. Pure:
    returns the top ``limit`` matches as (source_label, snippet); zero
    scorers are dropped."""
    terms = _terms(query)
    if not terms:
        return []
    scored = []
    for src, text in documents:
        s = score(text, terms)
        if s > 0:
            scored.append((s, src, (text or "")[:max_chars]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(src, snip) for _, src, snip in scored[:limit]]


def chunk_text(text: str, chunk_chars: int = 1200, overlap: int = 150):
    """Split text into overlapping chunks for retrieval. Pure. Overlap
    keeps a sentence that straddles a boundary from being lost."""
    text = text or ""
    if not text.strip():
        return []
    if len(text) <= chunk_chars:
        return [text]
    step = max(1, chunk_chars - overlap)
    chunks = []
    for start in range(0, len(text), step):
        piece = text[start:start + chunk_chars]
        if piece.strip():
            chunks.append(piece)
        if start + chunk_chars >= len(text):
            break
    return chunks


def retrieve_from_text(query: str, text: str, limit: int = 4,
                       chunk_chars: int = 1200, overlap: int = 150,
                       max_context: int = 6000) -> str:
    """Chunk ONE document and return the passages most relevant to the
    query, joined and capped. No keyword hits -> the opening. Pure."""
    if not text:
        return ""
    chunks = chunk_text(text, chunk_chars, overlap)
    if not chunks:
        return ""
    ranked = rank_snippets(
        query,
        [(f"part {i + 1}", c) for i, c in enumerate(chunks)],
        limit=limit, max_chars=chunk_chars,
    )
    if not ranked:
        return text[:max_context]
    out, total = [], 0
    for _src, snip in ranked:
        if total >= max_context:
            break
        if total + len(snip) > max_context:
            snip = snip[:max_context - total]
        out.append(snip)
        total += len(snip)
    return "\n…\n".join(out)


def retrieve_from_index(query, documents, doc_limit: int = 3,
                        per_doc_chars: int = 1500,
                        max_context: int = 6000) -> str:
    """Search MANY documents: rank whole docs, then pull the single best
    passage from each of the top few. ``documents`` = [(name, text)].
    Pure and testable."""
    terms = _terms(query)
    if not terms or not documents:
        return ""
    scored = sorted(
        ((score(text, terms), name, text) for name, text in documents),
        key=lambda x: x[0], reverse=True,
    )
    parts, total = [], 0
    for s, name, text in scored:
        if s <= 0 or len(parts) >= doc_limit or total >= max_context:
            break
        passage = retrieve_from_text(query, text, limit=1,
                                     max_context=per_doc_chars)
        if passage:
            parts.append(f"[{name}] {passage}")
            total += len(passage)
    if not parts:
        return ""
    return ("Relevant passages from the user's own files (cite the file "
            "names when useful):\n\n" + "\n\n".join(parts))
