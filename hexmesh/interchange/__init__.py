"""
Network interchange (decision 0032): importers → the network model → one
builder.

- ``model``: the format-neutral network model (``NetworkModel``, ``Port``,
  the ``Part`` classes, ``Connection``, ``Network``, ``Section``,
  ``Provenance``);
- ``build``: ``build(model, spec, …) → Assembly`` and
  ``build_pieces(model, spec, …) → {name: Assembly}``.

The importers stay in ``hexmesh.io.readers`` (``read_pcf``,
``read_bathymetry``).  The part classes share names with
``hexmesh.assembly``'s fittings; use them through this package
(``interchange.Straight``), never star-imported next to the assembly's.
"""

from .build import build, build_pieces
from .model import (
    FORMATTERS, PART_TYPES, Bend, Connection, InlineEquipment, Joint, Junction, Network,
    NetworkModel, Part, Polyline, Port, Provenance, Reducer, Section, Straight, Terminal,
    Transition, describe, register_formatter,
)

__all__ = [
    "build", "build_pieces", "describe", "register_formatter", "FORMATTERS", "PART_TYPES",
    "NetworkModel", "Port", "Part", "Straight", "InlineEquipment", "Bend", "Reducer",
    "Transition", "Junction", "Joint", "Terminal", "Polyline", "Connection", "Network",
    "Section", "Provenance",
]
