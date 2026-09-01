# Build Plan — Strata Console to 100%

_Planned 2026-09-01. Method: Eisenhower matrix for triage · Brian Tracy ABC
for sequence · Pomodoro cycles for execution · Buckminster Fuller
(recycle / reuse / redistribute) for the salvage discipline._

---

## 0. What "100% complete" means here

The owner's constraint is binding and narrows the work: **Strata Console is
to be left as designed.** Only material that transfers *without harm* moves
across. So "100%" is not "every good module in Sentinel Forge" — it is:

> **Every promise Strata already makes is fully kept, every known defect is
> closed, and the engineering apparatus that proves it is in place.**

A half-built capability is the same defect as a dead control. Measured
against that, Strata has **seven gaps**. Closing those seven is 100%.

| # | Gap | Kind |
| --- | --- | --- |
| 1 | CustomTkinter multiplies window geometry by display scaling (~1.75x) | **Open defect** |
| 2 | Dictation returns unpunctuated text — the mic works, the feature does not finish the job | **Half-built** |
| 3 | Read-aloud speaks raw markdown (asterisks, hashes, backticks) out loud | **Half-built** |
| 4 | No CI — SCOPE §3 names this acceptance criterion as "not yet in place" | **Missing gate** |
| 5 | No design-law linter — the traps that bit both projects can recur silently | **Missing gate** |
| 6 | No defect register, no CHANGELOG | **Missing record** |
| 7 | SCOPE.md drafted but not baselined | **Missing baseline** |

Anything that would *add a new feature* is out of scope for this build,
however good the donor code is. That is the "no harm" rule doing its job.

---

## 1. Eisenhower matrix

|  | **Urgent** | **Not urgent** |
| --- | --- | --- |
| **Important** | **Q1 — DO NOW**<br>Gap 1 DPI defect · Gap 2 dictation punctuation · Gap 3 read-aloud normalisation.<br>_These are live faults in a shipped app the owner uses daily._ | **Q2 — SCHEDULE**<br>Gap 4 CI · Gap 5 linter · Gap 6 register + changelog · Gap 7 baseline.<br>_Nothing breaks today without them; everything breaks eventually._ |
| **Not important** | **Q3 — AUTOMATE**<br>Mirror worktree → live → GitHub by hand every time; running the suite by hand.<br>_Repetitive, error-prone, no judgment required. CI absorbs it._ | **Q4 — DECLINE**<br>`prompt_coach` · `prompt_archive` · `legibility` presets · BM25 swap · `readability` · `doc_writer` · `stt_command` · `formula` · `password_strength`.<br>_Good code that would change Strata's design or duplicate Imprint. Declined on purpose, recorded so it is a decision and not an oversight._ |

The matrix's real work here is **Q4**. Two thousand lines of quality
engineering sit in that quadrant, and the temptation is to take it because
it is free. It is not free — it costs the design.

---

## 2. Brian Tracy ABC

A = serious consequence if left undone. B = should do, mild consequence.
C = nice, no consequence. **No B before every A is done.**

### A — must (closes the seven gaps)

| ID | Task | Pomodoros | Quadrant |
| --- | --- | --- | --- |
| **A1** | Port `platform_dpi` · declare DPI awareness before the Tk root · close gap 1 | 2 | Q1 |
| **A2** | Port `dictation_commands` + `dictation_guard` · wire into the Whisper return path · close gap 2 | 3 | Q1 |
| **A3** | Port `text_norm` · normalise before TTS · close gap 3 | 2 | Q1 |
| **A4** | CI workflow — `py_compile` + suite on 3.11 / 3.13 · close gap 4 | 1 | Q2 |
| **A5** | Adapt `lint_designlaws` to CustomTkinter · add as a test · close gap 5 | 2 | Q2 |
| **A6** | `FORMER_BUGS.md` seeded with all three known defects · `CHANGELOG.md` · close gap 6 | 2 | Q2 |
| **A7** | Baseline SCOPE.md against the finished state · close gap 7 | 1 | Q2 |

**A total: 13 pomodoros.**

### B — should (strengthens what exists, changes no design)

| ID | Task | Pomodoros | Why it is not an A |
| --- | --- | --- | --- |
| **B1** | Port `wcag` and audit the console's existing colour pairs | 1 | Reports findings; fixes nothing by itself |
| **B2** | Port `select_all` — Ctrl+A on both box species | 1 | Convenience on an existing control |
| **B3** | Port `sapi_tts` — voice and rate selection behind the existing 🔊 | 2 | 🔊 already works; this improves it |
| **B4** | Port `voice_pipeline` — speak each sentence as it streams | 3 | Needs `LLMBrain.stream()`; largest B, real payoff |
| **B5** | Port `accessibility_bridge` — NVDA announcements | 1 | Additive; no existing behaviour changes |

**B total: 8 pomodoros.**

### C — declined this build

Everything in Q4. Recorded in the transfer catalog with reasons. Not
deleted from the plan — *decided*.

---

## 3. Pomodoro cycles

25 minutes work / 5 short / 15 long after four. One task per pomodoro
where it fits; no task split across a break without a green test suite
first, so every break lands on solid ground.

| Cycle | Pomodoros | Contents | Ends with |
| --- | --- | --- | --- |
| **I** | 1–4 | A1 (×2), A2 (×2 of 3) | DPI closed; dictation kernel tested |
| **II** | 5–8 | A2 (×1), A3 (×2), A4 (×1) | Voice path complete; CI green |
| **III** | 9–12 | A5 (×2), A6 (×2) | Linter gating; defects on record |
| **IV** | 13–16 | A7 (×1), B1, B2, B3 (×1 of 2) | **100% reached at pomodoro 13** |
| **V** | 17–21 | B3 (×1), B4 (×3), B5 (×1) | Streaming speech; NVDA |

**Gate at pomodoro 13.** That is the completion line. Cycles IV–V past it
are strengthening, not completing, and can stop at any pomodoro without
leaving anything half-built.

---

## 4. Fuller: recycle · reuse · redistribute

Fuller's point is that there is no waste, only material in the wrong
place. Sentinel Forge is not a donor to be stripped — it is a stock of
already-paid-for engineering.

**REUSE — moves intact, no redesign.**
`platform_dpi` · `dictation_commands` · `dictation_guard` · `text_norm` ·
`wcag` · `select_all` · `accessibility_bridge`. Pure, dependency-free,
already test-proven. These transfer as-is with their docstrings, because
the docstrings carry *why* — which is the part that took the years.

**RECYCLE — the kernel is kept, the personal-development shell is stripped.**
`lint_designlaws` (rules kept, raw-Tk widget table rebuilt for
CustomTkinter) · `sapi_tts` and `voice_pipeline` (kept, rewired to
Strata's own brain and toolbar). The valuable part was never the wiring.

**REDISTRIBUTE — knowledge, not code.** The largest transfer carries no
modules at all: the design laws, the acceptance criteria, the CI gate,
the defect-register habit, and the scope discipline. Strata gets the
*method* Sentinel Forge paid to learn. This is the half that actually
raises Strata to standalone value, and it is the half that would have
been easiest to skip.

**The waste avoided:** ~2,600 lines correctly left where they are. Fuller's
method is not "move everything" — it is "nothing in the wrong place."

---

## 5. Execution log

| Pom | Task | Result |
| --- | --- | --- |
| — | Plan written | This document |
