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


import threading
import tkinter.font as tkfont
import customtkinter as ctk

from strata_tools import (dictation, keyboard, layout, modes,
                          selection, session, speech, theme, window_fit)

# The engine. Both shells import it; neither owns it. DB_PATH is
# deliberately NOT re-exported here -- see strata_core's docstring.
from strata_core import (ALL_GLYPHS, GLYPH_CHARS, GLYPH_CODEX, GLYPH_LOOKUP,
                         DYSLEXIA_FONT_PREFS, LLM_MODEL, InputNode, LLMBrain,
                         MemoryNode, OutputSynthNode, PersonaNode, RouterNode,
                         StrataDB, StrataPipeline)

# ═══════════════════════════════════════════════════════════════════════════════
# GUI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class _VoiceStop(Exception):
    """A voice-path stop that already carries its own owner-facing message."""


class StrataConsole:
    def __init__(self):
        self.pipeline = StrataPipeline()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Strata Console — local-first NLP inference pipeline")

        self.root.update_idletasks()

        # ORDER MATTERS HERE, and getting it wrong is how the window
        # ended up 700px tall on a 617px screen. Two traps, both
        # measured rather than reasoned about:
        #
        #  1. TWO COORDINATE SYSTEMS. Windows' SPI_GETWORKAREA reports
        #     PHYSICAL pixels, and CustomTkinter turns on DPI awareness
        #     when it initialises -- so a work-area query made after
        #     ctk.CTk() answered 1032px of height while Tk's own
        #     winfo_screenheight() still said 617. Mixing the two sized
        #     the window off the bottom of the desktop. Everything here
        #     now stays in Tk's coordinate system, which is the one the
        #     geometry manager actually uses.
        #
        #  2. TWO SCALING FACTORS. CustomTkinter keeps widget scaling
        #     (how large controls are drawn) separately from window
        #     scaling (what geometry() multiplies by), and the widget
        #     decision must be applied BEFORE the window scaling is read.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Make the CONTENT fit the window, not just the window fit the
        # screen. At the inherited scaling the chrome needed 919px in a
        # 486px window, so Tk silently stopped mapping children and
        # thirteen controls -- the transcript among them -- were never
        # drawn. Must be set before any widget is constructed.
        _, want_h = window_fit.target_pixels(screen_w, screen_h)
        self.widget_scaling = layout.plan_widget_scaling(want_h)
        ctk.set_widget_scaling(self.widget_scaling)
        self.layout_note = layout.describe(want_h, self.widget_scaling)

        # NOW read the window scaling and compensate for it.
        try:
            scaling = ctk.ScalingTracker.get_window_scaling(self.root)
        except Exception:
            scaling = 1.0
        geometry, min_w, min_h = window_fit.plan_geometry(
            screen_w, screen_h, scaling)
        self.root.geometry(geometry)
        self.root.minsize(min_w, min_h)

        self._setup_accessibility()
        self._create_widgets()

        # WCAG 2.1.1 Keyboard (Level A). CustomTkinter builds controls
        # from a Canvas plus a Label, neither of which joins the Tab
        # ring, so before this call the console had exactly two
        # keyboard-reachable widgets out of twenty-two. Measured, not
        # assumed -- tools/a11y_check.py reports the real ring.
        # Make the controls visible as SHAPES before making them
        # reachable. Measured: every button in the app failed WCAG
        # 1.4.11 against the frame it sits on -- the stock blue at
        # 2.47:1 and the inactive mode fills as low as 1.01:1, which is
        # invisible rather than merely dim.
        self._style_controls()
        self._keyboard_controls = keyboard.enable_tree(self.root)
        # The transcript is state="disabled" so it cannot be typed into,
        # and Tk drops disabled widgets out of the focus ring entirely.
        # A keyboard user could reach every button and not the text they
        # produce, so focus and scrolling are restored without making it
        # editable.
        keyboard.enable_reading_surface(self.output_box,
                                        keyboard._ring_on,
                                        keyboard._ring_off)

    # ── Accessibility (dyslexia fonts + size; persisted across restarts) ──────
    @staticmethod
    def _walk(widget):
        """Every widget beneath (and including) this one."""
        yield widget
        for child in widget.winfo_children():
            yield from StrataConsole._walk(child)

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

    _UI_FONT_KINDS = ("CTkButton", "CTkLabel", "CTkCheckBox",
                      "CTkOptionMenu", "CTkComboBox", "CTkSwitch")

    def _apply_font(self):
        """Apply the current font + size to the whole interface, and persist it.

        A+/A- used to move two widgets out of twenty-two, which is a
        text-resize control that mostly does not resize text. It now
        moves the reading surfaces without a ceiling and the chrome up to
        a measured cap -- past that cap the rows stop fitting and
        controls disappear, which would trade WCAG 1.4.4 for the far
        worse failure this console just finished fixing.
        """
        for w in (getattr(self, "output_box", None), getattr(self, "input_box", None)):
            if w is not None:
                try:
                    w.configure(font=(self.font_family, self.font_size))
                except Exception:
                    pass

        ui_size = layout.ui_font_size(self.font_size)
        for widget in self._walk(self.root):
            if type(widget).__name__ in self._UI_FONT_KINDS:
                try:
                    widget.configure(font=(self.font_family, ui_size))
                except Exception:
                    pass
        if getattr(self, "size_label", None) is not None:
            # Say when the interface has stopped following, so a capped
            # A+ reads as a designed limit rather than a dead button.
            capped = " (menus capped)" if layout.ui_font_is_capped(
                self.font_size) else ""
            self.size_label.configure(text=f"{self.font_size}pt{capped}")
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
        # The window title bar already says what this application is, so
        # a 86px banner repeating it cost the transcript a third of its
        # height for no information. Status moves into the row below,
        # which is one fewer stacked row -- the shop design law caps a
        # screen at five major choices, and this had seven.
        self.root.title("Strata Console — local-first NLP inference pipeline")

        # --- Reading row: font, text size, and live status ---
        access = ctk.CTkFrame(self.root)
        access.pack(side="top", fill="x", padx=16, pady=(6, 4))
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
        self.status_label = ctk.CTkLabel(access,
                                         text=self.pipeline.get_status(),
                                         anchor="e")
        self.status_label.pack(side="right", fill="x", expand=True,
                               padx=(12, 12), pady=6)

        # --- Floating toolbar (ported from Sentinel Forge): 🎤 dictation,
        #     🔊 read-aloud with speed, ❓ tour, dockable/floatable. ---
        self.quality_var = ctk.StringVar(value="Fast")
        self.speed_var = ctk.StringVar(value="Normal")
        self._tb_docked = True
        self._tb_win = None
        self._tb_drag = (0, 0)
        self._rec_stream = None
        self._rec_frames = []
        self._whisper_model = None
        self._whisper_tier = None
        self._rec_device_name = "the microphone"
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
        # Ctrl+L clears, the way every terminal on this laptop does.
        # Bound on the root so it works wherever focus happens to be.
        self.root.bind_all("<Control-l>",
                           lambda _e: (self.clear_window(), "break")[1])
        # Ctrl+A selects all of whatever is focused. Tk's default binding
        # is beginning-of-line, which is not what anyone on Windows
        # expects from this key.
        self.root.bind_all("<Control-a>", self._select_all_focused)

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

        # /status and /lexicon were dropped from this row on 2026-09-02.
        # The status line is already on screen at all times, so a button
        # to print it again was duplicating a live readout; /lexicon is a
        # rare reference lookup. Both remain as typed commands and in
        # /help. That takes the row from seven controls to five -- the
        # shop design law's ceiling -- and the width each button gets
        # back is why they can now be read.
        buttons = [
            ("/help", self.show_help),
            ("🧹 Clear", self.clear_window),
        ]

        for text, command in buttons:
            btn = ctk.CTkButton(button_frame, text=text, command=command, width=110)
            btn.pack(side="left", expand=True, padx=4, pady=8)

        # Colour-coded mode buttons. They were three identical blue
        # rectangles with the live mode named only in the status line;
        # a colour-carried category is pre-attentive, so it costs no
        # working memory to find. Colour is never the ONLY cue though
        # (WCAG 1.4.1) -- the active mode also carries a bullet in its
        # label and a raised border. Every colour is measured against
        # the text and the focus ring in tests/test_modes.py.
        self.mode_buttons = {}
        for key in modes.ORDER:
            btn = ctk.CTkButton(
                button_frame, width=110,
                command=lambda k=key: self.change_zone(k),
                **modes.appearance(key, key == self.pipeline.current_zone))
            btn.pack(side="left", expand=True, padx=4, pady=8)
            self.mode_buttons[key] = btn

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
            # _last_reply was never set on this path, so 🔊 Read replayed
            # the PREVIOUS answer instead of this one.
            self._last_reply = " ".join(
                str(output.get(k, "")) for k in
                ("summary", "description", "comments") if output.get(k))
            self._append_output(f"Strata: {output.get('summary', '')}")
            self._append_output(output.get('description', ''))
            self._append_output(output.get('comments', ''))
            self._append_output(output.get('closing', ''))
        self._set_busy(False)
        self.status_label.configure(text=self.pipeline.get_status())
        # Read the answer aloud without being asked, when Auto is on.
        if self._autoread_on() and (self._last_reply or "").strip():
            self._start_reading(self._last_reply)

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
    # Below this RMS the capture carried no signal, so an empty
    # transcript is the microphone's fault and must not be blamed on the
    # speaker. A quiet room measures near 0.0003; speech measures 0.01+.
    _SILENCE_FLOOR = 0.002
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
        # Read every answer aloud without being asked. Persisted, because
        # a preference that resets each launch is a preference the owner
        # has to keep re-stating.
        self.autoread_var = ctk.BooleanVar(
            value=self.pipeline.db.get_state("autoread", "0") == "1")
        self.autoread_box = ctk.CTkCheckBox(
            parent, text="Auto", variable=self.autoread_var, width=60,
            command=self._autoread_toggled)
        self.autoread_box.pack(side="left", padx=(0, 8), pady=6)
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
        # Preflight BOTH voice packages against the interpreter that is
        # actually running, before a word is recorded. Checking only
        # sounddevice here used to let the owner talk for twenty seconds
        # and only then hit a missing faster_whisper, reported as
        # "Transcription failed" -- which reads as a dead microphone.
        from strata_tools import interpreter as interp
        executable, missing = interp.current_report()
        if missing:
            self._append_output("🎤 " + interp.explain_missing(executable,
                                                            missing))
            return
        import sounddevice as sd
        self._rec_frames = []
        try:
            info = sd.query_devices(kind="input")
            self._rec_device_name = str(info["name"]).strip()
        except Exception:
            self._rec_device_name = "the microphone"
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
        """Budget RAM, keep one model resident, then transcribe.

        The old version cached every model it ever loaded, so cycling the
        quality picker stacked all three tiers into whatever RAM Ollama
        had left and the third load died inside MKL. It also gave no sign
        that a 14-second model load was under way, which reads as a dead
        microphone.
        """
        import gc

        from strata_tools import voice_budget as vb

        def status(msg):
            self.root.after(0,
                            lambda: self.status_label.configure(text=msg))

        err, text, stop_note = "", "", ""
        level = 0.0
        try:
            import numpy as np
            audio = np.concatenate(frames)[:, 0]
            level = float(np.sqrt((audio ** 2).mean()))

            wanted = self.quality_var.get()
            if wanted not in vb.TIER_MODELS:
                wanted = "Fast"
            _total, free = vb.free_ram_mb()
            tier, note = vb.plan_tier(free, wanted)
            if tier is None:
                stop_note = f"🎤 {note}"
                raise _VoiceStop()
            if tier != wanted:
                self.root.after(
                    0,
                    lambda n=note: self._append_output(f"🎤 {n}"))

            if self._whisper_tier != tier:
                # One resident model at a time.
                self._whisper_model = None
                self._whisper_tier = None
                gc.collect()
                secs = vb.TIER_LOAD_SECONDS.get(tier, 5)
                status(f"🎤 Loading the {tier} voice model "
                       f"(about {secs}s the first time)…")
                from faster_whisper import WhisperModel
                try:
                    self._whisper_model = WhisperModel(
                        vb.TIER_MODELS[tier], device="cpu",
                        compute_type="int8")
                except (MemoryError, RuntimeError) as e:
                    self._whisper_model = None
                    gc.collect()
                    stop_note = (
                        f"🎤 The {tier} voice model would not fit in "
                        f"RAM ({free} MB free). Ollama is holding the "
                        f"language model — close it, or pick Fast. "
                        f"[{type(e).__name__}: {e}]")
                    raise _VoiceStop()
                self._whisper_tier = tier

            status("🎤 Transcribing…")
            segments, _info = self._whisper_model.transcribe(audio,
                                                             beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
            # Spoken punctuation into real characters, then collisions
            # resolved -- Whisper auto-punctuates from pauses, so a
            # dictated "period" arrives on top of a mark it already
            # inserted. Pure and defensive: returns the raw transcript
            # unchanged rather than raising and losing the words.
            text = dictation.polish(text)
        except _VoiceStop:
            pass
        except Exception as e:
            err = f"{type(e).__name__}: {e}"

        def deliver():
            self.status_label.configure(text=self.pipeline.get_status())
            if stop_note:
                self._append_output(stop_note)
            elif err:
                self._append_output(f"🎤 Transcription failed: {err}")
            elif text:
                try:
                    self.input_box.insert("end", text)
                    self.input_box.focus_set()
                except Exception:
                    pass
            elif level <= self._SILENCE_FLOOR:
                self._append_output(
                    f"🎤 {self._rec_device_name} produced silence "
                    f"(level {level:.5f}). That is the microphone or its "
                    f"Windows input level — not you. Check Settings > "
                    f"System > Sound > Input.")
            else:
                self._append_output(
                    "🎤 Sound came through but I didn't find any words "
                    "— try again a little louder or closer to the mic.")
        self.root.after(0, deliver)

    # ── 🔊 Read: speak the last reply aloud (Windows voices, no setup) ─────
    def _style_controls(self):
        """Outline every control, and give the buttons a usable height.

        Mode buttons are skipped: they carry their own fill and their own
        selected/unselected outline from strata_tools.modes, and
        overwriting it here would erase which mode is live.
        """
        mode_buttons = set(getattr(self, "mode_buttons", {}).values())
        for widget in self._walk(self.root):
            kind = type(widget).__name__
            if widget in mode_buttons:
                # Colours are theirs; the height is everyone's.
                try:
                    widget.configure(height=theme.BUTTON_MIN_HEIGHT)
                except Exception:
                    pass
                continue
            try:
                if kind == "CTkButton":
                    widget.configure(fg_color=theme.BUTTON_FILL,
                                     hover_color=theme.BUTTON_HOVER,
                                     height=theme.BUTTON_MIN_HEIGHT,
                                     **theme.outline_kwargs())
                elif kind in ("CTkOptionMenu", "CTkComboBox"):
                    widget.configure(fg_color=theme.BUTTON_FILL,
                                     button_color=theme.BUTTON_HOVER,
                                     height=theme.BUTTON_MIN_HEIGHT)
            except Exception:
                pass

    def _autoread_on(self):
        """Is auto-read enabled? Safe before the toolbar exists."""
        try:
            return bool(self.autoread_var.get())
        except Exception:
            return False

    def _autoread_toggled(self):
        on = self._autoread_on()
        self.pipeline.db.set_state("autoread", "1" if on else "0")
        # Visible confirmation, per the design law -- a toggle that
        # changes nothing on screen reads as a toggle that did nothing.
        self._append_output("🔊 Auto-read ON — answers will be spoken as "
                            "they arrive." if on else
                            "🔊 Auto-read off — use the 🔊 Read button.")

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
        self._start_reading(text, announce=True)

    def _start_reading(self, raw, announce=False):
        """Speak a reply. The one path the button and auto-read share.

        Two callers meant two chances to drift, so there is one routine.
        ``announce`` is False for auto-read: an automatic action that
        cannot speak should stay quiet rather than push an error into
        the transcript after every single reply.
        """
        # The model answers in markdown. Handed to SAPI as-is it says
        # "asterisk asterisk important asterisk asterisk" and recites
        # code blocks character by character, so strip the markup and
        # spell out numbers, money and abbreviations first. Applied only
        # to the string given to the engine — the on-screen text is
        # untouched.
        text = speech.speakable(raw or "")
        if not text.strip():
            if announce:
                self._append_output("🔊 That reply had nothing sayable in "
                                    "it — no words outside the markup.")
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
        elif cmd in ("/clear", "/new"):
            self.clear_window()
        else:
            self._append_output(f"Unknown command: {command}. Try /help")

    def _select_all_focused(self, _event=None):
        """Select everything in the focused box, whichever species it is.

        The kernel raises for a widget that supports neither API; caught
        here so a stray Ctrl+A on a label is a no-op rather than a
        traceback in the Tk callback.
        """
        try:
            selection.select_all(self.root.focus_get())
        except Exception:
            return None
        return "break"

    def clear_window(self):
        """Empty the transcript AND stop the model recalling it.

        Both halves or neither: clearing only the view leaves MemoryNode
        feeding the last turns back to the model, which then quotes the
        conversation the owner just cleared. Nothing is deleted -- the
        rows stay in SQLite below a raised floor.
        """
        cleared = self.pipeline.db.raise_memory_floor()
        archived = self.pipeline.db.archived_thread_count()
        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.configure(state="disabled")
        self._append_output(session.clear_report(cleared, archived))
        self.status_label.configure(text=self.pipeline.get_status())
        try:
            self.input_box.focus_set()
        except Exception:
            pass

    def show_status(self):
        self._append_output(self.pipeline.get_status())

    def show_lexicon(self):
        text = "=== Operator Token Lexicon ===\n"
        for g in ALL_GLYPHS:
            text += f"{g['glyph']}  {g['name']}: {g['function']}\n"
        self._append_output(text)

    def _refresh_mode_buttons(self):
        """Repaint every mode button for the live mode.

        All three are repainted, not just the new one -- repainting only
        the winner leaves the previous mode still looking active, which
        is the classic way a colour-coded control set starts lying.
        """
        looks = modes.all_appearances(self.pipeline.current_zone)
        for key, button in getattr(self, "mode_buttons", {}).items():
            try:
                button.configure(**looks[key])
            except Exception:
                pass

    def change_zone(self, zone):
        result = self.pipeline.change_zone(zone)
        self._append_output(result)
        self._refresh_mode_buttons()
        self.status_label.configure(text=self.pipeline.get_status())

    def show_help(self):
        help_text = """
Available Commands:
/status          → Show current mode and context count
/lexicon         → Show the operator token lexicon
/mode green      → Switch to Green mode (active)
/mode yellow     → Switch to Yellow mode (analytical)
/mode red        → Switch to Red mode (archival)
/clear           → Clear the window and the recalled context (Ctrl+L)
                   (Ctrl+A selects all of whatever box has focus)
/help            → Show this help

🔊 Read speaks the last answer. Tick "Auto" beside it and every answer
is read aloud as it arrives — the 🐢/🐇 picker sets the speed, and the
button becomes ■ Stop while it is talking.

Speaking punctuation while you dictate (🎤):
  "period" "comma" "colon" "semicolon"      → . , : ;
  "question mark" "exclamation point"       → ? !
  "new line" "new paragraph"                → line breaks
  "open paren" / "close paren", "open quote" / "close quote"
  "dollar sign", "percent sign", "ellipsis"
  "cap <word>"          → capitalise the next word
  "caps on" ... "caps off"      → Title Case A Span
  "all caps on" ... "all caps off"  → SHOUT

Say them naturally — if the recogniser already heard the pause and
punctuated it for you, the duplicate is cleaned up automatically.
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
