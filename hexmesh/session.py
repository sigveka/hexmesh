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
GMSH session context manager.

``Assembly`` builds into the current GMSH model; ``Session`` owns the GMSH
process lifetime around it, so the model is always finalized, even on
exception::

    with Session("my_pipe") as s:
        asm = Assembly(pipe)
        asm.add(Straight(1.0, n_layers=10))
        asm.write("my_pipe.msh")
        s.show()            # optional: inspect in the GMSH GUI

The session never merges nodes (no ``removeDuplicateNodes``): the
assembly is conformal by construction (DESIGN.md P2).
"""

from __future__ import annotations

from . import _gmsh
from ._gmsh import gmsh


class Session:
    """Initialize GMSH, add a model, and finalize on exit.

    Needed for ``Assembly.mesh()``, ``check_quality()`` and the pipeline
    steps; ``Assembly.to_mesh()`` needs none.  Opened while a ``Mesh`` is
    open, it shares that gmsh: at its end it closes the meshes made in
    it and removes its own model instead of finalizing (task 0167).

    Parameters
    ----------
    name : str
        Model name passed to ``gmsh.model.add``.
    verbose : bool
        If False (default) GMSH prints errors only.
    """

    def __init__(self, name: str = "hexmesh", verbose: bool = False) -> None:
        self.name = name
        self.verbose = verbose

    def __enter__(self) -> "Session":
        _gmsh.load()                    # GmshUnavailable here, not mid-build
        # gmsh that Assembly.to_mesh() started holds open Meshes: share it,
        # and remove only this session's model at the end (task 0167)
        self._shared = gmsh.isInitialized() and _gmsh.started()
        if not self._shared:
            _gmsh.initialize()          # keeps PATH on Windows (task 0173)
        self._verbosity = gmsh.option.getNumber("General.Verbosity")
        gmsh.option.setNumber("General.Verbosity", 5 if self.verbose else 1)
        gmsh.model.add(self.name)
        self._model = gmsh.model.getCurrent()
        _gmsh.sessions.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        _gmsh.sessions.remove(self)
        for m in list(_gmsh.open_meshes):
            if m._session is self:
                m.close()
        if self._shared:
            gmsh.option.setNumber("General.Verbosity", self._verbosity)
            _gmsh.release(self._model)
        else:
            gmsh.finalize()
            _gmsh.finalized()
        return False

    @staticmethod
    def show() -> None:
        """Open the GMSH GUI on the current model (blocks until closed)."""
        gmsh.fltk.run()
