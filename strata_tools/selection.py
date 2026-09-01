r"""Select-all that works on BOTH box species. Pure kernel.

Reused from Sentinel Forge's ``lyceum/select_all.py``, and it is worth
saying why that module exists, because the reason applies here
unchanged.

Owner QA find, 2026-07-21, with a screenshot: "Select all" did nothing
on a single-line field. The old helper spoke only the multi-line Text
API (``tag_add``), so on an Entry it raised AttributeError inside the
callback -- an invisible failure. The control looked present and did
nothing, which is the defect this shop names first.

The kernel dispatches on what the widget can DO, not on its class, so it
needs no tkinter import and tests headless against fakes. Verified
against the real CustomTkinter widgets before wiring:

    CTkEntry    select_range yes · icursor yes · tag_add no
    CTkTextbox  tag_add yes · mark_set yes · see yes · select_range no

Deliberately raises for a widget supporting neither API. The imperative
shell catches it; silence here would recreate the exact invisible
failure this repairs.
"""


def select_all(widget):
    """Select the entire contents of a Text-like or Entry-like widget.

    Raises AttributeError for a widget that is neither -- a Label, say.
    """
    if hasattr(widget, "tag_add"):            # multi-line Text family
        widget.tag_add("sel", "1.0", "end")
        widget.mark_set("insert", "1.0")
        widget.see("insert")
    elif hasattr(widget, "select_range"):     # single-line Entry family
        widget.select_range(0, "end")
        widget.icursor("end")
    else:
        raise AttributeError(
            f"{type(widget).__name__} supports neither tag_add nor "
            f"select_range; select-all has no meaning for it")
