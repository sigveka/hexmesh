"""
Smooth 90° bend example.

Demonstrates a rotational-extrusion elbow between two straight runs for
a two-layer insulated pipe (fluid core + pipe wall).

Geometry
--------
The pipe runs horizontally along the +X axis, executes a 90° smooth
elbow in the XZ plane, then exits vertically along the +Z axis.

    ↑  (+Z)
    │
    ╰────────  (+X)

Starting cursor:
  direction = (1, 0, 0)       ← pipe runs along +X
  up        = (0, 0, 1)       ← "up" is +Z
  right     = direction × up  = (0, −1, 0)   ← bend axis, curves in XZ plane

After Bend(radius, angle=90):
  direction = (0, 0, 1)       ← outlet runs along +Z
  bend centre at inlet_pos + radius·up = (x_inlet, 0, radius)

Parameters
----------
The bend radius R_bend is measured from the pipe centreline to the
centre of curvature.  Choose R_bend ≥ D_outer to avoid cell folding.

Physical groups produced
------------------------
    fluid             — fluid volume
    pipe_wall         — pipe wall volume
    fluid_inlet       — inlet face
    fluid_outlet      — outlet face
    pipe_wall_inlet   — inlet face (wall layer)
    pipe_wall_outlet  — outlet face (wall layer)
    fluid_wall        — outer surface of fluid (fluid/wall interface)
    pipe_wall_wall    — outer surface of pipe (external surface)
    fluid_to_pipe_wall — conformal interface

Run
---
    python -m hexmesh.examples.smooth_bend
    # produces smooth_bend.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, Bend


# ---------------------------------------------------------------------------
# Cross-section
# ---------------------------------------------------------------------------
PIPE = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",      radius=0.3, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=0.06, nrad=2)
)

# Default Network orientation: direction = +X, up = +Z
# right = direction × up = (0,–1,0) → bend curves in the XZ plane toward –Z

R_FLUID     = 0.3           # fluid core radius
T_WALL      = 0.06          # pipe wall thickness
D_OUTER     = 2 * (R_FLUID + T_WALL)   # ≈ 0.72 m
R_BEND      = 1.5 * D_OUTER            # bend radius (centreline to centre of curvature)


# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------

def smooth_bend(output: str = "smooth_bend.msh") -> None:
    """Straight inlet → 90° smooth elbow → straight outlet."""

    with Model("smooth_bend", verbose=False) as m:
        net = Network(PIPE)

        net.add(Straight(length=0.5, n_layers=5))          # inlet run
        net.add(Bend(radius=R_BEND, angle=90, n_layers=8)) # smooth elbow
        net.add(Straight(length=0.5, n_layers=5))          # outlet run

        net.write(output)

    print(f"Smooth 90° bend  →  {output}")
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
    smooth_bend()
