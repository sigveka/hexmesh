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

import gmsh


class Session:
    """Initialize GMSH, add a model, and finalize on exit.

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
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 5 if self.verbose else 1)
        gmsh.model.add(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        gmsh.finalize()
        return False

    @staticmethod
    def show() -> None:
        """Open the GMSH GUI on the current model (blocks until closed)."""
        gmsh.fltk.run()
