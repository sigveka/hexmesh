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
"""Tools for agents and for people writing hexmesh JSON by hand
(decision 0040's tool layer; task 0095 starts it).

Built on the public API only.  Nothing in the library imports this
package (``tests/test_architecture.py``).

- :func:`schema`: a JSON Schema (draft 2020-12) of the saved
  ``hexmesh.assembly`` description, generated from the fitting, spec,
  shape and equipment registries and from ``limits.LIMITS``.
"""

from ._schema import dumps, schema

__all__ = ["dumps", "schema"]
