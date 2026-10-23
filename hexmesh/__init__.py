"""
hexmesh — composable structured hex mesh generation for CFD pipe systems.

Quick start
-----------
::

    from hexmesh import Model
    from hexmesh.core import PipeSpec, Cursor, Plane
    from hexmesh.core.shape import CircleShape
    from hexmesh.connectors import Straight, Bend
    from hexmesh.network import Network

    pipe = (
        PipeSpec(nang=5)
        .core("fluid",      shape=CircleShape(0.3, nang=5), nrad=5)
        .shell("pipe_wall", dR=0.05, nrad=3)
        .shell("insulation",dR=0.10, nrad=4)
    )

    with Model("insulated_pipe") as m:
        net = Network(pipe)
        net.add(Straight(length=1.0, n_layers=10))
        net.add(Bend(radius=0.5, angle=90, n_layers=8))
        net.add(Straight(length=0.5, n_layers=5))
        net.write_physical_groups()
        m.mesh(dim=3)
        m.write("insulated_pipe.msh")
"""

from .model       import Model
from .network     import Network, Node, QualityReport, RegionQuality
from .quality_hex import (
    HexVolumeQuality,
    all_metrics as hex_all_metrics,
)

__all__ = [
    "Model", "Network", "Node", "QualityReport", "RegionQuality",
    "HexVolumeQuality", "hex_all_metrics",
]
__version__ = "0.2.0"
