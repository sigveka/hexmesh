"""
T-junction example — side-tap stub block architecture.

Demonstrates the non-overlapping all-hex T-junction using the
``branch_r`` parameter.  A stub block connects the saddle-curve opening
on the main pipe outer surface to the branch OH inlet face; no volumes
overlap.

The ``approach_length`` and ``departure_length`` parameters define the
straight runs upstream and downstream of the T-point that are built
*inside* the TJunction block.  In CFD practice these are typically
1–2 main pipe diameters to allow flow development near the junction.

Network topology
----------------
    CURSOR
      │
    Straight(inlet_run)              ← inlet run (before TJunction approach)
      │ n_inlet
    TJunction(branch_r=R_BRANCH)     ← approach + stub + departure
     │                └───
    Straight(outlet_run)   Straight(0.5)
    n_main                 n_branch
      │                      │
    main outlet            branch outlet (fluid only)

Geometry
--------
    Main pipe outer radius   R_OUTER  = 0.36 m  (fluid 0.30 + wall 0.06)
    Branch pipe outer radius R_BRANCH = 0.18 m  (half of main)
    D_OUTER  = 2 × R_OUTER  = 0.72 m  (main pipe outer diameter)
    approach_length = departure_length = D_OUTER (1 diameter each side)
    branch_length = 0.40 m  > R_OUTER (required by stub block)

Notes
-----
The stub block and branch Straight carry the **fluid** layer only; the
pipe_wall shell is not extended into the branch in this example.

Physical groups produced
------------------------
    fluid             — fluid volumes (main + branch)
    pipe_wall         — pipe wall volumes (main only)
    fluid_inlet       — single system inlet face
    fluid_outlet      — main + branch outlet faces
    pipe_wall_inlet   — pipe wall inlet face
    pipe_wall_outlet  — pipe wall main outlet face
    fluid_wall        — outer fluid surface
    pipe_wall_wall    — outer pipe surface
    fluid_to_pipe_wall — conformal fluid/wall interface

Run
---
    python -m hexmesh.examples.t_junction
    # produces t_junction.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "..", "pipemesh", "pipemesh"))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, TJunction


# ---------------------------------------------------------------------------
# Shared cross-section
# ---------------------------------------------------------------------------
PIPE = (
    PipeSpec(nang=6, mbmp=1.0)
    .core("fluid",      radius=0.3, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=0.06, nrad=2)
)

# Outer radius of main pipe — used to size the junction block
R_OUTER  = 0.3 + 0.06          # fluid core + pipe wall = 0.36 m
R_BRANCH = R_OUTER / 2         # branch outer radius = 0.18 m
D_OUTER  = 2 * R_OUTER         # main pipe outer diameter = 0.72 m


# ---------------------------------------------------------------------------
# T-junction case
# ---------------------------------------------------------------------------

def t_junction(output: str = "t_junction.msh") -> None:
    """Single 90° T-junction: inlet → stub-block junction → main + branch."""

    with Model("t_junction", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        # Inlet run — ends one approach_length before the T-point so the
        # cursor arrives at the TJunction entry face.
        APPROACH  = D_OUTER   # 1 main-pipe diameter approach within junction
        DEPARTURE = D_OUTER   # 1 main-pipe diameter departure within junction
        n_inlet = net.add(Straight(length=4 - APPROACH, n_layers=4))

        # Junction block — side-tap stub block (non-overlapping).
        # approach_length / departure_length set the straight runs built
        # inside the junction block upstream/downstream of the T-point.
        # branch_length must exceed R_OUTER so the branch face clears
        # the main pipe outer surface.
        n_main, n_branch = net.add(
            n_inlet,
            TJunction(
                approach_length  = APPROACH,
                departure_length = DEPARTURE,
                branch_length    = 0.40,        # > R_OUTER = 0.36
                branch_direction = [1, 0, 0],
                n_layers         = 2,
                branch_r         = R_BRANCH,    # enables stub-block path
            ),
        )

        # Outlet runs (after junction departure)
        net.add(n_main,   Straight(length=1.0, n_layers=4))
        net.add(n_branch, Straight(length=0.5, n_layers=4))

        net.write(output)

    print(f"T-junction  →  {output}")
    _report(output)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _report(path: str) -> None:
    """Print a brief summary of the mesh file's Physical groups."""
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
    t_junction()
