"""RAM budgeting for the Whisper dictation models.

The README documents pinning ``num_ctx`` so llama3.2's KV cache fits an
8 GB laptop. Whisper needed the same discipline and never had it: the
console used to keep every model it had ever loaded, so cycling the
quality picker stacked all three tiers into whatever RAM Ollama had left
and the third load died inside MKL with ``mkl_malloc: failed to
allocate memory``.

Everything here is pure except :func:`free_ram_mb`, so the decision the
owner sees can be graded without a microphone or a model.
"""

import ctypes

# Model behind each quality tier.
TIER_MODELS = {"Fast": "base.en", "Accurate": "small.en",
               "Best": "medium.en"}

# Peak additional working set each tier costs, measured on this laptop
# by loading the model in a fresh interpreter and decoding ten seconds of
# audio, then subtracting the 53 MB interpreter baseline:
#
#   base.en    peak 373 MB   ->  320
#   small.en   peak 724 MB   ->  671
#   medium.en  peak 1468 MB  -> 1415
#
# Peak matters rather than steady state, because allocation fails at the
# peak. These are budget figures, not steady-state footprints — base.en
# settles back to about 144 MB of weights once loaded.
TIER_PEAK_MB = {"Fast": 320, "Accurate": 671, "Best": 1415}

# Rough cold-load wall time, so the console can tell the owner how long
# the wait will be instead of freezing on "Transcribing…" for 14 seconds.
TIER_LOAD_SECONDS = {"Fast": 2, "Accurate": 3, "Best": 14}

# Left free so Windows is not pushed into swapping at the moment of the
# largest allocation.
SAFETY_MB = 150

# Tiers largest first — fallback walks down this order.
TIER_ORDER = ["Best", "Accurate", "Fast"]


def tier_cost(tier):
    """RAM a tier needs at its peak, including the safety margin."""
    return TIER_PEAK_MB[tier] + SAFETY_MB


def plan_tier(free_mb, wanted):
    """Pick the largest tier at or below ``wanted`` that fits in ``free_mb``.

    Returns ``(chosen_tier, note)``. ``chosen_tier`` is ``None`` when even
    the smallest tier will not fit — that is a stop for the owner to
    decide, never a silent downgrade and never a crash.
    """
    if free_mb >= tier_cost(wanted):
        return (wanted, "fits")
    for tier in TIER_ORDER[TIER_ORDER.index(wanted) + 1:]:
        if free_mb >= tier_cost(tier):
            return (tier, f"{wanted} needs about {tier_cost(wanted)} MB "
                          f"but only {free_mb} MB is free — using {tier} "
                          f"instead")
    return (None, f"even Fast needs about {tier_cost('Fast')} MB and only "
                  f"{free_mb} MB is free — close Ollama or other apps, "
                  f"then try again")


def free_ram_mb():
    """``(total, available)`` physical RAM in MB. Windows only; impure."""
    class MemStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MemStatus()
    status.dwLength = ctypes.sizeof(MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return (int(status.ullTotalPhys // 2 ** 20),
            int(status.ullAvailPhys // 2 ** 20))
