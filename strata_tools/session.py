r"""Clearing the console window, without lying about what was cleared.

Ported discipline from Sentinel Forge's ``lyceum/`` functional core: the
rules live here as pure functions with headless tests, and the Tk layer
only renders what they decide.

Two of that project's design laws shape this module:

*Archive, never delete.* Clearing the window must not destroy the
owner's history. Nothing is deleted -- a **floor** is raised, and the
console shows and recalls only threads above it. The rows stay in
SQLite.

*A control that does nothing is a defect.* A Clear that wiped the
transcript but left ``MemoryNode`` feeding the last three turns back to
the model would look clean and then quote the cleared conversation
straight back at the owner. Clearing the view and clearing what the
model recalls are the same action, so they move together.

The floor is monotonic: a later Clear can never sit below an earlier
one, so history cannot reappear because a counter went backwards.
"""

STATE_KEY = "memory_floor"


def parse_floor(raw, default=0):
    """Read a stored floor tolerantly. Pure.

    ``system_state`` holds text, may be missing, and has been hand-edited
    before now. Anything unreadable means "no floor yet" rather than a
    crash that would take the console down at startup.
    """
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def next_floor(current_floor, latest_id):
    """The floor after a Clear. Pure and monotonic.

    ``latest_id`` is the highest thread id at the moment Clear is
    pressed. Never returns less than ``current_floor``: an empty database
    (``latest_id`` 0) or a re-used id must not un-hide what was already
    cleared.
    """
    return max(int(current_floor or 0), int(latest_id or 0))


def is_visible(thread_id, floor):
    """Is this thread above the floor? Pure."""
    return int(thread_id) > int(floor or 0)


def hidden_count(total_threads, visible_threads):
    """How many threads the floor is hiding. Pure, never negative."""
    return max(0, int(total_threads) - int(visible_threads))


def clear_report(cleared, archived_total):
    """What the console says after a Clear. Pure.

    Names the number archived, because "cleared" that silently meant
    "deleted" would be the more alarming reading of the same word.
    """
    if cleared <= 0:
        return ("Window cleared. There was no conversation to carry over"
                " — nothing was archived.")
    turns = "turn" if cleared == 1 else "turns"
    return (f"Window cleared. {cleared} {turns} archived and no longer "
            f"recalled; {archived_total} kept in the database. "
            f"Nothing was deleted.")
