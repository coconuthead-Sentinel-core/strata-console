# Former Bugs and Regressions — Strata Console

Every defect, its root cause, and **the guard that now prevents it**. A
fix without a guard is a defect waiting for its second appearance.

Adopted from Sentinel Forge, where this register is the reason the same
crash stopped recurring. Seeded 2026-09-01 with the history that was
already in hand but unrecorded.

Format: what the owner saw · what was actually wrong · the guard.

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

## Near-misses — caught before shipping, recorded because the reasoning is the value

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
