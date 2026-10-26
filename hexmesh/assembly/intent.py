"""
Intent layer serialisation (DESIGN.md §3, docs/tasks/0006).

An assembly is saved as the record of how it was built, not as geometry:

* ``inlet``: pose (``position``, ``normal``, ``up``) and spec of the first
  interface (index 0), and ``nozzle`` (drum and nozzle name) for a network
  started with ``Assembly.from_nozzle``; the drum then sets the pose;
* ``edges``: in creation order, each a fitting (``type`` + dataclass
  fields) with ``source`` (the interface index it was added from),
  ``close`` (the ``[source, target]`` interfaces it joins), or
  ``prepend: true`` (placed upstream of the inlet), and its ``label`` if
  set;
* ``names``: interface index → name, for every named interface;
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
    """Numbers, tuples, arrays and specs as JSON-native values."""
    if isinstance(v, PipeSpec):
        return v.to_dict()
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, (tuple, list, np.ndarray)):
        return [_plain(x) for x in v]
    return v


def _tuples(v):
    """Inverse of _plain for tuple-valued fields (lists become tuples, and
    dicts inside them specs, as in ``stack_changes``)."""
    if isinstance(v, dict):
        return PipeSpec.from_dict(v)
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
    first = asm.interfaces[0]
    edges = []
    for edge in asm.edges:
        e = {"fitting": fitting_to_dict(edge.fitting)}
        if edge.label is not None:
            e["label"] = edge.label
        src, *outs = edge.ports
        if edge.kind == "close":
            e["close"] = [src.index, outs[0].index]
        elif edge.kind == "prepend":
            e["prepend"] = True
        else:
            e["source"] = src.index
            placed = [fr for fr, _ in edge.fitting.ports(src.frame, src.spec)]
            frames = {str(k): _frame_to_dict(o.frame)
                      for k, (o, fr) in enumerate(zip(outs, placed))
                      if not _same_frame(o.frame, fr)}
            if frames:
                e["frames"] = frames
        edges.append(e)
    d = {
        "format": FORMAT, "version": VERSION,
        "inlet": {**_frame_to_dict(first.frame), "spec": first.spec.to_dict(),
                  **({"nozzle": {"drum": asm._nozzle[0].to_dict(), "name": asm._nozzle[1]}}
                     if asm._nozzle is not None else {})},
        "edges": edges,
        "names": {str(i.index): i.name for i in asm.interfaces if i.name is not None},
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
    if "nozzle" in inlet:
        from .equipment import Drum
        asm = cls.from_nozzle(Drum.from_dict(inlet["nozzle"]["drum"]),
                              inlet["nozzle"]["name"], lc=d.get("lc"))
    else:
        asm = cls(PipeSpec.from_dict(inlet["spec"]), lc=d.get("lc"))
        asm.inlet.frame = _frame_from_dict(inlet)
    for e in d["edges"]:
        fitting = fitting_from_dict(e["fitting"])
        ifaces = asm.interfaces
        if "close" in e:
            src, tgt = e["close"]
            asm.close(ifaces[src], ifaces[tgt], fitting, label=e.get("label"))
            continue
        if e.get("prepend"):
            asm.prepend(fitting, label=e.get("label"))
            continue
        out = asm.add(ifaces[e["source"]], fitting, label=e.get("label"))
        outs = out if isinstance(out, list) else [out]
        for k, fr in e.get("frames", {}).items():
            outs[int(k)].frame = _frame_from_dict(fr)
    names = d.get("names", {})
    for iface in asm.interfaces:
        iface.name = names.get(str(iface.index))
    tail = d.get("tail")
    asm._tail = None if tail is None else asm.interfaces[tail]
    return asm


# --- uniform refinement (task 0026, decision 0015) ----------------------------

# Axial cell counts per fitting type.  Everything else in a fitting is
# geometry or topology (MiterBend.n_cuts included) and stays.
AXIAL_COUNTS = ("n_layers", "n_run", "n_branch", "n_turn")


def refine_spec_dict(d: dict, k: int) -> dict:
    """A :meth:`PipeSpec.to_dict` description at k× the density: every
    angular and radial count × k, every radial ``mprg`` → ``mprg ** (1/k)``
    so each coarse cell splits into k cells of the same growth.  Topology
    (``n_outer``, ``rot``, layers), ``mbmp`` and geometry are unchanged."""
    d = json.loads(json.dumps(d))
    for key in ("nang", "nang_w", "nang_h"):
        if d.get(key) is not None:
            d[key] *= k
    for key in ("nang", "nang_w", "nang_h"):
        if key in d["core"]["shape"]:
            d["core"]["shape"][key] *= k
    for layer in (d["core"], *d["shells"]):
        layer["nrad"] *= k
        layer["mprg"] = layer.get("mprg", 1.0) ** (1.0 / k)
    return d


def _refine_fitting_dict(d: dict, k: int) -> dict:
    d = dict(d)
    for key in AXIAL_COUNTS:
        if key in d:
            d[key] *= k
    if "axial_grading" in d:
        d["axial_grading"] **= 1.0 / k
    if "outlet" in d:
        d["outlet"] = refine_spec_dict(d["outlet"], k)
    if "stack_changes" in d:          # (axial cell index, spec): cell i → cell k·i
        d["stack_changes"] = [[i * k, refine_spec_dict(spec, k)]
                              for i, spec in d["stack_changes"]]
    return d


def refined_dict(d: dict, k: int) -> dict:
    """:func:`to_dict` output at k× the density in every direction."""
    d = json.loads(json.dumps(d))
    inlet = d["inlet"]
    inlet["spec"] = refine_spec_dict(inlet["spec"], k)
    if "nozzle" in inlet:
        for n in inlet["nozzle"]["drum"]["nozzles"]:
            n["spec"] = refine_spec_dict(n["spec"], k)
    for e in d["edges"]:
        e["fitting"] = _refine_fitting_dict(e["fitting"], k)
    return d


def dumps(asm: "Assembly") -> str:
    """Human-readable JSON: indented, sorted keys."""
    return json.dumps(to_dict(asm), indent=2, sort_keys=True) + "\n"
