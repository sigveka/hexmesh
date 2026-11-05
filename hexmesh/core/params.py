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
"""Field metadata: unit, doc and range of every saved parameter (task 0095).

A dataclass field carries it in ``dataclasses.field(metadata=…)``,
through :func:`param`; a method's arguments in a table of
:func:`describe` entries next to its signature (``PipeSpec.core``).
``hexmesh.agent.schema`` reads both.  Nothing here changes behaviour.

Units: ``length`` (the user's length unit: hexmesh never converts);
``deg``; ``1`` (a ratio or a factor); ``cells`` (a cell or layer count);
``-`` (not a quantity: a name, a choice, a spec, a shape or a vector of
mixed meaning).

Ranges use JSON Schema's words: ``minimum``, ``exclusiveMinimum``,
``maximum``, ``exclusiveMaximum`` and ``enum``.  ``limit`` names a
``hexmesh.assembly.limits.LIMITS`` entry the field is checked against
(a ``{"minimum": name}``-style mapping, or a name for a rule documented
there).
"""

from __future__ import annotations

import dataclasses

UNITS = ("length", "deg", "1", "cells", "-")
RANGES = ("minimum", "exclusiveMinimum", "maximum", "exclusiveMaximum", "enum")


def describe(unit: str, doc: str, *, limit=None, **ranges) -> dict:
    """The metadata of one parameter: *unit* (one of :data:`UNITS`), a
    one-line *doc*, and optionally a *limit* and plain *ranges*."""
    if unit not in UNITS or set(ranges) - set(RANGES) or not doc:
        raise AssertionError(f"parameter metadata: unit {unit!r}, ranges {sorted(ranges)}")
    out = {"unit": unit, "doc": doc, **ranges}
    if limit is not None:
        out["limit"] = limit
    return out


def param(unit: str, doc: str, *, default=dataclasses.MISSING, input: bool = False,
          limit=None, **ranges):
    """A dataclass field with :func:`describe` metadata.  *input*: an input
    field, left out of ``to_dict`` while None (``intent.fitting_to_dict``)."""
    meta = describe(unit, doc, limit=limit, **ranges)
    if input:
        meta["input"] = True
        default = None
    return dataclasses.field(default=default, metadata=meta)
