"""
Network interchange (decision 0032): importers → the network model → one
builder.

- ``model``: the format-neutral network model (``NetworkModel``, ``Port``,
  the ``Part`` classes, ``Connection``, ``Network``, ``Section``,
  ``Provenance``);
- ``build``: ``build(model, spec, …) → Assembly`` and
  ``build_pieces(model, spec, …) → {name: Assembly}``;
- ``importers``: ``read_pcf``, ``read_bathymetry`` (task 0066; the old
  ``hexmesh.io.readers`` path is deprecated, removed in 0.8).

The builder and the model import no importer.  The part classes share names with
``hexmesh.assembly``'s fittings; use them through this package
(``interchange.Straight``), never star-imported next to the assembly's.
"""

from .build import build, build_pieces
from . import operations                 # noqa: F401  (registers the model operations)
from .model import (
    FORMATTERS, PART_TYPES, Bend, Connection, InlineEquipment, Joint, Junction, Network,
    NetworkModel, Part, Polyline, Port, Provenance, Reducer, Section, Straight, Terminal,
    Transition, describe, register_formatter,
)

__all__ = [
    "build", "build_pieces", "read_pcf", "read_bathymetry", "describe", "register_formatter", "FORMATTERS", "PART_TYPES",
    "NetworkModel", "Port", "Part", "Straight", "InlineEquipment", "Bend", "Reducer",
    "Transition", "Junction", "Joint", "Terminal", "Polyline", "Connection", "Network",
    "Section", "Provenance",
]


def __getattr__(name: str):
    """``read_pcf`` and ``read_bathymetry``, loaded on first use: importing
    the builder or the model loads no importer (constraint 1)."""
    if name in ("read_pcf", "read_bathymetry"):
        from . import importers
        return getattr(importers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
