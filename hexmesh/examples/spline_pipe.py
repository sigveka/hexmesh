"""
SplinePipe example — hex pipe following a curved 3D path.

Demonstrates two configurations for a single-layer pipe (D = 0.1 m):

    Case A — S-bend in the XY plane
        Smooth S-curve that offsets the pipe centre by 0.2 m laterally
        over an axial run of 0.8 m.  No discrete miter cuts — the full
        path is one SplinePipe connector bracketed by straight inlet/outlet
        runs.

              ╭───────╮
        ──────╯       ╰──────

    Case B — 3D curve
        Pipe curves in both the horizontal (X) and vertical (Z) directions
        while advancing along Y, then returns to a straight outlet.
        Demonstrates that the Bishop (parallel-transport) frame keeps the
        cross-section correctly oriented with no spurious roll.

Physical groups produced
------------------------
    fluid          — fluid volume
    fluid_inlet    — inlet face
    fluid_outlet   — outlet face
    fluid_wall     — outer cylindrical wall

Run
---
    python -m hexmesh.examples.spline_pipe
    # produces spline_s_bend.msh and spline_3d_curve.msh
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight, SplinePipe


# ---------------------------------------------------------------------------
# Shared cross-section  (D_outer = 0.1 m, i.e. R = 0.05 m)
# ---------------------------------------------------------------------------

R_OUTER = 0.05   # pipe outer radius [m]
PIPE = (
    PipeSpec(nang=6)
    .core("fluid", radius=R_OUTER, nrad=4)
)


# ---------------------------------------------------------------------------
# Case A — S-bend in the XY plane
# ---------------------------------------------------------------------------

def s_bend(output: str = "spline_s_bend.msh") -> None:
    """Smooth S-bend: offset pipe centreline by 4R over 16R axial length."""

    with Model("spline_s_bend", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        net.add(Straight(length=0.10, n_layers=2))   # inlet run

        # S-curve: lateral offset +X = 4R, axial length ≈ 16R = 0.8 m
        net.add(SplinePipe(
            waypoints = [
                [0.00, 0.10, 0.0],   # start — matches end of inlet run
                [0.05, 0.25, 0.0],   # shoulder (bends toward +X)
                [0.10, 0.40, 0.0],   # apex of first half
                [0.15, 0.55, 0.0],   # shoulder (straightens back)
                [0.20, 0.70, 0.0],   # start of second half
                [0.20, 0.90, 0.0],   # end — exits straight in +Y
            ],
            n_stations = 10,
            n_layers   = 1,
        ))

        net.add(Straight(length=0.10, n_layers=2))   # outlet run

        net.write(output)

    print(f"S-bend            →  {output}")
    _report(output)


# ---------------------------------------------------------------------------
# Case B — 3D curve
# ---------------------------------------------------------------------------

def curve_3d(output: str = "spline_3d_curve.msh") -> None:
    """Pipe curves in XY then rises in Z; returns to straight outlet."""

    with Model("spline_3d_curve", verbose=False) as m:
        net = Network(PIPE, direction=[0, 1, 0], up=[0, 0, 1])

        net.add(Straight(length=0.10, n_layers=2))   # inlet run

        # 3D path: drifts +X then rises +Z over ~0.7 m
        net.add(SplinePipe(
            waypoints = [
                [ 0.00, 0.10,  0.00],  # start
                [ 0.05, 0.25,  0.00],  # curves in XY
                [ 0.10, 0.40,  0.03],  # begins to rise
                [ 0.10, 0.55,  0.08],  # rises in Z
                [ 0.05, 0.70,  0.10],  # curves back toward Y axis
                [ 0.00, 0.80,  0.10],  # exits offset +Z by 2R
            ],
            n_stations = 10,
            n_layers   = 1,
        ))

        net.add(Straight(length=0.10, n_layers=2))   # outlet run

        net.write(output)

    print(f"3D curve          →  {output}")
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
    s_bend()
    curve_3d()
