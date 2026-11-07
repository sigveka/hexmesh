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
- :func:`describe`: what an assembly or a network model is, as JSON
  data, without GMSH (task 0097).
- :func:`preview`: a PNG of it, without GMSH (needs matplotlib, the
  ``preview`` extra).
- :func:`advise`: the resolution advisor, and :func:`apply`, which writes
  its resolution table into a description (task 0098).
- :func:`manifest`: one JSON account of all of it, for an agent to read
  first (task 0102).
- ``hexmesh`` (``cli.main``): all of them as one command.

The functions live in private modules (``_schema``, ``_describe``,
``_preview``), so that ``hexmesh.agent.schema`` and the rest stay the
functions; ``python3 -m hexmesh.agent.schema`` is the one command.
"""

from ._describe import describe
from ._manifest import manifest
from .advise import AdviceError, advise, apply
from ._preview import preview
from ._schema import dumps, schema

__all__ = ["AdviceError", "advise", "apply", "describe", "dumps", "manifest", "preview",
           "schema"]
