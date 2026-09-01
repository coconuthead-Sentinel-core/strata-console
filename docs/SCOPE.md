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
- **Stack chosen for that horizon**: CPython + Tkinter (via
  CustomTkinter) + SQLite, with Ollama as a replaceable model backend.
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
| `strata_console.py` is a single ~1,300-line file mixing pipeline, DB, and Tk shell. | Small today. The seam is the `StrataDB` / pipeline-node boundary — each node lifts into `strata_tools/` on the existing pattern. Named here while it is cheap; this is the trap that produced Sentinel's 28k-line shell. |
| Two Python interpreters on the laptop, only one carrying the voice packages. | Fixed and tested (`interpreter.py`), but the machine can drift again. `cscript //nologo launch_strata.vbs /which` is the check. |
| CustomTkinter multiplies window geometry by display scaling (~1.75x here). | **Closed.** The compensation is now a tested kernel (`window_fit.py`), the invariant is swept in tests, and design-law rule B fails the build on a hardcoded size. DPI awareness was measured and declined — it would halve the window (NM-002). |
| Whisper and Ollama compete for RAM on an 8 GB laptop. | Handled: `voice_budget.py` plans a tier against free RAM and stops rather than dying inside MKL. |

## 6. Change log for this scope

| Date | Change | Decision |
| --- | --- | --- |
| 2026-08-31 | Document drafted from shipped truth; personal-development features declared permanently out of scope. | Superseded by the row below. |
| 2026-09-01 | Baselined. Seven completion gaps closed (see `docs/BUILD_PLAN.md`). Three acceptance criteria added: design-law gate, defect register, CI. | Owner instruction: complete the build. |
| 2026-09-01 | DPI awareness declined on measurement; seven donor modules declined as design-changing. | Recorded in `docs/TRANSFER_CATALOG.md` and `docs/FORMER_BUGS.md` NM-002 — decisions, not oversights. |
