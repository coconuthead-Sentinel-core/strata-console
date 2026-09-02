# Scope Statement — Strata Console

> Written per the `scope-first` skill: reconstructed from the shipped
> truth of this repository. From baseline, work is checked against this
> document; changes to it are explicit logged decisions, never drift. Standards frame:
> ISO/IEC/IEEE 12207 · SWEBOK · IEEE 29148.
>
> _Drafted 2026-08-31 · **Baselined 2026-09-01** on the owner's
> instruction to complete the build · Owner: Shannon Brian Kelley
> (architect / QA) · Maintainers: owner + AI coding assistant._

## 1. In scope

- A **local-first NLP console** for one user on Windows: a chat
  workspace over an onboard language model (Ollama / llama3.2), with
  operating modes, a persistent SQLite context store, and slash
  commands.
- **Voice both ways**: push-to-talk Whisper dictation with a RAM-budgeted
  model tier, and read-aloud of the assistant's replies.
- **Context sources the model never reaches directly**: web search,
  OneDrive document indexing, and single-file upload — each gathered by
  the console and passed in as text.
- **Accessibility-first presentation**: dyslexia-friendly reading fonts
  (OpenDyslexic when installed), adjustable text size, persisted
  preferences, a dockable toolbar.
- **The engineering discipline**: a pure functional core in
  `strata_tools/` with headless tests, a documented runtime and
  interpreter rule, and honest owner-facing failure messages.
- Capability transferred from Sentinel Forge per
  [`TRANSFER_CATALOG.md`](TRANSFER_CATALOG.md), phase by phase, each
  port owing tests in this repository before its UI is wired.

## 2. Out of scope (explicit)

- **Personal-development features.** Habits, goals, streaks, spaced
  repetition, gamification, finance, bills, and appointment reminders
  stay in Sentinel Forge. This is a standing decision, not a backlog
  item.
- **Cloud services, accounts, or telemetry.** The model runs locally.
  Web search is opt-in per message and degrades gracefully when off.
- **Multi-user, sync-server, or mobile** versions.
- **macOS / Linux ports.** The launcher, DPI handling, and TTS are
  Windows-specific by design.
- **Non-stdlib runtime dependencies for core logic.** `strata_tools/`
  stays standard-library only; parsers, voice, and the model client are
  optional and degrade gracefully when absent.
- **A second document-authoring product.** Writing real Word and Excel
  files is Imprint's job unless that overlap is explicitly resolved.

## 3. Acceptance criteria (how "done" is known)

- Every feature ships as a **pure kernel first**, with headless tests
  green **before** any UI is wired.
- **A control that does nothing is a defect.** Every button, command,
  and shortcut performs its full action — including the parts the owner
  cannot see. (Clearing the window also clears what the model recalls;
  clearing only the view would be a defect of this kind.)
- **Archive, never delete.** No owner data is destroyed by any control.
  Where something disappears from view, it remains in SQLite.
- **Failure messages must be actionable and true.** Any "missing
  dependency" message names `sys.executable` and a command pinned to it.
- The full suite is green at every merge to `main`, proven by CI on
  Python 3.11 and 3.13. _(In place: `.github/workflows/ci.yml`.)_
- **No shipped source violates a design law.** The linter runs inside
  the suite, so a violation fails the build rather than shipping
  (`strata_tools/design_laws.py`).
- **Every defect is recorded with its guard** in `docs/FORMER_BUGS.md`.
  A fix without a guard is a defect waiting for its second appearance.
- The owner can perform each shipped workflow on his real ~1097x617
  effective display.
- The worktree, the live install, and GitHub agree at the same commit.

## 4. Lifecycle target

- **Horizon: 5-10 years** as a daily-use tool, single owner, maintained
  by owner + AI assistant.
- **Stack chosen for that horizon**: CPython + SQLite, with Ollama as a
  replaceable model backend, and **one shell** over one engine
  (`strata_core.py`): HTML/CSS/JS in a WebView2 window. The engine
  imports no UI library, which is what made replacing the front end
  cheap instead of existential — and that claim is no longer
  theoretical: a shell was swapped out on 2026-09-01 and the engine did
  not change.
- **Documented runtime**: Python 3.13 on this laptop, targeting 3.11+.
  The interpreter rule is enforced by `strata_tools/interpreter.py` and
  `launch_strata.vbs`, because two Python installs on one machine is the
  defect that took dictation down.
- **Rebuildability**: the README plus a future `Rebuild-Blueprint.md`
  and `Database-Schema.md` must stay sufficient for a from-scratch
  reconstruction. At ~1,300 lines this is achievable and cheap now.

## 5. Named structural risks

| Risk | Seam / mitigation |
| --- | --- |
| ~~`strata_console.py` is a single ~1,300-line file mixing pipeline, DB, and Tk shell.~~ | **Closed 2026-09-01** — the file is gone with the Tk shell. The habit it warned about is not: `strata_web.py` is the shell now and must not become the same thing. Every rule it needs goes to `strata_tools/` as a tested kernel first (`context_sources.py`, `commands.py` were both extracted this way, not written in place). |
| Two Python interpreters on the laptop, only one carrying the voice packages. | Fixed and tested (`interpreter.py`), but the machine can drift again. `cscript //nologo launch_strata.vbs /which` is the check. |
| ~~CustomTkinter multiplies window geometry by display scaling (~1.75x here).~~ | **Closed permanently 2026-09-01** — the risk left with the toolkit. It cost this project FB-001, FB-005 and NM-002 before it was tamed, and the tested kernel that tamed it (`window_fit.py`) was retired alongside the shell it served. The WebView2 window sizes itself as a fraction of the screen and CSS reflows rather than refusing to draw. |
| Whisper and Ollama compete for RAM on an 8 GB laptop. | Handled: `voice_budget.py` plans a tier against free RAM and stops rather than dying inside MKL. |

## 6. Change log for this scope

| Date | Change | Decision |
| --- | --- | --- |
| 2026-08-31 | Document drafted from shipped truth; personal-development features declared permanently out of scope. | Superseded by the row below. |
| 2026-09-01 | Baselined. Seven completion gaps closed (see `docs/BUILD_PLAN.md`). Three acceptance criteria added: design-law gate, defect register, CI. | Owner instruction: complete the build. |
| 2026-09-01 | DPI awareness declined on measurement; seven donor modules declined as design-changing. | Recorded in `docs/TRANSFER_CATALOG.md` and `docs/FORMER_BUGS.md` NM-002 — decisions, not oversights. |
| 2026-09-01 | **Two shells → one.** The CustomTkinter console is retired; the HTML/CSS/JS shell is the only shell. §4 amended. | **Owner decision**, asked for directly: "get rid of the tkinter shell… that way there is only one." Gated on parity, not preference — slash commands and the operator token lexicon existed only in the Tk console and were ported and tested (`strata_tools/commands.py`) *before* it was removed. Carrying two front ends meant paying maintenance twice for a comparison that had already concluded. |
| 2026-09-01 | CustomTkinter dropped from required dependencies; Tk-only kernels (`layout.py`, `window_fit.py`, `selection.py`) and the five CustomTkinter measuring tools removed with the shell they measured. | Consequence of the row above. Design-law rules A and B are **kept but re-scoped** — they can no longer fire on the shipped shell, so `design_laws.py` now says so plainly rather than letting them read as ongoing proof. |
