#!/usr/bin/env python3
"""Strata Console — the web shell. Same engine, different front end.

A second shell over ``strata_core``, rendered as HTML and CSS inside a
native window (pywebview on Edge WebView2, which Windows already has).
Nothing about the engine changes, and ``strata_console.py`` is untouched
and still shipped: this exists to be compared against, not to replace it
before it has earned the job.

**Still local-first.** No server is exposed and no port is opened to the
network — pywebview loads the page from disk and talks to Python through
its own bridge. The model is the same Ollama daemon on loopback.

Why it is worth trying, in one line each — every item is something the
Tk shell needed hand-written Python to achieve, measured across the
accessibility work of 2026-09-01/02:

  * keyboard operation      a ``<button>`` is focusable; no module needed
  * visible focus           ``:focus-visible``, built in
  * text resize             one CSS variable instead of walking widgets
  * nothing silently hidden CSS overflows and scrolls; it never stops
                            drawing a control the way Tk's packer does
  * reading width           ``max-width: 65ch``, the thing measured at 53
                            characters and left unfixed in the Tk shell
  * markdown                rendered, rather than stripped before speech

What this shell does NOT do is make the assistant smarter. Same model,
same prompts, same answers — this is about whether they can be read.

Run it:  py -3 strata_web.py
"""

import json
import os
import threading

import webview

from strata_core import ALL_GLYPHS, StrataPipeline
from strata_tools import dictation, session, speech

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "web", "index.html")


class Api:
    """The bridge the page calls. One method per thing the UI can ask.

    Every method returns a plain dict so the boundary stays JSON and the
    page never holds a Python object. Errors come back as data rather
    than exceptions, because an exception across this bridge surfaces in
    the page as a silent rejected promise -- the web equivalent of a
    control that does nothing.
    """

    def __init__(self):
        self.pipeline = StrataPipeline()
        self._lock = threading.Lock()
        self._rec_stream = None
        self._rec_frames = []
        self._whisper_model = None
        self._whisper_tier = None

    # --- state ------------------------------------------------------------
    def bootstrap(self):
        """Everything the page needs on load."""
        db = self.pipeline.db
        return {
            "status": self.pipeline.get_status(),
            "zone": self.pipeline.current_zone,
            "brain": bool(self.pipeline.brain.available),
            "model": getattr(self.pipeline.brain, "model", ""),
            "error": getattr(self.pipeline.brain, "last_error", "") or "",
            "fontFamily": db.get_state("web_font", "system"),
            "fontSize": int(db.get_state("web_font_size", "17") or 17),
            "autoread": db.get_state("autoread", "0") == "1",
            "glyphs": [dict(g) for g in ALL_GLYPHS],
        }

    def set_pref(self, key, value):
        allowed = {"web_font", "web_font_size", "autoread"}
        if key not in allowed:
            return {"ok": False, "error": f"unknown preference {key!r}"}
        self.pipeline.db.set_state(key, str(value))
        return {"ok": True}

    # --- conversation -----------------------------------------------------
    def send(self, text):
        """Run one message through the engine. Blocking; called off the UI."""
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "empty message"}
        with self._lock:
            try:
                out = self.pipeline.process_input(text)
            except Exception as e:
                return {"ok": False,
                        "error": f"{type(e).__name__}: {e}"}
        reply = out.get("response") or " ".join(
            str(out.get(k, "")) for k in ("summary", "description", "comments")
            if out.get(k))
        return {
            "ok": True,
            "reply": reply,
            "closing": out.get("closing", ""),
            "status": self.pipeline.get_status(),
            "speakable": speech.speakable(reply),
        }

    def change_zone(self, zone):
        result = self.pipeline.change_zone(zone)
        return {"ok": True, "message": result,
                "zone": self.pipeline.current_zone,
                "status": self.pipeline.get_status()}

    def clear(self):
        """Same contract as the Tk shell: archive, never delete."""
        cleared = self.pipeline.db.raise_memory_floor()
        archived = self.pipeline.db.archived_thread_count()
        return {"ok": True,
                "message": session.clear_report(cleared, archived),
                "status": self.pipeline.get_status()}

    # --- voice ------------------------------------------------------------
    def polish_dictation(self, raw):
        """Spoken punctuation into characters -- the shared kernel."""
        return {"ok": True, "text": dictation.polish(raw or "")}

    def speakable(self, raw):
        """Markdown out, numbers spelled out, for the page's own TTS."""
        return {"ok": True, "text": speech.speakable(raw or "")}

    # --- dictation --------------------------------------------------------
    #
    # Capture and transcription stay in Python: the microphone work, the
    # Whisper RAM budgeting and the interpreter rule were all hard-won
    # (FB-002), and re-solving them in JavaScript to save a bridge call
    # would be throwing away the most expensive lessons in the project.
    # The browser is asked only to draw the button.

    def start_recording(self):
        if self._rec_stream is not None:
            return {"ok": False, "error": "already recording"}
        try:
            import sounddevice as sd
        except Exception as e:
            from strata_tools import interpreter as interp
            executable, missing = interp.current_report()
            return {"ok": False,
                    "error": interp.explain_missing(executable, missing or
                                                    ["sounddevice"])}
        self._rec_frames = []
        try:
            info = sd.query_devices(kind="input")
            self._rec_device = str(info["name"]).strip()
        except Exception:
            self._rec_device = "the microphone"
        try:
            self._rec_stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="float32",
                callback=lambda indata, frames, t, status:
                    self._rec_frames.append(indata.copy()))
            self._rec_stream.start()
        except Exception as e:
            self._rec_stream = None
            return {"ok": False,
                    "error": f"Could not open the microphone: {e}"}
        return {"ok": True, "device": self._rec_device}

    def stop_recording(self, tier="Fast"):
        """Stop, transcribe, and return punctuated text."""
        stream, self._rec_stream = self._rec_stream, None
        if stream is None:
            return {"ok": False, "error": "not recording"}
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        frames, self._rec_frames = self._rec_frames, []
        if not frames:
            return {"ok": False, "error": "nothing was captured"}
        try:
            import gc

            import numpy as np

            from strata_tools import voice_budget as vb
            audio = np.concatenate(frames)[:, 0]
            level = float(np.sqrt((audio ** 2).mean()))

            wanted = tier if tier in vb.TIER_MODELS else "Fast"
            _total, free = vb.free_ram_mb()
            chosen, note = vb.plan_tier(free, wanted)
            if chosen is None:
                return {"ok": False, "error": note}
            if self._whisper_tier != chosen:
                self._whisper_model = None
                self._whisper_tier = None
                gc.collect()
                from faster_whisper import WhisperModel
                try:
                    self._whisper_model = WhisperModel(
                        vb.TIER_MODELS[chosen], device="cpu",
                        compute_type="int8")
                except (MemoryError, RuntimeError) as e:
                    self._whisper_model = None
                    gc.collect()
                    return {"ok": False,
                            "error": f"The {chosen} voice model would not "
                                     f"fit in RAM ({free} MB free). Close "
                                     f"Ollama, or pick Fast. "
                                     f"[{type(e).__name__}]"}
                self._whisper_tier = chosen
            segments, _info = self._whisper_model.transcribe(audio,
                                                             beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
            text = dictation.polish(text)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if not text:
            if level <= 0.002:
                return {"ok": False,
                        "error": f"{self._rec_device} produced silence "
                                 f"(level {level:.5f}). That is the "
                                 f"microphone or its Windows input level."}
            return {"ok": False,
                    "error": "Sound came through but no words were found."}
        return {"ok": True, "text": text, "note": note if note != "fits"
                else ""}


def main():
    if not os.path.exists(INDEX):
        raise SystemExit(f"missing {INDEX}")
    api = Api()
    # Sized as a fraction of the screen rather than a fixed pixel count:
    # the Tk shell's oldest defect was a hardcoded size that did not fit,
    # and there is no reason to import that mistake into a new shell.
    window = webview.create_window(
        "Strata Console — web shell",
        INDEX,
        js_api=api,
        width=1000,
        height=680,
        min_size=(640, 460),
        background_color="#12161A",
    )
    # Edge WebView2 explicitly: it is present on this machine and the
    # alternative backends are not, so failing loudly beats falling back
    # to something untested.
    webview.start(gui="edgechromium", debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
