# Former Bugs and Regressions — Strata Console

Every defect, its root cause, and **the guard that now prevents it**. A
fix without a guard is a defect waiting for its second appearance.

Adopted from Sentinel Forge, where this register is the reason the same
crash stopped recurring. Seeded 2026-09-01 with the history that was
already in hand but unrecorded.

Format: what the owner saw · what was actually wrong · the guard.

> **On the Tk-era entries (2026-09-01).** The CustomTkinter shell was
> retired; FB-001, FB-005, FB-006 and NM-002 describe a toolkit this
> project no longer ships, and their guards (`window_fit.py`,
> `layout.py`, the CustomTkinter probes under `tools/`) went with it.
>
> They are **kept in full and not struck through.** Three reasons. The
> reasoning outlived the toolkit — "verify the right LEVEL" was learned
> from a window that fit a screen while half the application was
> undrawn, and that mistake is available in any UI. They are the
> evidence for retiring Tk at all: three defects of one class is the
> argument. And a register that deletes what is no longer convenient is
> not a register.
>
> What is *not* claimed: that those guards still run. They do not. The
> standing laws below are the part that carries forward.

---

## FB-001 — The window sized itself off the bottom of the screen

**Status:** fixed, guarded · **Found:** 2026-06 · **Severity:** blocking

**What the owner saw.** Panels looked blank and non-interactive. The
send button and the mode row were simply not there.

**What was actually wrong.** Nothing was blank. CustomTkinter multiplies
whatever you pass to `geometry()` by the display scaling factor — 1.75
on this laptop — so `geometry("1000x700")` became 1750×1225 physical on
a 1097×617 effective display. The bottom third of the window was below
the screen edge. A control you cannot reach is a control that does
nothing, which is a defect and not a cosmetic issue.

**Guard.**
- `strata_tools/window_fit.py` holds the sizing rule as a pure kernel:
  compute in real pixels, cap to the screen, divide the scaling back out.
- `tests/test_window_fit.py` proves the fit invariant across 110 screen
  sizes × 5 scaling factors, and asserts the original 1750×1225 shape
  fails.
- Design-law **rule B** fails the build on any hardcoded `geometry("WxH")`.
- `tools/dpi_check.py` measures the real mapped window against the real
  screen.

---

## FB-002 — The microphone was "dead" for weeks; nothing was wrong with it

**Status:** fixed, guarded · **Found:** 2026-08-31 · **Severity:** blocking

**What the owner saw.** Dictation did nothing. The hardware tested fine.
An earlier session had concluded "the mic is fine, the RAM ceiling is
not" and fixed a genuine but unrelated Whisper memory problem.

**What was actually wrong.** `launch_strata.vbs` hunted down the Windows
Store Python under `C:\Program Files\WindowsApps` and launched that,
while `sounddevice` and `faster_whisper` were installed in the ordinary
per-user Python. The console imported `sounddevice`, got
`ModuleNotFoundError`, and reported it correctly — which reads as dead
hardware.

**Why it survived so long — two compounding traps.**
1. `tools/voice_check.py` was run with `py -3`, which resolves to the
   interpreter that *does* have the packages. All three bench stages
   passed while the console could not record a word. **A bench that does
   not name its interpreter is not checking the owner's path.**
2. The error said `pip install sounddevice`. Typed at a normal prompt,
   that targets the other Python, answers "Requirement already
   satisfied", and changes nothing. The owner reasonably concluded the
   app was lying.

**Guard.**
- `launch_strata.vbs` prefers an interpreter that actually carries the
  voice packages; `/which` reports its choice.
- `strata_tools/interpreter.py` + `tests/test_interpreter.py` hold the
  rule, including "installed over there is not installed over here".
- `tools/voice_check.py` stage 0 prints its own interpreter *and* the
  one a double-click would use.
- Design-law **rule C** fails the build on any install instruction that
  does not name `sys.executable`.

---

## FB-003 — Dictation returned an unpunctuated wall of text

**Status:** fixed · **Found:** 2026-09-01 · **Severity:** major

**What the owner saw.** The mic worked, and produced a paragraph with no
punctuation and no capitals. Speaking "period" typed the word "period".

**What was actually wrong.** Only half the dictation path existed. Speech
in, text out — but someone dictating instead of typing dictates
*everything*, punctuation included. A half-built capability is the same
defect as a dead control.

**Guard.** `strata_tools/dictation.py` + 24 tests, including the
collision case where Whisper has already auto-punctuated from an
acoustic pause and the spoken mark lands on top of it.

---

## FB-004 — Read-aloud spoke the markdown

**Status:** fixed · **Found:** 2026-09-01 · **Severity:** major

**What the owner saw.** 🔊 said "asterisk asterisk important asterisk
asterisk", read headings as "hash hash", and recited fenced code blocks
character by character.

**What was actually wrong.** `self._last_reply` went straight to SAPI.
The model answers in markdown; the button worked, it just was not
speaking English.

**Guard.** `strata_tools/speech.py` + 26 tests. Markdown stripped, then
numbers, money and abbreviations expanded, with inline code held atomic.

---

## FB-005 — Thirteen controls were never drawn, including the transcript

**Status:** fixed, guarded · **Found:** 2026-09-01 · **Severity:** blocking

**What the owner saw.** A console that worked, mostly. What he could not
see is that the entire bottom row (all three Mode buttons, /status,
/lexicon, /help, Clear), the context-source row (Web, OneDrive, Upload),
two toolbar buttons and **the transcript box itself** were not being
rendered at all.

**What was actually wrong.** FB-001 was closed on the wrong measurement.
The window fits the screen — 999×486 inside 1097×617, verified and
tested. Nobody checked that the *content* fits the *window*.
CustomTkinter multiplies every widget by the display scaling of 1.75, so
the chrome needed **919px of the 486 available**. Tk's packer does not
raise; it silently stops mapping children once it runs out of room, in
reverse order of packing.

**Verified as pre-existing**, not introduced by the accessibility work:
commit `807c5ba` hides 9 controls under the same probe.

**Guard.**
- `strata_tools/layout.py` chooses a widget scaling from the real screen
  and gives the transcript a floor rather than the leftovers.
- The redundant title banner is gone and status moved into the row
  below — one fewer stacked row, which is the shop design law (≤5 major
  choices) doing real work.
- `tools/layout_probe.py` counts controls Tk actually mapped, **from
  inside a live mainloop** — measuring an unmapped window reports
  nonsense and passes.
- `tests/test_layout.py` asserts the defect configuration (1.75 in a
  486px window) reports `content_fits == False`.

**The lesson, which is the reusable part:** *verifying the wrong level
passes.* FB-001's test was true and irrelevant.

---

## FB-006 — Every button was unreachable by keyboard

**Status:** fixed, guarded · **Found:** 2026-09-01 · **Severity:** blocking

**What the owner saw.** Nothing — this is invisible unless you try to
drive the console without a mouse.

**What was actually wrong.** The real Tab ring contained **two** widgets
out of twenty-two. CustomTkinter builds each control from a `Canvas`
plus a `Label`; a Tk `Canvas` is not in the default traversal order and
a `Label` carries `takefocus=0`, so the whole widget family drops out of
the focus ring. A library default, and it costs WCAG 2.1.1 Keyboard —
**Level A**, the floor.

The transcript was a second case: held `state="disabled"` so it cannot
be typed into, which also drops it out of the ring entirely. Right for
an input, wrong for a reading surface.

**Guard.** `strata_tools/keyboard.py` + 20 tests; `tools/a11y_check.py`
walks the real ring and now reports 24 reachable widgets. The focus ring
colour is re-measured against every surface in the test suite.

---

## FB-007 — Every button failed contrast against the surface it sat on

**Status:** fixed, guarded · **Found:** 2026-09-02 · **Severity:** major

**What the owner saw.** "The buttons are very small and hard to see."
Reported from the field, after the accessibility pass.

**What was actually wrong.** Two things, and the audit before this one
missed both because it asked the wrong question.

*Contrast.* WCAG 1.4.11 requires a control to reach 3:1 against its
background. Measured against the frame:

    CustomTkinter default blue  #1F6AA5  ->  2.47:1
    GREEN inactive              #16301B  ->  1.01:1
    YELLOW inactive             #33270A  ->  1.03:1
    RED inactive                #3A1414  ->  1.15:1

1.01:1 is not a dim control, it is an invisible one — and that one was
introduced by the colour-coding work the day before. The earlier pass
verified the **text on** the buttons and never the **button against what
it sits on**. Same class of error as FB-005: checking that the window
fits the screen and not that the content fits the window.

A third, also pre-existing: the stock blue carries its own label at
4.47:1, just under the 4.5:1 AA line.

*Size.* Widget scaling had been dropped to 0.71 to fit every control on
a 617px screen, which left buttons about 35px tall.

**Guard.**
- `strata_tools/theme.py` + 12 tests. An outline (`#C0CAD5`) chosen by
  sweep clears 3:1 against the frame and every fill; the fill keeps
  doing the text job and the outline does the shape job, so 1.4.11 is
  not bought by losing 1.4.3. Button fill corrected to `#1A5A8C`
  (5.68:1).
- Tests assert the ORIGINAL fills fail unaided, so removing the outline
  as a "simplification" breaks the build.
- `tools/a11y_check.py` section 6 now measures this on every run.
- Buttons raised to 49px drawn, and `/status` and `/lexicon` left the
  bottom row — both duplicated things already on screen or typeable,
  and the width they freed is why the rest can be read.

---

## FB-008 — The console held a voice model nobody was using

**Status:** fixed, guarded · **Found:** 2026-09-02 (owner, field test) ·
**Severity:** major

**What the owner saw.** Dictation refused: *"even Fast needs about 470 MB
and only 406 MB is free."* He closed other applications and it worked
again.

**Two separate things were true.**

*The guard was correct.* It declined instead of dying inside MKL, which
is exactly what it was built for. That half is not a defect and was not
changed.

*The console was part of the problem.* After the first dictation the
Whisper model was kept resident forever. Measured on the owner's 8 GB
laptop that day:

    loading base.en           -134 MB free
    model + runtime resident   ~174 MB
    releasing it              +180 to +221 MB free

On a machine that lives at 400–600 MB free, that is the entire margin.
Keeping one model resident was the right answer when the problem was
three of them stacking up (the earlier RAM fix); it is the wrong answer
once the machine itself is the constraint.

*And the advice could not work.* The message said "close Ollama or other
apps". Ollama was holding **13 MB** — its model was not loaded. Sending
someone to close a 13 MB process to recover 64 MB is advice that cannot
work, which is the same failure that kept FB-002 alive for weeks.

**Guard.**
- `voice_budget.should_release()` — release after 5 minutes idle, or
  immediately below 700 MB free. Pure, and `LOW_RAM_MB` is asserted to
  sit *above* `tier_cost("Fast")`, so releasing fires before dictation
  starts failing rather than after.
- Both shells watch once a minute and say so when they release; a
  background action that changes how long the next dictation takes
  should not be a surprise.
- `shortfall_advice()` names the actual gap in MB and the levers that
  return the most.
- `tests/test_voice_memory.py`, 16 tests, including the owner's exact
  reported condition (406 MB free).

**One test had to be changed, and that is worth recording.**
`test_no_tier_fits_is_a_stop_not_a_silent_downgrade` asserted the
message contained the literal string "close Ollama" — so the suite was
holding the bad advice in place. A test that pins exact wording pins the
wording's defects too. It now asserts what the message must *achieve*.

---

## FB-009 — The web shell's memory watch reported to nobody

**Status:** fixed, guarded · **Found:** 2026-09-02 · **Severity:** silent

**What the owner saw.** Nothing — which is the problem. In the desktop
shell, releasing the idle voice model prints a line saying so. In the
web shell the same release happened and was never mentioned.

**What was actually wrong.** `Api.memory_note()` existed, was correct,
and was called by no one. `app.js` had no poll and no timer, so the
note it returned had no route to the page. The background watch was
doing real work — freeing ~221 MB on a machine that lives at 400–600 MB
free — and its report went into a variable that was overwritten on the
next tick.

This is the same defect class as FB-005 and FB-006, wearing new
clothes: **a capability the owner cannot reach is a capability that
does not exist.** In a Tk shell it looks like a control that was never
drawn. Across a JavaScript bridge it looks like a method nobody calls,
which greps clean and reads as finished code.

**Guard.**
- `poll_notes()` replaces it — a drained queue, polled every five
  seconds, shared by the memory watch and OneDrive indexing.
- `tests/test_web_shell.py::test_the_notes_queue_is_actually_drained`
  fails if the timer is removed.
- `BridgeSurfaceTests::test_every_method_the_page_calls_exists_on_the_bridge`
  imports the bridge and resolves **every** `api.*` call in `app.js`
  against it. This catches the mirror-image failure — the page calling
  a method that does not exist, which surfaces as a rejected promise
  and looks, to the owner, exactly like nothing happening.

---

## FB-010 — Eleven web-search trigger phrases, none of them tested

**Status:** fixed, guarded · **Found:** 2026-09-02 · **Severity:** latent

**What the owner saw.** Nothing yet. This was found by reading, not by
failing.

**What was actually wrong.** Saying "look this up" turns on web search
without touching the checkbox. The eleven phrases that do it were a
literal tuple inside `strata_console.py`'s send handler — UI code, with
no test able to reach it without a screen. A typo in any entry would
have been invisible: the phrase would simply never fire, and the owner
would conclude the feature was unreliable rather than that one string
was wrong. The port to the web shell would have copied the tuple, and
two copies of a rule is two rules.

**Guard.**
- The rule moved to `strata_tools/context_sources.py` as
  `wants_web()` — pure, and shared by both shells.
- `test_every_shipped_phrase_actually_fires` asserts each entry in
  `TRIGGER_PHRASES` triggers, so a dead phrase fails the build.
- `test_an_ordinary_question_does_not_reach_the_network` holds the
  other side: an ordinary question must not silently reach the web.

---

## Near-misses — caught before shipping, recorded because the reasoning is the value

### NM-008 — The layout planner and its own checker disagreed

`plan_widget_scaling` divided by the bare widget-height sum while
`chrome_height` had been corrected to include the packer's inter-row
padding. The planner returned 0.91 and `describe()` then reported that
very scaling would clip — the module contradicting itself in one call.
`tools/fit_sweep.py` (new) settles it empirically: it builds the real
console at a range of scalings and counts what Tk mapped. 0.71 is the
ceiling; above it three controls vanish. The sweep is now the authority
and the constant is derived from it.

### NM-005 — A default argument sent the probes at the live database

`StrataDB.__init__(self, path=DB_PATH)` binds the module constant when
the class is **defined**, so the accessibility probes' `strata_console.DB_PATH
= tmp` was silently ignored and they wrote to the real store — pressing
A+ against it and changing a saved font size. Caught by noticing the
audit reported 36pt on a supposedly fresh database. The live install was
untouched (the probes ran from the worktree); the worktree's own copy was
restored. Fixed by resolving `DB_PATH` at call time, with a regression
test. The unit tests were never affected — they pass `path=` explicitly.

### NM-006 — Two coordinate systems in one window calculation

An attempt to reclaim screen height with `SPI_GETWORKAREA` produced a
700px window on a 617px screen. That API answers in **physical** pixels,
and CustomTkinter enables DPI awareness during init, so a work-area query
made after `ctk.CTk()` reported 1032px of height while `winfo_screenheight()`
still said 617. Reverted; `work_area()` is kept for diagnostics with the
trap written into its docstring. Related: two *scaling* factors exist as
well (widget and window), and the widget decision must be applied before
the window scaling is read.

### NM-007 — A focus ring invisible on the buttons it was drawn for

The first focus-ring colour was an amber that looked right on the dark
chrome and measured **2.81:1 against the button blue** — under the 3:1
that WCAG 1.4.11 requires. Caught by measuring rather than looking.
White clears every surface at worst 4.83:1. The rejected colour is kept
in a test, so a future "tidy this to a brand colour" shows its cost.

### NM-001 — Clear would have cleared only the window

Wiping the transcript was the obvious implementation. `MemoryNode` feeds
the last three turns back to the model on every message, so a "cleared"
console would have gone on quoting the conversation the owner had just
cleared. **Clearing the view and clearing recall are one action or the
control is lying.** Caught by reading the memory path before writing the
button.

### NM-002 — `platform_dpi` was the catalog's top recommendation, and was wrong

The transfer catalog named it the highest-value port: it fixes blurry
bitmap-stretched text. Measurement overturned it. Declaring per-monitor-v2
awareness makes Windows report the true 1920×1080 instead of the
virtualized 1097×617, so the same 999-pixel window falls from **91% of
screen width to 52%**, accessibility fonts shrinking with it. Crisper
text, half-size window. Declined, and `tools/dpi_check.py --aware`
reproduces the measurement. **The catalog was reasoning from the module's
contract; the bench measured the owner's screen.**

### NM-003 — A guard that could not fail

`window_fit.fits_on_screen()` was written as a runtime check and can
never return `False` — the caps guarantee fit by construction. A check
that cannot fail is not a check; it is a comment that costs a function
call. Converted into an explicitly swept and proven invariant plus
`margins_cover_origin()` naming its precondition.

### NM-004 — The linter's first run flagged the linter

Rule C fired on `design_laws.py`'s own finding text, and on `tests/`,
which carry deliberate bad samples as fixtures. Both were fixed at the
source — the message reworded, `tests/` excluded by design — rather than
suppressed. **A linter that has to exempt itself is a rule with a hole in
it.** The gate now also asserts it still reaches `strata_console.py`, so
it cannot pass by scanning nothing.

---

## The standing laws these produced

1. **A control that does nothing is a defect** — including the half of
   the action the owner cannot see.
2. **Archive, never delete.** Where something leaves the view, it stays
   in SQLite.
3. **A bench that does not name its interpreter is not a bench.**
4. **Advice that cannot work is a defect.** Install instructions name
   `sys.executable`.
5. **Measure on the owner's machine before trusting a module's contract.**
6. **A check that cannot fail is not a check.**
7. **Verify the right LEVEL.** "The window fits the screen" was true
   while half the application was undrawn. Ask what the next enclosing
   thing is, and check that too.
8. **Measure from inside a live mainloop.** A Tk window that has never
   run an event loop reports unmapped children and heights of 1, so an
   audit run against it passes while seeing nothing.
9. **Colour is never the only cue** (WCAG 1.4.1), and **a claim in the
   repository has to survive checking** — including a comment about
   what research says.
