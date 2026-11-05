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
"""What a network is, without GMSH: ``describe()`` (task 0097).

``describe(x)`` takes an ``Assembly``, its saved description
(``Assembly.to_dict()``, any version ``intent.upgrade`` reads) or a
``hexmesh.interchange.NetworkModel``, and returns JSON-safe data:
- per fitting: index, label, type, its inlet and outlet frames, its
  centreline length, its section and its exact cell count;
- the open ends, under the patch names the build gives them;
- the junctions' branch directions and the angles between them;
- totals: bounding box, centreline length per section, cells, and what
  ``validate()`` says (warnings and an error, with their codes).

For a model it lists the parts, ports, connections (declared or
inferred) and networks as they stand, and the parts the builder would
reject, with the reason (``Part.reject``).

Everything is computed from the fittings' own geometry (``path``,
``centreline_length``, ``cell_counts``), so no GMSH session is needed.
The output is deterministic: floats are rounded to 12 significant
digits and lists follow the assembly's or the model's order.
"""

from __future__ import annotations

import math
import warnings

import numpy as np

from hexmesh import Assembly, HexmeshError, HexmeshWarning
from hexmesh.interchange import NetworkModel

#: units of the output.  An assembly's lengths are in its own unit
#: (hexmesh never converts; the examples use metres); a model's are metres.
UNITS_ASSEMBLY = {"length": "as given", "angle": "deg"}
UNITS_MODEL = {"length": "m", "angle": "deg"}


def describe(x) -> dict:
    """A JSON-safe summary of *x*: an ``Assembly``, an ``Assembly.to_dict()``
    description, or a ``NetworkModel``.  Needs no GMSH session."""
    if isinstance(x, NetworkModel):
        return _model(x)
    if isinstance(x, dict):
        x = Assembly.from_dict(x)
    if not isinstance(x, Assembly):
        raise TypeError(f"describe() takes an Assembly, its to_dict() description or a "
                        f"NetworkModel, not {type(x).__name__}")
    return _assembly(x)


# --- numbers ---------------------------------------------------------------------

def _num(v: float) -> float:
    """*v* rounded to 12 significant digits (no -0.0): stable across
    platforms' last-bit differences."""
    v = float(v)
    if v == 0 or not math.isfinite(v):
        return 0.0 if v == 0 else v
    return float(f"{v:.12g}") + 0.0


def _vec(v) -> list[float]:
    return [_num(x) for x in np.asarray(v, dtype=float)]


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return _num(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def _angle(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    c = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return _num(math.degrees(math.acos(max(-1.0, min(1.0, c)))))


# --- assemblies ------------------------------------------------------------------

def section(spec) -> dict:
    """A spec's section: the layout, every layer's name and outline (as
    ``to_dict`` saves outlines), and the outer extent."""
    return _jsonable({
        "layout": spec.layout,
        "layers": [{"name": n, "outline": o.to_dict()}
                   for n, o in zip(spec.layer_names, spec.outlines)],
        "outer_extent": spec.outlines[-1].max_extent,
        "rot": spec.rot,
    })


def _key(sec: dict) -> str:
    """A section's short name, for the per-section totals."""
    def size(o):
        if o["type"] == "circle":
            return f"r={o['radius']:g}"
        return f"{2 * o['half_w']:g}x{2 * o['half_h']:g}"
    return " / ".join(f"{l['name']} {l['outline']['type']} {size(l['outline'])}"
                      for l in sec["layers"])


def _frame(iface) -> dict:
    return {"interface": iface.index, "position": _vec(iface.frame.position),
            "direction": _vec(iface.frame.normal)}


def centreline(edge) -> list[np.ndarray]:
    """The fitting's centreline as polylines: a sweep's station positions;
    a junction's runs from its centre to each port.  A sweep whose path
    stops short of a port (a transition's built-in switch to an H face)
    is joined to it by a straight run, which the switch is."""
    f, ports = edge.fitting, edge.ports
    if hasattr(f, "path"):
        p = f.path(ports[0].frame, ports[1].frame, ports[0].spec)
        pts = [fr.position for fr in p.frames]
        for end, at in ((ports[0].frame.position, 0), (ports[1].frame.position, len(pts))):
            if np.linalg.norm(pts[0 if at == 0 else -1] - end) > 1e-9 * (1 + np.linalg.norm(end)):
                pts.insert(at, end)
        return [np.array(pts)]
    centre = junction_centre(edge)
    return [np.array([ports[0].frame.position, centre])] + [
        np.array([centre, o.frame.position]) for o in ports[1:]]


def junction_centre(edge) -> np.ndarray:
    """Where a junction's runs meet: ``run_length`` along the inlet axis."""
    a = edge.ports[0].frame
    return a.position + edge.fitting.run_length * a.normal


def _length(edge) -> float:
    f, ports = edge.fitting, edge.ports
    if hasattr(f, "centreline_length") and len(ports) == 2:
        return f.centreline_length(ports[0].frame, ports[0].spec, ports[1].frame)
    return sum(float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum()) for c in centreline(edge))


def _checks(asm: Assembly) -> tuple[list, dict | None, dict]:
    """``validate()``'s warnings and error, and the cell counts."""
    found, error, cells = [], None, {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            asm.validate()
            cells = asm.cell_counts()
        except HexmeshError as e:
            error = e.to_dict()
    for w in caught:
        m = w.message
        found.append({"code": m.code if isinstance(m, HexmeshWarning) else None,
                      "message": str(m)})
    return found, error, cells


def _assembly(asm: Assembly) -> dict:
    warned, error, cells = _checks(asm)
    fittings, junctions, points = [], [], []
    per_section: dict[str, dict] = {}
    for e in asm.edges:
        sec = section(e.ports[0].spec)
        try:
            length = _length(e)
            lines = centreline(e)
        except HexmeshError:            # validate() already said why
            length, lines = None, []
        for c in lines:
            points.append(c)
        fittings.append({
            "index": e.index, "label": e.label, "name": e.name,
            "type": type(e.fitting).__name__, "kind": e.kind,
            "inlet": _frame(e.ports[0]), "outlets": [_frame(o) for o in e.ports[1:]],
            "centreline_length": None if length is None else _num(length),
            "section": sec,
            **({"outlet_section": section(e.ports[-1].spec)}
               if e.ports[-1].spec is not e.ports[0].spec
               and section(e.ports[-1].spec) != sec else {}),
            "cells": cells.get(e.index)})
        if length is not None:
            t = per_section.setdefault(_key(sec), {"section": _key(sec), "length": 0.0})
            t["length"] += length
        if len(e.ports) > 2:
            inlet = e.ports[0].frame.normal
            branches = [{"port": i, "interface": o.index,
                         "direction": _vec(o.frame.normal),
                         "deflection": _angle(inlet, o.frame.normal)}
                        for i, o in enumerate(e.ports[1:], 1)]
            junctions.append({
                "index": e.index, "name": e.name, "type": type(e.fitting).__name__,
                "centre": _vec(junction_centre(e)), "inlet_direction": _vec(inlet),
                "branches": branches,
                "angles": [{"ports": [a["port"], b["port"]],
                            "angle": _angle(a["direction"], b["direction"])}
                           for k, a in enumerate(branches) for b in branches[k + 1:]]})
    ends = []
    for i in asm.open_interfaces():
        edge = i.edges[0]
        outward = -i.frame.normal if edge.ports[0] is i else i.frame.normal
        ends.append({"name": asm.patch_name(i), "interface": i.index,
                     "position": _vec(i.frame.position), "outward": _vec(outward),
                     "equipment": i.equipment, "section": section(i.spec)})
    pts = np.vstack(points + [i.frame.position[None] for i in asm.interfaces])
    return _jsonable({
        "kind": "assembly", "units": UNITS_ASSEMBLY,
        "fittings": fittings, "open_ends": ends, "junctions": junctions,
        "totals": {
            "bounding_box": {"min": _vec(pts.min(axis=0)), "max": _vec(pts.max(axis=0))},
            "centreline_length": [{"section": t["section"], "length": _num(t["length"])}
                                  for t in per_section.values()],
            "cells": sum(cells.values()) if cells else None,
            "fittings": len(fittings), "open_ends": len(ends)},
        "warnings": warned, "error": error,
    })


# --- network models ---------------------------------------------------------------

def _provenance(p) -> dict | None:
    if p is None:
        return None
    out = {k: getattr(p, k) for k in ("source", "format", "record", "record_id", "line")
           if getattr(p, k) not in (None, "")}
    return out or None


def _section_model(s) -> dict | None:
    if s is None:
        return None
    return {k: getattr(s, k) for k in ("shape", "nominal", "diameter", "width", "height")
            if getattr(s, k) is not None}


def _model(m: NetworkModel) -> dict:
    parts = []
    for p in m.parts.values():
        parts.append({"id": p.id, "type": type(p).__name__, "record": p.type,
                      "name": p.name, "system": p.system, "ports": list(p.ports),
                      "reject": p.reject, "source": _provenance(p.provenance)})
    ports = [{"id": q.id,
              "position": None if q.position is None else _vec(q.position),
              "direction": None if q.direction is None else _vec(q.direction),
              "flow": q.flow, "section": _section_model(q.section),
              "equipment": q.equipment is not None}
             for q in m.ports.values()]
    connections = [{"a": c.a, "b": c.b, "origin": c.origin,
                    "inferred": c.origin == "inferred", "distance": _num(c.distance)}
                   for c in m.connections]
    networks = [{"name": n.name, "kind": n.kind, "parts": sorted(n.parts, key=_natural)}
                for n in m.networks.values()]
    pos = [q.position for q in m.ports.values() if q.position is not None]
    return _jsonable({
        "kind": "network_model", "units": UNITS_MODEL,
        "parts": parts, "ports": ports, "connections": connections, "networks": networks,
        "rejected": [{"id": p["id"], "name": p["name"], "record": p["record"],
                      "reason": p["reject"], "source": p["source"]}
                     for p in parts if p["reject"]],
        "totals": {
            "parts": len(parts), "ports": len(ports), "connections": len(connections),
            "inferred_connections": sum(c["inferred"] for c in connections),
            "bounding_box": None if not pos else {
                "min": _vec(np.min(pos, axis=0)), "max": _vec(np.max(pos, axis=0))}},
    })


def _natural(s: str):
    """Sort ids as numbers where they are ("2" before "10")."""
    return (0, int(s), "") if str(s).isdigit() else (1, 0, str(s))
