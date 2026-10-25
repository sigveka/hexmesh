"""
Intent layer serialisation (DESIGN.md §3, docs/tasks/0006).

An assembly is saved as the record of how it was built, not as geometry:

* ``inlet``: pose (``position``, ``normal``, ``up``), spec and name;
* ``edges``: in creation order, each a fitting (``type`` + dataclass
  fields) with either ``source`` (the interface index it was added from)
  or ``close`` (the ``[source, target]`` interfaces it joins);
* ``tail``: the interface index ``add(fitting)`` continues from.

Replaying the edges recreates the interfaces in the same order, so
interface indices are stable.  Outlet frames follow from the fittings;
only a frame set by hand after ``add()`` is stored, under ``frames``, as an
override.

Lengths are in the user's unit and are stored unconverted.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING

import numpy as np

from ..core.spec import PipeSpec
from .fittings import Bend, Closure, Elbow, MiterBend, Reducer, SplinePipe, Straight
from .interface import Frame
from .tee import Tee

if TYPE_CHECKING:
    from .assembler import Assembly

FORMAT = "hexmesh.assembly"
VERSION = 1

# Explicit registry: no plugins or entry points (DESIGN §6.1).
FITTING_TYPES = {cls.__name__: cls for cls in (
    Straight, Bend, MiterBend, Elbow, Reducer, SplinePipe, Closure, Tee,
)}


def _plain(v):
    """Numbers, tuples and arrays as JSON-native values."""
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, (tuple, list, np.ndarray)):
        return [_plain(x) for x in v]
    return v


def _tuples(v):
    """Inverse of _plain for tuple-valued fields (lists become tuples)."""
    return tuple(_tuples(x) for x in v) if isinstance(v, list) else v


def _frame_to_dict(f: Frame) -> dict:
    return {"position": _plain(f.position), "normal": _plain(f.normal),
            "up": _plain(f.up)}


def _frame_from_dict(d: dict) -> Frame:
    # Stored frames are already orthonormal; rebuild them bit for bit
    # rather than renormalising through Frame.from_vectors.
    return Frame(*(np.array(d[k], dtype=float) for k in ("position", "normal", "up")))


def _same_frame(a: Frame, b: Frame) -> bool:
    return all(np.array_equal(getattr(a, k), getattr(b, k))
               for k in ("position", "normal", "up"))


def fitting_to_dict(fitting) -> dict:
    name = type(fitting).__name__
    if FITTING_TYPES.get(name) is not type(fitting):
        raise TypeError(f"cannot serialise fitting type {name}")
    d = {"type": name}
    for f in dataclasses.fields(fitting):
        v = getattr(fitting, f.name)
        d[f.name] = v.to_dict() if isinstance(v, PipeSpec) else _plain(v)
    return d


def fitting_from_dict(d: dict):
    d = dict(d)
    name = d.pop("type")
    try:
        cls = FITTING_TYPES[name]
    except KeyError:
        raise ValueError(f"unknown fitting type {name!r}; known: "
                         f"{', '.join(sorted(FITTING_TYPES))}") from None
    kw = {}
    for f in dataclasses.fields(cls):
        if f.name not in d:
            continue
        v = d.pop(f.name)
        kw[f.name] = PipeSpec.from_dict(v) if f.type == "PipeSpec" else _tuples(v)
    if d:
        raise ValueError(f"{name}: unknown fields {sorted(d)}")
    return cls(**kw)


def to_dict(asm: "Assembly") -> dict:
    inlet = asm.inlet
    edges = []
    for edge in asm.edges:
        e = {"fitting": fitting_to_dict(edge.fitting)}
        src, *outs = edge.ports
        if outs and any(o.edges[0] is not edge for o in outs):
            # a close(): the outlet interfaces already existed
            e["close"] = [src.index, outs[0].index]
        else:
            e["source"] = src.index
            if any(o.name is not None for o in outs):
                e["names"] = [o.name for o in outs]
            placed = [fr for fr, _ in edge.fitting.ports(src.frame, src.spec)]
            frames = {str(k): _frame_to_dict(o.frame)
                      for k, (o, fr) in enumerate(zip(outs, placed))
                      if not _same_frame(o.frame, fr)}
            if frames:
                e["frames"] = frames
        edges.append(e)
    d = {
        "format": FORMAT, "version": VERSION,
        "inlet": {**_frame_to_dict(inlet.frame), "spec": inlet.spec.to_dict(),
                  "name": inlet.name},
        "edges": edges,
        "tail": None if asm._tail is None else asm._tail.index,
    }
    if asm._lc is not None:
        d["lc"] = asm._lc
    return d


def from_dict(cls, d: dict) -> "Assembly":
    if d.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} description (format={d.get('format')!r})")
    if d.get("version") != VERSION:
        raise ValueError(f"unsupported {FORMAT} version {d.get('version')!r}")
    inlet = d["inlet"]
    asm = cls(PipeSpec.from_dict(inlet["spec"]), lc=d.get("lc"),
              inlet_name=inlet.get("name", "inlet"))
    asm.inlet.frame = _frame_from_dict(inlet)
    for e in d["edges"]:
        fitting = fitting_from_dict(e["fitting"])
        ifaces = asm.interfaces
        if "close" in e:
            src, tgt = e["close"]
            asm.close(ifaces[src], ifaces[tgt], fitting)
            continue
        out = asm.add(ifaces[e["source"]], fitting, names=e.get("names"))
        outs = out if isinstance(out, list) else [out]
        for k, fr in e.get("frames", {}).items():
            outs[int(k)].frame = _frame_from_dict(fr)
    tail = d.get("tail")
    asm._tail = None if tail is None else asm.interfaces[tail]
    return asm


def dumps(asm: "Assembly") -> str:
    """Human-readable JSON: indented, sorted keys."""
    return json.dumps(to_dict(asm), indent=2, sort_keys=True) + "\n"
