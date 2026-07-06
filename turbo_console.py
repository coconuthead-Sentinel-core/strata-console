#!/usr/bin/env python3
"""
TURBO — Neural Activator / Dev Console for Quantum Nexus Forge
Built for Shannon Bryan Kelly (Coconut Head)

A terminal coding companion that keeps the project ON TRACK and catches DRIFT.
It does three jobs:
  1. ANCHOR  — holds the project vision + hard constraints in one place.
  2. FOCUS   — tracks the single "node" (task) you're working on right now.
  3. ACTIVATE— runs fractal (recursive) health + drift checks against the rules.

100% local. No cloud. Python + SQLite only — same constraints as the app it guards.

Usage (from this folder):
    python turbo_console.py                 # full status dashboard
    python turbo_console.py activate        # run all checks  (aliases: check, turbo)
    python turbo_console.py focus "task"    # set the current focus node
    python turbo_console.py log "note"      # add a dev-log entry
    python turbo_console.py charter         # show vision + hard constraints
    python turbo_console.py help
"""

import os
import re
import sys
import json
import importlib.util
from datetime import datetime

# ─── Paths (all local, next to this file) ──────────────────────────────────────
HERE       = os.path.dirname(os.path.abspath(__file__))
TARGET     = os.path.join(HERE, "strata_console.py")  # the app we guard
STATE_FILE = os.path.join(HERE, "turbo_state.json")

# ─── Project anchor: the vision + the rules drift loves to break ───────────────
VISION = "Strata — a local-first NLP inference pipeline: a 5-stage text-processing pipeline (customtkinter desktop client) driven by a LOCAL LLM (Ollama)."

HARD_CONSTRAINTS = [
    "100% local / offline — the ONLY allowed network is the loopback to the local Ollama daemon. No cloud APIs, no API keys.",
    "Python 3.13 is the core language.",
    "SQLite is the data store (single local .db file).",
    "Local LLM backend via Ollama — must degrade gracefully to template mode if the model isn't ready.",
    "Do NOT break the GUI (customtkinter) — keep it working.",
    "Keep the 5 pipeline-stage method signatures intact (process/route/retrieve/adjust/synthesize).",
    "Preserve the four-part fallback response (Summary / Description / Comments / Closing).",
    "Keep the operating-mode system (Green / Yellow / Red).",
]

# ─── Drift rules: patterns that mean the project has wandered off its vision ────
# Each rule = (label, kind, regex). kind "forbid" = must NOT appear; "require" = must appear.
DRIFT_RULES = [
    ("No cloud/network calls",      "forbid",  r"\b(import\s+requests|urllib\.request|http\.client|aiohttp|websockets|boto3|openai|socket\.socket)\b"),
    ("SQLite persistence present",  "require", r"import\s+sqlite3"),
    ("GUI (customtkinter) present", "require", r"import\s+customtkinter"),
    ("GUI class intact",            "require", r"class\s+StrataConsole"),
    ("Local LLM brain wired",       "require", r"class\s+LLMBrain"),
    ("Brain degrades gracefully",   "require", r"self\.brain\.available"),
    ("Node: InputNode.process",     "require", r"def\s+process\s*\(\s*self\s*,\s*user_input"),
    ("Node: RouterNode.route",      "require", r"def\s+route\s*\(\s*self\s*,\s*input_data"),
    ("Node: MemoryNode.retrieve",   "require", r"def\s+retrieve\s*\(\s*self\s*,\s*routed_data"),
    ("Node: PersonaNode.adjust",    "require", r"def\s+adjust\s*\(\s*self\s*,\s*memory_data"),
    ("Node: OutputSynth.synthesize","require", r"def\s+synthesize\s*\(\s*self\s*,\s*persona_data"),
]

# ─── Tiny terminal styling (works in standard Windows terminal) ────────────────
G, Y, R, B, DIM, RST = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[2m", "\033[0m"
OK, BAD, WARN = f"{G}PASS{RST}", f"{R}FAIL{RST}", f"{Y}DRIFT{RST}"


def _enable_ansi():
    """Turn on ANSI colors in legacy Windows consoles."""
    if os.name == "nt":
        os.system("")  # no-op that flips the VT100 flag on modern Windows


# ─── State (focus node + dev log) ──────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"focus": None, "log": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ─── Checks ────────────────────────────────────────────────────────────────────
def _load_target_module():
    """Import the app module by path WITHOUT launching the GUI (name guard protects us)."""
    spec = importlib.util.spec_from_file_location("qnf_app", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_compile():
    """Does the app file compile?"""
    import py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
        return True, "Source compiles cleanly."
    except py_compile.PyCompileError as e:
        return False, str(e).strip().splitlines()[-1]


def check_engine():
    """Headless smoke test of the engine — no window, real pipeline + in-memory DB."""
    try:
        mod = _load_target_module()
        forge = mod.StrataPipeline(db=mod.StrataDB(":memory:"))
        forge.change_zone("yellow")
        out = forge.process_input("turbo smoke test 💠🔺")
        missing = [k for k in ("summary", "description", "comments", "closing") if k not in out]
        if missing:
            return False, f"Output missing keys: {missing}"
        if forge.db.thread_count() != 1:
            return False, "Memory thread was not persisted."
        return True, "Engine pipeline + memory working (4-part output, glyphs decoded)."
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_drift():
    """Scan the source against the drift rules. Returns (passed_bool, [results])."""
    try:
        with open(TARGET, encoding="utf-8") as f:
            src = f.read()
    except FileNotFoundError:
        return False, [("Target file found", BAD, "quantum_nexus_forge_gui.py is missing")]

    results, ok = [], True
    for label, kind, pattern in DRIFT_RULES:
        found = re.search(pattern, src) is not None
        if kind == "require":
            passed = found
            note = "present" if found else "MISSING — vision drift"
        else:  # forbid
            passed = not found
            note = "clean" if passed else "FOUND — off-vision (cloud/network crept in)"
        results.append((label, OK if passed else WARN, note))
        ok = ok and passed
    return ok, results


# ─── Views ─────────────────────────────────────────────────────────────────────
def banner():
    print(f"{B}╔══════════════════════════════════════════════════════════════╗{RST}")
    print(f"{B}║  TURBO — project guard  ·  Strata Console                     ║{RST}")
    print(f"{B}╚══════════════════════════════════════════════════════════════╝{RST}")


def cmd_charter():
    banner()
    print(f"\n{B}VISION{RST}\n  {VISION}\n")
    print(f"{B}HARD CONSTRAINTS (anti-drift anchor){RST}")
    for c in HARD_CONSTRAINTS:
        print(f"  • {c}")
    print()


def cmd_activate():
    """The big one: run every check and give a single GO / NO-GO verdict."""
    banner()
    print(f"\n{B}ACTIVATING — running fractal health + drift checks...{RST}\n")

    all_ok = True

    ok, msg = check_compile()
    all_ok &= ok
    print(f"  [{OK if ok else BAD}] Compile      · {msg}")

    ok, msg = check_engine()
    all_ok &= ok
    print(f"  [{OK if ok else BAD}] Engine       · {msg}")

    print(f"\n{B}DRIFT SCAN (is the code still on-vision?){RST}")
    drift_ok, results = check_drift()
    all_ok &= drift_ok
    for label, tag, note in results:
        print(f"  [{tag}] {label:<28} {DIM}{note}{RST}")

    print()
    if all_ok:
        print(f"{G}██ SYSTEM ONLINE — GREEN ZONE. No drift. Cleared to code. ██{RST}")
    else:
        print(f"{R}██ ATTENTION — issues above. Fix before continuing. ██{RST}")
    print()
    return all_ok


def cmd_status():
    banner()
    state = load_state()
    focus = state.get("focus")
    print(f"\n{B}CURRENT FOCUS NODE{RST}")
    if focus:
        print(f"  🔺 {focus['task']}   {DIM}(set {focus['since']}){RST}")
    else:
        print(f"  {DIM}(none set — run: python turbo_console.py focus \"your task\"){RST}")

    # Pull live memory count from the app's own DB if it exists
    try:
        mod = _load_target_module()
        if os.path.exists(mod.DB_PATH):
            forge = mod.StrataPipeline()
            print(f"\n{B}APP STATE{RST}\n  {forge.get_status()}")
    except Exception:
        pass

    log = state.get("log", [])
    if log:
        print(f"\n{B}RECENT DEV LOG{RST}")
        for entry in log[-5:]:
            print(f"  {DIM}{entry['time']}{RST}  {entry['note']}")
    print(f"\n{DIM}Run 'python turbo_console.py activate' to verify the system is on-track.{RST}\n")


def cmd_focus(task):
    state = load_state()
    state["focus"] = {"task": task, "since": datetime.now().strftime("%Y-%m-%d %H:%M")}
    save_state(state)
    print(f"{G}🔺 Focus node set:{RST} {task}")
    print(f"{DIM}Everything you code now should serve THIS node. Drift = working on anything else.{RST}")


def cmd_log(note):
    state = load_state()
    state.setdefault("log", []).append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "note": note})
    save_state(state)
    print(f"{G}🧊 Logged.{RST}")


def cmd_help():
    print(__doc__)


# ─── Entry point ───────────────────────────────────────────────────────────────
def main(argv):
    _enable_ansi()
    cmd = (argv[0].lower() if argv else "status")
    arg = " ".join(argv[1:]).strip().strip('"') if len(argv) > 1 else ""

    if cmd in ("activate", "check", "turbo", "online"):
        ok = cmd_activate()
        sys.exit(0 if ok else 1)
    elif cmd == "charter":
        cmd_charter()
    elif cmd == "focus":
        if not arg:
            print(f"{R}Usage: python turbo_console.py focus \"what you're working on\"{RST}")
        else:
            cmd_focus(arg)
    elif cmd == "log":
        if not arg:
            print(f"{R}Usage: python turbo_console.py log \"a note\"{RST}")
        else:
            cmd_log(arg)
    elif cmd in ("status", "dashboard"):
        cmd_status()
    elif cmd in ("help", "-h", "--help"):
        cmd_help()
    else:
        print(f"{R}Unknown command: {cmd}{RST}")
        cmd_help()


if __name__ == "__main__":
    main(sys.argv[1:])
