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
The assembly's error classes (task 0094): a leaf inside ``assembly``, so
fittings, layouts and the assembler raise the same classes without
importing each other.  ``AssemblyError`` is re-exported by ``assembler``
and the package.
"""

from __future__ import annotations

from ..errors import HexmeshError


class AssemblyError(HexmeshError):
    """Raised during validation; names the offending fitting or interface
    (and carries ``code``, ``where``, …: ``hexmesh.errors``)."""


class AssemblyTypeError(AssemblyError, TypeError):
    """An :class:`AssemblyError` for an argument of the wrong kind: still a
    ``TypeError``, as it was before task 0094."""
