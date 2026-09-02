# Changelog — Strata Console

All notable changes to this project. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Reconstructed 2026-09-01 from the commit history, then maintained
forward. Defect entries link to `docs/FORMER_BUGS.md`, which carries the
root cause and the guard.

---

## [1.5.0] — 2026-09-02

### Added
- **The three context sources reach the web shell**: 🌐 web search,
  ☁ OneDrive files and 📎 upload, which until now only the desktop
  shell had. Both stay switched on across turns, which is the point —
  the material can be discussed over a whole conversation rather than
  consulted once. Typing "look this up" still turns the web on for a
  single message without touching the checkbox.
- **Answers say what they read.** A `Read: 📎 lease.pdf · 🌐 web` line
  under a reply reports which sources were actually consulted. Without
  it there is no way to tell a grounded answer from the model answering
  confidently out of its own head.
- **`strata_tools/context_sources.py`** — the rule for what the model is
  handed, lifted out of `strata_console.py` into a pure, headless-tested
  kernel that both shells now call. 28 tests. It had been UI code no
  test could reach, and copying it into the second shell would have
  produced two rules that agreed until the first edit.

### Fixed
- **The web shell's note channel was never connected.** `Api` exposed
  `memory_note()` and no page ever called it, so the voice-model release
  watch — which does real work and frees ~221 MB — reported to nobody.
  Replaced with `poll_notes()`, a drained queue the page polls every
  five seconds, now shared with OneDrive indexing. A method the UI never
  calls is the bridge equivalent of a button that does nothing.
- **The web-search trigger phrases were never tested.** Eleven phrases
  shipped inside the Tk shell with no coverage; a dead entry among them
  would have been invisible. Each one is now asserted to fire.

### Guarded
- `tests/test_web_shell.py` imports the bridge and checks that **every**
  `api.*` call in `app.js` resolves to a real method on `Api`. A method
  indented one level wrong greps clean and fails at runtime as a
  rejected promise, which the page shows as nothing happening.
- The upload dialog's filter is asserted equal to `doc_index.SUPPORTED`,
  so the dialog can never offer a format the extractor cannot open.

## [1.4.1] — 2026-09-02

### Added
- **Read-along highlighting** in the web shell. While an answer is read
  aloud the sentence being spoken is highlighted and the current word is
  underlined, so the text can be followed by eye and by ear at once.
  Click any sentence to hear it again from that point; Escape stops.

  The alignment problem, and how it is solved: what is *spoken* is not
  always what is *shown* — `speech.speakable()` turns "$32" into
  "thirty-two dollars" so the engine pronounces it. The page therefore
  splits the **rendered** text and Python returns each piece's spoken
  form plus a `matches` flag. Sentence highlighting is exact because
  both sides index one array. Word highlighting uses the engine's
  character offsets, which only point into the displayed string when
  `matches` is true — otherwise it is skipped rather than lighting up
  the wrong word.

  Verified in a browser harness: a sentence running across `**bold**`
  stays one highlight over three spans; code blocks are excluded from
  what is read; every character offset maps to the correct word,
  including across an element boundary.

  Both highlight colours keep the body text above 4.5:1 (8.04:1 and
  6.04:1 measured), and the current word carries an underline as well as
  a background, so the two levels are not distinguished by colour alone.

---

## [1.4.0] — 2026-09-02

A second shell, and the engine split out so both can share it.

### Added
- **`strata_core.py`** — the engine with no interface attached: the
  SQLite store, the five pipeline stages, the model client. Imports no
  Tk and nothing that assumes a window.
- **`strata_web.py` + `web/`** — an HTML/CSS/JS front end in a native
  WebView2 window (pywebview). Same database, same modes, same voice
  path, same Ollama daemon. Launch with `launch_strata_web.vbs`.
- Auto-read, spoken punctuation, the clear floor and the RAM budget all
  work in both shells because they were already kernels.
- `tests/test_web_shell.py` — 18 tests that parse the real stylesheet and
  markup, so the two shells cannot drift into different palettes or
  different accessibility stories.

### Fixed
- Auto-read for the desktop shell, and its template-mode path, which had
  never set `_last_reply` and so replayed the previous answer.
- Buttons: FB-007. Every control failed WCAG 1.4.11 against its frame.

### Notes
- **The Tk shell is unchanged and still the default.** This is a
  comparison, not a replacement. Nothing was thrown away.
- What HTML gave for free that Tk needed written by hand: keyboard
  operation, a visible focus ring, whole-interface text resize, content
  that scrolls instead of silently not being drawn, and a 68ch reading
  column — the measurement the Tk shell reported at ~53 characters and
  could not fix.
- What it does **not** do: make the assistant smarter. Same model, same
  prompts, same answers.

---

## [1.3.0] — 2026-09-01

The accessibility pass. Planned in `docs/ACCESSIBILITY_PLAN.md`, which
also sets out honestly which standards actually bind a personal desktop
tool (none) and which one we hold to anyway (WCAG 2.1 AA, plus the
cognitive criteria added in 2.2).

### Fixed
- **Thirteen controls were never drawn**, including the transcript —
  FB-005. The chrome needed 919px in a 486px window and Tk silently
  stopped mapping children. Verified pre-existing at commit `807c5ba`.
- **Every button was unreachable by keyboard** — FB-006. The real Tab
  ring held 2 widgets of 22. WCAG 2.1.1, Level A.
- `StrataDB` resolved `DB_PATH` as a default argument, so tools that
  redirected it still wrote to the real database — NM-005.

### Added
- **Keyboard operation** for every control, with Return and Space, and a
  visible focus ring whose colour clears 3:1 on every surface it can
  land on (`strata_tools/keyboard.py`).
- **Colour-coded modes** — green, amber and red, each measured against
  the label text at AA. The active mode also carries a bullet and a
  border, so colour is never the only cue (WCAG 1.4.1).
- **App-wide text scaling**: A+/A− now moves 22 widgets instead of 2,
  with the chrome capped at a measured 12pt so growing text cannot
  re-hide controls.
- `strata_tools/layout.py` — content-fits-the-window as a tested kernel;
  `tools/a11y_check.py` and `tools/layout_probe.py` as benches.

### Changed
- The decorative title banner is gone (the window title bar already said
  it) and status moved into the row below — one fewer stacked row.
- The dyslexia-font comment in `strata_console.py` was **corrected**: the
  research does not support the claim it made. The font menu stays,
  because reader *choice* is the intervention that is supported.

### Known
- Reading width is ~53 characters against BDA guidance of 60–80. Short
  rather than long, and reported rather than forced.

---

## [1.2.0] — 2026-09-01

The completion pass. Every capability the console already advertised now
works end to end, and the engineering apparatus that proves it is in
place. Planned in `docs/BUILD_PLAN.md`; the transfer that supplied the
material is catalogued in `docs/TRANSFER_CATALOG.md`.

### Added
- **Clear** — button, `/clear` (and `/new`), or **Ctrl+L**. Empties the
  transcript *and* the context the model recalls. Nothing is deleted: a
  floor is raised in `system_state` and the rows stay in SQLite
  (`strata_tools/session.py`).
- **Spoken punctuation for dictation** — "period", "comma", "question
  mark", "new line", "cap", "caps on/off", "all caps on/off" and the
  rest become real characters, with recogniser collisions resolved
  (`strata_tools/dictation.py`). Listed in `/help`.
- **A speech front end for read-aloud** — markdown stripped, then
  numbers, money, percents, ordinals, years and abbreviations expanded,
  with inline code held atomic (`strata_tools/speech.py`).
- **Continuous integration** — `py_compile` plus the unit suite on
  Windows against Python 3.11 and 3.13, every push and pull request,
  including a degraded-mode import check that proves the console still
  starts with nothing optional installed.
- **A design-law linter** with three rules, each earned by a real
  defect, gated over the whole repository inside the test suite
  (`strata_tools/design_laws.py`).
- **`requirements.txt`** — a documented runtime, carrying the
  two-interpreters warning at the top.
- **Documentation set** — `docs/SCOPE.md`, `docs/BUILD_PLAN.md`,
  `docs/TRANSFER_CATALOG.md`, `docs/FORMER_BUGS.md`, this changelog.
- **Ctrl+A** selects all of whichever box has focus
  (`strata_tools/selection.py`).
- **WCAG contrast audit** of the console's real palette, read from the
  CustomTkinter theme (`strata_tools/wcag.py`).

### Changed
- Window sizing moved from inline arithmetic to a tested kernel
  (`strata_tools/window_fit.py`). **Behaviour is byte-identical** —
  verified at 999×486+30+20 before and after.
- `/status` now counts the threads still in play rather than every row
  ever written, so it agrees with what the model can actually see.

### Fixed
- **Dictation returned unpunctuated text** — FB-003.
- **Read-aloud spoke the markdown** — FB-004.

### Known and accepted
- Two colour pairs miss WCAG AA: the default button at 4.47:1 (against
  4.5 — CustomTkinter's stock theme) and the recording-state red at
  3.77:1. Reported rather than recoloured, with reasons, in
  `wcag.ACCEPTED_SHORTFALLS`. The recording red also changes its label
  to "Stop", so state is not carried by colour alone.

### Decided against
- **`platform_dpi` (DPI awareness)** — declined on measurement, not
  preference. It would drop the window from 91% to 52% of screen width.
  See NM-002; reproduce with `tools/dpi_check.py --aware`.
- **`prompt_coach`, `prompt_archive`, `legibility` presets, the BM25
  retrieval swap, `readability`, `doc_writer`, `stt_command`** — all
  would change the console's design or duplicate Imprint. Recorded in
  `docs/TRANSFER_CATALOG.md` so each is a decision, not an oversight.

---

## [1.1.1] — 2026-08-31

### Fixed
- **The microphone was dead for weeks and the hardware was fine** — the
  launcher was starting a Python without the voice packages installed.
  FB-002. The launcher now prefers an interpreter that carries them, and
  `cscript //nologo launch_strata.vbs /which` reports its choice.

---

## [1.1.0] — 2026-08-23

### Added
- Voice-path bench check (`tools/voice_check.py`) running capture, RAM
  budget and transcription as separate stages.
- Sentinel-style dockable toolbar: 🎤 dictation with Fast/Accurate/Best
  tiers, 🔊 read-aloud with a 🐢/🐇 speed picker, ❓ guided tour.
- Context sources: 🌐 web search, ☁ OneDrive document indexing,
  📎 single-file upload.

### Fixed
- Whisper model loading exhausted RAM alongside Ollama and died inside
  MKL. Each tier's peak working set is now measured and budgeted against
  free RAM, and only one model is ever resident
  (`strata_tools/voice_budget.py`).

---

## [1.0.0] — 2026-07-06

Initial baseline as running on the laptop: the five-stage local-first
NLP pipeline, SQLite context store, operating modes, slash commands, and
dyslexia-friendly reading fonts, answered by a local model via Ollama
with a deterministic template fallback.
