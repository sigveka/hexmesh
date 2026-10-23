"""
Pipe network example.

Demonstrates a small distribution network with two T-junctions and a smooth
elbow, producing one inlet and three outlets.

Network topology
----------------
    CURSOR (dir=+X, up=+Z)
      │
    Straight(0.5)                 ← inlet run
      │ n_inlet
    TJunction(branch_dir=+Y)      ← horizontal split: main +X, branch_1 +Y
      │                  └─────────────────────────────────────────
    Straight(0.5)                  Bend(R_BEND_B, 90°)   ← curves +Y → +Z
      │ n_main1                    │ n_b1_bend
    TJunction(branch_dir=+Z)       Straight(0.4)
      │                  └───      outlet_b1 (exits along +Z)
    Straight(0.4)          Straight(0.4)
    outlet_main            outlet_b2 (exits along +Z)

Cross-section notes
-------------------
    Main pipe: fluid (r=0.30) + pipe_wall shell (dR=0.06), nang=6.
    Branch stubs: fluid-only with r=R_BRANCH (= R_outer/2 = 0.18), nang=6.
    r=R_outer/2 satisfies the saddle-arc conformality condition for nang=6
    (arcsin(0.5) = 30° = 2 × 15° = 2 × 90°/nang).

Physical groups produced
------------------------
    fluid             — fluid volume
    pipe_wall         — pipe wall volume
    fluid_inlet       — single system inlet face
    fluid_outlet      — main + branch_1 + branch_2 outlet faces
    pipe_wall_inlet   — same for pipe wall layer
    pipe_wall_outlet  — same
    fluid_wall        — outer fluid surface (cylindrical walls)
    pipe_wall_wall    — outer pipe surface
    fluid_to_pipe_wall — conformal fluid/wall interface

Run
---
    python -m hexmesh.examples.pipe_network
    # produces pipe_network.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, Bend, TJunction


# ---------------------------------------------------------------------------
# Shared cross-section
# ---------------------------------------------------------------------------
R_FLUID  = 0.30
T_WALL   = 0.06
R_OUTER  = R_FLUID + T_WALL       # 0.36 m — main pipe outer radius
D_OUTER  = 2 * R_OUTER            # 0.72 m

# Branch stub radius: R_OUTER/2 gives arcsin(0.5) = 30° = 2 × (90°/6)
# → conformal saddle arc with nang=6.
R_BRANCH = R_OUTER / 2            # 0.18 m

# nang=6: divisions per 90° arc.  Required for R_BRANCH/R_OUTER = 0.5
# conformality (nang=5 does not divide 30° evenly into 15° steps).
PIPE = (
    PipeSpec(nang=6, mbmp=1.0)
    .core("fluid",      radius=R_FLUID, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=T_WALL, nrad=2)
)

# Bend radius for branch legs (fluid-only, r=R_BRANCH).
R_BEND_B = 1.5 * 2 * R_BRANCH     # 0.54 m


# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------

def pipe_network(output: str = "pipe_network.msh") -> None:
    """Distribution network: inlet → two T-junctions → three outlets."""
    with Model("pipe_network", verbose=False) as m:
        net = Network(PIPE)

        # ── Inlet run ────────────────────────────────────────────────────
        n_inlet = net.add(Straight(length=0.5, n_layers=5))

        # ── First T-junction (horizontal split in XY plane) ──────────────
        # main → continues along +X
        # branch_1 → branch_direction=[0,1,0] → +Y
        n_main1, n_b1 = net.add(
            n_inlet,
            TJunction(
                approach_length  = D_OUTER / 2,   # 0.36 >= R_BRANCH ✓
                branch_length    = 0.40,           # > R_OUTER ✓
                branch_direction = [0, 1, 0],
                branch_r         = R_BRANCH,
                n_layers         = 2,
            ),
        )

        # ── branch_1: smooth 90° elbow (YZ plane) + outlet run ───────────
        # cursor at n_b1 has direction=+Y, up=+Z → bend curves toward +Z
        n_b1_bend = net.add(n_b1, Bend(radius=R_BEND_B, angle=90, n_layers=6))
        net.add(n_b1_bend, Straight(length=0.4, n_layers=4))

        # ── Second T-junction (vertical split in XZ plane) ───────────────
        # main → continues along +X
        # branch_2 → branch_direction=[0,0,1] → +Z
        n_main2, n_b2 = net.add(
            n_main1,
            TJunction(
                approach_length  = D_OUTER / 2,   # 0.36 >= R_BRANCH ✓
                branch_length    = 0.40,           # > R_OUTER ✓
                branch_direction = [0, 0, 1],
                branch_r         = R_BRANCH,
                n_layers         = 2,
            ),
        )

        # ── Outlet runs ───────────────────────────────────────────────────
        net.add(n_main2, Straight(length=0.4, n_layers=4))   # main outlet (+X)
        net.add(n_b2,    Straight(length=0.4, n_layers=4))   # branch_2 outlet (+Z)

        net.write(output)

    print(f"Pipe network  →  {output}")
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
    pipe_network()
