r"""Keyboard access for CustomTkinter controls. WCAG 2.1.1, Level A.

**The finding this exists for.** Measured 2026-09-01 with
``tools/a11y_check.py``: the console's real Tab ring contained *two*
widgets — the message box and the transcript. Every button, checkbox and
dropdown was unreachable by keyboard. Twenty controls, none of them
operable without a mouse.

This is not something the console did wrong. CustomTkinter builds each
control out of a ``Canvas`` plus a ``Label``; a Tk ``Canvas`` is not in
the default focus traversal order and a ``Label`` carries
``takefocus=0``, so the whole widget family falls out of the Tab ring.
It is a library default, and it silently costs you the most fundamental
conformance requirement there is:

    WCAG 2.1.1 Keyboard (Level A) — all functionality operable through a
    keyboard interface.

Level A is the floor. Every AA criterion above it is moot while this
fails, and it is the criterion that matters most to the people this
console is built for: anyone who cannot reliably use a mouse, anyone
navigating with a screen reader, and anyone with ADHD for whom the
keyboard path is simply the one that keeps attention on the task.

Two halves, and both are required — focusable without visible focus is
its own trap:

  * **Reach** — the inner canvas joins the Tab ring, and Return or Space
    activates the control the way a native button does.
  * **See** — WCAG 2.4.7 Focus Visible (AA). The focused control draws a
    ring whose colour clears 3:1 against both the control and the
    surface behind it (WCAG 1.4.11 Non-text Contrast), verified in
    ``tests/test_keyboard.py`` against ``strata_tools.wcag``.

The policy is pure and unit-tested. The shell is duck-typed — it asks
what a widget can do rather than what it is — so it tests headlessly
against fakes and cannot crash the console on a widget it does not
recognise.
"""

# How each control family is activated from the keyboard. Probed against
# CustomTkinter 5.2.2 rather than assumed: CTkButton exposes invoke(),
# CTkCheckBox toggle(), CTkOptionMenu only the private dropdown opener.
# Tried in order; the first the widget actually has is used.
ACTIVATORS = {
    "CTkButton": ("invoke", "_clicked"),
    "CTkCheckBox": ("toggle",),
    "CTkSwitch": ("toggle",),
    "CTkOptionMenu": ("_open_dropdown_menu", "_clicked"),
    "CTkComboBox": ("_open_dropdown_menu", "_clicked"),
    "CTkSegmentedButton": ("invoke",),
}

# Keys that activate a control. Space and Return are what a native
# Windows button answers to; both are bound so neither habit is wrong.
ACTIVATION_KEYS = ("<Return>", "<KP_Enter>", "<space>")

# Focus ring. Chosen by measurement, not taste. The first candidate was
# an amber #F5A524, which reads well on the dark chrome and then scored
# 2.81:1 against the button blue and 2.37:1 against the recording red --
# under the 3:1 that WCAG 1.4.11 Non-text Contrast requires. That is a
# focus ring you cannot see on the very controls it is drawn for. White
# clears every surface in this console with the widest margin: worst
# case 4.83:1, against the recording red.
FOCUS_RING = "#FFFFFF"

# Every background a focus ring can land on here. The test re-measures
# the ring against all of them, so a new UI colour that the ring cannot
# clear fails the build.
FOCUS_SURFACES = {
    "button blue": "#1F6AA5",
    "button hover": "#144870",
    "frame grey": "#2B2B2B",
    "transcript": "#1D1E1E",
    "entry": "#343638",
    "recording red": "#DC2626",
}
FOCUS_RING_WIDTH = 3


def is_control(class_name):
    """Is this a CustomTkinter control a person operates? Pure."""
    return class_name in ACTIVATORS


def activator_names(class_name):
    """Method names to try, best first, for activating this class. Pure."""
    return ACTIVATORS.get(class_name, ())


def find_activator(widget):
    """The bound method that activates ``widget``, or None. Duck-typed.

    Asks what the widget can do rather than what it is, so a future
    CustomTkinter release that renames a class keeps working and one
    that removes a method degrades to "not activatable" instead of
    raising inside a key binding.
    """
    for name in activator_names(type(widget).__name__):
        method = getattr(widget, name, None)
        if callable(method):
            return method
    return None


def focus_hosts(widget):
    """The inner Tk widgets that must join the Tab ring. Duck-typed.

    CustomTkinter wraps a Canvas (and sometimes a Label) inside a Frame.
    The Canvas is what should take focus: it is the thing that draws, so
    it is the thing a focus ring belongs on.
    """
    hosts = []
    for child in getattr(widget, "winfo_children", lambda: [])():
        if child.winfo_class() == "Canvas":
            hosts.append(child)
    return hosts


def enable_widget(widget, on_focus=None, on_blur=None):
    """Make one control keyboard-reachable and operable.

    Returns True if it was enabled. Never raises: a control that cannot
    be enabled is left exactly as it was, because a half-configured
    widget is worse than an untouched one.
    """
    activate = find_activator(widget)
    if activate is None:
        return False
    hosts = focus_hosts(widget)
    if not hosts:
        return False

    def activated(_event=None):
        activate()
        return "break"

    for host in hosts:
        try:
            host.configure(takefocus=1)
            for key in ACTIVATION_KEYS:
                host.bind(key, activated)
            if on_focus is not None:
                host.bind("<FocusIn>", lambda _e, w=widget: on_focus(w))
            if on_blur is not None:
                host.bind("<FocusOut>", lambda _e, w=widget: on_blur(w))
        except Exception:
            return False
    return True


def _ring_on(widget):
    """Draw the focus ring. Remembers what it replaced."""
    try:
        if not hasattr(widget, "_a11y_border"):
            widget._a11y_border = (widget.cget("border_color"),
                                   widget.cget("border_width"))
        widget.configure(border_color=FOCUS_RING,
                         border_width=FOCUS_RING_WIDTH)
    except Exception:
        pass


def _ring_off(widget):
    """Restore whatever border the control had before it was focused."""
    try:
        previous = getattr(widget, "_a11y_border", None)
        if previous is not None:
            widget.configure(border_color=previous[0],
                             border_width=previous[1])
    except Exception:
        pass


def enable_tree(root, walk=None):
    """Enable every control beneath ``root``. Returns how many.

    The count is the point: it is asserted by the bench, so a future
    CustomTkinter release that changes its internals shows up as a drop
    in the number rather than as a console nobody can Tab through.
    """
    def default_walk(widget):
        yield widget
        for child in widget.winfo_children():
            yield from default_walk(child)

    walker = walk or default_walk
    return sum(1 for w in walker(root)
               if is_control(type(w).__name__)
               and enable_widget(w, _ring_on, _ring_off))


# Keys that scroll a read-only reading surface.
SCROLL_KEYS = {
    "<Up>": (-1, "units"),
    "<Down>": (1, "units"),
    "<Prior>": (-1, "pages"),      # Page Up
    "<Next>": (1, "pages"),        # Page Down
}


def inner_text(widget):
    """The real Tk Text inside a CTkTextbox, or None. Duck-typed."""
    for child in getattr(widget, "winfo_children", lambda: [])():
        if child.winfo_class() == "Text":
            return child
    return None


def enable_reading_surface(widget, on_focus=None, on_blur=None):
    """Make a read-only transcript reachable and scrollable by keyboard.

    The transcript is held ``state="disabled"`` so it cannot be typed
    into, and Tk drops disabled widgets out of the focus ring entirely.
    That is right for an input and wrong for a reading surface: someone
    navigating by keyboard could reach every button in the console and
    not the text those buttons produce. WCAG 2.1.1 covers reading, not
    just operating.

    Focus is restored and the arrow and page keys are bound to scroll,
    without re-enabling editing.
    """
    text = inner_text(widget)
    if text is None:
        return False
    try:
        text.configure(takefocus=1)
        for key, (amount, what) in SCROLL_KEYS.items():
            text.bind(key,
                      lambda _e, a=amount, w=what: (widget._textbox.yview_scroll(a, w)
                                                    if hasattr(widget, "_textbox")
                                                    else None) or "break")
        if on_focus is not None:
            text.bind("<FocusIn>", lambda _e, w=widget: on_focus(w))
        if on_blur is not None:
            text.bind("<FocusOut>", lambda _e, w=widget: on_blur(w))
    except Exception:
        return False
    return True
