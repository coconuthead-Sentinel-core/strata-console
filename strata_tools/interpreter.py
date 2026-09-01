r"""Which Python interpreter is Strata actually running under?

The microphone "broke" without a line of voice code changing. The cause
was never the microphone and never the RAM ceiling the previous fix
addressed -- it was that ``launch_strata.vbs`` hunted down the *Store*
Python under ``C:\Program Files\WindowsApps`` and launched that, while
``sounddevice`` and ``faster_whisper`` had been installed into the
ordinary per-user install at ``%LOCALAPPDATA%\Programs\Python``. The
console imported ``sounddevice``, got ``ModuleNotFoundError``, and said
so -- correctly, but the owner reads that as "the mic is dead".

The trap that made it stick: the old message said ``pip install
sounddevice``. Typed at a normal prompt that resolves to the *other*
interpreter, which already had it, so pip answered "Requirement already
satisfied" and the console still refused. Advice that cannot work is a
defect, so the message here is always pinned to ``sys.executable``.

Everything except :func:`current_report` is pure -- the filesystem is
injected as an ``exists`` probe -- so the rule can be graded without a
microphone, a model, or a second Python install.
"""

import os
import sys

# Import name -> what it is on disk inside ``Lib/site-packages``.
# ``sounddevice`` ships as a single module file; ``faster_whisper`` is a
# package directory. Both spellings are probed, so neither layout can
# make a present dependency look missing.
VOICE_DEPS = ("sounddevice", "faster_whisper")


def site_packages(py_dir):
    """The ``Lib/site-packages`` belonging to an interpreter directory."""
    return os.path.join(py_dir, "Lib", "site-packages")


def dep_present(py_dir, dep, exists):
    """Is ``dep`` installed under ``py_dir``? Pure -- ``exists`` is the probe.

    A dependency counts as present as either ``<dep>.py`` or ``<dep>/``,
    because a package that ships as one module file is still installed.
    """
    root = site_packages(py_dir)
    return exists(os.path.join(root, dep + ".py")) or \
        exists(os.path.join(root, dep))


def missing_deps(py_dir, exists, deps=VOICE_DEPS):
    """Which of ``deps`` are absent under ``py_dir``. Pure."""
    return [d for d in deps if not dep_present(py_dir, d, exists)]


def has_voice_deps(py_dir, exists, deps=VOICE_DEPS):
    """Can this interpreter run the whole voice path? Pure."""
    return not missing_deps(py_dir, exists, deps)


def rank_candidates(py_dirs, exists, deps=VOICE_DEPS):
    """Order interpreters best-first: voice-capable ones win.

    Ordering within each group is preserved, so the caller's own
    preference still decides between two equally capable installs. This
    is the rule ``launch_strata.vbs`` implements at launch time; it lives
    here in testable form so the rule can be graded on the bench.
    """
    capable = [d for d in py_dirs if has_voice_deps(d, exists, deps)]
    rest = [d for d in py_dirs if not has_voice_deps(d, exists, deps)]
    return capable + rest


def install_command(executable, deps):
    """The pip line that installs ``deps`` into *this* interpreter.

    Pinned to the running executable on purpose. A bare ``pip install``
    is what sent the owner in a circle.
    """
    return f'"{executable}" -m pip install ' + " ".join(deps)


def explain_missing(executable, missing):
    """Owner-facing text naming the interpreter and the command that fixes it.

    Pure: the caller supplies the executable and the gap.
    """
    names = " and ".join(missing)
    return (f"Voice needs {names}, which is not installed for the Python "
            f"that is running Strata:\n    {executable}\n"
            f"Another Python on this machine may already have it -- that is "
            f"why a bare 'pip install' looks like it succeeds and changes "
            f"nothing. Install it into this one:\n"
            f"    {install_command(executable, missing)}\n"
            f"Or relaunch with launch_strata.vbs, which now prefers a "
            f"Python that already carries the voice packages.")


def current_report(deps=VOICE_DEPS):
    """``(executable, missing)`` for the interpreter running right now.

    Impure: it asks the live import system rather than the filesystem
    layout, so it stays correct for virtualenvs and unusual installs.
    """
    import importlib.util
    missing = []
    for dep in deps:
        try:
            found = importlib.util.find_spec(dep) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(dep)
    return (sys.executable, missing)
