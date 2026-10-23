"""
Miter bend example.

Demonstrates two miter configurations for an insulated pipe:

    Case A — single-cut 90° miter
        One abrupt direction change.  Produces the sharpest joint
        and the most skewed cells at the corner.

        ──────────┐
                  │

    Case B — 3-cut 90° miter  (multi-piece approximation)
        Three 30° miter cuts with short straight segments between
        them, approximating a smooth elbow with flat faces.
        Common in sheet-metal HVAC ductwork.

        ─────────╮
                 ╰─
                   │

Both cases use the same cross-section: fluid core + pipe wall.

Physical groups produced per case
----------------------------------
    fluid             — fluid volume
    pipe_wall         — pipe wall volume
    fluid_inlet       — inlet face
    fluid_outlet      — outlet face
    pipe_wall_inlet   — inlet face (wall layer)
    pipe_wall_outlet  — outlet face (wall layer)
    fluid_wall        — outer wall of fluid (= fluid/wall interface)
    pipe_wall_wall    — outer wall of pipe (external surface)
    fluid_to_pipe_wall — conformal interface

Run
---
    python -m hexmesh.examples.miter_bend
    # produces miter_single.msh and miter_3cut.msh
"""

from __future__ import annotations
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, MiterBend


# ---------------------------------------------------------------------------
# Shared cross-section
# ---------------------------------------------------------------------------
PIPE = (
    PipeSpec(nang=5, mbmp=1.0)
    .core("fluid",     radius=0.3, nrad=4, mprg=0.9)
    .shell("pipe_wall", dR=0.06, nrad=2)
)



# ---------------------------------------------------------------------------
# Case A — single-cut 90° miter
# ---------------------------------------------------------------------------

def single_cut_miter(output: str = "miter_single.msh") -> None:
    """One 90° miter joint between two straight legs."""

    with Model("miter_single", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        net.add(Straight(length=0.5, n_layers=5))   # inlet leg
        net.add(MiterBend(angle=90, roll=0.0))       # ← instantaneous turn
        net.add(Straight(length=0.5, n_layers=5))   # outlet leg

        net.write(output)

    print(f"Single-cut miter  →  {output}")
    _report(output)


# ---------------------------------------------------------------------------
# Case B — 3-cut 90° miter
# ---------------------------------------------------------------------------

def three_cut_miter(output: str = "miter_3cut.msh") -> None:
    """Three 30° miter cuts approximating a smooth 90° elbow."""

    n_cuts       = 3
    total_angle  = 90.0
    cut_angle    = total_angle / n_cuts   # 30° per cut
    leg_length   = 0.12                  # straight length between cuts
    n_leg_layers = 2                     # hex layers per leg

    with Model("miter_3cut", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        net.add(Straight(length=0.4, n_layers=4))    # inlet run

        for _ in range(n_cuts):
            net.add(Straight(length=leg_length, n_layers=n_leg_layers))
            net.add(MiterBend(angle=cut_angle, roll=0.0))

        net.add(Straight(length=0.4, n_layers=4))    # outlet run

        net.write(output)

    print(f"3-cut miter       →  {output}")
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
    single_cut_miter()
    three_cut_miter()
