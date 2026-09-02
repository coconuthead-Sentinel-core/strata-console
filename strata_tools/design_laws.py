r"""Design-law linter -- a static guard for this codebase's own traps.

Recycled from Sentinel Forge's ``lyceum/lint_designlaws.py``. The
machinery transfers; the rule set does not, because the traps are not
identical. Sentinel's widget table is raw Tk/ttk and Strata is built on
CustomTkinter, so rule A had to be rebuilt or it would have matched
nothing and passed silently -- a linter that cannot fire is worse than
no linter, because it reads as proof.

Each rule is here because it has already cost this shop a defect. None
is a style preference.

**Rules A and B after the Tk retirement (2026-09-01).** Strata's shell
is HTML in a WebView2 window now; the CustomTkinter console is gone,
and with it every line these two rules were written to catch. They are
deliberately KEPT rather than deleted, for two honest reasons: the
dormant ``turbo_console.py`` in this folder is still CustomTkinter and
still scanned, and if a Tk widget ever returns the tripwire should
already be in place rather than needing to be remembered. What must not
happen is either rule being read as ongoing proof that the shipped
shell is safe -- the shell contains no Tk at all, so they say nothing
about it either way. Rule C is the one that still guards live code.

  **A  Tuple padding in a widget CONSTRUCTOR.**
     ``pady=(12, 4)`` is valid in ``.pack()`` and ``.grid()`` and raises
     ``bad screen distance`` inside a widget constructor. Sentinel
     Forge's oldest recurring crash, inherited here the moment Strata
     started building widgets the same way.

  **B  A hardcoded ``geometry("WxH")`` literal.**
     The window-sizing trap. A fixed size multiplied by CustomTkinter's
     1.75 scaling put the send button off the bottom of the owner's
     screen. Sizes must derive from ``winfo_screenwidth/height`` --
     ``strata_tools/window_fit.py`` is the sanctioned way. f-strings are
     allowed precisely because they are how a computed size arrives.

  **C  A "pip install" instruction that does not name the interpreter.**
     Earned 2026-08-31. The console told the owner to ``pip install
     sounddevice``; typed at a prompt that resolves to the other Python
     on this laptop, pip answered "Requirement already satisfied" and
     the microphone still refused. Advice that cannot work is a defect.
     Any install instruction must interpolate ``sys.executable`` -- so
     an f-string carrying a substitution passes, and a flat literal does
     not.

Pure and importable: no Tk, no I/O beyond reading a file the caller
names. Run headless as part of the suite -- ``tests/test_design_laws.py``
scans the whole repository, so a violation fails CI rather than shipping.
"""

import ast
import re

# CustomTkinter widget constructors, plus the plain Tk/ttk names that can
# still appear in a Tk-based app. Rule A applies to all of them.
WIDGETS = {
    # CustomTkinter
    "CTk", "CTkToplevel", "CTkFrame", "CTkScrollableFrame", "CTkLabel",
    "CTkButton", "CTkEntry", "CTkTextbox", "CTkCheckBox", "CTkRadioButton",
    "CTkSwitch", "CTkSlider", "CTkProgressBar", "CTkOptionMenu",
    "CTkComboBox", "CTkSegmentedButton", "CTkTabview", "CTkScrollbar",
    # Tk / ttk
    "Label", "Button", "Frame", "LabelFrame", "Entry", "Text", "Canvas",
    "Listbox", "Scrollbar", "Toplevel", "Checkbutton", "Radiobutton",
    "Scale", "Spinbox", "Menu", "Menubutton", "PanedWindow", "Message",
    "OptionMenu", "Combobox", "Treeview", "Notebook", "Progressbar",
    "Separator", "Sizegrip", "ScrolledText",
}

_GEOMETRY_RE = re.compile(r"^\d+x\d+")
_INSTALL_RE = re.compile(r"pip\s+install", re.IGNORECASE)


class Finding:
    """One violation. Plain class so it prints usefully in a test failure."""

    def __init__(self, line, rule, message):
        self.line = line
        self.rule = rule
        self.message = message

    def __repr__(self):
        return f"line {self.line} [rule {self.rule}] {self.message}"

    def __eq__(self, other):
        return (isinstance(other, Finding) and self.line == other.line
                and self.rule == other.rule and self.message == other.message)


def _func_tail(func):
    """Last name of a call target: ``ctk.CTkLabel`` -> 'CTkLabel'. Pure."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _docstring_nodes(tree):
    """Every Constant that is a docstring -- rules never fire on prose."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _interpolated_nodes(tree):
    """Constants inside an f-string that carries a substitution.

    Such a string is building its text at runtime from real values, so a
    "pip install" inside it is presumed to be naming the interpreter --
    which is exactly what rule C asks for.
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr) and any(
                isinstance(part, ast.FormattedValue) for part in node.values):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant):
                    out.add(id(child))
    return out


def scan_source(src):
    """Design-law violations in Python source text. Pure."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [Finding(e.lineno or 0, "parse", f"could not parse: {e.msg}")]

    findings = []
    exempt = _docstring_nodes(tree) | _interpolated_nodes(tree)

    for node in ast.walk(tree):
        # --- Rule C: install advice that cannot work -------------------
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in exempt
                and _INSTALL_RE.search(node.value)):
            findings.append(Finding(
                getattr(node, "lineno", 0), "C",
                "a package-install instruction with no interpreter "
                "named -- a bare pip resolves to a different Python on "
                "this laptop and reports success while changing "
                "nothing; interpolate sys.executable"))

        if not isinstance(node, ast.Call):
            continue
        tail = _func_tail(node.func)

        # --- Rule A: tuple padding in a widget constructor -------------
        if tail in WIDGETS:
            for kw in node.keywords:
                if kw.arg in ("pady", "padx") and isinstance(kw.value,
                                                             ast.Tuple):
                    findings.append(Finding(
                        node.lineno, "A",
                        f"{tail}(... {kw.arg}=(tuple) ...) -- tuple padding "
                        f"in a constructor raises 'bad screen distance'; "
                        f"move it to .pack() or .grid()"))

        # --- Rule B: hardcoded geometry --------------------------------
        if tail == "geometry" and node.args:
            first = node.args[0]
            if (isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and _GEOMETRY_RE.match(first.value)):
                findings.append(Finding(
                    node.lineno, "B",
                    f'geometry("{first.value}") -- a hardcoded size is '
                    f'multiplied by the display scaling and pushes controls '
                    f'off screen; derive it from window_fit.plan_geometry'))

    findings.sort(key=lambda f: (f.line, f.rule))
    return findings


def scan_file(path):
    """Scan a Python file on disk. Returns [] for an unreadable file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return scan_source(handle.read())
    except OSError:
        return []


def format_findings(path, findings):
    """One line per violation, prefixed with the file. Pure."""
    return [f"{path}:{f.line}: [{f.rule}] {f.message}" for f in findings]
