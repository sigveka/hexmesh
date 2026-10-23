"""
Simple 3-D pipe run.

A single-path pipe that twists through all three dimensions using straight
sections, a sharp mitre turn, a smooth elbow, a reducer and an expander.
No branching — one inlet, one outlet.

How the 3-D path works
----------------------
``Bend`` always curves in the plane spanned by ``cursor.direction`` and
``cursor.up`` (i.e. it rotates around ``cursor.right``).  To change the
bend plane, ``MiterBend(roll=0.0)`` is used first: it rotates around
``cursor.up``, which is a *horizontal* turn that changes ``cursor.right``
so the next ``Bend`` lies in a completely different plane.

Path (all turns 90°)
--------------------
    Cursor starts:  direction = +X,  up = +Z

    Straight(0.5)                          along +X
    MiterBend(90°, roll=0.0)               sharp horizontal left
                                           → direction = +Y,  up = +Z
    Straight(0.5)                          along +Y
    Reducer(PIPE_SMALL, 0.3)              contract to smaller bore
    Bend(R_SMALL, 90°)                     smooth bend *upward*
                                           → direction = +Z,  up = −Y
    Straight(0.4)                          along +Z  [small bore]
    Expander(PIPE_LARGE, 0.3)             expand back to full bore
    MiterBend(90°, roll=0.0)               sharp horizontal left
                                           → direction = −X,  up = −Y
    Straight(0.4)                          along −X  [outlet]

    End position is displaced in all three axes — inlet at (0,0,0),
    outlet near (−0.1, 1.5, 1.4).

Physical groups produced
------------------------
    fluid              — fluid volume
    pipe_wall          — pipe wall volume
    fluid_inlet        — inlet face
    fluid_outlet       — outlet face
    pipe_wall_inlet / pipe_wall_outlet
    fluid_wall         — outer fluid surface
    pipe_wall_wall     — outer pipe surface
    fluid_to_pipe_wall — conformal fluid/wall interface

Run
---
    python -m hexmesh.examples.simple_network
    # produces simple_network.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, Bend, MiterBend, Reducer, Expander


# ---------------------------------------------------------------------------
# Cross-section specifications
# ---------------------------------------------------------------------------

# Large bore (inlet / outlet legs)
R_LARGE  = 0.30
T_LARGE  = 0.06
D_LARGE  = 2 * (R_LARGE + T_LARGE)    # outer diameter ≈ 0.72 m

PIPE_LARGE = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",      radius=R_LARGE, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=T_LARGE, nrad=2)
)

# Small bore (middle section, after reducer)
R_SMALL  = 0.18
T_SMALL  = 0.04
D_SMALL  = 2 * (R_SMALL + T_SMALL)    # outer diameter ≈ 0.44 m
R_BEND   = 1.5 * D_SMALL              # smooth elbow centreline radius

PIPE_SMALL = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",      radius=R_SMALL, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=T_SMALL, nrad=2)
)

# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------

def simple_network(output: str = "simple_network.msh") -> None:
    """Single pipe run that turns and rises through 3-D space."""

    with Model("simple_network", verbose=False) as m:
        net = Network(PIPE_LARGE)

        # ── Leg 1: along +X ──────────────────────────────────────────────
        net.add(Straight(length=0.5, n_layers=5))

        # ── Turn 1: sharp 90° horizontal left (in the XY plane) ─────────
        # MiterBend(roll=0.0) rotates around cursor.up = +Z
        # After: direction = +Y,  up = +Z,  right = +X
        net.add(MiterBend(angle=90, roll=0.0))

        # ── Leg 2: along +Y ──────────────────────────────────────────────
        net.add(Straight(length=0.5, n_layers=5))

        # ── Reducer: large bore → small bore ─────────────────────────────
        net.add(Reducer(outlet=PIPE_SMALL, length=0.3, n_layers=3))

        # ── Turn 2: smooth 90° elbow upward (in the YZ plane) ───────────
        # Bend rotates around cursor.right = +X
        # After: direction = +Z,  up = −Y
        net.add(Bend(radius=R_BEND, angle=90, n_layers=6))

        # ── Leg 3: along +Z (small bore) ─────────────────────────────────
        net.add(Straight(length=0.4, n_layers=4))

        # ── Expander: small bore → large bore ────────────────────────────
        net.add(Expander(outlet=PIPE_LARGE, length=0.3, n_layers=3))

        # ── Turn 3: sharp 90° horizontal left (viewed from above) ────────
        # MiterBend(roll=0.0) rotates around cursor.up = −Y
        # After: direction = −X,  up = −Y
        net.add(MiterBend(angle=90, roll=0.0))

        # ── Leg 4: along −X (outlet) ─────────────────────────────────────
        net.add(Straight(length=0.4, n_layers=4))

        net.write(output)

    print(f"Simple 3-D pipe run  →  {output}")
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
    simple_network()
