"""Bench check for the Strata Console voice path.

Runs the same three stages the console's microphone button runs, and
reports which one actually fails:

    stage 1  capture   - does the microphone deliver signal?
    stage 2  budget    - does the chosen Whisper tier fit in free RAM?
    stage 3  transcribe - does Whisper turn the capture into words?

Usage:
    py -3 tools/voice_check.py                  # meter the default device
    py -3 tools/voice_check.py --tier Best      # check a specific tier
    py -3 tools/voice_check.py --device 6 --seconds 10
"""

import argparse
import ctypes
import sys
import time

# Capture thresholds. A quiet room on this laptop floors near 0.0003 RMS;
# a spoken sentence measured 0.076 peak / 0.0076 mean at 16 kHz.
SILENCE_FLOOR = 0.002
SPEECH_FLOOR = 0.01

# Resident weight cost per tier, measured from the cached model files.
# base.en 141 MB, small.en 464 MB, medium.en 1460 MB on disk.
TIER_MODELS = {"Fast": "base.en", "Accurate": "small.en",
               "Best": "medium.en"}
TIER_COST_MB = {"Fast": 141, "Accurate": 464, "Best": 1460}
# Whisper needs room for activations and the decode beam on top of the
# weights, and Ollama is usually holding llama3.2:3b at the same time.
HEADROOM_MB = 400


def verdict(peak_rms):
    """Classify a capture by its loudest RMS window. Pure."""
    if peak_rms <= SILENCE_FLOOR:
        return ("DEAD", "The device produced silence. This is the "
                        "microphone or its Windows level, not you.")
    if peak_rms < SPEECH_FLOOR:
        return ("WEAK", "Signal is present but too quiet for Whisper. "
                        "Raise the input level in Windows sound settings.")
    return ("GOOD", "The device is carrying speech.")


def tier_plan(free_mb, wanted):
    """Pick the largest tier that fits in free_mb. Pure.

    Returns (chosen_tier, note). chosen_tier is None when even the
    smallest tier will not fit, which is a stop, not a fallback.
    """
    order = ["Best", "Accurate", "Fast"]
    need = TIER_COST_MB[wanted] + HEADROOM_MB
    if free_mb >= need:
        return (wanted, "fits")
    for tier in order[order.index(wanted) + 1:]:
        if free_mb >= TIER_COST_MB[tier] + HEADROOM_MB:
            return (tier, f"{wanted} needs ~{need} MB but only "
                          f"{free_mb} MB is free — falling back to {tier}")
    return (None, f"even Fast needs ~{TIER_COST_MB['Fast'] + HEADROOM_MB} "
                  f"MB and only {free_mb} MB is free — close Ollama or "
                  f"other apps first")


def free_ram_mb():
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
    m = MemStatus()
    m.dwLength = ctypes.sizeof(MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return int(m.ullTotalPhys // 2 ** 20), int(m.ullAvailPhys // 2 ** 20)


def list_devices(sd):
    print("Input devices:")
    default_in = sd.default.device[0]
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            host = sd.query_hostapis()[d["hostapi"]]["name"]
            mark = "  <- system default" if i == default_in else ""
            print(f"  [{i:>2}] {d['name'].strip()[:44]:<44} "
                  f"{host:<20} {d['max_input_channels']}ch{mark}")
    print()


def stage_capture(sd, np, device, seconds):
    info = sd.query_devices(device if device is not None
                            else sd.default.device[0])
    name = info["name"].strip()
    print(f"[1/3] capture  device: {name}")
    print(f"      Speak a full sentence now ({seconds}s).")
    frames = []
    try:
        stream = sd.InputStream(device=device, samplerate=16000, channels=1,
                                dtype="float32",
                                callback=lambda i, f, t, s:
                                    frames.append(i.copy()))
    except Exception as e:
        print(f"      FAILED to open {name}: {type(e).__name__}: {e}")
        return None, name
    peak = 0.0
    with stream:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            time.sleep(0.1)
            if not frames:
                continue
            window = np.concatenate(frames[-5:])[:, 0]
            rms = float(np.sqrt((window ** 2).mean()))
            peak = max(peak, rms)
            bars = "#" * min(40, int(rms * 400))
            sys.stdout.write(f"\r      |{bars:<40}| rms {rms:.5f} "
                             f"peak {peak:.5f}")
            sys.stdout.flush()
    print()
    if not frames:
        print("      No frames arrived. Treat this as a dead device.")
        return None, name
    label, why = verdict(peak)
    print(f"      {label}: {why}")
    return (np.concatenate(frames)[:, 0] if label != "DEAD" else None), name


def stage_budget(wanted):
    total, free = free_ram_mb()
    print(f"\n[2/3] budget   {total} MB total, {free} MB free")
    tier, note = tier_plan(free, wanted)
    print(f"      requested {wanted} (~{TIER_COST_MB[wanted]} MB weights)")
    print(f"      {note}")
    return tier


def stage_transcribe(audio, tier):
    print(f"\n[3/3] transcribe  tier {tier} -> {TIER_MODELS[tier]}")
    t0 = time.monotonic()
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(TIER_MODELS[tier], device="cpu",
                             compute_type="int8")
    except Exception as e:
        print(f"      MODEL LOAD FAILED: {type(e).__name__}: {e}")
        print("      This is the RAM ceiling, not the microphone. "
              "Close Ollama or pick a smaller tier.")
        return 1
    print(f"      model loaded in {time.monotonic() - t0:.1f}s "
          f"(the console shows no progress during this wait)")
    t0 = time.monotonic()
    segments, _ = model.transcribe(audio, beam_size=1)
    text = " ".join(s.text.strip() for s in segments).strip()
    print(f"      transcribed in {time.monotonic() - t0:.1f}s")
    if not text:
        print("      Sound was present but no words were recognised.")
        return 1
    print(f"      heard: {text!r}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--tier", choices=list(TIER_MODELS), default="Fast")
    args = ap.parse_args(argv)
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as e:
        print(f"Missing a dependency: {e}")
        print("Install with: py -3 -m pip install sounddevice numpy")
        return 3
    list_devices(sd)
    audio, name = stage_capture(sd, np, args.device, args.seconds)
    tier = stage_budget(args.tier)
    if audio is None:
        print(f"\nStopped at capture: {name} carried no usable signal.")
        return 1
    if tier is None:
        print("\nStopped at budget: no tier fits in free RAM.")
        return 1
    return stage_transcribe(audio, tier)


if __name__ == "__main__":
    raise SystemExit(main())
