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
The readers moved to ``hexmesh.interchange.importers`` (task 0066,
decision 0037 item 4).  ``hexmesh.io.readers`` re-exports them, unchanged,
and is deprecated: importing it warns, and 0.8 removes it (task 0148).
"""

import warnings

from ...interchange.importers import read_bathymetry, read_pcf

warnings.warn("hexmesh.io.readers is deprecated and is removed in 0.8: use "
              "hexmesh.interchange.read_pcf / read_bathymetry",
              DeprecationWarning, stacklevel=2)

__all__ = ["read_pcf", "read_bathymetry"]
