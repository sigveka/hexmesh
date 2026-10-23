"""
Multi wall zone example.

Demonstrates position-based wall BC assignment using ``outer_wall_classifier``.
By default ``net.write()`` puts all outer wall surfaces for a given material into
one group (e.g. ``fluid_wall``).  Passing a classifier lets you split that group
into any number of named zones without touching the connector code.

Two cases are shown:

    Case A — heated pipe section
        Three consecutive straight segments; the middle one is labelled
        ``wall_heated``, the two end segments are ``wall_adiabatic``.  Common
        in conjugate heat transfer (CHT) simulations where a localised
        heating/cooling source wraps a pipe section.

        Physical groups produced
        ─────────────────────────────────
            fluid            — fluid volume
            fluid_inlet      — upstream face
            fluid_outlet     — downstream face
            wall_adiabatic   — cylindrical wall at entry and exit
            wall_heated      — cylindrical wall of the heated section

    Case B — Y-junction with per-branch walls
        Inlet run + symmetric ±45° Y-split; the inlet run and each branch
        get independent wall groups.  Useful when the two branches carry
        different fluids (or fluids at different temperatures) and each wall
        section needs a separate BC.

        Physical groups produced
        ─────────────────────────────────
            fluid            — fluid volume
            fluid_inlet      — upstream face
            fluid_outlet     — both branch outlet faces
            wall_inlet       — cylindrical wall of the inlet run
            wall_branch_1    — cylindrical wall of the right branch (+X side)
            wall_branch_2    — cylindrical wall of the left branch (−X side)

Run
---
    python -m hexmesh.examples.wall_zones
    # produces wall_heated.msh and wall_zones_y.msh
"""

from __future__ import annotations
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import gmsh

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, YJunction


# ---------------------------------------------------------------------------
# Case A — heated pipe section
# ---------------------------------------------------------------------------

# Single-layer pipe running along +Y; outer wall is the no-slip / heat-flux surface.
_PIPE_A = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=4)

L_COLD_IN  = 0.10   # unheated entry length [m]
L_HOT      = 0.20   # heated section length [m]
L_COLD_OUT = 0.10   # unheated exit length  [m]

# Axial bounds of the heated section (pipe runs along Y).
_Y_HOT_START = L_COLD_IN
_Y_HOT_END   = L_COLD_IN + L_HOT


def _wall_classifier_heated(surf_tag: int) -> str:
    """Return ``wall_heated`` for surfaces in the heated section, else ``wall_adiabatic``.

    ``getBoundingBox`` returns (xmin, ymin, zmin, xmax, ymax, zmax); the midpoint
    y-coordinate reliably identifies which axial segment a cylindrical arc patch
    belongs to.
    """
    bb = gmsh.model.getBoundingBox(2, surf_tag)
    cy = (bb[1] + bb[4]) / 2
    if _Y_HOT_START <= cy <= _Y_HOT_END:
        return "wall_heated"
    return "wall_adiabatic"


def heated_pipe(output: str = "wall_heated.msh") -> None:
    """Straight inlet → heated section → straight outlet with split wall BCs."""

    with Model("wall_heated", verbose=False):
        net = Network(_PIPE_A, direction=[0, 1, 0], up=[0, 0, 1])

        net.add(Straight(L_COLD_IN,  n_layers=3))   # cold entry
        net.add(Straight(L_HOT,      n_layers=6))   # heated section
        net.add(Straight(L_COLD_OUT, n_layers=3))   # cold exit

        net.write(output, outer_wall_classifier=_wall_classifier_heated)

    print(f"Heated pipe  →  {output}")
    _report(output)


# ---------------------------------------------------------------------------
# Case B — Y-junction with per-branch wall zones
# ---------------------------------------------------------------------------

# rot=-π/4 required for n_outer=4: inner corners land on cardinal axes so the
# N-S bifurcation split falls exactly along corner boundaries.
_PIPE_B = (
    PipeSpec(nang=4, rot=-math.pi / 4)
    .core("fluid", radius=0.1, nrad=3)
)

# Network runs along +Y; junction cursor is at y = L_INLET.
L_INLET  = 0.40   # inlet run length [m]
L_BRANCH = 0.40   # outlet run length on each branch [m]

# With roll=0 and cursor up=+Z, branch_1 deflects toward +X, branch_2 toward -X.
# Classifier splits post-junction surfaces by the sign of their centroid's x-coord.
# Surfaces at the bifurcation block are assigned to the nearest branch by the same
# criterion; a small number of arc patches right at the split may land on either
# side — this is acceptable for a CFD wall-BC assignment.


def _wall_classifier_y(surf_tag: int) -> str:
    """Three-zone classifier: inlet / branch_1 (right) / branch_2 (left)."""
    bb = gmsh.model.getBoundingBox(2, surf_tag)
    cx = (bb[0] + bb[3]) / 2
    cy = (bb[1] + bb[4]) / 2
    if cy < L_INLET:
        return "wall_inlet"          # inlet run — strictly upstream of junction
    return "wall_branch_1" if cx >= 0 else "wall_branch_2"


def y_wall_zones(output: str = "wall_zones_y.msh") -> None:
    """Y-junction mesh with three independent wall BC zones."""

    with Model("wall_zones_y", verbose=False):
        net = Network(_PIPE_B, direction=[0, 1, 0], up=[0, 0, 1])

        n_inlet = net.add(Straight(L_INLET, n_layers=4))

        n1, n2 = net.add(
            n_inlet,
            YJunction(
                length=L_BRANCH,
                half_angle=45,
                roll=0.0,
                n_layers=2,
            ),
        )

        net.write(output, outer_wall_classifier=_wall_classifier_y)

    print(f"Y wall zones →  {output}")
    _report(output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report(path: str) -> None:
    """Print a brief summary of the mesh file's physical groups."""
    groups = []
    in_block = False
    with open(path) as fh:
        for line in fh:
            if "$PhysicalNames" in line:
                in_block = True
                continue
            if "$EndPhysicalNames" in line:
                break
            if in_block:
                parts = line.split()
                if len(parts) == 3:
                    dim, tag, name = parts
                    groups.append((int(dim), name.strip('"')))

    vols  = [n for d, n in groups if d == 3]
    surfs = [n for d, n in groups if d == 2]
    print(f"  volumes  : {vols}")
    print(f"  surfaces : {surfs}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    heated_pipe()
    y_wall_zones()
