#!/usr/bin/env python3
"""
Strata Console — a local-first NLP inference pipeline (desktop client).

Text flows through five processing stages (input classification, routing,
context management, style conditioning, response synthesis) and is answered by
a LOCAL language model via Ollama — no cloud, no API key, no internet. If the
local model isn't available, the pipeline falls back to a deterministic
template engine so the app always responds.

Author: Shannon Brian Kelly. Built with AI assistance. Applied systems-
engineering project — not novel research.
"""

import os
import sqlite3
import threading
import tkinter.font as tkfont
import customtkinter as ctk
from datetime import datetime

# Dyslexia-friendly reading fonts, best-first (ported from Sentinel Forge).
# OpenDyslexic / Atkinson Hyperlegible are purpose-built for readability;
# Comic Sans MS and Verdana are repeatedly cited in dyslexia research.
DYSLEXIA_FONT_PREFS = [
    "OpenDyslexic", "OpenDyslexic3", "Atkinson Hyperlegible",
    "Comic Sans MS", "Verdana", "Tahoma", "Segoe UI", "Arial",
]

# Local LLM via Ollama — talks ONLY to the local daemon (loopback). Optional:
# if the package or daemon is missing, the app runs in template mode instead.
try:
    import ollama
    _OLLAMA_IMPORTED = True
except Exception:
    _OLLAMA_IMPORTED = False

# Small model chosen to fit a CPU-only laptop with ~8 GB RAM. Swap freely.
LLM_MODEL = os.environ.get("STRATA_MODEL", "llama3.2:3b")

# Local DB file lives next to this script — 100% offline, no cloud.
# (Filename kept for data continuity with earlier installs.)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quantum_nexus_forge.db")

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATOR TOKEN LEXICON
# A small controlled vocabulary: optional single-character tokens a user can
# include in a message to hint at the operation they want. Detected by the input
# classifier and passed to the model as intent hints. (Internal lookup variables
# retain the legacy "glyph" naming.)
# ═══════════════════════════════════════════════════════════════════════════════

GLYPH_CODEX = {
    "core": [
        {"glyph": "🔺", "name": "TRANSFORM",   "function": "Transform input"},
        {"glyph": "🧊", "name": "STABILIZE",   "function": "Logic / structure"},
        {"glyph": "🔸", "name": "PROCESS",     "function": "Process"},
        {"glyph": "⭕", "name": "SENTIMENT",   "function": "Tone / sentiment"},
        {"glyph": "💠", "name": "REFLECT",     "function": "Self-reference"},
        {"glyph": "🌀", "name": "EXPAND",      "function": "Iterate / grow"},
        {"glyph": "🔮", "name": "MAP",         "function": "Concept mapping"},
        {"glyph": "🥥", "name": "AUTHOR",      "function": "Author intent"},
        {"glyph": "🤝", "name": "COLLABORATE", "function": "Collaboration"},
    ]
}

ALL_GLYPHS = []
for category in GLYPH_CODEX.values():
    ALL_GLYPHS.extend(category)

# Fast lookups for token detection in the input classifier
GLYPH_CHARS = {g["glyph"] for g in ALL_GLYPHS}
GLYPH_LOOKUP = {g["glyph"]: g for g in ALL_GLYPHS}

# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL PERSISTENCE (SQLite — offline, single-file)
# ═══════════════════════════════════════════════════════════════════════════════

class StrataDB:
    """Local SQLite store for context entries, saved nodes, and system state."""

    def __init__(self, path=DB_PATH):
        self.path = path
        # check_same_thread=False: customtkinter callbacks may touch the DB
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_threads (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                input     TEXT NOT NULL,
                zone      TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS forged_nodes (
                name    TEXT PRIMARY KEY,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS system_state (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        self.conn.commit()

    # --- context entries ------------------------------------------------------
    def add_thread(self, timestamp, user_input, zone):
        self.conn.execute(
            "INSERT INTO memory_threads (timestamp, input, zone) VALUES (?, ?, ?)",
            (timestamp, user_input[:100], zone),
        )
        self.conn.commit()

    def recent_threads(self, limit=3):
        rows = self.conn.execute(
            "SELECT timestamp, input, zone FROM memory_threads ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]  # oldest → newest

    def thread_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM memory_threads").fetchone()[0]

    # --- saved nodes ----------------------------------------------------------
    def save_node(self, name, payload):
        self.conn.execute(
            "INSERT OR REPLACE INTO forged_nodes (name, payload) VALUES (?, ?)",
            (name, payload),
        )
        self.conn.commit()

    def all_nodes(self):
        rows = self.conn.execute("SELECT name, payload FROM forged_nodes").fetchall()
        return {r["name"]: r["payload"] for r in rows}

    # --- system state ---------------------------------------------------------
    def set_state(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_state(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM system_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE STAGES
# ═══════════════════════════════════════════════════════════════════════════════

class InputNode:
    """Input classifier: detects intent, operator tokens, and command structure."""

    def process(self, user_input):
        text = user_input.strip()
        glyphs = [g for g in GLYPH_CHARS if g in text]

        # Strip tokens to see how much plain text is left underneath
        residual = text
        for g in glyphs:
            residual = residual.replace(g, "")
        residual = residual.strip()

        is_command = text.startswith("/")
        # "token-heavy" = mostly tokens, little or no surrounding prose
        glyph_heavy = len(glyphs) >= 1 and len(residual) <= max(2, len(glyphs) * 2)

        lowered = text.lower()
        if is_command:
            intent = "command"
        elif glyph_heavy:
            intent = "symbolic"
        elif "?" in text or lowered.startswith(
            ("what", "how", "why", "who", "when", "where", "can ", "is ", "are ", "do ", "does ")
        ):
            intent = "query"
        else:
            intent = "reflection"

        return {
            "text": user_input,
            "intent": intent,
            "is_command": is_command,
            "glyphs": glyphs,
            "glyph_meanings": [GLYPH_LOOKUP[g] for g in glyphs if g in GLYPH_LOOKUP],
            "glyph_heavy": glyph_heavy,
            "residual": residual,
        }

class RouterNode:
    """Dispatcher: chooses a processing path from the detected intent and tokens."""

    def route(self, input_data):
        intent = input_data.get("intent", "reflection")
        if intent == "command":
            path = "command"
        elif intent == "symbolic" or input_data.get("glyphs"):
            path = "symbolic"      # operator-token path
        elif intent == "query":
            path = "synthesis"     # analytical path
        else:
            path = "reflective"
        return {"data": input_data, "route": path}

class MemoryNode:
    """Context manager: stores and retrieves recent conversational context via SQLite."""

    def __init__(self, db):
        self.db = db

    def retrieve(self, routed_data):
        recent = self.db.recent_threads(3)
        if recent:
            lines = []
            for t in recent:
                snippet = t.get("input", "")[:40]
                lines.append(f"[{t.get('zone', '?')}] {snippet}")
            context = "Recent context → " + " | ".join(lines)
        else:
            context = "No prior context — this is the opening of the session."
        return {"data": routed_data, "context": context, "recent": list(recent)}

class PersonaNode:
    """Style-conditioning stage: sets tone/voice from the active operating mode."""

    TONES = {
        "GREEN":  {"label": "active",     "voice": "energized and forward-driving"},
        "YELLOW": {"label": "analytical", "voice": "measured, pattern-focused, diagnostic"},
        "RED":    {"label": "grounded",   "voice": "slow, careful and calm"},
    }

    def adjust(self, memory_data):
        # Mode is threaded into the original input_data by the pipeline
        try:
            zone = memory_data["data"]["data"]["zone"]
        except Exception:
            zone = "GREEN"
        tone = self.TONES.get(zone, self.TONES["GREEN"])
        return {"data": memory_data, "tone": tone, "zone": zone}

class OutputSynthNode:
    """Response synthesizer: builds a structured four-part fallback response."""

    ROUTE_DESC = {
        "symbolic":   "Processed via the operator-token path (tokens detected).",
        "synthesis":  "Processed via the analytical path (query parsed for intent).",
        "reflective": "Processed via the default reflective path.",
        "command":    "Routed to the command handler.",
    }

    CLOSING_BY_ZONE = {
        "GREEN":  "[mode: active]",
        "YELLOW": "[mode: analytical]",
        "RED":    "[mode: archival]",
    }

    def synthesize(self, persona_data, current_zone):
        try:
            memory_data = persona_data["data"]
            routed = memory_data["data"]
            input_data = routed["data"]
            text = input_data.get("text", "")
            intent = input_data.get("intent", "reflection")
            glyphs = input_data.get("glyphs", [])
            glyph_meanings = input_data.get("glyph_meanings", [])
            route = routed.get("route", "reflective")
            context = memory_data.get("context", "")
            tone = persona_data.get("tone", {})
        except Exception:
            text, intent, glyphs, glyph_meanings = str(persona_data), "reflection", [], []
            route, context, tone = "reflective", "", {}

        voice = tone.get("voice", "clear")
        label = tone.get("label", "active")
        snippet = text.strip()[:80]

        # SUMMARY — what came in
        if glyphs:
            summary = (
                f"Received {len(glyphs)} operator token(s) {' '.join(glyphs)}"
                f" + '{snippet}' | Intent: {intent} | Mode: {current_zone}"
            )
        else:
            summary = f"Input: '{snippet}' | Intent: {intent} | Route: {route} | Mode: {current_zone}"

        # DESCRIPTION — how it was processed (route-specific)
        description = self.ROUTE_DESC.get(route, self.ROUTE_DESC["reflective"])
        if glyph_meanings:
            fns = ", ".join(f"{m['glyph']}={m['function']}" for m in glyph_meanings)
            description += f" Active tokens: {fns}."

        # COMMENTS — reflect tone + recent context
        comments = f"[{label} tone — {voice}] " + (context or "No prior context.")

        # CLOSING — mode marker
        closing = self.CLOSING_BY_ZONE.get(current_zone, "[mode: active]")

        return {
            "summary": summary,
            "description": description,
            "comments": comments,
            "closing": closing,
        }

# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL LLM BACKEND (Ollama — offline, no cloud, no API key)
# ═══════════════════════════════════════════════════════════════════════════════

class LLMBrain:
    """Wraps a LOCAL Ollama model. 100% offline: the only network touch is the
    loopback connection to the Ollama daemon running on this machine.

    .available is False (and the app falls back to template mode) when the
    package isn't installed, the daemon isn't running, or the model isn't pulled.
    """

    # Operating mode → sampling temperature: bolder when active, careful when analytical.
    ZONE_TEMP = {"GREEN": 0.8, "YELLOW": 0.45, "RED": 0.3}

    def __init__(self, model=LLM_MODEL):
        self.model = model
        self.available = False
        self.last_error = None
        # Context window MUST stay small on low-RAM machines: the KV cache scales
        # with num_ctx, and llama3.2's 128K default tries to allocate ~15 GB and
        # OOMs on an 8 GB laptop. 2048 keeps the cache to a few hundred MB.
        self.num_ctx = int(os.environ.get("STRATA_NUM_CTX", "2048"))
        # Keep the model resident between messages so only the FIRST reply pays
        # the ~90s cold-load; later replies stay warm.
        self.keep_alive = os.environ.get("STRATA_KEEP_ALIVE", "10m")
        if not _OLLAMA_IMPORTED:
            self.last_error = "ollama package not installed"
            return
        try:
            names = self._installed_models()
            self.available = any(self.model.split(":")[0] in n for n in names)
            if not self.available:
                self.last_error = f"model '{self.model}' not pulled (run: ollama pull {self.model})"
        except Exception as e:
            self.last_error = f"Ollama daemon not reachable: {type(e).__name__}"

    @staticmethod
    def _installed_models():
        """Return installed model names, tolerant of ollama lib version differences."""
        data = ollama.list()
        models = getattr(data, "models", None)
        if models is None and isinstance(data, dict):
            models = data.get("models", [])
        names = []
        for m in (models or []):
            n = getattr(m, "model", None)
            if n is None and isinstance(m, dict):
                n = m.get("model") or m.get("name")
            if n:
                names.append(n)
        return names

    def _system_prompt(self, zone, tone, glyph_meanings, context):
        voice = tone.get("voice", "clear and direct")
        token_line = ""
        if glyph_meanings:
            ops = ", ".join(f"{m['glyph']} ({m['function']})" for m in glyph_meanings)
            token_line = f"\nThe user included these operator tokens; factor in their intent: {ops}."
        return (
            "You are Strata, a local language assistant running fully offline on the "
            "user's own computer. You help with conversation, planning, writing, and code.\n"
            f"Operating mode: {zone} — respond in a manner that is {voice}.{token_line}\n"
            f"Recent context — {context}\n"
            "Be accurate and concise. If something isn't in the context or you are "
            "unsure, say so plainly instead of inventing details. When asked for code, "
            "return clean, working code."
        )

    def respond(self, user_input, zone, tone, glyph_meanings, context):
        """Return the model's reply, or None if the backend is unavailable / errors out."""
        if not self.available:
            return None
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt(zone, tone, glyph_meanings, context)},
                    {"role": "user", "content": user_input},
                ],
                keep_alive=self.keep_alive,
                options={
                    "temperature": self.ZONE_TEMP.get(zone, 0.7),
                    "num_predict": 512,   # cap output so CPU generation stays responsive
                    "num_ctx": self.num_ctx,  # bound the KV cache to fit RAM (see __init__)
                },
            )
            return resp["message"]["content"].strip()
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return None


class StrataPipeline:
    """Orchestrates the five stages and the local LLM backend."""

    def __init__(self, db=None):
        self.db = db or StrataDB()
        # Restore last operating mode from disk if present, else default GREEN
        self.current_zone = self.db.get_state("current_zone", "GREEN")
        self.forged_nodes = self.db.all_nodes()

        self.input_node = InputNode()
        self.router_node = RouterNode()
        self.memory_node = MemoryNode(self.db)
        self.persona_node = PersonaNode()
        self.output_node = OutputSynthNode()
        self.brain = LLMBrain()  # local LLM; falls back to template mode if unavailable

    def process_input(self, user_input, extra_context=""):
        input_data = self.input_node.process(user_input)
        input_data["zone"] = self.current_zone  # thread mode so PersonaNode can style by it
        routed = self.router_node.route(input_data)
        memory_data = self.memory_node.retrieve(routed)
        persona = self.persona_node.adjust(memory_data)
        output = self.output_node.synthesize(persona, self.current_zone)

        # Primary path: hand the full context to the local LLM. The template
        # output above remains as the structured fallback / telemetry.
        context = memory_data.get("context", "")
        if extra_context:
            # App-retrieved grounding (web results, OneDrive passages, an
            # attached document) rides alongside the conversation memory.
            context = (context + "\n\nAdditional context (web/files):\n"
                       + extra_context[:6000])
        reply = self.brain.respond(
            user_input,
            self.current_zone,
            persona.get("tone", {}),
            input_data.get("glyph_meanings", []),
            context,
        )
        output["response"] = reply          # None when running in template mode
        output["brain"] = self.brain.available

        # Persist this interaction as a context entry
        self.db.add_thread(datetime.now().isoformat(), user_input, self.current_zone)
        return output

    def change_zone(self, new_zone):
        if new_zone.upper() in ["GREEN", "YELLOW", "RED"]:
            self.current_zone = new_zone.upper()
            self.db.set_state("current_zone", self.current_zone)  # persist across restarts
            return f"Mode changed to {self.current_zone}"
        return "Invalid mode. Use: Green, Yellow, or Red"

    def get_status(self):
        brain = "🧠 LLM online" if self.brain.available else "🧩 template mode"
        return f"Mode: {self.current_zone} | Context entries: {self.db.thread_count()} | {brain}"

# ═══════════════════════════════════════════════════════════════════════════════
# GUI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class StrataConsole:
    def __init__(self):
        self.pipeline = StrataPipeline()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Strata Console — local-first NLP inference pipeline")

        # CustomTkinter multiplies the geometry we pass by the display scaling factor.
        # Compute the size in *actual* pixels (capped to the screen), then divide it
        # back out so the real window fits — keeping the bottom controls on-screen.
        self.root.update_idletasks()
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self.root)
        except Exception:
            scaling = 1.0
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        want_w = min(1000, sw - 80)      # actual px we want, capped to screen
        want_h = min(700, sh - 130)      # leave room for the taskbar
        self.root.geometry(f"{int(want_w / scaling)}x{int(want_h / scaling)}+30+20")
        self.root.minsize(int(640 / scaling), int(460 / scaling))

        self._setup_accessibility()
        self._create_widgets()

    # ── Accessibility (dyslexia fonts + size; persisted across restarts) ──────
    def _setup_accessibility(self):
        """Pick the best installed dyslexia-friendly font and restore saved prefs."""
        try:
            installed = set(tkfont.families())
        except Exception:
            installed = set()
        self.available_fonts = [f for f in DYSLEXIA_FONT_PREFS if f in installed] or ["Segoe UI"]
        db = self.pipeline.db
        saved = db.get_state("font_family", self.available_fonts[0])
        self.font_family = saved if saved in self.available_fonts else self.available_fonts[0]
        try:
            self.font_size = int(db.get_state("font_size", "14"))
        except (TypeError, ValueError):
            self.font_size = 14

    def _apply_font(self):
        """Apply the current font + size to the reading surfaces and persist it."""
        for w in (getattr(self, "output_box", None), getattr(self, "input_box", None)):
            if w is not None:
                try:
                    w.configure(font=(self.font_family, self.font_size))
                except Exception:
                    pass
        if getattr(self, "size_label", None) is not None:
            self.size_label.configure(text=f"{self.font_size}pt")
        self.pipeline.db.set_state("font_family", self.font_family)
        self.pipeline.db.set_state("font_size", str(self.font_size))

    def smaller_text(self):
        self.font_size = max(10, self.font_size - 2)   # floor 10pt
        self._apply_font()

    def bigger_text(self):
        self.font_size = min(36, self.font_size + 2)   # ceiling 36pt
        self._apply_font()

    def _on_font_change(self, value=None):
        if value:
            self.font_family = value
        self._apply_font()

    def _create_widgets(self):
        title_label = ctk.CTkLabel(
            self.root,
            text="Strata Console — local-first NLP inference pipeline",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="top", pady=(12, 4))

        self.status_label = ctk.CTkLabel(
            self.root,
            text=self.pipeline.get_status(),
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(side="top", pady=(0, 6))

        # --- Accessibility row: dyslexia-friendly font + text size ---
        access = ctk.CTkFrame(self.root)
        access.pack(side="top", fill="x", padx=16, pady=(0, 4))
        ctk.CTkLabel(access, text="Reading font:").pack(side="left", padx=(10, 6), pady=6)
        self.font_menu = ctk.CTkOptionMenu(
            access, values=self.available_fonts, command=self._on_font_change, width=190
        )
        self.font_menu.set(self.font_family)
        self.font_menu.pack(side="left", padx=(0, 10), pady=6)
        ctk.CTkButton(access, text="A−", width=44, command=self.smaller_text).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(access, text="A+", width=44, command=self.bigger_text).pack(side="left", padx=2, pady=6)
        self.size_label = ctk.CTkLabel(access, text=f"{self.font_size}pt")
        self.size_label.pack(side="left", padx=(8, 6), pady=6)

        # --- Floating toolbar (ported from Sentinel Forge): 🎤 dictation,
        #     🔊 read-aloud with speed, ❓ tour, dockable/floatable. ---
        self.quality_var = ctk.StringVar(value="Fast")
        self.speed_var = ctk.StringVar(value="Normal")
        self._tb_docked = True
        self._tb_win = None
        self._tb_drag = (0, 0)
        self._rec_stream = None
        self._rec_frames = []
        self._read_proc = None
        self._last_reply = ""
        self._attachment = None
        self._tb_host = ctk.CTkFrame(self.root)
        self._tb_host.pack(side="top", fill="x", padx=16, pady=(0, 4))
        self._build_toolbar_widgets(self._tb_host)

        # --- Bottom controls are packed FIRST and pinned to the bottom, so they
        #     are ALWAYS visible no matter how tall the content or window is. ---
        input_frame = ctk.CTkFrame(self.root)
        input_frame.pack(side="bottom", fill="x", padx=16, pady=(6, 12))

        self.input_box = ctk.CTkEntry(input_frame, placeholder_text="Type a message…",
                                      font=(self.font_family, self.font_size))
        self.input_box.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=8)
        self.input_box.bind("<Return>", self.send_message)

        self.send_btn = ctk.CTkButton(input_frame, text="Send", command=self.send_message, width=100)
        self.send_btn.pack(side="left", padx=(0, 10), pady=8)

        # --- Context sources: give the model eyes (web) and reading
        #     access (OneDrive + uploaded documents). ---
        sources = ctk.CTkFrame(self.root)
        sources.pack(side="bottom", fill="x", padx=16, pady=(2, 0))
        self.web_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sources, text="🌐 Web search", variable=self.web_var,
                        ).pack(side="left", padx=(10, 8), pady=6)
        self.onedrive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(sources, text="☁ OneDrive files",
                        variable=self.onedrive_var,
                        command=self._onedrive_toggled,
                        ).pack(side="left", padx=(0, 8), pady=6)
        ctk.CTkButton(sources, text="📎 Upload document", width=150,
                      command=self._upload_document).pack(side="left",
                                                          padx=(0, 8), pady=6)
        self.attach_label = ctk.CTkLabel(sources, text="", anchor="w")
        self.attach_label.pack(side="left", fill="x", expand=True, pady=6)
        self.attach_label.bind("<Button-1>", lambda _e: self._clear_attachment())

        button_frame = ctk.CTkFrame(self.root)
        button_frame.pack(side="bottom", fill="x", padx=16, pady=(4, 0))

        buttons = [
            ("/status", self.show_status),
            ("/lexicon", self.show_lexicon),
            ("Mode: Green", lambda: self.change_zone("GREEN")),
            ("Mode: Yellow", lambda: self.change_zone("YELLOW")),
            ("Mode: Red", lambda: self.change_zone("RED")),
            ("/help", self.show_help),
        ]

        for text, command in buttons:
            btn = ctk.CTkButton(button_frame, text=text, command=command, width=110)
            btn.pack(side="left", expand=True, padx=4, pady=8)

        # --- Output box fills whatever space is left in the middle ---
        self.output_box = ctk.CTkTextbox(self.root, font=(self.font_family, self.font_size))
        self.output_box.pack(side="top", fill="both", expand=True, padx=16, pady=6)
        if self.pipeline.brain.available:
            banner = (f"Strata Console online — local model active ({self.pipeline.brain.model}).\n"
                      "Chat, planning, and code — local-first. Ask me to \"search the web for …\",\n"
                      "check ☁ OneDrive files to let me read your documents, or 📎 upload a file.\n"
                      "🎤 dictate and 🔊 listen from the toolbar above. Type below.\n\n")
        else:
            banner = ("Strata Console — template mode.\n"
                      f"Local model offline: {self.pipeline.brain.last_error}.\n"
                      "Responses use the deterministic engine until the model is ready.\n\n")
        self.output_box.insert("end", banner)
        self.output_box.configure(state="disabled")

    def _append_output(self, text):
        self.output_box.configure(state="normal")
        self.output_box.insert("end", text + "\n\n")
        self.output_box.see("end")
        self.output_box.configure(state="disabled")

    def send_message(self, event=None):
        user_input = self.input_box.get().strip()
        if not user_input:
            return

        self.input_box.delete(0, "end")

        if user_input.startswith("/"):
            self.handle_command(user_input)
            self.status_label.configure(text=self.pipeline.get_status())
            return

        # Context sources: checked boxes, or natural phrasing — asking
        # Strata to search should just WORK.
        use_web = bool(self.web_var.get())
        use_onedrive = bool(self.onedrive_var.get())
        low = user_input.lower()
        if not use_web:
            for phrase in ("search the web", "search the internet",
                           "search online", "web search", "look online",
                           "look this up", "look up online",
                           "check the internet", "check online",
                           "google ", "on the internet"):
                if phrase in low:
                    use_web = True
                    break

        # Conversational input → run the (possibly slow, CPU-bound) pipeline off the
        # UI thread so the window stays responsive while the local model thinks.
        self._append_output(f"You: {user_input}")
        self._set_busy(True)
        busy = "🔎 searching…" if (use_web or use_onedrive or self._attachment) \
            else "thinking (local model)…"
        self.status_label.configure(text=busy)
        threading.Thread(
            target=self._process_async,
            args=(user_input, use_web, use_onedrive), daemon=True
        ).start()

    def _process_async(self, user_input, use_web=False, use_onedrive=False):
        """Runs in a worker thread; hands results back to the UI thread via .after()."""
        try:
            extra = self._gather_context(user_input, use_web, use_onedrive)
            output = self.pipeline.process_input(user_input,
                                                 extra_context=extra)
        except Exception as e:
            output = {"error": f"{type(e).__name__}: {e}"}
        self.root.after(0, self._deliver, output)

    def _deliver(self, output):
        """Render the pipeline result on the UI thread, then re-enable input."""
        if output.get("error"):
            self._append_output(f"⚠️ {output['error']}")
        elif output.get("response"):
            # Real LLM answer is the headline; closing is a small mode marker.
            self._last_reply = output["response"]     # for 🔊 Read
            self._append_output(f"Strata: {output['response']}")
            self._append_output(output.get('closing', ''))
        else:
            # Template fallback (model not ready) — the structured four-part reply.
            self._append_output(f"Strata: {output.get('summary', '')}")
            self._append_output(output.get('description', ''))
            self._append_output(output.get('comments', ''))
            self._append_output(output.get('closing', ''))
        self._set_busy(False)
        self.status_label.configure(text=self.pipeline.get_status())

    def _set_busy(self, busy):
        """Disable the entry + Send button while a response is generating."""
        state = "disabled" if busy else "normal"
        self.input_box.configure(state=state)
        self.send_btn.configure(state=state)
        if not busy:
            self.input_box.focus_set()


    # ═══ Floating toolbar (ported from Sentinel Forge) ═════════════════════
    _WHISPER_MODELS = {"Fast": "base.en", "Accurate": "small.en",
                       "Best": "medium.en"}
    _READ_SPEEDS = {"🐢 Slowest": -5, "🐢 Slower": -2, "Normal": 0,
                    "🐇 Faster": 2}

    def _build_toolbar_widgets(self, parent):
        for ch in list(parent.winfo_children()):
            try:
                ch.destroy()
            except Exception:
                pass
        grip = ctk.CTkLabel(parent, text="⋮⋮", width=22, cursor="fleur")
        grip.pack(side="left", padx=(10, 2), pady=6)
        grip.bind("<ButtonPress-1>", self._tb_drag_start)
        grip.bind("<B1-Motion>", self._tb_drag_move)
        ctk.CTkLabel(parent, text="Quality:").pack(side="left", padx=(6, 2))
        q_menu = ctk.CTkOptionMenu(parent, width=110,
                                   values=list(self._WHISPER_MODELS),
                                   variable=self.quality_var)
        q_menu.pack(side="left", padx=(0, 6), pady=6)
        self.voice_btn = ctk.CTkButton(parent, text="🎤 Voice", width=92,
                                       command=self._toggle_voice)
        self.voice_btn.pack(side="left", padx=(0, 6), pady=6)
        self.read_btn = ctk.CTkButton(parent, text="🔊 Read", width=84,
                                      command=self._toggle_read)
        self.read_btn.pack(side="left", padx=(0, 6), pady=6)
        ctk.CTkLabel(parent, text="Speed:").pack(side="left", padx=(4, 2))
        s_menu = ctk.CTkOptionMenu(parent, width=110,
                                   values=list(self._READ_SPEEDS),
                                   variable=self.speed_var)
        s_menu.pack(side="left", padx=(0, 6), pady=6)
        self._tb_dock_btn = ctk.CTkButton(
            parent, text=("⇱ Undock" if self._tb_docked else "⇲ Dock"),
            width=90, command=self._tb_toggle_dock)
        self._tb_dock_btn.pack(side="right", padx=(4, 10), pady=6)
        tour_btn = ctk.CTkButton(parent, text="❓ Tour", width=76,
                                 command=self._show_tour)
        tour_btn.pack(side="right", padx=(4, 2), pady=6)
        # Tour registry: (widget, title, text) — flashed in order.
        self._tour_items = [
            (grip, "⋮⋮  Drag grip",
             "When the bar is floating, hold this grip and drag to move it."),
            (q_menu, "Quality picker",
             "How carefully the microphone listens. Fast types quickest; "
             "Best is most accurate but slower."),
            (self.voice_btn, "🎤 Voice",
             "Click, speak your message, then click ■ Stop — your words are "
             "typed into the message box for you."),
            (self.read_btn, "🔊 Read",
             "Reads Strata's last reply aloud so you can listen instead of "
             "read. Click again to stop."),
            (s_menu, "🐢 / 🐇 Reading speed",
             "How fast the voice reads. Pick 🐢 Slower if the words sound "
             "rushed."),
            (tour_btn, "❓ Tour",
             "This walkthrough — open it any time."),
            (self._tb_dock_btn, "⇱ / ⇲ Dock",
             "⇱ Undock pops the bar out into its own little window that "
             "floats on top; ⇲ Dock puts it back at the top of the console."),
        ]

    def _tb_toggle_dock(self):
        if self._tb_docked:
            self._tb_docked = False
            for ch in list(self._tb_host.winfo_children()):
                try:
                    ch.destroy()
                except Exception:
                    pass
            win = ctk.CTkToplevel(self.root)
            win.title("Strata toolbar")
            try:
                win.attributes("-topmost", True)
            except Exception:
                pass
            try:
                scaling = ctk.ScalingTracker.get_window_scaling(self.root)
            except Exception:
                scaling = 1.0
            win.geometry(f"{int(820 / scaling)}x{int(54 / scaling)}+180+120")
            win.protocol("WM_DELETE_WINDOW", self._tb_toggle_dock)
            self._tb_win = win
            self._build_toolbar_widgets(win)
        else:
            self._tb_docked = True
            if self._tb_win is not None:
                try:
                    self._tb_win.destroy()
                except Exception:
                    pass
                self._tb_win = None
            self._build_toolbar_widgets(self._tb_host)

    def _tb_drag_start(self, event):
        self._tb_drag = (event.x_root, event.y_root)

    def _tb_drag_move(self, event):
        if self._tb_win is None:
            return
        dx = event.x_root - self._tb_drag[0]
        dy = event.y_root - self._tb_drag[1]
        self._tb_drag = (event.x_root, event.y_root)
        try:
            x = self._tb_win.winfo_x() + dx
            y = self._tb_win.winfo_y() + dy
            self._tb_win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    # ── 🎤 Voice: push-to-talk dictation into the message box ─────────────
    def _toggle_voice(self):
        if self._rec_stream is not None:
            self._stop_voice()
            return
        try:
            import sounddevice as sd
        except Exception as e:
            self._append_output(f"🎤 Voice needs the sounddevice package "
                                f"(pip install sounddevice): {e}")
            return
        self._rec_frames = []
        try:
            self._rec_stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="float32",
                callback=lambda indata, frames, t, status:
                    self._rec_frames.append(indata.copy()))
            self._rec_stream.start()
        except Exception as e:
            self._rec_stream = None
            self._append_output(f"🎤 Could not open the microphone: {e}")
            return
        self.voice_btn.configure(text="■ Stop", fg_color="#dc2626",
                                 hover_color="#b91c1c")
        self.status_label.configure(
            text="🎤 Listening — speak, then click ■ Stop…")

    def _stop_voice(self):
        stream = self._rec_stream
        self._rec_stream = None
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        self.voice_btn.configure(text="🎤 Voice", fg_color="#1f6aa5",
                                 hover_color="#144870")
        frames = self._rec_frames
        self._rec_frames = []
        if not frames:
            self.status_label.configure(text=self.pipeline.get_status())
            return
        self.status_label.configure(text="🎤 Transcribing…")
        threading.Thread(target=self._transcribe_async, args=(frames,),
                         daemon=True).start()

    def _transcribe_async(self, frames):
        err, text = "", ""
        try:
            import numpy as np
            from faster_whisper import WhisperModel
            audio = np.concatenate(frames)[:, 0]
            name = self._WHISPER_MODELS.get(self.quality_var.get(), "base.en")
            cache = getattr(self, "_whisper_cache", None) or {}
            model = cache.get(name)
            if model is None:
                model = WhisperModel(name, device="cpu", compute_type="int8")
                cache[name] = model
                self._whisper_cache = cache
            segments, _info = model.transcribe(audio, beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            err = f"{type(e).__name__}: {e}"

        def deliver():
            self.status_label.configure(text=self.pipeline.get_status())
            if err:
                self._append_output(f"🎤 Transcription failed: {err}")
            elif text:
                try:
                    self.input_box.insert("end", text)
                    self.input_box.focus_set()
                except Exception:
                    pass
            else:
                self._append_output("🎤 I didn't catch anything — try again "
                                    "a little louder or closer to the mic.")
        self.root.after(0, deliver)

    # ── 🔊 Read: speak the last reply aloud (Windows voices, no setup) ─────
    def _toggle_read(self):
        proc = self._read_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            self._read_proc = None
            self.read_btn.configure(text="🔊 Read")
            return
        text = (self._last_reply or "").strip()
        if not text:
            self._append_output("🔊 Nothing to read yet — send a message "
                                "first.")
            return
        import os
        import subprocess
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        rate = self._READ_SPEEDS.get(self.speed_var.get(), 0)
        ps = ("Add-Type -AssemblyName System.Speech; "
              f"$t = Get-Content -Raw -Encoding UTF8 -LiteralPath '{tmp}'; "
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Rate = {rate}; $s.Speak($t)")
        self._read_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.read_btn.configure(text="■ Stop")

        def watch():
            p = self._read_proc
            if p is None or p.poll() is not None:
                self._read_proc = None
                try:
                    self.read_btn.configure(text="🔊 Read")
                except Exception:
                    pass
                return
            self.root.after(300, watch)
        self.root.after(300, watch)

    # ── ❓ Tour: one control per step, flashed while explained ─────────────
    def _show_tour(self):
        items = [it for it in (getattr(self, "_tour_items", None) or [])]
        if not items:
            return
        win = ctk.CTkToplevel(self.root)
        win.title("❓ Toolbar tour")
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self.root)
        except Exception:
            scaling = 1.0
        win.geometry(f"{int(470 / scaling)}x{int(250 / scaling)}+220+200")
        step_l = ctk.CTkLabel(win, text="", anchor="w",
                              font=ctk.CTkFont(size=12))
        step_l.pack(anchor="w", padx=14, pady=(10, 0))
        title_l = ctk.CTkLabel(win, text="", anchor="w",
                               font=ctk.CTkFont(size=16, weight="bold"))
        title_l.pack(anchor="w", padx=14, pady=(2, 4))
        body_l = ctk.CTkLabel(win, text="", anchor="w", justify="left",
                              wraplength=420, font=ctk.CTkFont(size=13))
        body_l.pack(anchor="w", fill="x", padx=14)
        brow = ctk.CTkFrame(win)
        brow.pack(side="bottom", fill="x", padx=12, pady=10)
        state = {"i": 0, "lit": None}

        def unflash():
            lit = state["lit"]
            state["lit"] = None
            if lit is None:
                return
            widget, orig = lit
            try:
                widget.configure(fg_color=orig)
            except Exception:
                pass

        def flash(widget):
            unflash()
            try:
                orig = widget.cget("fg_color")
                widget.configure(fg_color="#d97706")
                state["lit"] = (widget, orig)
            except Exception:
                pass

        def close():
            unflash()
            try:
                win.destroy()
            except Exception:
                pass

        def show(i):
            i = max(0, min(i, len(items) - 1))
            state["i"] = i
            widget, title, text = items[i]
            step_l.configure(text=f"Step {i + 1} of {len(items)}")
            title_l.configure(text=title)
            body_l.configure(text=text)
            flash(widget)
            back.configure(state=("normal" if i > 0 else "disabled"))
            nxt.configure(text=("✓ Done" if i == len(items) - 1 else "Next ▶"))

        def next_step():
            if state["i"] >= len(items) - 1:
                close()
            else:
                show(state["i"] + 1)

        back = ctk.CTkButton(brow, text="◀ Back", width=90,
                             command=lambda: show(state["i"] - 1))
        back.pack(side="left", padx=(6, 0), pady=4)
        nxt = ctk.CTkButton(brow, text="Next ▶", width=90, command=next_step)
        nxt.pack(side="right", padx=(0, 6), pady=4)
        win.protocol("WM_DELETE_WINDOW", close)
        show(0)

    # ═══ Context sources: web, OneDrive, uploaded documents ════════════════
    def _gather_context(self, user_input, use_web, use_onedrive):
        """Assemble grounding text for this turn (worker thread)."""
        parts = []
        att = self._attachment
        if att:
            from strata_tools.retrieval import retrieve_from_text
            body = retrieve_from_text(user_input, att.get("text", ""))
            if body:
                parts.append(f"From the attached file '{att['name']}':\n"
                             + body)
        if use_onedrive:
            parts.append(self._onedrive_context(user_input))
        if use_web:
            from strata_tools.web_search import web_search_context
            parts.append(web_search_context(user_input))
        return "\n\n".join(p for p in parts if p)

    def _onedrive_toggled(self):
        if self.onedrive_var.get():
            self._ensure_onedrive_index()

    def _ensure_onedrive_index(self):
        if getattr(self, "_onedrive_index", None) is not None:
            return
        if getattr(self, "_onedrive_building", False):
            return
        self._onedrive_building = True
        self._append_output("☁ Indexing your OneDrive files — the first "
                            "time can take a few minutes; after that it's "
                            "cached.")

        def work():
            from strata_tools import doc_index
            try:
                import os
                cache = os.path.join(doc_index.cache_dir(),
                                     "onedrive_index.json")
                idx = doc_index.build_index_over(doc_index.onedrive_root(),
                                                 cache)
                self._onedrive_index = idx
                note = f"☁ OneDrive ready — {len(idx)} files searchable."
            except Exception as e:
                self._onedrive_index = []
                note = f"☁ OneDrive indexing failed: {e}"
            self._onedrive_building = False
            try:
                self.root.after(0, lambda: self._append_output(note))
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _onedrive_context(self, query):
        index = getattr(self, "_onedrive_index", None)
        if index is None:
            try:
                self.root.after(0, self._ensure_onedrive_index)
            except Exception:
                pass
            return ("NOTE: the user's OneDrive files are still being "
                    "indexed. Tell the user the file index is still "
                    "building and to ask again in a few minutes.")
        if not index:
            return ""
        from strata_tools.retrieval import retrieve_from_index
        hits = retrieve_from_index(query, index)
        return ("From the user's OneDrive files:\n" + hits) if hits else ""

    def _upload_document(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Upload a document for Strata to read",
            filetypes=[("Readable files",
                        "*.txt *.md *.docx *.pdf *.html *.htm "
                        "*.xlsx *.xlsm *.csv"),
                       ("All files", "*.*")])
        if not path:
            return
        import os
        from strata_tools.doc_index import extract_text
        name = os.path.basename(path)
        text = extract_text(path) or ""
        if not text.strip():
            self._append_output(f"📎 Couldn't read {name} — unsupported "
                                "format or empty file.")
            return
        self._attachment = {"name": name, "text": text[:2_000_000]}
        kb = max(1, len(text) // 1024)
        self.attach_label.configure(
            text=f"📎 {name} ({kb} KB) — attached; click here to remove")
        self._append_output(f"📎 Attached {name}. Ask me about it — I'll "
                            "read the relevant parts. It stays attached "
                            "until you remove it.")

    def _clear_attachment(self):
        if self._attachment is None:
            return
        self._attachment = None
        self.attach_label.configure(text="")
        self._append_output("📎 Attachment removed.")

    def handle_command(self, command):
        cmd = command.lower()
        if cmd == "/status":
            self._append_output(self.pipeline.get_status())
        elif cmd == "/lexicon":
            self.show_lexicon()
        elif cmd.startswith("/mode ") or cmd.startswith("/zone "):
            mode = command.split(" ")[1]
            result = self.pipeline.change_zone(mode)
            self._append_output(result)
            self.status_label.configure(text=self.pipeline.get_status())
        elif cmd == "/help":
            self.show_help()
        else:
            self._append_output(f"Unknown command: {command}. Try /help")

    def show_status(self):
        self._append_output(self.pipeline.get_status())

    def show_lexicon(self):
        text = "=== Operator Token Lexicon ===\n"
        for g in ALL_GLYPHS:
            text += f"{g['glyph']}  {g['name']}: {g['function']}\n"
        self._append_output(text)

    def change_zone(self, zone):
        result = self.pipeline.change_zone(zone)
        self._append_output(result)
        self.status_label.configure(text=self.pipeline.get_status())

    def show_help(self):
        help_text = """
Available Commands:
/status          → Show current mode and context count
/lexicon         → Show the operator token lexicon
/mode green      → Switch to Green mode (active)
/mode yellow     → Switch to Yellow mode (analytical)
/mode red        → Switch to Red mode (archival)
/help            → Show this help
"""
        self._append_output(help_text)

    def run(self):
        self.root.mainloop()

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = StrataConsole()
    app.run()
