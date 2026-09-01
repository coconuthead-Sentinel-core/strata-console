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
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from strata_tools.voice_budget import (TIER_MODELS,  # noqa: E402
                                       TIER_PEAK_MB, free_ram_mb, plan_tier,
                                       tier_cost)

# Capture thresholds. A quiet room on this laptop floors near 0.0003 RMS;
# a spoken sentence measured 0.076 peak / 0.0076 mean at 16 kHz.
SILENCE_FLOOR = 0.002
SPEECH_FLOOR = 0.01

def verdict(peak_rms):
    """Classify a capture by its loudest RMS window. Pure."""
    if peak_rms <= SILENCE_FLOOR:
        return ("DEAD", "The device produced silence. This is the "
                        "microphone or its Windows level, not you.")
    if peak_rms < SPEECH_FLOOR:
        return ("WEAK", "Signal is present but too quiet for Whisper. "
                        "Raise the input level in Windows sound settings.")
    return ("GOOD", "The device is carrying speech.")


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
    tier, note = plan_tier(free, wanted)
    print(f"      requested {wanted} (peak ~{TIER_PEAK_MB[wanted]} MB, "
          f"budget {tier_cost(wanted)} MB)")
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


def launcher_choice(vbs_path):
    """Ask launch_strata.vbs which interpreter a double-click would use.

    Impure and best-effort: if cscript is unavailable the bench still
    runs, it just cannot compare the two paths for the owner.
    """
    import subprocess
    if not os.path.exists(vbs_path):
        return "unknown (launch_strata.vbs not found)"
    try:
        out = subprocess.run(["cscript", "//nologo", vbs_path, "/which"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or "unknown (no answer from launcher)"
    except Exception as e:
        return f"unknown ({type(e).__name__}: {e})"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", type=int, default=None)
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--tier", choices=list(TIER_MODELS), default="Fast")
    args = ap.parse_args(argv)
    # Stage 0 exists because stages 1-3 once all passed while the console
    # could not record a thing. The bench was run with "py -3" and the
    # console was launched with the Store Python -- two different
    # interpreters, only one of which had the voice packages. A bench
    # that does not name its interpreter is not checking the owner's path.
    from strata_tools import interpreter as interp
    executable, missing = interp.current_report()
    print(f"[0/3] interpreter  {executable}")
    launcher = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "launch_strata.vbs")
    print(f"      the console launches: {launcher_choice(launcher)}")
    if missing:
        indent = chr(10) + "      "
        print("      " + interp.explain_missing(
            executable, missing).replace(chr(10), indent))
        return 3
    print("      voice packages present: "
          + ", ".join(interp.VOICE_DEPS))
    import numpy as np
    import sounddevice as sd
    print()
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
