"""
hexmesh — structured all-hex meshes for CFD pipe networks.

Quick start
-----------
::

    from hexmesh import Assembly, Bend, CircleShape, PipeSpec, Session, Straight

    pipe = (
        PipeSpec(nang=4)
        .core("fluid",      CircleShape(radius=0.1, nang=4), nrad=4)
        .shell("pipe_wall", dR=0.01, nrad=2)
    )

    with Session("elbow"):
        asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.5, n_layers=10))
        asm.add(Bend(radius=0.3, angle=90, n_layers=12))
        asm.add(Straight(0.5, n_layers=10))
        asm.validate()              # pure Python, before any GMSH call
        print(asm.cell_count())     # exact, before meshing
        asm.write("elbow.msh")
        print(asm.check_quality())

See ``README.md`` and ``API.md``; the design rules are in ``DESIGN.md``.
"""

from .assembly import (
    Assembly, AssemblyError, Bend, Closure, Elbow, Frame, Interface,
    MiterBend, Reducer, SplinePipe, Straight, Tee, Transition, Wye,
    Drum, Nozzle, OnShell, OnHead, EquipmentError,
)
from .assembly.quality import QualityReport, RegionQuality
from .core.shape import CircleShape
from .core.spec import PipeSpec
from .quality_hex import HexVolumeQuality, all_metrics as hex_all_metrics
from .session import Session

__all__ = [
    "Assembly", "AssemblyError", "Frame", "Interface",
    "Straight", "Bend", "Elbow", "MiterBend", "Reducer", "Transition", "SplinePipe",
    "Closure", "Tee", "Wye",
    "Drum", "Nozzle", "OnShell", "OnHead", "EquipmentError",
    "PipeSpec", "CircleShape",
    "QualityReport", "RegionQuality", "HexVolumeQuality", "hex_all_metrics",
    "Session",
]


def _version() -> str:
    """``pyproject.toml``'s version in a source checkout, else the
    installed distribution's (an editable install's metadata is only as
    fresh as its last install)."""
    import re
    from pathlib import Path
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text()
        if re.search(r'^name\s*=\s*"hexmesh"', text, re.M):
            return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("hexmesh")
    except PackageNotFoundError:
        return "unknown"


__version__ = _version()

