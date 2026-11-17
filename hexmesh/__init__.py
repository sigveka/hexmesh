#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
hexmesh — structured all-hex meshes for CFD pipe networks.

Quick start
-----------
::

    from hexmesh import Assembly, Bend, CircleShape, PipeSpec, Session, Straight

    pipe = (
        PipeSpec(n_arc=4)
        .core("fluid",      shape=CircleShape(radius=0.1, n_arc=4), n_radial=4)
        .shell("pipe_wall", dR=0.01, n_radial=2)
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

See ``README.md``, ``docs/GUIDE.md`` (the user's guide) and ``API.md``; the
design rules are in ``DESIGN.md``.
"""

from .assembly import (
    Assembly, AssemblyError, Bend, Closure, Elbow, Frame, Interface,
    MiterBend, Profile, Reducer, SplinePipe, Straight, Switch, Tee, TeeOutlets, Transition, Wye,
    WyeOutlets,
    Drum, Nozzle, OnShell, OnHead, EquipmentError,
)
from .assembly.quality import QualityReport, RegionQuality
from .core.shape import CircleShape
from .core.spec import PipeSpec
from .errors import HexmeshError, HexmeshNotice, HexmeshWarning
from .quality_hex import HexVolumeQuality, all_metrics as hex_all_metrics
from .session import Session

__all__ = [
    "Assembly", "AssemblyError", "Frame", "Interface",
    "Straight", "Bend", "Elbow", "MiterBend", "Reducer", "Profile", "Transition", "SplinePipe",
    "Closure", "Tee", "TeeOutlets", "Wye", "WyeOutlets", "Switch",
    "Drum", "Nozzle", "OnShell", "OnHead", "EquipmentError",
    "HexmeshError", "HexmeshWarning", "HexmeshNotice",
    "PipeSpec", "CircleShape",
    "QualityReport", "RegionQuality", "HexVolumeQuality", "hex_all_metrics",
    "Session",
]

from .version import __version__                               # noqa: E402
