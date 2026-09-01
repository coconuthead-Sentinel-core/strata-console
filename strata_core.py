#!/usr/bin/env python3
"""Strata Console — the engine, with no user interface attached.

Everything here is shell-agnostic: the SQLite store, the five pipeline
stages, and the local-model client. It imports no Tk, no CustomTkinter,
and nothing that assumes a window exists.

That separation is the point. ``strata_console.py`` is the desktop shell
and ``strata_web.py`` is a second shell over the same engine, so a
front-end experiment cannot cost the work that took the longest to get
right. Adding a shell must never mean forking this file.

**DB_PATH lives here and only here.** It used to be a module constant in
the shell that tools reassigned to redirect the database at a throwaway
file. If the shell kept its own copy after this split, that reassignment
would rebind a name nothing reads and the tools would go on writing to
the owner's real store — which is precisely the defect recorded as
NM-005. So the shell does not define DB_PATH at all: anything redirecting
the database sets ``strata_core.DB_PATH``, and anything that gets it
wrong fails loudly instead of quietly.
"""

import os
import sqlite3
from datetime import datetime

from strata_tools import session

# Reading fonts offered to the owner, best-first (ported from Sentinel
# Forge). CORRECTED 2026-09-01 -- the previous comment here claimed these
# were "repeatedly cited in dyslexia research", which overstates what the
# evidence supports, and a claim in this repository has to survive
# checking.
#
# What controlled studies actually found: a specialised dyslexia face
# (OpenDyslexic) produced NO improvement in reading rate or accuracy
# against Arial and Times New Roman, for individual readers or as a
# group, and some work measured it slower. Participants did not report
# preferring it. The literature overall is mixed at best.
#
# What IS well supported, and what this list is really for:
#   * the reader choosing their own face, size and spacing -- which is a
#     WCAG principle rather than a font claim, and the reason this menu
#     exists at all;
#   * larger text and more line spacing;
#   * shorter line lengths (British Dyslexia Association: 60-80 chars).
#
# So the menu stays -- choice is the evidence-backed feature -- and the
# claim goes. Atkinson Hyperlegible is kept on separate and better
# grounds: the Braille Institute designed it for LOW VISION, which is a
# different and better-evidenced claim than a dyslexia one.
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

    def __init__(self, path=None):
        # Resolved at CALL time, not bound as a default argument. A
        # default of `path=DB_PATH` captures the module constant when
        # the class is defined, so a tool or test that later sets
        # strata_console.DB_PATH to a throwaway file is quietly ignored
        # and writes to the owner's real database instead. That is
        # exactly what happened to the accessibility probes on
        # 2026-09-01 -- they pressed A+ against the live store.
        self.path = path or DB_PATH
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
        # Above the clear floor only. Clearing the window must also clear
        # what the model recalls, or the "cleared" conversation gets
        # quoted straight back at the owner.
        rows = self.conn.execute(
            "SELECT timestamp, input, zone FROM memory_threads "
            "WHERE id > ? ORDER BY id DESC LIMIT ?",
            (self.memory_floor(), limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]  # oldest → newest

    def thread_count(self):
        """Threads still in play — what /status should report."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM memory_threads WHERE id > ?",
            (self.memory_floor(),)).fetchone()[0]

    def archived_thread_count(self):
        """Every thread ever stored, floor included. Nothing is deleted."""
        return self.conn.execute(
            "SELECT COUNT(*) FROM memory_threads").fetchone()[0]

    # --- the clear floor (archive, never delete) ------------------------------
    def memory_floor(self):
        return session.parse_floor(self.get_state(session.STATE_KEY))

    def latest_thread_id(self):
        row = self.conn.execute(
            "SELECT MAX(id) AS top FROM memory_threads").fetchone()
        return row["top"] or 0

    def raise_memory_floor(self):
        """Hide everything logged so far. Returns how many turns moved."""
        before = self.thread_count()
        floor = session.next_floor(self.memory_floor(),
                                   self.latest_thread_id())
        self.set_state(session.STATE_KEY, str(floor))
        return before

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
