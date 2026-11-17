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
Interface-first network assembly — prototype of the DESIGN.md assembly rules.

Interfaces (shared faces) are placed and validated before any GMSH call,
built exactly once, and fittings fill between them.  No fragment, no
duplicate-node merging.
"""

from .interface import Frame, Interface, port_type
from .fittings  import (
    Straight, Bend, MiterBend, Elbow, Reducer, Transition, SplinePipe, Closure, FillResult,
)
from .profile   import Profile
from .assembler import Assembly, AssemblyError, AssemblyTypeError
from .mesh      import Mesh, ELEMENT_TYPES
from .tee       import Tee, TeeOutlets
from .switch    import Switch
from .wye       import Wye, WyeOutlets
from .equipment import Drum, Nozzle, OnHead, OnShell, EquipmentError

__all__ = [
    "Frame", "Interface", "port_type",
    "Straight", "Bend", "MiterBend", "Elbow", "Reducer", "Transition", "SplinePipe", "Closure",
    "FillResult", "Profile",
    "Assembly", "AssemblyError", "AssemblyTypeError", "Mesh", "ELEMENT_TYPES", "Tee", "TeeOutlets", "Wye", "WyeOutlets", "Switch",
    "Drum", "Nozzle", "OnShell", "OnHead", "EquipmentError",
]
