"""
Reducer network example.

A linear pipe run that contracts through a reducer, turns 90°, travels
along the smaller bore, then expands back and turns 90° again.

Geometry
--------
The pipe starts along +X, bends up to +Z, then bends back to −X,
giving a hairpin-like shape in the XZ plane:

    ← (−X) ─────────────────────────────────┐  expander + 2nd bend
                                             │
                    small-bore section (+Z) ─┤
                                             │
    (+X) ────── reducer + 1st bend ──────────┘

Connector sequence
------------------
    Straight(LARGE)          ← inlet run
    Reducer(SMALL)           ← contracts to smaller bore
    Bend(R_SMALL, 90°)       ← turns +X → +Z
    Straight(SMALL)          ← small-bore run
    Expander(LARGE)          ← expands back to full bore
    Bend(R_LARGE, 90°)       ← turns +Z → −X
    Straight(LARGE)          ← outlet run

Physical groups produced
------------------------
    fluid             — fluid volume
    pipe_wall         — pipe wall volume
    fluid_inlet       — single system inlet face
    fluid_outlet      — single system outlet face
    pipe_wall_inlet / pipe_wall_outlet
    fluid_wall        — outer fluid surface
    pipe_wall_wall    — outer pipe surface
    fluid_to_pipe_wall — conformal fluid/wall interface

Run
---
    python -m hexmesh.examples.reducer_network
    # produces reducer_network.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, Bend, Reducer, Expander


# ---------------------------------------------------------------------------
# Cross-section specifications
# ---------------------------------------------------------------------------

# Large-bore pipe (inlet / outlet)
R_LARGE   = 0.30
T_LARGE   = 0.06
D_LARGE   = 2 * (R_LARGE + T_LARGE)     # outer diameter ≈ 0.72 m
R_BEND_L  = 1.5 * D_LARGE               # bend radius for large bore

PIPE_LARGE = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",      radius=R_LARGE, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=T_LARGE, nrad=2)
)

# Small-bore pipe (middle section)
R_SMALL   = 0.18
T_SMALL   = 0.04
D_SMALL   = 2 * (R_SMALL + T_SMALL)     # outer diameter ≈ 0.44 m
R_BEND_S  = 1.5 * D_SMALL               # bend radius for small bore

PIPE_SMALL = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",      radius=R_SMALL, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=T_SMALL, nrad=2)
)

# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------

def reducer_network(output: str = "reducer_network.msh") -> None:
    """Straight → reducer → bend → straight → expander → bend → straight."""

    with Model("reducer_network", verbose=False) as m:
        net = Network(PIPE_LARGE)

        # Inlet run (large bore, along +X)
        net.add(Straight(length=0.5, n_layers=5))

        # Contract to small bore
        net.add(Reducer(outlet=PIPE_SMALL, length=0.3, n_layers=3))

        # First 90° bend: +X → +Z  (in the XZ plane)
        net.add(Bend(radius=R_BEND_S, angle=90, n_layers=6))

        # Small-bore straight run (along +Z)
        net.add(Straight(length=0.5, n_layers=5))

        # Expand back to large bore
        net.add(Expander(outlet=PIPE_LARGE, length=0.3, n_layers=3))

        # Second 90° bend: +Z → −X  (in the ZX plane, same bend axis)
        net.add(Bend(radius=R_BEND_L, angle=90, n_layers=6))

        # Outlet run (large bore, along −X)
        net.add(Straight(length=0.5, n_layers=5))

        net.write(output)

    print(f"Reducer network  →  {output}")
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
    reducer_network()
