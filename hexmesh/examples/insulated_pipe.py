"""
Insulated pipe example.

Three concentric regions — fluid / pipe_wall / insulation — extruded as a
straight pipe segment.  Demonstrates the full workflow:

    PipeSpec  →  Network  →  net.write()  →  .msh

Run
---
    python -m hexmesh.examples.insulated_pipe
    # or
    python insulated_pipe.py

Output
------
    insulated_pipe.msh   (in the current directory)
"""

from __future__ import annotations
import sys
import os

# Allow running directly without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.connectors import Straight


def main(output: str = "insulated_pipe.msh") -> None:
    # ------------------------------------------------------------------
    # Cross-section specification
    # ------------------------------------------------------------------
    pipe = (
        PipeSpec(nang=5, mbmp=1.0)
        .core("fluid",       radius=0.5, nrad=5, mprg=0.9)
        .shell("pipe_wall",  dR=0.1,  nrad=3)
        .shell("insulation", dR=0.2,  nrad=4)
    )

    # ------------------------------------------------------------------
    # Network assembly
    # ------------------------------------------------------------------
    with Model("insulated_pipe", verbose=False) as m:
        net = Network(pipe, direction=[0, 1, 0], up=[0, 0, 1])
        net.add(Straight(length=1.0, n_layers=5))
        net.write(output)

    print(f"Mesh written to: {output}")


if __name__ == "__main__":
    main()
