# Accessibility Build Plan — Strata Console

_Planned 2026-09-01. Eisenhower for triage · Tracy ABC for sequence ·
Pomodoro for execution. Every finding below was **measured** on the
owner's 1097×617 display, not inferred from source._

---

## 0. What standard, honestly

The owner asked for compliance with "the guidelines and regulations set
by the educational system." Being precise about what those actually are
matters, because three different things get called the same thing:

| Thing | What it really is | Binding here? |
| --- | --- | --- |
| **WCAG 2.1 Level AA** | The technical standard. Named in the DOJ's 2024 ADA Title II rule for state and local government, which includes public universities. | The bar we hold to |
| **ADA Title II deadline** | DOJ extended it in April 2026: **26 April 2027** for entities serving ≥50,000, 2028 below that. The standard itself is unchanged. | Not legally — see below |
| **Section 508** | US federal procurement; incorporates WCAG AA. | Only if sold to a federal agency |
| **WCAG 2.2** | Adds criteria aimed squarely at cognitive load — 2.5.8 Target Size, 3.2.6 Consistent Help, 3.3.7 Redundant Entry. | Adopted here voluntarily |
| **UDL (CAST)** | A *framework* used across higher ed. Guidance, not regulation. | Informs, does not bind |
| **W3C COGA** "Making Content Usable" | A W3C Note for cognitive and learning disabilities. Guidance, not normative. | Informs, does not bind |

**The honest position:** Strata Console is a personal, local desktop
application. No accessibility law binds it — Title II covers public
entities' services, not a tool one person runs on his own laptop.

That changes nothing about what we build. WCAG AA is the right bar
because it is the one that has been argued out in public over twenty
years, and because a console the owner cannot fully operate is a defect
regardless of who is legally entitled to complain. It is also the bar
that makes this repository credible to anyone reading it as work.

Conformance is claimed only for what is tested. Anything unverified is
listed as unverified.

---

## 1. Measured findings

Run `py -3 tools/a11y_check.py` and `py -3 tools/layout_probe.py` to
reproduce all of these.

| # | Finding | Criterion | Level |
| --- | --- | --- | --- |
| **F1** | **13 of 22 controls are not rendered at all** — the whole bottom row (all three Mode buttons, /status, /lexicon, /help, Clear), the context-source row (Web, OneDrive, Upload), two toolbar buttons, **and the transcript box itself**. Chrome needs 919px in a 486px window. | 1.4.10 Reflow / operability | **A** |
| **F2** | **Tab reached 2 of 22 controls.** CustomTkinter builds controls from Canvas + Label, neither of which joins the focus ring. | 2.1.1 Keyboard | **A** |
| **F3** | No visible focus indicator anywhere. | 2.4.7 Focus Visible | AA |
| **F4** | A+/A− resizes **2 of 22** widgets. Everything else has a hardcoded font. | 1.4.4 Resize Text | AA |
| **F5** | The three Mode buttons are **identical blue**, and nothing marks which mode is active except one line of status text. | 1.4.1 Use of Colour + shop design law | A |
| **F6** | 7 stacked rows, ~20 simultaneous controls. | Design law: ≤5 major choices (ADHD executive load) | Shop |
| **F7** | Two colour pairs below AA (recorded earlier, accepted with reasons). | 1.4.3 Contrast | AA |
| **F8** | The code claims Comic Sans and Verdana are "repeatedly cited in dyslexia research". Overstated — see §4. | Evidence integrity | Shop |

**F1 predates this session.** Verified against commit `807c5ba`: the
baseline hides 9 controls including the transcript. FB-001 was recorded
as fixed because the *window* fits the *screen* — nobody checked that the
*content* fits the *window*. That is the lesson, and it is now a test.

---

## 2. Eisenhower

|  | **Urgent** | **Not urgent** |
| --- | --- | --- |
| **Important** | **Q1 — DO NOW**<br>F1 invisible controls · F2 keyboard · F3 focus ring · F5 mode state.<br>_Two Level A failures. F1 also gates F2 — an unmapped widget cannot take focus, so the keyboard fix is only half-effective until the layout is fixed._ | **Q2 — SCHEDULE**<br>F4 text scaling · F6 control density · F8 evidence correction.<br>_Real, not bleeding._ |
| **Not important** | **Q3 — AUTOMATE**<br>Re-running the audits by hand.<br>_Fold the invariants into the suite so CI catches regressions._ | **Q4 — DECLINE**<br>AAA criteria · a full screen-reader rewrite · replacing CustomTkinter.<br>_Out of proportion to a single-user local tool._ |

---

## 3. Tracy ABC

**A — must. Level A failures and what unblocks them.**

| ID | Task | Pom | Fixes |
| --- | --- | --- | --- |
| **A1** | Make every control visible: drop the redundant title row, merge status into the top row, fit widget scaling to the screen | 4 | F1, F6 |
| **A2** | Keyboard reach + activation for every CustomTkinter control | 3 | F2 |
| **A3** | Visible focus ring, contrast-verified on every surface | 2 | F3 |
| **A4** | Mode buttons colour-coded *and* marked with a non-colour active state | 2 | F5 |

**B — should. AA criteria that are real but not blocking.**

| ID | Task | Pom | Fixes |
| --- | --- | --- | --- |
| **B1** | A+/A− scales the whole interface, not just two boxes | 3 | F4 |
| **B2** | Correct the dyslexia-font claim; document what the evidence supports | 1 | F8 |
| **B3** | Fold the audits into the suite as regression tests | 2 | Q3 |

**C — declined this pass.** Screen-reader announcements (needs NVDA on
the machine to verify, and an unverifiable accessibility feature is
worse than none); dyscalculia numeric visuals; AAA contrast.

---

## 4. The evidence correction (F8)

`strata_console.py` carries this comment:

> OpenDyslexic / Atkinson Hyperlegible are purpose-built for
> readability; Comic Sans MS and Verdana are repeatedly cited in
> dyslexia research.

The second clause overstates what the research shows, and this shop's
rule is that a claim in a repository has to survive checking.

**What the evidence actually says.** Controlled studies of OpenDyslexic
have found **no improvement** in reading rate or accuracy against Arial
and Times New Roman, in individual students and as a group; some work
found it *slowed* reading. Participants did not report preferring it.
Results across the literature are mixed at best, with a minority
reporting gains in specific measures.

**What is well supported**, and what this console should therefore lean
on:

- **User control over presentation.** Letting the reader choose the
  face, the size and the spacing is the intervention with the strongest
  support — and it is a WCAG principle rather than a font claim.
- **Larger text and increased line spacing.**
- **Shorter line lengths** (the British Dyslexia Association style
  guidance is 60–80 characters).
- Sans-serif faces generally, without any one being magic.

**So the font menu stays.** Choice is the evidence-backed feature, and
Atkinson Hyperlegible has a separate and better-grounded provenance — it
was designed by the Braille Institute for low vision, which is a
different claim from a dyslexia claim. What changes is the comment: it
will describe these as *offered because the reader may prefer them*, not
as clinically established.

Removing the fonts would be the wrong correction. Overstating why they
are there is the thing to fix.

---

## 5. Execution log

| Pom | Task | Result |
| --- | --- | --- |
| — | Audit | `a11y_check.py`, `layout_probe.py`, `_one_scaling.py` written; F1–F8 measured |
| 1–4 | **A1** visibility | Title row dropped, status merged, widget scaling fitted from the screen. **13 hidden controls → 0.** Two wrong turns recorded as NM-006. |
| 5–7 | **A2** keyboard | `keyboard.py` + 20 tests. **Tab ring 2 → 24.** Transcript given focus and scroll keys without becoming editable. |
| 8–9 | **A3** focus ring | White, chosen by measurement after the first colour scored 2.81:1 on the button blue (NM-007). Re-measured in tests against 6 surfaces. |
| 10–11 | **A4** mode colour | `modes.py` + 22 tests. Colour **plus** a bullet **plus** a border — 1.4.1 satisfied three ways over. Yellow hover rejected at 4.42:1 and darkened. |
| 12–14 | **B1** text scaling | A+/A− moved **2 of 22 widgets → 22 of 22**. Chrome capped at a measured 12pt; above that the bottom row overflows horizontally. |
| 15 | **B2** evidence | Dyslexia-font claim corrected in source; the menu stays because *choice* is the supported intervention. |
| 16–17 | **B3** regression | Layout, keyboard, mode and font-cap invariants folded into the suite. **221 tests green.** |

### Final audit

```
TARGET SIZE   PASS  every control ≥ 24×24
KEYBOARD      PASS  every control reachable by Tab (ring = 24)
TEXT SCALING  PASS  22 of 22 widgets resize; 0 fixed
MODE          PASS  three colours + bullet + border
LAYOUT        PASS  0 hidden controls at every text size 10–36pt
LINE LENGTH   ~53 characters (BDA guidance 60–80) — see below
```

**The one thing still outside guidance** is reading width: about 53
characters where the British Dyslexia Association suggests 60–80. It is
*short*, not long, which is the harmless direction, and it moves with
the text size and window width. Left as a reported finding rather than
forced, because fixing it means either shrinking the reading font or
widening the window past the screen.
