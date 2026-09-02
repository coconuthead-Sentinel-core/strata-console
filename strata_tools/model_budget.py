"""strata_tools/model_budget.py -- can the language model afford to run?

The voice model has had a RAM budget since FB-002: measure free memory,
plan a tier, and STOP with a reason rather than die inside MKL. The
language model had none, and it is the bigger tenant. Measured on the
owner's 8 GB laptop on 2026-09-02:

    free RAM 978 MB  -> a reply takes  2.9s
    free RAM 475 MB  -> the same reply takes 103.5s   (3.3 GB in pagefile)

Nothing in the code changed between those two numbers. The machine was
simply crowded, and the app said nothing about it -- it showed the same
"thinking..." either way, so a hardware condition presented as a broken
application. This module decides two things, both pure:

  * should the model be warmed at startup? Warming a 2.3 GB model into
    475 MB of free RAM does not make the first reply faster; it makes the
    whole machine freeze while the page is still trying to draw.
  * what should the owner be TOLD, in numbers he can act on.

Model size is passed in rather than assumed, because Ollama reports it
and a different model would have a different number.
"""
from __future__ import annotations

# Ollama needs the model file plus a KV cache plus working room. Measured
# resident size for llama3.2:3b is 2,325 MB; below this much FREE RAM the
# load spills to the pagefile and every token pays a disk read.
SAFETY_MB = 300

# Below this, do not even try to warm at startup -- the load itself is
# what freezes the machine. The owner gets a note instead.
LIGHTER_MODEL = "llama3.2:1b"


def model_need_mb(model_size_bytes):
    """RAM the model wants resident, including working margin. Pure."""
    try:
        size_mb = int(int(model_size_bytes) / (1024 * 1024))
    except (TypeError, ValueError):
        size_mb = 0
    return size_mb + SAFETY_MB


def plan(free_mb, model_size_bytes, model_name=""):
    """Decide whether to warm the model, and what to say. Pure.

    Returns ``{"warm": bool, "starved": bool, "note": str}``.

    ``starved`` is the honest label for "this will be slow and it is the
    machine, not the software." The note carries the two numbers the
    owner needs -- what is free and what is wanted -- and the two things
    he can actually do about it.
    """
    need = model_need_mb(model_size_bytes)
    try:
        free = int(free_mb)
    except (TypeError, ValueError):
        free = 0

    if need <= SAFETY_MB:
        # No size known: cannot budget, do not pretend to.
        return {"warm": True, "starved": False, "note": ""}

    if free >= need:
        return {"warm": True, "starved": False, "note": ""}

    short = need - free
    name = model_name or "the local model"
    return {
        "warm": False,
        "starved": True,
        "note": (f"⚠ Low memory: {free:,} MB free, and {name} wants about "
                 f"{need:,} MB — {short:,} MB short. Replies will be slow "
                 f"(measured: 3 s with room, over 100 s without). Close "
                 f"other programs, or switch to the lighter "
                 f"{LIGHTER_MODEL}."),
    }


def status_fragment(free_mb):
    """The RAM figure for the status line. Pure.

    Always shown, not only when low: a number the owner has seen every
    day is a number he can read at a glance when it drops.
    """
    try:
        return f"RAM {int(free_mb):,} MB free"
    except (TypeError, ValueError):
        return "RAM ?"
