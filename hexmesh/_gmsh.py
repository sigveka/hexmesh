#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
gmsh, loaded when first used (task 0107).

Only building and meshing need gmsh, and importing it costs about 0.13 s
and fails where its shared libraries can't load (decision 0039).  The
modules that call gmsh import it from here::

    from ._gmsh import gmsh

and keep their ``gmsh.model…`` calls.  The first attribute read imports
the real module; :class:`~hexmesh.Session` does that when it starts, so
meshing behaves as before.  When the import fails, :func:`load` raises
:class:`~hexmesh.errors.GmshUnavailable` with the reason and the fix.
"""

from __future__ import annotations

import atexit
import sys
import weakref
from contextlib import contextmanager

from .errors import GmshUnavailable

#: the commands that work without gmsh: hexmesh.agent._commands.NEEDS_GMSH
#: lists the rest
WITHOUT_GMSH = "schema, manifest, validate, estimate, describe, preview, advise and apply"

_module = None


def load():
    """The real gmsh module, imported on the first call."""
    global _module
    if _module is None:
        try:
            import gmsh as module
        except (ImportError, OSError) as e:          # OSError: a shared library missing
            fix = "pip install gmsh"
            if sys.platform.startswith("linux"):
                fix += ("; on Linux gmsh also needs libglu1-mesa, libxrender1, libxcursor1, "
                        "libxft2 and libxinerama1 (as in .github/workflows/tests.yml)")
            raise GmshUnavailable(
                f"gmsh could not be imported ({type(e).__name__}: {e}); building and meshing "
                f"need it, but {WITHOUT_GMSH} work without it",
                code="gmsh_unavailable", value=f"{type(e).__name__}: {e}", hint=fix) from e
        _module = module
    return _module


class _Lazy:
    """Stands in for the gmsh module: every attribute is the real module's."""

    __slots__ = ()

    def __getattr__(self, name):
        return getattr(load(), name)

    def __repr__(self) -> str:
        return "<gmsh, loaded on first use>" if _module is None else repr(_module)


gmsh = _Lazy()


# --- who drives gmsh (task 0167) --------------------------------------------
# A Session started by the caller, gmsh initialized by the caller's own
# code, or hexmesh itself for Assembly.to_mesh(), which initializes gmsh
# when nothing has and finalizes it when its last Mesh closes (or at exit).
# Each Mesh holds a model of its own.

_started = False                  # hexmesh initialized gmsh (to_mesh)
sessions: list = []               # the Sessions open now, innermost last
open_meshes: "weakref.WeakSet" = weakref.WeakSet()
_inside = 0                       # depth of to_mesh / Mesh calls running


def started() -> bool:
    """True while the running gmsh is the one hexmesh started: one of its
    meshes' models is alive, or a to_mesh is running.  The caller may
    have finalized it, and maybe initialized gmsh again, under them."""
    global _started
    if _started and _inside == 0:
        live = set(models())
        if not any(m._model in live for m in open_meshes):
            _started = False
    return _started


def caller_drives() -> bool:
    """True inside a Session, or when the caller initialized gmsh
    itself: the calls that act on gmsh's current model may run."""
    started()
    return (_module is not None and _module.isInitialized()
            and (bool(sessions) or not _started))


def may_mesh() -> bool:
    """True where the assembly's gmsh calls may run: in the caller's gmsh
    (:func:`caller_drives`) or inside a to_mesh / Mesh call."""
    return _inside > 0 or caller_drives()


def models() -> list[str]:
    """The model names of the running gmsh; none when it isn't running."""
    if _module is None or not _module.isInitialized():
        return []
    return _module.model.list()


def start() -> None:
    """Initialize gmsh if nothing has, quietly, and finalize it at exit."""
    global _started
    module = load()
    started()
    if module.isInitialized():
        return
    module.initialize()
    module.option.setNumber("General.Verbosity", 1)
    if not _started:
        atexit.register(_finish)
    _started = True


def _finish() -> None:
    """At exit: forget the open meshes, then finalize the gmsh hexmesh
    started.  Never raises."""
    global _started
    for m in list(open_meshes):
        m._forget()
    try:
        if _started and _module is not None and _module.isInitialized() and not sessions:
            _module.finalize()
    except Exception:                                   # noqa: BLE001  (exit)
        pass
    _started = False


def finalized() -> None:
    """gmsh was finalized (a Session ended): every open mesh is gone."""
    global _started
    for m in list(open_meshes):
        m._forget()
    _started = False


@contextmanager
def model(name: str):
    """*name* the current model inside the block (it must exist), and the
    caller's current model again after it, so a call never moves it."""
    global _inside
    previous = _module.model.getCurrent()
    _module.model.setCurrent(name)
    _inside += 1
    try:
        yield
    finally:
        _inside -= 1
        if previous in _module.model.list():
            _module.model.setCurrent(previous)


def release(name: str) -> None:
    """Remove model *name*, keeping the current model current; then
    finalize the gmsh hexmesh started once nothing uses it (no Session,
    no open Mesh), so it never outlives its meshes.  Never raises: it
    runs from ``weakref.finalize``, maybe at exit."""
    remove_model(name)
    global _started
    try:
        if _started and not sessions and not open_meshes and _module.isInitialized():
            _module.finalize()
            _started = False
    except Exception:                                   # noqa: BLE001  (finalizer)
        pass


def remove_model(name: str) -> None:
    """Remove model *name*, keeping the current model current.  Never
    raises."""
    try:
        if _module is None or not _module.isInitialized() or name not in _module.model.list():
            return
        previous = _module.model.getCurrent()
        _module.model.setCurrent(name)
        _module.model.remove()
        if previous != name and previous in _module.model.list():
            _module.model.setCurrent(previous)
    except Exception:                                   # noqa: BLE001  (finalizer)
        pass
