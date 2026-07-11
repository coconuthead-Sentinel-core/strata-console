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

## Features (v1.1)

- **Chat console** with dyslexia-friendly reading fonts (OpenDyslexic
  when installed), adjustable text size, persisted preferences.
- **Toolbar** (dockable — pop it out to float on top): 🎤 push-to-talk
  Whisper dictation (faster-whisper, Fast/Accurate/Best), 🔊 read the
  last reply aloud with a 🐢/🐇 speed picker, ❓ step-by-step guided
  tour.
- **Context sources** the model itself never touches directly:
  - 🌐 **Web search** — checkbox or natural phrasing ("search the web
    for …"); DuckDuckGo lite via the standard library, no API key.
  - ☁ **OneDrive files** — a cached, read-only index of the user's
    synced documents (.docx/.pdf/.xlsx/.csv/.md/.txt/.html).
  - 📎 **Upload document** — attach any readable file; the console
    retrieves the passages relevant to each question.
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

# 3. The local model (one-time)
ollama pull llama3.2:3b

# 4. Run it
py -3 strata_console.py
```

Or double-click `launch_strata.vbs` for a no-console launch (resolves a
real Python interpreter, avoiding the Windows Store stub).

## Tests

```powershell
py -3 -m unittest discover -s tests
```

Covers the context tools: cached file indexing (including Excel
extraction and repo-directory exclusion) and the pure retrieval
ranking.

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
