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
Predicted non-orthogonality of junction blocks (decision 0031, amendment
2026-11-07, item 5; task 0104).

A junction's cells come from its block layout (``BlockLayout.cells``:
its edges' curves, divisions and grading, transfinite interpolation).
Their worst face by OpenFOAM's definition is checked on the outline tiers
in ``validate()``: a warning above ``OUTLINE_NONORTH_WARN``, an error above
``OUTLINE_NONORTH_MAX``.  The message names the fitting's block and what
lowers it.  Measured against meshed junctions in
``benchmarks/junction_nonorth.py``.

The prediction is cached by value (the fitting's fields, the frames and
the spec, as ``Wye.layout``), so repeated ``validate()`` calls on an
unchanged junction cost nothing.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from dataclasses import fields

import numpy as np

from . import limits
from .errors import AssemblyError
from .interface import port_type

_CACHE: OrderedDict = OrderedDict()
_CACHE_SIZE = 64
_LOCK = threading.Lock()


def _value(v):
    """A hashable value of a field: arrays and sequences by their floats'
    bytes, the rest by repr (exact for floats)."""
    if isinstance(v, (np.ndarray, list, tuple)):
        return ("array", np.asarray(v, dtype=float).tobytes())
    return repr(v)


def _layout_key(fitting, frames, spec) -> tuple:
    """Everything a junction's layout reads, by value: every field of the
    fitting, every frame's vectors, and the spec (its description and its
    port type).  An equal fitting at equal frames hits; any change misses
    (``Wye.layout``'s cache, task 0112; the prediction's, task 0104)."""
    return (tuple((f.name, _value(getattr(fitting, f.name))) for f in fields(fitting)),
            tuple(np.asarray(a, dtype=float).tobytes()
                  for fr in frames for a in (fr.position, fr.normal, fr.up)),
            json.dumps(spec.to_dict(), sort_keys=True), repr(port_type(spec)))


def _predicted(fitting, frames, spec, layout) -> tuple[float, frozenset]:
    """(worst angle, the stations of its block), cached by value; *layout*
    is called on a miss."""
    key = (type(fitting).__name__, _layout_key(fitting, frames, spec))
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            _CACHE.move_to_end(key)
            return hit
    lay = layout()
    angle, b = lay.predicted_nonorth()
    stations = frozenset(v[0] if isinstance(v, tuple) else str(v) for v in lay.blocks[b][0])
    with _LOCK:
        _CACHE[key] = (angle, stations)
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)
    return angle, stations


def predicted_angle(fitting, frames, spec, layout) -> float:
    """The junction's predicted worst non-orthogonality (cached)."""
    return _predicted(fitting, frames, spec, layout)[0]


def _where(stations: frozenset, names: list[tuple[frozenset, str]]) -> str:
    """The first name whose stations are all in the block's, else the
    block by its stations."""
    for need, name in names:
        if need <= stations:
            return name
    return "the block between stations " + ", ".join(sorted(stations))


def nonorth_tiers(fitting, frames, spec, layout, names, hint: str,
                  reject: bool = True) -> list[str]:
    """Apply the outline non-orthogonality tiers to a junction's predicted
    cells: raise above ``OUTLINE_NONORTH_MAX``, return a warning above
    ``OUTLINE_NONORTH_WARN`` (the assembler names the fitting).  *layout*
    builds the block layout on a cache miss; *names* maps station sets to
    block names (most specific first); *hint* says what lowers it.  Without
    *reject* (the wye, until its layout redesign, as its SJ tier) the
    maximum only warns."""
    angle, stations = _predicted(fitting, frames, spec, layout)
    block = _where(stations, names)
    if angle > limits.OUTLINE_NONORTH_MAX and not reject:
        return [f"predicted non-orthogonality {angle:.1f}° in {block} is above "
                f"OUTLINE_NONORTH_MAX {limits.OUTLINE_NONORTH_MAX:g}° (no reject tier until "
                f"the layout redesign); {hint}"]
    if angle > limits.OUTLINE_NONORTH_MAX:
        raise AssemblyError(
            f"predicted non-orthogonality {angle:.1f}° in {block} is above "
            f"OUTLINE_NONORTH_MAX {limits.OUTLINE_NONORTH_MAX:g}°; {hint}",
            code="predicted_nonorth_above_maximum", value=float(angle),
            limit="OUTLINE_NONORTH_MAX", hint=hint)
    if angle > limits.OUTLINE_NONORTH_WARN:
        return [f"predicted non-orthogonality {angle:.1f}° in {block} is above "
                f"OUTLINE_NONORTH_WARN {limits.OUTLINE_NONORTH_WARN:g}°; {hint}"]
    return []


# What lowers it, per junction: in validate()'s and mesh()'s messages
TEE_HINT = "a larger branch ratio r/R, or a larger angle, lowers it"
TAP_HINT = "a tap on the main's wide face lowers it (narrow-face taps predict about 72–75°)"
WYE_HINT = ("the wye's layout sets it, at any angle; the layout redesign "
            "(decision 0043) measures alternatives")

# Block names by the stations their vertices belong to (each fitting's
# layout docstring): most specific first.
TEE_BLOCKS = [
    (frozenset({"Sa", "Sd", "Z"}), "a turn block beside the branch"),
    (frozenset({"Sa", "Z"}), "the turn block on the branch's upstream side"),
    (frozenset({"Sd", "Z"}), "the turn block on the branch's downstream side"),
    (frozenset({"E", "Z"}), "the branch run"),
    (frozenset({"Sa", "Sd"}), "the junction core under the branch"),
    (frozenset({"A", "Sa"}), "the approach run"),
    (frozenset({"B", "Sd"}), "the departure run"),
]
TAP_BLOCKS = [
    (frozenset({"D"}), "the dome under the hole"),
    (frozenset({"C", "W"}), "the ring around the hole"),
    (frozenset({"E", "W"}), "the branch run"),
    (frozenset({"Sa", "Sd"}), "the main's core under the hole"),
    (frozenset({"A", "Sa"}), "the approach run"),
    (frozenset({"B", "Sd"}), "the departure run"),
]
CUBE_HINT = "the junction cube sets it; a branch radius <= TEE_MAX_RATIO R avoids the cube"
# The equal tee's junction cube (cube.py): a port's ring and column end at
# its station S<pipe>; F is the centre hex, C the cube corners on the wall.
CUBE_BLOCKS = [(frozenset({"F", "C", "S" + p}), f"the {w} port's ring")
               for p, w in (("A", "inlet"), ("B", "run outlet"), ("E", "branch"))] + [
    (frozenset({"C", "S" + p}), f"the {w} port's shell")
    for p, w in (("A", "inlet"), ("B", "run outlet"), ("E", "branch"))] + [
    (frozenset({"F", "S" + p}), f"the {w} port's column")
    for p, w in (("A", "inlet"), ("B", "run outlet"), ("E", "branch"))] + [
    (frozenset({p, "S" + p}), f"the {w} run")
    for p, w in (("A", "inlet"), ("B", "run outlet"), ("E", "branch"))] + [
    (frozenset({"F", "C"}), "a wall side of the junction cube"),
    (frozenset({"C"}), "a wall side's shell"), (frozenset({"F"}), "the centre hex")]

WYE_BLOCKS = [
    (frozenset({"W"}), "the ring at the crotch"),
    (frozenset({"F"}), "the hub"),
    (frozenset({"SL", "Sa"}), "a daughter's turn"),
    (frozenset({"SR", "Sa"}), "a daughter's turn"),
    (frozenset({"L", "SL"}), "a daughter's run"),
    (frozenset({"R", "SR"}), "a daughter's run"),
    (frozenset({"A", "Sa"}), "the approach run"),
]
