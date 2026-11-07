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
The parts graph (decision 0032; split from ``build``, task 0066): the
parts as the builder works on them (``_Comp``), the connection graph
within a tolerance, the tree check, the pieces, root choice, junction
entry, and the names of the open ends.  Format-neutral, as ``build``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

from .model import (
    Bend, InlineEquipment, Joint, Junction, NetworkModel, Part, Polyline, Reducer, Section,
    Straight, Terminal, describe,
)


#: Connectivity tolerance floor, just above the 1/16" weld gap (pcf2iso: 0.11").
TOL_FLOOR = 0.11 * 0.0254


#: Connectivity tolerance relative to the model's bounding-box diagonal.
TOL_RELATIVE = 1e-4


@dataclass
class _Comp:
    """A part as the builder works on it: positions by role, oriented and
    split as placement needs (the model is never changed)."""

    kind:    str                         # pipe fitting elbow reducer joint tee seton ypiece
    start:   np.ndarray
    end:     np.ndarray
    centre:  np.ndarray | None = None
    sec:     Section | None = None       # the part's size (its first port's)
    end_sec: Section | None = None       # a reducer's outlet
    branch:  np.ndarray | None = None
    branch_sec: Section | None = None
    branch2: np.ndarray | None = None
    branch2_sec: Section | None = None
    label:   str = ""
    type:    str = ""
    system:  str = ""
    part:    Part | None = None
    index:   int = -1                    # the part's position in the model
    flow_in: int | None = None           # the port flow enters by (0 or 1), if stated
    eccentric: bool = False
    offset:  bool = False                # a tap whose branch is tangential or offset
    insulation: str | None = None                # "ON" / "OFF" / None
    end_insulation: tuple = (None, None)
    branch_insulation: tuple = (None, None)
    ins: tuple = (0.0, 0.0)              # insulation thickness at (start, end), m
    ins_junction: float = 0.0            # through a junction, m; 0 bare

    @property
    def bore(self) -> float:
        return (self.sec.nominal or 0.0) if self.sec is not None else 0.0

    @property
    def end_bore(self) -> float | None:
        return self.end_sec.nominal if self.end_sec is not None else None

    @property
    def branch_bore(self) -> float | None:
        return self.branch_sec.nominal if self.branch_sec is not None else None

    @property
    def branch2_bore(self) -> float | None:
        return self.branch2_sec.nominal if self.branch2_sec is not None else None


_KINDS = {Straight: "pipe", InlineEquipment: "fitting", Bend: "elbow", Reducer: "reducer",
          Joint: "joint"}


_FORMS = {"tee": "tee", "tap": "seton", "wye": "ypiece", "cross": "junction?"}


def _upper(status):
    return status.upper() if status else None


def _comps(model: NetworkModel, ids) -> list[_Comp]:
    """The parts *ids* (model order) as ``_Comp``s; terminals left out."""
    out = []
    for index, part in enumerate(model.parts.values()):
        if (ids is not None and part.id not in ids) or isinstance(part, Terminal):
            continue
        ports = [model.ports[q] for q in part.ports]
        pos = [None if q.position is None else q.position.copy() for q in ports]
        ins = [_upper(q.insulation) for q in ports]
        common = dict(label=part.name, type=part.type, system=part.system, part=part,
                      index=index, insulation=_upper(part.insulation))
        if isinstance(part, Polyline):
            for i in range(len(ports) - 1):
                out.append(_Comp("pipe", pos[i], pos[i + 1], sec=ports[i].section,
                                 **{**common, "label": f"{part.name}_{i + 1}"},
                                 end_insulation=(ins[i], ins[i + 1])))
            continue
        flows = [q.flow for q in ports[:2]]
        flow_in = 0 if flows[:1] == ["in"] else 1 if flows[1:2] == ["in"] else None
        if isinstance(part, Junction):
            kind = _FORMS[part.form]
            c = _Comp(kind, pos[0], pos[0], centre=None if part.centre is None
                      else np.asarray(part.centre, dtype=float).copy(),
                      sec=ports[0].section, flow_in=flow_in, offset=part.offset, **common)
            if kind in ("tee", "junction?"):
                c.end = pos[1]
                legs = list(zip(pos[2:], ports[2:], ins[2:])) + [(None, None, None)] * 2
                (c.branch, b1, i1), (c.branch2, b2, i2) = legs[0], legs[1]
                c.branch_sec = b1.section if b1 is not None else None
                c.branch2_sec = b2.section if b2 is not None else None
                c.end_insulation, c.branch_insulation = (ins[0], ins[1]), (i1, i2)
            else:
                legs = list(zip(pos[1:], ports[1:], ins[1:])) + [(None, None, None)] * 2
                (c.branch, b1, i1), (c.branch2, b2, i2) = legs[0], legs[1]
                c.branch_sec = b1.section if b1 is not None else None
                c.branch2_sec = b2.section if b2 is not None else None
                c.end_insulation, c.branch_insulation = (ins[0], None), (i1, i2)
            out.append(c)
            continue
        c = _Comp(_KINDS[type(part)] if type(part) in _KINDS else "reducer", pos[0], pos[1],
                  sec=ports[0].section, flow_in=flow_in, end_insulation=(ins[0], ins[1]),
                  **common)
        if isinstance(part, Bend):
            c.centre = None if part.corner is None else np.asarray(part.corner, float).copy()
        if isinstance(part, Reducer):
            c.end_sec, c.eccentric = ports[1].section, part.eccentric
        out.append(c)
    return out


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _model_tolerance(comps: list[_Comp]) -> float:
    pts = np.array([q for c in comps for q in (c.start, c.end)])
    diagonal = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 0.0
    return max(TOL_RELATIVE * diagonal, TOL_FLOOR)


def _name(text: str) -> str:
    """*text* as a patch-name / label fragment: letters, digits and ``_``."""
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")


@dataclass
class _Part:
    """A component in the graph: its ports' points (entry candidates)."""

    comp:  _Comp
    label: str
    ports: list                              # points, metres
    nodes: list = field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.comp.kind


def _ports(c: _Comp) -> list:
    if c.kind == "tee":
        return [c.start, c.end, c.branch]
    if c.kind == "wye":
        return [c.start, c.branch, c.branch2]
    return [c.start, c.end]


def _source(x) -> dict:
    """The provenance of *x* (a component, a graph piece or a part) for an
    error's ``where["source"]`` (task 0094), and the ``origin`` its fitting
    is added with (task 0096): file, format, record, record id, line and
    guid, where known."""
    part = getattr(getattr(x, "comp", x), "part", x)
    prov = getattr(part, "provenance", None)
    if prov is None:
        return {}
    out = {"file": prov.source, "format": prov.format, "record": prov.record,
           "record_id": prov.record_id, "line": prov.line, "guid": prov.guid}
    return {k: v for k, v in out.items() if v not in (None, "")}


def _part_id(x) -> str | None:
    """The network-model part id of *x* (a component, a graph piece or a
    part), for an error's ``where["part"]`` (task 0094)."""
    part = getattr(getattr(x, "comp", x), "part", x)
    return getattr(part, "id", None)


def _describe(c: _Comp, label: str) -> str:
    """The part as messages name it (``model.describe``: the importer's
    formatter), at its centre (junctions) or its start."""
    at = c.centre if c.kind in ("seton", "ypiece", "tee", "wye") else c.start
    if c.part is None:
        return f"{c.type or c.kind} {label} at {np.round(at, 4)}"
    return describe(c.part, at, label)


def _cut_index(model: NetworkModel) -> dict:
    """``model.cuts`` by part: {part a, part b} → [(the two ports' points)]
    (task 0066)."""
    owner = {q: part.id for part in model.parts.values() for q in part.ports}
    out: dict[frozenset, list] = {}
    for c in model.cuts:
        pa, pb = model.ports[c.a].position, model.ports[c.b].position
        if pa is not None and pb is not None:
            out.setdefault(frozenset((owner[c.a], owner[c.b])), []).append((pa, pb))
    return out


def _blocked(cuts: dict, a, b, x, y, tol: float) -> bool:
    """Whether a cut separates part *a* at point *x* from part *b* at *y*."""
    if not cuts or a is b or a is None or b is None:
        return False
    return any(min(np.linalg.norm(x - u) + np.linalg.norm(y - v),
                   np.linalg.norm(x - v) + np.linalg.norm(y - u)) <= 2 * tol
               for u, v in cuts.get(frozenset((a.id, b.id)), ()))


def _graph(parts: list[_Part], joints: list[_Comp], tol: float, cuts: dict | None = None):
    """Cluster port points into nodes: node → [(part, port)], and node →
    the joints at it.  A joint's two ends are one node (it is absorbed,
    never a part), so a zero-length weld does not count as a component.
    Points that a cut separates (*cuts*, ``_cut_index``) aren't joined; a
    cut that the other points join anyway raises ``model_cut_bypassed``."""
    from ..assembly import AssemblyError
    pts = [x for p in parts for x in p.ports] + [x for j in joints for x in (j.start, j.end)]
    who = [p.comp.part for p in parts for _ in p.ports] + [j.part for j in joints for _ in (0, 1)]
    root = list(range(len(pts)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    held = []
    for i in range(len(pts)):
        for j in range(i):
            if np.linalg.norm(pts[i] - pts[j]) <= tol and \
                    _blocked(cuts, who[i], who[j], pts[i], pts[j], tol):
                held.append((i, j))
            elif np.linalg.norm(pts[i] - pts[j]) <= tol:
                root[find(i)] = find(j)
    base = sum(len(p.ports) for p in parts)
    for m in range(len(joints)):
        root[find(base + 2 * m + 1)] = find(base + 2 * m)
    for i, j in held:
        if find(i) == find(j):
            raise AssemblyError(
                f"the cut between {who[j].name} and {who[i].name} at {np.round(pts[i], 4)} "
                f"is bypassed: other ports there still join them; cut_at() each port",
                code="model_cut_bypassed", where={"source": _source(who[i])})
    ids: dict[int, int] = {}
    nodes: list[list[tuple[int, int]]] = []
    i = 0
    for k, p in enumerate(parts):
        p.nodes = []
        for q in range(len(p.ports)):
            n = ids.setdefault(find(i), len(ids))
            if n == len(nodes):
                nodes.append([])
            nodes[n].append((k, q))
            p.nodes.append(n)
            i += 1
    at_node: dict[int, list] = {}
    for m, j in enumerate(joints):
        n = ids.get(find(base + 2 * m))
        if n is not None:
            at_node.setdefault(n, []).append(j)
    points = {p.nodes[q]: p.ports[q] for p in parts for q in range(len(p.ports))}
    for n, at in enumerate(nodes):
        if len(at) > 2:
            raise AssemblyError(
                f"{len(at)} components meet at {np.round(points[n], 4)} "
                f"({', '.join(parts[k].label for k, _ in at)}); a junction must be "
                f"a tee, a tap or a wye",
                code="junction_degree", where={"source": _source(parts[at[0][0]])}, value=len(at),
                limit={"max": 2})
    return nodes, at_node


def _joints_from(joints: list[_Comp], x: np.ndarray) -> list[_Comp]:
    """*joints* (at one node) in order away from point *x*, each oriented so
    it starts at the end nearer the previous one."""
    left, out = list(joints), []
    while left:
        j = min(left, key=lambda j: min(np.linalg.norm(j.start - x), np.linalg.norm(j.end - x)))
        left.remove(j)
        j = replace(j, start=j.start.copy(), end=j.end.copy())
        if np.linalg.norm(j.end - x) < np.linalg.norm(j.start - x):
            j.start, j.end = j.end, j.start
        out.append(j)
        x = j.end
    return out


def _pieces_hint(model, comps: list[_Comp], tol: float) -> str:
    """For a network that isn't one piece: its pieces, and what to do."""
    pieces = _pieces(comps, tol, _cut_index(model))
    if len(pieces) < 2:
        return ""
    return (f".  The model holds {len(pieces)} unconnected pieces: "
            + "; ".join(_describe_piece(model, comps, ks) for ks in pieces)
            + "; read each with to_assemblies(), or close the gap")


def _check_tree(parts, nodes, hint=lambda: "") -> None:
    from ..assembly import AssemblyError
    seen, stack = {0}, [(0, None)]
    while stack:
        k, via = stack.pop()
        for n in parts[k].nodes:
            if n == via:
                continue
            for j, _ in nodes[n]:
                if j == k:
                    continue
                if j in seen:
                    raise AssemblyError(f"{parts[j].label} is on a loop; loops are not "
                                        f"built from a network (decision 0023)",
                                        code="network_loop",
                                        where={"part": _part_id(parts[j]),
                                               "source": _source(parts[j])})
                seen.add(j)
                stack.append((j, n))
    missing = [k for k in range(len(parts)) if k not in seen]
    if missing:
        # name the gap: the unreached port nearest to an open end of the rest
        ends = [(k, q) for k in seen for q, n in enumerate(parts[k].nodes)
                if len(nodes[n]) == 1]
        gap, j, k = min((float(np.linalg.norm(parts[j].ports[r] - parts[k].ports[q])), j, k)
                        for j in missing for r in range(len(parts[j].ports))
                        for k, q in ends) if ends else (math.inf, missing[0], 0)
        raise AssemblyError(
            f"{_describe(parts[j].comp, parts[j].label)}: starts {gap:.3g} m from the "
            f"open end of {_describe(parts[k].comp, parts[k].label)}; the network "
            f"must be one connected piece" + hint(),
            code="network_disconnected",
            where={"part": _part_id(parts[j]), "source": _source(parts[j])}, value=gap)


def _entries(parts, nodes, root: tuple[int, int]) -> str | None:
    """Walk from *root* (part, port); the first junction entered other than
    through its inlet, described, or None."""
    stack = [root]
    seen = set()
    while stack:
        k, q = stack.pop()
        if k in seen:
            continue
        seen.add(k)
        p = parts[k]
        if p.kind == "tee" and q == 2:
            return f"{_describe(p.comp, p.label)} would be entered from its branch"
        if p.kind == "wye" and q != 0:
            return f"{_describe(p.comp, p.label)} would be entered from a daughter"
        for r, n in enumerate(p.nodes):
            if r != q:
                stack += [(j, s) for j, s in nodes[n] if j != k]
    return None


def _end_names(parts, nodes, skip=()) -> dict[int, str | None]:
    """Open-end node → ``<network>_end<k>`` (model order), None for a part
    in no network.  The nodes in *skip* (named by ``_boundary_names``)
    aren't counted."""
    ends = sorted((k, q, n) for n, at in enumerate(nodes) if len(at) == 1
                  for k, q in at if n not in skip)
    count: dict[str, int] = {}
    out = {}
    for k, q, n in ends:
        pipe = _name(parts[k].comp.system)
        if not pipe:
            out[n] = None
            continue
        count[pipe] = count.get(pipe, 0) + 1
        out[n] = f"{pipe}_end{count[pipe]}"
    return out


def _boundary_names(model: NetworkModel, parts, nodes, ids, tol: float) -> dict[int, str]:
    """Open-end node → name, for the ends at a cut or at the boundary of
    the parts built (*ids*): where, in the whole model, another part's
    port meets this one (task 0066).  The name is the port's ``tag``, or
    ``<network>_<port id>``."""
    cut = {q for c in model.cuts for q in (c.a, c.b)}
    out = {}
    for n, at in enumerate(nodes):
        if len(at) != 1:
            continue
        k, q = at[0]
        part, x = parts[k].comp.part, parts[k].ports[q]
        if part is None:
            continue
        mine = [(np.linalg.norm(model.ports[p].position - x), p) for p in part.ports
                if model.ports[p].position is not None]
        if not mine or min(mine)[0] > tol:
            continue
        pid = min(mine)[1]
        outside = any(other.id not in ids and not isinstance(other, Terminal)
                      and model.ports[r].position is not None
                      and np.linalg.norm(model.ports[r].position - x) <= tol
                      for other in model.parts.values() if other is not part
                      for r in other.ports)
        if pid in cut or outside:
            port = model.ports[pid]
            out[n] = _name(port.tag) if port.tag else \
                f"{_name(part.system) or 'end'}_{_name(pid)}"
    return out


def _choose_root(parts, nodes, names, inlet, tol):
    from ..assembly import AssemblyError
    ends = sorted((k, q, n) for n, at in enumerate(nodes) if len(at) == 1
                  for k, q in at)
    if not ends:
        raise AssemblyError("the network has no open end to start from",
                            code="network_no_open_end")
    if inlet is not None:
        if isinstance(inlet, str):
            pick = [e for e in ends if names.get(e[2]) == inlet]
        else:
            x = np.asarray(inlet, dtype=float)
            pick = [e for e in ends
                    if np.linalg.norm(parts[e[0]].ports[e[1]] - x) <= tol]
        if not pick:
            known = ", ".join(str(names[e[2]]) for e in ends if names.get(e[2]))
            raise AssemblyError(f"inlet {inlet!r} is not an open end"
                                + (f" (open ends: {known})" if known else ""),
                                code="inlet_not_open_end", where={"field": "inlet"}, value=inlet)
        bad = _entries(parts, nodes, pick[0][:2])
        if bad:
            raise AssemblyError(f"from inlet {inlet!r}, {bad}",
                                code="inlet_enters_junction_wrongly", where={"field": "inlet"},
                                value=inlet)
        return pick[0]

    def upstream(e):                        # the source declares flow in here
        return parts[e[0]].comp.flow_in == e[1]
    first_bad = None
    for e in sorted(ends, key=lambda e: not upstream(e)):
        bad = _entries(parts, nodes, e[:2])
        if bad is None:
            return e
        first_bad = first_bad or bad
    raise AssemblyError(f"no open end enters every junction through its inlet: "
                        f"{first_bad}", code="network_no_valid_inlet")


def _orient(c: _Comp, port: int) -> _Comp:
    """*c* entered at *port*: start is the entry (2-port parts)."""
    c = replace(c, start=c.start.copy(), end=c.end.copy())
    if port == 1 and c.kind not in ("tee", "wye"):
        c.start, c.end = c.end, c.start
        c.ins = c.ins[::-1]
        if c.kind == "reducer":
            c.sec, c.end_sec = c.end_sec, c.sec
    elif port == 1 and c.kind == "tee":
        c.start, c.end = c.end, c.start
    return c


def _equipment_ends(model, terminals, parts, nodes, names, tol, describe) -> set[int]:
    """Name the open ends attached to *terminals* (``Terminal`` parts) after
    them, and return their nodes.  A terminal attaches by its port's
    position (else its ``check_point``); when it has both, they must agree."""
    from ..assembly import AssemblyError
    from .model import describe as name_of
    ends = [(k, q, n) for n, at in enumerate(nodes) if len(at) == 1 for k, q in at]
    marked: dict[int, str] = {}
    for t in terminals:
        port = model.ports[t.ports[0]]
        what = name_of(t)
        label = t.name
        point, nz_point = port.position, t.check_point
        if point is not None and nz_point is not None \
                and np.linalg.norm(point - nz_point) > tol:
            nozzle = (port.equipment or {}).get("nozzle", "")
            raise AssemblyError(
                f"{what}: nozzle {nozzle} is at {np.round(nz_point, 4)} but the connection "
                f"is at {np.round(point, 4)}, "
                f"{np.linalg.norm(point - nz_point):.3g} m apart",
                code="terminal_points_disagree", where={"part": _part_id(t), "source": _source(t)})
        at = point if point is not None else nz_point
        if at is None:
            raise AssemblyError(f"{what}: no position to attach it by",
                                code="terminal_position_missing",
                                where={"part": _part_id(t), "source": _source(t)})
        if not ends:
            raise AssemblyError(f"{what}: the network has no open end",
                                code="network_no_open_end",
                                where={"part": _part_id(t), "source": _source(t)})
        d, k, q, n = min((float(np.linalg.norm(parts[k].ports[q] - at)), k, q, n)
                         for k, q, n in ends)
        if d > tol:
            raise AssemblyError(
                f"{what} at {np.round(at, 4)}: no open pipe end there; the nearest, "
                f"{describe(parts[k])}, is {d:.3g} m away",
                code="terminal_no_open_end", where={"part": _part_id(t), "source": _source(t)}, value=d,
                limit={"max": tol})
        if n in marked:
            raise AssemblyError(f"{what}: that end is already attached to {marked[n]}",
                                code="terminal_end_taken",
                                where={"part": _part_id(t), "source": _source(t)})
        if label in marked.values():
            raise AssemblyError(f"{what}: two ends would be named {label!r}",
                                code="terminal_name_duplicate",
                                where={"part": _part_id(t), "source": _source(t)})
        marked[n] = label
        names[n] = label
    return set(marked)


def _reject_unsupported(comps: list[_Comp]) -> None:
    """Raise for the parts the importer read but marked unbuildable
    (``Part.reject``), and for crosses."""
    from ..assembly import AssemblyError
    for c in comps:
        if c.part is not None and c.part.reject:
            raise AssemblyError(f"{_describe(c, c.label)}: {c.part.reject}",
                                code="part_rejected",
                                where={"part": _part_id(c), "source": _source(c)})
        if c.kind == "junction?":
            raise AssemblyError(f"{_describe(c, c.label)}: crosses are not supported "
                                f"(decision 0023)",
                                code="cross_unsupported",
                                where={"part": _part_id(c), "source": _source(c)})


def _pieces(comps: list[_Comp], tol: float, cuts: dict | None = None) -> list[list[int]]:
    """The connected pieces, as component indices in model order, pieces in
    the order of their first component.  Components connect where their
    points meet within *tol*, unless a cut separates them (*cuts*,
    ``_cut_index``); a tap or wye also connects to a pipe its centre lies
    on."""
    pts, owner = [], []
    for k, c in enumerate(comps):
        centre = c.centre if c.kind in ("seton", "ypiece") else None
        for x in (c.start, c.end, c.branch, c.branch2, centre):
            if x is not None:
                pts.append(x)
                owner.append(k)
    root = list(range(len(comps)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    pts = np.array(pts)
    for i in range(len(pts)):
        near = np.flatnonzero(np.linalg.norm(pts[:i] - pts[i], axis=1) <= tol)
        for j in near:
            if not _blocked(cuts, comps[owner[i]].part, comps[owner[j]].part, pts[i], pts[j],
                            tol):
                root[find(owner[i])] = find(owner[j])
    for k, c in enumerate(comps):
        if c.kind not in ("seton", "ypiece") or c.centre is None:
            continue
        for h, hc in enumerate(comps):
            d = hc.end - hc.start
            L = float(np.linalg.norm(d))
            if hc.kind != "pipe" or L == 0:
                continue
            t = float(np.dot(c.centre - hc.start, d)) / L
            if -tol <= t <= L + tol and np.linalg.norm(hc.start + t * d / L - c.centre) <= tol:
                root[find(k)] = find(h)
    out: dict[int, list[int]] = {}
    for k in range(len(comps)):
        out.setdefault(find(k), []).append(k)
    return list(out.values())


def _describe_piece(model, comps: list[_Comp], ks: list[int]) -> str:
    """``pipeline A-100 (components 0–5, 8)``: the networks, and the parts'
    indices in the model."""
    comps_by = {c.index: c for c in comps}
    ks = sorted({comps[k].index for k in ks})
    runs, start = [], ks[0]
    for a, b in zip(ks, ks[1:] + [None]):
        if b != a + 1:
            runs.append(f"{start}" if start == a else f"{start}–{a}")
            start = b
    pipes = list(dict.fromkeys(comps_by[k].system for k in ks if comps_by[k].system))
    nets = [model.networks[n] for n in pipes if n in model.networks]
    kind = nets[0].kind if nets else "network"
    what = f"{kind} {', '.join(pipes)}" if pipes else "no network"
    return f"{what} (components {', '.join(runs)})"
