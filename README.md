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
inference pipeline with a native desktop window, built to demonstrate how a
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

## Features (v2.0.0)

- **Chat console** with reading fonts (Atkinson Hyperlegible,
  OpenDyslexic when installed), adjustable text size, persisted
  preferences.
- **Voice both ways**: 🎤 push-to-talk Whisper dictation
  (faster-whisper, Fast/Accurate/Best) and 🔊 read-aloud. While an
  answer is spoken the current sentence is highlighted and the current
  word underlined; click any sentence to hear it again from there, and
  tick **Auto** to have every answer read as it arrives.
- **Spoken punctuation** while dictating — "period", "question mark",
  "new line", "cap", "caps on/off", "all caps on/off". Whisper's own
  auto-punctuation is de-duplicated against what you say, so a spoken
  mark landing on one it already inserted collapses to a single mark.
- **Read-aloud speaks English, not markup** — markdown is stripped and
  numbers, money, percents, ordinals, years and abbreviations are
  expanded before the text reaches the voice. Inline `code` is held
  atomic so a file path is not read as arithmetic.
- **Keyboard throughout** — every control is a real `<button>` or
  `<input>`, so Tab reaches all of them and `:focus-visible` shows
  where you are. **Enter** sends, **Shift+Enter** starts a new line,
  **Ctrl+L** clears, **Escape** stops reading.
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

  All three persist: an attached file and a ticked box stay in force
  for the rest of the conversation, so the material can be discussed
  over many turns rather than consulted once. The rule deciding what
  gets handed to the model lives in `strata_tools/context_sources.py`
  as a tested kernel rather than inside the shell. Each answer carries
  a `Read:` line naming the sources actually consulted.
- **Slash commands** — `/status`, `/lexicon`, `/mode green|yellow|red`,
  `/clear`, `/help`; `/zone` and `/new` still accepted. The grammar is
  a kernel too (`strata_tools/commands.py`), so an unknown command is
  reported rather than quietly answered by the model.
- **Graceful degradation** — if Ollama or the model is missing, the
  deterministic template engine answers and the UI says so honestly.

## Quick start

```powershell
# 1. Get the code
git clone https://github.com/coconuthead-Sentinel-core/strata-console.git
cd strata-console

# 2. The shell (Edge WebView2 is already on Windows; no browser or
#    server is installed, and no port is opened)
py -3 -m pip install pywebview

# 3. Optional — voice and file features enable themselves when present
py -3 -m pip install ollama faster-whisper sounddevice python-docx pypdf openpyxl beautifulsoup4

# 4. The local model (one-time)
ollama pull llama3.2:3b

# 5. Run it
py -3 strata_web.py
```

### One shell over one engine

`strata_core.py` is the engine — SQLite store, the five pipeline stages,
the model client — and it imports no user-interface library at all. One
shell sits on top of it:

| | Launch | What it is |
| --- | --- | --- |
| **Strata Console** | `launch_strata.vbs` — desktop and Start-menu icon **Strata Console** | HTML/CSS/JS in a native WebView2 window via pywebview. |

Start-menu shortcuts live in
`%APPDATA%\Microsoft\Windows\Start Menu\Programs`.

> Renaming or moving a launcher orphans its shortcut. `launch_strata.vbs`
> has **two** shortcuts pointing at it — one on the desktop, one in the
> Start menu — so if it moves, repoint both. This is why the file kept
> its name when the shell behind it was replaced.

### "It launched but it just says wait"

Not a fault. Measured on this laptop (8 GB RAM, no GPU):

| | Time |
| --- | --- |
| Window open, controls live | **0.01s** |
| First reply, model **cold** | **~20s** — Ollama reads 2.3 GB into RAM |
| Replies once **warm** | **~3s** |

Ollama drops the model after `keep_alive` (10 minutes), so the 20-second
load comes back on its own. Nothing is stuck; something large is being
read from disk.

Two things were changed so that wait is never mistaken for a hang again:

1. **The model is warmed at startup.** A background thread loads it as
   soon as the window opens, while the opening message is still being
   read — so the cost is paid before anything is asked of it. Measured
   effect: first user message went from **20.5s to 6.3s**. The console
   says `🧠 Warming the local model — about 20 seconds, once.` and then
   `🧠 Model ready`.
2. **The wait counts out loud.** The placeholder ticks — `thinking
   (local model)… 7s` — and when the model is genuinely cold it says so
   instead: `loading the local model — first message, about 20 seconds…
   12s`. A number that changes is the difference between an application
   that is working and one that has frozen; a static placeholder for
   twenty seconds is indistinguishable from a crash, and the owner read
   it that way, correctly.

**If replies take a minute or more, it is memory, and the header says
so.** Free RAM is shown at the top right at all times, and at startup
the console says plainly when the machine is short — with the numbers:

> ⚠ Low memory: 1,277 MB free, and llama3.2:3b wants about 2,225 MB —
> 948 MB short. Replies will be slow (measured: 3 s with room, over
> 100 s without). Close other programs, or switch to the lighter
> llama3.2:1b.

Measured on this 8 GB laptop, same code and same question: **2.9 s**
with 978 MB free, **103 s** with 475 MB free and 3.3 GB in the pagefile.
The app is the same at both readings; the machine is not. Closing a
browser, Claude Code, or Voice Access typically returns over a gigabyte.
The lighter model is a one-time `ollama pull llama3.2:1b` and roughly
halves the requirement.

If it stays on `loading…` well past a minute, check the daemon:

```bash
curl http://127.0.0.1:11434/api/ps
```

An empty `models` list plus a climbing counter means Ollama is still
loading. No response at all means the daemon is not running, and the
console will say `🧩 template mode` rather than pretending.

#### Why the CustomTkinter console was retired (2026-09-01)

The project ran two interchangeable shells for a day so they could be
compared on the owner's real screen. The comparison ended: the HTML shell
won, and carrying a second one was paying maintenance twice for a
competition already decided.

What HTML gave for free that the Tk console needed written by hand:
keyboard operation, a visible focus indicator, whole-interface text
resize, content that scrolls rather than silently not being drawn, and a
68-character reading column — the measurement the Tk console reported at
~53 characters and could not fix without shrinking the font. Three of the
project's recorded defects (FB-001, FB-005, FB-006) exist because a Tk
widget was drawn off-screen or unreachable; CSS does not have that
failure mode.

Retirement was gated on **parity, not preference**. The Tk console
understood slash commands and could show the operator token lexicon; the
web shell could not. Those were ported and tested first
(`strata_tools/commands.py`), and only then was the console removed. What
went with it: `strata_console.py`, the Tk-only kernels
(`layout.py`, `window_fit.py`, `selection.py`), their tests, and the five
CustomTkinter measuring tools under `tools/`. Nothing is lost — it is all
in the history at tag-worthy commit depth, and `git log -- strata_console.py`
still reads.

The shell is local-first: no port is opened and no server runs —
pywebview loads the page from disk and bridges to Python in-process.
Microphone capture and Whisper transcription stay in Python, because the
interpreter rule and the RAM budget (FB-002) were expensive to learn and
there is nothing to gain by re-learning them in JavaScript.

What the change does **not** do is alter the assistant. Same model, same
prompts, same answers, same database.

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
