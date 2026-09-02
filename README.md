# Strata Console — a local-first NLP inference pipeline

> A native Windows desktop console that runs a staged natural-language
> pipeline over a fully local language model (Ollama / llama3.2:3b).
> 100% local-first: the only network calls are the loopback to the
> Ollama daemon and the user-invoked 🌐 web search. No cloud AI API,
> no keys, no telemetry.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)

## What it is

Strata Console is an applied systems-engineering project: a five-stage
inference pipeline with a desktop shell, built to demonstrate how a
small local model becomes genuinely useful when the *application layer*
does the heavy lifting — routing, context management, retrieval, and
honest fallbacks.

**Pipeline stages** (each a plain Python class, testable in isolation):

| Stage | Responsibility |
| --- | --- |
| Input classifier | Tokenizes the message, extracts operator tags |
| Dispatcher | Routes by intent and operating mode |
| Context manager | Retrieves recent conversation threads (SQLite) |
| Style conditioner | Adjusts tone per operating mode (GREEN/YELLOW/RED) |
| Response synthesizer | Local LLM reply, with a deterministic template fallback |

The **operating modes** trade boldness for care: GREEN (active,
temperature 0.8) → YELLOW (analytical) → RED (archival, 0.3). Mode
persists across restarts.

**RAM-safe by design:** the model's context window is pinned
(`num_ctx=2048`) so the KV cache fits an 8 GB laptop — the documented
lesson being that llama3.2's 128K default tries to allocate ~15 GB and
fails. `keep_alive` keeps the model warm between messages.

The same discipline governs dictation. Each Whisper tier's peak working
set was measured (Fast 320 MB, Accurate 671 MB, Best 1415 MB), only one
model is ever resident, and `strata_tools/voice_budget.py` checks free
RAM before loading — falling back a tier and saying why, rather than
dying inside MKL. `tools/voice_check.py` runs capture, budget, and
transcription as separate stages so a voice problem can be attributed to
the right one.

That attribution has one prior stage, learned the hard way. Dictation
once failed with nothing wrong with the microphone, the RAM budget, or
Whisper: the launcher started the Windows Store Python while
`sounddevice` and `faster-whisper` were installed in the ordinary
per-user Python, so the import failed and the owner read it as a dead
mic. The bench missed it because `py -3` resolved to the *other*
interpreter and passed. `strata_tools/interpreter.py` now holds that
rule in pure, tested form: `launch_strata.vbs` prefers an interpreter
that actually carries the voice packages, `tools/voice_check.py` reports
which interpreter it is running under and which one a double-click would
use, and the console's own error names `sys.executable` and the exact
pip line for it -- because a bare `pip install` resolves elsewhere,
answers "Requirement already satisfied", and changes nothing.

## Features (v1.1)

- **Chat console** with dyslexia-friendly reading fonts (OpenDyslexic
  when installed), adjustable text size, persisted preferences.
- **Toolbar** (dockable — pop it out to float on top): 🎤 push-to-talk
  Whisper dictation (faster-whisper, Fast/Accurate/Best), 🔊 read the
  last reply aloud with a 🐢/🐇 speed picker, ❓ step-by-step guided
  tour.
- **Spoken punctuation** while dictating — "period", "question mark",
  "new line", "cap", "caps on/off", "all caps on/off". Whisper's own
  auto-punctuation is de-duplicated against what you say, so a spoken
  mark landing on one it already inserted collapses to a single mark.
- **Read-aloud speaks English, not markup** — markdown is stripped and
  numbers, money, percents, ordinals, years and abbreviations are
  expanded before the text reaches the voice. Inline `code` is held
  atomic so a file path is not read as arithmetic.
- **Ctrl+A** selects all of whichever box has focus.
- **Clear** (button, `/clear`, or Ctrl+L) empties the transcript *and*
  the context the model recalls. Both halves move together: clearing
  only the view would leave the assistant quoting the conversation you
  just cleared. Nothing is deleted -- a floor is raised in
  `system_state` and the rows stay in SQLite.
- **Context sources** the model itself never touches directly:
  - 🌐 **Web search** — checkbox or natural phrasing ("search the web
    for …"); DuckDuckGo lite via the standard library, no API key.
  - ☁ **OneDrive files** — a cached, read-only index of the user's
    synced documents (.docx/.pdf/.xlsx/.csv/.md/.txt/.html).
  - 📎 **Upload document** — attach any readable file; the console
    retrieves the passages relevant to each question.

  All three are available in **both shells**, and all three persist:
  an attached file and a ticked box stay in force for the rest of the
  conversation, so the material can be discussed over many turns rather
  than consulted once. The rule deciding what gets handed to the model
  lives in `strata_tools/context_sources.py` — one tested kernel, not a
  copy per shell. In the web shell each answer carries a `Read:` line
  naming the sources actually consulted.
- **Graceful degradation** — if Ollama or the model is missing, the
  deterministic template engine answers and the UI says so honestly.

## Quick start

```powershell
# 1. Get the code
git clone https://github.com/coconuthead-Sentinel-core/strata-console.git
cd strata-console

# 2. Dependencies (the console runs on the stdlib + customtkinter;
#    voice and file features enable themselves when their libs exist)
py -3 -m pip install customtkinter ollama faster-whisper sounddevice python-docx pypdf openpyxl beautifulsoup4

# 2b. Optional — only for the web shell (uses the Edge WebView2 runtime
#     Windows already ships; no browser or server is installed)
py -3 -m pip install pywebview

# 3. The local model (one-time)
ollama pull llama3.2:3b

# 4. Run it
py -3 strata_console.py
```

### Two shells, one engine

`strata_core.py` is the engine — SQLite store, the five pipeline stages,
the model client — and it imports no user-interface library at all. Two
shells sit on top of it:

| | Launch | What it is |
| --- | --- | --- |
| **Desktop** (default) | `launch_strata.vbs` — desktop icon **Strata Console** (violet tile, ⚡) | CustomTkinter. The shipped, tested one. |
| **Web** | `launch_strata_web.vbs` — desktop icon **Strata Console (Web)** (dark tile, blue **W**) | HTML/CSS/JS in a native WebView2 window via pywebview. Adds read-along highlighting, and reports which sources each answer read. |

The two icons differ by colour and glyph, not only by name: they sit side
by side on the desktop, and telling them apart should not require reading
the label. `make_icons.py` generates them.

Both also appear in the **Start menu** under **S**, with wordmark icons
that differ by lettering colour — **white** for the desktop console,
**gold** for the web shell — because in an alphabetical list the two
names sit directly on top of each other and reading the label is the
slow way to tell them apart.

Start-menu shortcuts live in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs`.

> Renaming or moving a launcher orphans its shortcut. Each `.vbs` now has
> **two** shortcuts pointing at it — one on the desktop, one in the Start
> menu — so if a launcher moves, repoint both.

Both use the **same database, modes, voice path, context sources and
Ollama daemon**. Neither is a rewrite of the other; the web shell
exists to be compared against.

As of 1.5.0 the comparison is fair: the web shell has the same three
context sources as the desktop one. What made that safe was moving the
rule into `strata_tools/context_sources.py` rather than copying it —
duplicating logic across shells is how "two shells, one engine" stops
being true, one edit at a time.

The web shell is still local-first: no port is opened and no server runs
— pywebview loads the page from disk and bridges to Python in-process.
Microphone capture and Whisper transcription stay in Python, because the
interpreter rule and the RAM budget (FB-002) were expensive to learn and
there is nothing to gain by re-learning them in JavaScript.

What HTML gave for free that the desktop shell needed written by hand:
keyboard operation, a visible focus indicator, whole-interface text
resize, content that scrolls rather than silently not being drawn, and a
68-character reading column — the measurement the desktop shell reports
at ~53 characters and cannot fix without shrinking the font.

What it does **not** do is change the assistant. Same model, same
prompts, same answers.

Or double-click `launch_strata.vbs` for a no-console launch. It resolves
a real `pythonw.exe` by full path (so the Store alias, which does not
resolve when a script starts it, is never used) and prefers an
interpreter that already has the voice packages installed.

To see which interpreter a double-click would actually use:

```powershell
cscript //nologo launch_strata.vbs /which
```

## Tests

```powershell
py -3 -m unittest discover -s tests
```

Covers the context tools (cached file indexing including Excel
extraction and repo-directory exclusion, and the pure retrieval ranking)
and the voice path (capture-level verdicts, the Whisper RAM budget, and
the interpreter rule that decides whether dictation can run at all),
spoken punctuation, the read-aloud front end, window sizing, WCAG
contrast, and the design-law linter — which is gated over the whole
repository from inside the suite, so a violation fails the build.

CI runs the same suite on Windows against Python 3.11 and 3.13 on every
push and pull request, plus a degraded-mode import check that proves the
console still starts with nothing optional installed.

Engineering records live in `docs/`: [SCOPE.md](docs/SCOPE.md) (baselined),
[BUILD_PLAN.md](docs/BUILD_PLAN.md), [FORMER_BUGS.md](docs/FORMER_BUGS.md)
— every defect with the guard that now prevents it — and
[TRANSFER_CATALOG.md](docs/TRANSFER_CATALOG.md), which records what was
taken from Sentinel Forge and, just as deliberately, what was not.

## Honest scope

This is applied systems engineering, not novel research. The model is a
small 3B-parameter LLM; the engineering value is in the pipeline
around it — retrieval, mode control, RAM discipline, accessibility, and
graceful fallbacks. Environment overrides: `STRATA_NUM_CTX`,
`STRATA_KEEP_ALIVE`, `STRATA_INDEX_DIR`.

## License

MIT — see [LICENSE](LICENSE).

## Author

**Shannon Brian Kelley** ·
[github.com/coconuthead-Sentinel-core](https://github.com/coconuthead-Sentinel-core)

> Healthcare CNA → AI Systems Developer transition · neurodivergent-first
> design · accessibility-focused AI engineering.
