"""
Y-junction example.

Demonstrates a symmetric Y-junction: one inlet run splits into two equal
branches, each deflected by ±45° from the inlet direction.  Neither branch
continues straight — both use fresh faces perpendicular to their respective
extrusion directions so no zero-volume hexahedra are produced.

Network topology
----------------
    CURSOR (dir=+Y, up=+Z)
           │
         Straight(0.4)          ← inlet run
           │ n_inlet
         YJunction(±45°, roll=0.0)   ← split block
        /             \\
  Straight(0.4)   Straight(0.4)
  branch_1 (+45°)  branch_2 (−45°)

Physical groups produced
------------------------
    fluid             — fluid volume
    pipe_wall         — pipe wall volume
    fluid_inlet       — single system inlet face (upstream of split)
    fluid_outlet      — branch_1 + branch_2 outlet faces
    pipe_wall_inlet   — same for pipe wall layer
    pipe_wall_outlet  — same
    fluid_wall        — outer fluid surface (cylindrical walls)
    pipe_wall_wall    — outer pipe surface
    fluid_to_pipe_wall — conformal fluid/wall interface

Run
---
    python -m hexmesh.examples.y_junction
    # produces y_junction.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import math

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, YJunction


# ---------------------------------------------------------------------------
# Shared cross-section
# ---------------------------------------------------------------------------
# rot=-π/4 is required by build_y_junction_block: with this rotation the inner
# corners land at E/N/W/S (cardinal axes) so the N-S split line falls exactly
# along inner-corner boundaries.
PIPE = (
    PipeSpec(nang=5, mbmp=1.0, rot=-math.pi / 4)
    .core("fluid",      radius=0.3, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=0.06, nrad=2)
)

# Junction block length — half the outer diameter is a good default
D_OUTER  = 2 * (0.3 + 0.06)   # ≈ 0.72 m
JUNC_LEN = D_OUTER / 2         # ≈ 0.36 m


# ---------------------------------------------------------------------------
# Y-junction case
# ---------------------------------------------------------------------------

def y_junction(output: str = "y_junction.msh") -> None:
    """Symmetric ±45° Y-junction: one inlet splits into two equal branches."""

    with Model("y_junction", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        # Inlet run
        n_inlet = net.add(Straight(length=0.4, n_layers=4))

        # Y-split: both branches deflect ±45° from the inlet direction.
        # roll=0.0 rotates around cursor.up (horizontal plane split).
        # length sets the axial extent of each branch block.
        n1, n2 = net.add(
            n_inlet,
            YJunction(
                length=JUNC_LEN,
                half_angle=45,
                roll=0.0,
                n_layers=2,
            ),
        )

        # Outlet runs on each branch
        net.add(n1, Straight(length=0.4, n_layers=4))
        net.add(n2, Straight(length=0.4, n_layers=4))

        net.write(output)

    print(f"Y-junction  →  {output}")
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
    y_junction()
