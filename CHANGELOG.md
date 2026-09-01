# Changelog — Strata Console

All notable changes to this project. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Reconstructed 2026-09-01 from the commit history, then maintained
forward. Defect entries link to `docs/FORMER_BUGS.md`, which carries the
root cause and the guard.

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

### Changed
- Window sizing moved from inline arithmetic to a tested kernel
  (`strata_tools/window_fit.py`). **Behaviour is byte-identical** —
  verified at 999×486+30+20 before and after.
- `/status` now counts the threads still in play rather than every row
  ever written, so it agrees with what the model can actually see.

### Fixed
- **Dictation returned unpunctuated text** — FB-003.
- **Read-aloud spoke the markdown** — FB-004.

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
