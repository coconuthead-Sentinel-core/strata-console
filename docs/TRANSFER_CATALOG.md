# Transfer Catalog — Sentinel Forge → Strata Console

_Surveyed 2026-08-31 against `OneDrive/Sentinel personal development` at
its live state: 44 modules / 5,466 lines in `lyceum/`, 5,301 lines of
tests, 24 wiki pages, CI on Python 3.11 + 3.13._

**The question this answers:** Sentinel Forge is a personal-development
workstation. Strata Console is a local NLP console. Take out everything
that is personal development — what is left that Strata should have?

**The short answer:** about **1,900 lines of the functional core**, and
**all of the engineering process**. The process is the more valuable
half, and it is the half Strata has none of.

---

## 1. How each module was judged

Three questions, in order:

1. **Is it personal development?** Habits, goals, streaks, money,
   appointments, spaced repetition, gamification — out, by the owner's
   instruction, regardless of quality.
2. **Does it serve what Strata actually is?** A local-first chat console
   with voice in, voice out, and retrieval over the owner's own files.
   A spreadsheet formula engine is excellent code and has no job here.
3. **Is it already solved in Strata, better or worse?** Where both
   projects have a module, the catalog says which wins and why.

A module is only "TAKE" if it is pure or cleanly separable. Anything
welded to the 28,536-line Tk shell is a rewrite, not a transfer, and is
marked as such.

---

## 2. TAKE — direct fit, little or no change (~900 lines)

| Module | Lines | Why Strata wants it |
| --- | --- | --- |
| `platform_dpi.py` | 58 | Declares Windows DPI awareness before the Tk root exists. Strata has a **documented, unfixed** DPI defect (CustomTkinter multiplying geometry by ~1.75x). This is the fix, already written and proven. |
| `dictation_commands.py` | 123 | Turns spoken "period", "new line", "cap that" into real characters. Strata's mic now works — and hands back an unpunctuated wall of text. This is the missing half of dictation. |
| `dictation_guard.py` | 110 | Collision and duplicate resolution for the above (a spoken "period" that was meant as the word). |
| `wcag.py` | 63 | W3C contrast math and AA thresholds. Becomes the gate on any new colour pair in the console. |
| `text_norm.py` | 176 | Read-aloud front end: normalises text before it reaches TTS. Strata's 🔊 currently speaks raw markdown. |
| `sapi_tts.py` | 68 | Windows SAPI5 voices with voice and rate selection. Strata shells out to a subprocess and cannot pick a voice. |
| `accessibility_bridge.py` | 59 | Speaks through the owner's running NVDA. |
| `select_all.py` | 34 | Select-all that works on both text-box species. |
| `util.py` | 78 | Small pure helpers; cherry-pick what the ported modules need. |
| `readability.py` | 117 | Reading-difficulty analysis. On-theme for an NLP console: point it at a reply or an uploaded document. |

## 3. ADAPT — the idea transfers, the code needs work (~1,000 lines)

| Module | Lines | What changes |
| --- | --- | --- |
| `voice_pipeline.py` | 76 | **The biggest single UX win available.** Streams the model's reply and speaks each sentence the moment it completes, instead of waiting for the whole answer. Requires adding a `stream()` method to Strata's `LLMBrain`, which today only returns complete replies. `iter_sentences` is a pure generator and ports untouched. |
| `local_context.py` | 326 | Real BM25 ranking, query expansion, chunking. Strata's `strata_tools/retrieval.py` is a simpler scorer. Take the ranking core; drop the `study.db` readers (notes, glossary, journal, topics are personal development). |
| `doc_index.py` | 226 | Both projects have one. Compare against `strata_tools/doc_index.py` and keep the better; Sentinel's handles a larger tree. |
| `legibility.py` | 115 | Accessibility presets to a concrete font spec. Strata already has font family and size; this generalises them into named presets. Currently tied to Study read-panes. |
| `lint_designlaws.py` | 87 | Static AST guard against two recurring UI traps. Rules port directly, but the widget-name table is raw Tk/ttk and needs CustomTkinter class names added. |
| `prompt_coach.py` | 165 | Prompt-quality analyser (persona / task / context / format rubric). Strongly on-theme — this is a console for talking to a model. Sentinel ties it to its own review docs; the rubric itself is general. |
| `prompt_archive.py` | 83 | Prompt library rendering. Pairs with `prompt_coach`. |
| `doc_writer.py` | 213 | Writes real `.docx` and `.xlsx`. Strata can read documents but cannot produce one. Optional dependency, degrades gracefully. Note: Imprint already has this capability — decide whether Strata should duplicate it. |
| `stt_command.py` | 90 | Voice command-and-control ("scroll down", "send"). Adds a Vosk dependency on top of Whisper. Real value, real cost — defer until the rest lands. |

## 4. DROP — personal development, out by instruction (~2,600 lines)

`srs.py` (416, FSRS spaced repetition) · `reward_engine.py` (226,
variable-ratio gamification) · `job_readiness.py` (207) ·
`finance.py` (151) · `bills.py` (114) · `reminders.py` (140) ·
`reminder_flash.py` (304) · `goals.py` (70) · `streaks.py` (53,
Never-Miss-Twice) · `pomo_clock.py` · `ambience.py` (225) ·
`room_signs.py` (70) · `idea_collision.py` (42) · `ideas.py` ·
`harvest.py` (137) · `entry_parse.py` (138, parses pasted *study* text) ·
`flow_carry.py` (90, Blueprint §12) · `metrics.py` (66, progress
metrics) · `handoff_view.py` · `reading.py` (40).

Also dropped as out-of-domain rather than personal: `formula.py` (317,
a spreadsheet formula engine) and `password_strength.py` (154). Both are
good code with no job in a chat console.

> Several of these are the best engineering in the repository — `srs.py`
> is FSRS-backed and 241 lines of tests deep. Dropping them is a scope
> decision, not a quality judgment. If Strata ever grows a study mode,
> this catalog is where to look first.

---

## 5. The process transfer — the half that matters more

Strata has **no `docs/`, no `.github/`, no CHANGELOG, and no CI.** It has
54 tests and a README. Sentinel Forge has the full apparatus, and it
transfers at near-zero risk because none of it is application code.

| Asset | What it is | Effort |
| --- | --- | --- |
| `.github/workflows/ci.yml` | `py_compile` plus unit tests on Windows, Python 3.11 and 3.13, every push and PR. | Copy, retarget paths. **Under an hour.** |
| `docs/SCOPE.md` | In-scope / explicitly-out-of-scope / acceptance criteria / lifecycle target. Sentinel's was written retroactively and is the template. | Half a session — drafted alongside this catalog. |
| Design laws | The subset that applies to Strata: size windows from `winfo_screenwidth/height`; row heights from font metrics; reading surfaces honour the font choice; visible confirmation for every action; **archive, never delete**; tuple `pady` only in `.pack()` / `.grid()`. | Copy the applicable rows; enforce via the linter. |
| `Former-Bugs-and-Regressions.md` | Every defect, its root cause, and the guard that now prevents it. Strata already has two entries' worth of unrecorded history: the DPI geometry trap, and the interpreter/voice-package defect fixed today. | Start it now, while both are fresh. |
| `ACCEPTANCE_CRITERIA.md` + `SDLC_STATUS.md` | How "done" is known; where the project sits against ISO/IEC/IEEE 12207. | Directly serves the architect/QA framing. |
| `Rebuild-Blueprint.md` + `Database-Schema.md` | Documentation as disaster insurance — sufficient to rebuild from scratch. | Strata is ~1,300 lines; genuinely achievable here, unlike in a 28k-line shell. |

---

## 6. Recommended order

**Phase 1 — process (no application risk).** CI, `docs/SCOPE.md`, the
applicable design laws, and `Former-Bugs-and-Regressions.md` seeded with
the two defects already in hand. Nothing in the console changes; the
project gains a quality gate and a baseline.

**Phase 2 — finish the voice path.** `dictation_commands` +
`dictation_guard` (dictation currently returns unpunctuated text), then
`text_norm` + `sapi_tts`, then `voice_pipeline` streaming speech. This is
the thread already being pulled, and it ends with a console that listens
and answers aloud without a dead wait.

**Phase 3 — fix the known DPI defect.** `platform_dpi` plus the linter
rules that stop it recurring, with `wcag` as the gate on new colours.

**Phase 4 — retrieval and prompting.** `local_context` ranking into
`strata_tools/retrieval.py`; then `prompt_coach` + `prompt_archive` as a
genuinely on-theme feature for an NLP console.

**Deferred.** `doc_writer` (settle the Imprint overlap first),
`stt_command` (new dependency), `legibility` presets.

---

## 7. Honest notes

- **This is a build, and the standing priority is the job search.**
  Phase 1 is the part that pays into that directly: a CI gate, a scope
  document, and a defect register are demonstrable engineering process,
  and they are cheap. Phases 2-4 are feature work and should wait unless
  the owner decides otherwise.
- **Nothing here has been ported yet.** Line counts are measured; fit
  judgments come from reading each module's contract, not from running
  it inside Strata. Every "TAKE" still owes headless tests in Strata's
  own suite before its UI is wired — that is the house rule.
- **Sentinel Forge is in maintenance mode.** This catalog copies *from*
  it; it does not modify it.
