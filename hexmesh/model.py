"""
GMSH session context manager.

Wraps gmsh.initialize / gmsh.finalize and gmsh.model.add so that a
hexmesh session is always properly cleaned up, even on exception.

Why Model and Network are separate
-----------------------------------
``Model`` owns the GMSH process lifetime; ``Network`` owns pipe topology
and mesh constraints.  Keeping them separate lets you pause between the
two and call ``m.show()`` to open the GMSH GUI at any point:

::

    with Model("my_pipe", verbose=True) as m:
        net = Network(...)
        net.add(Straight(...))

        net.write_physical_groups()
        m.show()        # inspect geometry before meshing

        net.mesh(dim=3)
        m.show()        # inspect the mesh

        m.write("my_pipe.msh")

``verbose=True`` on ``Model`` restores full GMSH terminal output
(entity counts, meshing progress, quality warnings).

**Important**: always call ``net.mesh()`` rather than ``m.mesh()`` when
the network contains ``Reducer``, ``Expander``, or other connectors that
build geometry manually.  ``net.mesh()`` re-applies deferred transfinite
constraints that ``occ.synchronize()`` would otherwise reset; ``m.mesh()``
skips that step and produces an invalid mesh without raising an error.

The context manager also sets ``Mesh.SubdivisionAlgorithm = 2`` by
default so that any residual tetrahedral elements are subdivided into
hexahedra, giving a hex-dominant volume mesh for all topologies.
"""

from __future__ import annotations
import gmsh


class Model:
    """GMSH session context manager.

    Parameters
    ----------
    name : str
        Model name passed to gmsh.model.add.
    verbose : bool
        If False (default) suppress most GMSH terminal output.
    subdivide : bool
        Apply ``Mesh.SubdivisionAlgorithm = 2`` before meshing so that
        tetrahedral elements from any non-structured regions are
        subdivided into hexahedra.  Default True.
    """

    def __init__(
        self,
        name:      str = "hexmesh",
        verbose:   bool = False,
        subdivide: bool = True,
    ) -> None:
        self._name      = name
        self._verbose   = verbose
        self._subdivide = subdivide

    def __enter__(self) -> "Model":
        gmsh.initialize()
        if not self._verbose:
            gmsh.option.setNumber("General.Verbosity", 1)
        gmsh.model.add(self._name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        gmsh.finalize()
        return False   # do not suppress exceptions

    def mesh(self, dim: int = 3) -> None:
        """Generate the mesh.

        Parameters
        ----------
        dim : int
            Mesh dimension (1, 2, or 3).
        """
        gmsh.model.occ.synchronize()
        if self._subdivide and dim == 3:
            gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 2)
        gmsh.model.mesh.generate(dim)
        try:
            gmsh.model.mesh.removeDuplicateNodes()
        except AttributeError:
            pass  # gmsh < 4.4
        try:
            gmsh.model.mesh.optimize()
        except AttributeError:
            pass  # gmsh < 4.4 does not expose mesh.optimize()

    def write(self, path: str) -> None:
        """Write the mesh to *path* (format determined by extension).

        Common extensions: ``.msh`` (GMSH), ``.vtk``, ``.cgns``.
        """
        gmsh.write(path)

    def show(self) -> None:
        """Open the GMSH GUI to inspect the model (blocking)."""
        gmsh.fltk.run()
