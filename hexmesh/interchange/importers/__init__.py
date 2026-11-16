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
Importers (decision 0032 §8): each reads one source format into a
``hexmesh.interchange.NetworkModel``.

- ``pcf``: ``read_pcf``, Alias PCF piping files (isometrics);
- ``bathymetry``: ``read_bathymetry``, seabed routes.

They moved here from ``hexmesh.io.readers`` (task 0066, decision 0037
item 4), removed in 0.8.  ``NetworkSpec`` is what ``read_pcf`` returns.
"""

from .bathymetry import read_bathymetry
from .pcf import NetworkSpec, read_pcf

__all__ = ["read_pcf", "read_bathymetry", "NetworkSpec"]
