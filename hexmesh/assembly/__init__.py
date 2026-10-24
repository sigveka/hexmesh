"""
Interface-first network assembly — prototype of the DESIGN.md assembly rules.

Interfaces (shared faces) are placed and validated before any GMSH call,
built exactly once, and fittings fill between them.  No fragment, no
duplicate-node merging.
"""

from .interface import Frame, Interface, port_type
from .fittings  import Straight, Bend, MiterBend, Elbow, Reducer, Closure, FillResult
from .assembler import Assembly, AssemblyError
from .tee       import Tee

__all__ = [
    "Frame", "Interface", "port_type",
    "Straight", "Bend", "MiterBend", "Elbow", "Reducer", "Closure", "FillResult",
    "Assembly", "AssemblyError", "Tee",
]
