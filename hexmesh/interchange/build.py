"""
The builder (decision 0032): a network model → an ``Assembly``.

Format-neutral: it never branches on the source format (decision 0032,
constraint 1).  Format facts reach it only as model content (stated bend
angles, rejections, flow directions, equipment tags) and through the
importer's message formatter (``model.register_formatter``).

Moved from the PCF reader (task 0065) without changing its behaviour:
the connection graph within a tolerance, joint absorption, the tree check,
root choice, junction entry, insulation planning, equipment ends and
placement.
"""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import dataclass, field, replace

import numpy as np

from .model import (
    BUILDERS, Bend, InlineEquipment, Joint, Junction, NetworkModel, Part, Polyline, Reducer,
    Section, Straight, Terminal, describe,
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


def _section_spec(spec):
    """*spec* as the builder calls it: a ``PipeSpec`` as is, or a callable
    of a ``Section``.  A callable whose first parameter is named
    ``section`` or annotated ``Section`` gets the section; any other gets
    its nominal size (``spec(bore)``, metres; 0 if unknown)."""
    if not callable(spec):
        return spec
    try:
        params = list(inspect.signature(spec).parameters.values())
    except (TypeError, ValueError):
        params = []
    first = params[0] if params else None
    if first is not None and (first.name == "section"
                              or first.annotation in (Section, "Section")):
        return lambda sec: spec(sec if sec is not None else Section())
    return lambda sec: spec((sec.nominal or 0.0) if sec is not None else 0.0)


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _perpendicular(v: np.ndarray) -> np.ndarray:
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(v, candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    return _unit(np.cross(v, candidate))


def _start_direction(comp: _Comp) -> np.ndarray:
    """Unit direction in which *comp* leaves its start point."""
    if comp.kind == "elbow" and comp.centre is not None:
        return _unit(comp.centre - comp.start)       # along the incoming leg
    return _unit(comp.end - comp.start)


@dataclass(frozen=True)
class ElbowGeometry:
    """An elbow from its corner point (the guide's convention)."""

    radius:   float          # centreline bend radius, metres
    angle:    float          # bend angle, degrees
    incoming: np.ndarray     # unit direction of the incoming leg
    turn:     np.ndarray     # unit in-plane direction the bend turns toward


def _elbow_params(comp: _Comp) -> ElbowGeometry:
    """Radius, angle and plane of a bend whose corner point C is the
    intersection of its tangent legs: with a = start − C and b = end − C,
    θ = 180° − ∠(a, b), R = |a| / tan(θ/2), incoming direction −â."""
    if comp.centre is None:
        raise ValueError("bend has no corner point (where its tangent legs meet)")
    a, b = comp.start - comp.centre, comp.end - comp.centre
    la, lb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if la < 1e-12 or lb < 1e-12:
        raise ValueError("bend corner point coincides with an end point")
    corner = math.degrees(math.acos(float(np.clip(np.dot(a, b) / (la * lb), -1, 1))))
    theta = 180.0 - corner
    if not 1e-6 < theta < 180.0 - 1e-6:
        raise ValueError(f"bend legs give a bend angle of {theta:.4g}°")
    incoming = -a / la
    bu = b / lb
    turn = _unit(bu - np.dot(bu, incoming) * incoming)
    return ElbowGeometry(la / math.tan(math.radians(theta) / 2), theta, incoming, turn)


# ---------------------------------------------------------------------------
# Assembly builder
# ---------------------------------------------------------------------------

def _model_tolerance(comps: list[_Comp]) -> float:
    pts = np.array([q for c in comps for q in (c.start, c.end)])
    diagonal = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 0.0
    return max(TOL_RELATIVE * diagonal, TOL_FLOOR)


def _straight_meshed(c: _Comp) -> bool:
    return c.kind in ("pipe", "fitting")


def _absorb_joints(comps: list[_Comp], report: dict) -> list[_Comp]:
    """Remove joints, extending an adjacent straight run over each one.

    The preceding straight-meshed component is extended to the joint's end;
    otherwise the following one starts at the joint's start.  A joint at an
    open end with no straight neighbour is dropped.  Between two
    non-straight fittings it raises: there is no run to absorb it.
    """
    out: list[_Comp] = []
    pending: list[_Comp] = []          # joints waiting for a following run
    for c in comps:
        if c.kind == "joint":
            if out and _straight_meshed(out[-1]) and not pending:
                out[-1].end = c.end.copy()
                report["joints"].append((c.type, "absorbed"))
            else:
                pending.append(c)
            continue
        if pending:
            if _straight_meshed(c):
                c.start = pending[0].start.copy()
                report["joints"].extend((j.type, "absorbed") for j in pending)
            elif not out:
                report["joints"].extend((j.type, "dropped") for j in pending)
            else:
                from ..assembly import AssemblyError
                raise AssemblyError(
                    f"{pending[0].type} at {np.round(pending[0].start, 4)} sits "
                    f"between two non-straight fittings ({out[-1].type}, "
                    f"{c.type}); there is no straight run to absorb it")
            pending = []
        out.append(c)
    report["joints"].extend((j.type, "dropped") for j in pending)
    return out


# --- graph (decision 0023) ---------------------------------------------------

class _Reroll(Exception):
    """Raised at the first junction: rebuild with the root rolled by *miss*."""

    def __init__(self, miss: float):
        self.miss = miss


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


def _describe(c: _Comp, label: str) -> str:
    """The part as messages name it (``model.describe``: the importer's
    formatter), at its centre (junctions) or its start."""
    at = c.centre if c.kind in ("seton", "ypiece", "tee", "wye") else c.start
    if c.part is None:
        return f"{c.type or c.kind} {label} at {np.round(at, 4)}"
    return describe(c.part, at, label)


def _radius(spec) -> float:
    return spec.core_shape.radius


def _branch_radius(spec, R: float, branch: Section, main_bore: float) -> float:
    """A tee branch's radius: the spec's for its section, or *R* scaled
    like a Reducer by the nominal sizes when the spec is fixed."""
    return _radius(spec(branch)) if callable(spec) else R * branch.nominal / main_bore


def _split_hosts(comps, labels, tol, seton_run):
    """Replace each tap (set-on) and wye (Y piece) by a ``tee`` / ``wye``
    with explicit ports, splitting its host pipe (pure).  A tap's run each
    side of its centre is ``seton_run(set-on, host, thickness)``: the Tee's own
    default (``Tee(run_length=None)``, task 0054), set by the geometry
    alone, so the same for any density.  A Y piece's inlet run is
    ``r·(tan h + margin + 0.5)``, ``r`` the stem's nominal radius and ``h``
    half the daughters' angle."""
    from ..assembly import AssemblyError
    from ..assembly.wye import inlet_clearance
    comps, labels = list(comps), list(labels)
    while True:
        todo = [i for i, c in enumerate(comps) if c.kind in ("seton", "ypiece")]
        if not todo:
            return comps, labels
        i = todo[0]
        j_c = comps[i]
        what = _describe(j_c, labels[i])
        if j_c.kind == "seton" and j_c.offset:
            raise AssemblyError(f"{what}: tangential and offset set-ons are not "
                                f"supported; a Tee branch is perpendicular and centred")
        if j_c.centre is None or j_c.branch is None:
            raise AssemblyError(f"{what}: needs a centre and a branch point")
        c = j_c.centre
        hosts = []
        for h, hc in enumerate(comps):
            if hc.kind != "pipe":
                continue
            d = hc.end - hc.start
            L = float(np.linalg.norm(d))
            t = float(np.dot(c - hc.start, d)) / L
            off = float(np.linalg.norm(hc.start + t * d / L - c))
            if off <= tol and -tol <= t <= L + tol:
                hosts.append((h, t, L))
        if j_c.kind == "seton":
            inside = [x for x in hosts if tol < x[1] < x[2] - tol]
            if not inside:
                raise AssemblyError(f"{what}: no straight pipe passes through its centre "
                                    f"(the branch must be centred on a straight pipe)")
            h, t, L = inside[0]
            host = comps[h]
            axis = (host.end - host.start) / L
            if not j_c.branch_bore:
                raise AssemblyError(f"{what}: needs a size on its branch")
            t_j = _junction_thickness([j_c.ins_junction, *host.ins], what)
            run = seton_run(j_c, host, t_j)
            if t - run <= tol or t + run >= L - tol:
                raise AssemblyError(
                    f"{what}: host pipe {labels[h]} is too short around the branch; "
                    f"the tee needs {run:.4g} m on each side of its centre")
            a, b = c - run * axis, c + run * axis
            tee = replace(j_c, kind="tee", start=a, end=b, sec=host.sec, ins_junction=t_j)
            pieces = [replace(host, start=host.start.copy(), end=a, ins=(host.ins[0],) * 2),
                      tee,
                      replace(host, start=b, end=host.end.copy(), ins=(host.ins[1],) * 2)]
            names = [f"{labels[h]}_1", labels[i], f"{labels[h]}_2"]
        else:
            ends = [x for x in hosts if x[1] <= tol or x[1] >= x[2] - tol]
            if not ends or j_c.branch2 is None:
                raise AssemblyError(f"{what}: needs a stem pipe ending at its "
                                    f"centre, and two branch points")
            h, t, L = ends[0]
            host = comps[h]
            far = host.start if t >= L - tol else host.end
            n = _unit(c - far)
            d1, d2 = _unit(j_c.branch - c), _unit(j_c.branch2 - c)
            half = math.acos(float(np.clip(np.dot(d1, n), -1, 1)))
            R = 0.5 * host.bore
            run = R * (inlet_clearance(half) + 0.5)
            if run >= L - tol:
                raise AssemblyError(
                    f"{what}: stem pipe {labels[h]} ({L:.4g} m) is shorter than the "
                    f"{run:.4g} m the Wye's inlet run needs")
            a = c - run * n
            wye = replace(j_c, kind="wye", start=a, end=a, sec=host.sec,
                          ins_junction=_junction_thickness([j_c.ins_junction, *host.ins], what))
            stem = replace(host, start=far.copy(), end=a)
            pieces, names = [stem, wye], [labels[h], labels[i]]
        # the pieces take the host's place in model order; the junction's
        # own record goes
        comps[h:h + 1], labels[h:h + 1] = pieces, names
        k = next(m for m, c in enumerate(comps) if c is j_c)
        del comps[k], labels[k]


def _graph(parts: list[_Part], joints: list[_Comp], tol: float):
    """Cluster port points into nodes: node → [(part, port)], and node →
    the joints at it.  A joint's two ends are one node (it is absorbed,
    never a part), so a zero-length weld does not count as a component."""
    from ..assembly import AssemblyError
    pts = [x for p in parts for x in p.ports] + [x for j in joints for x in (j.start, j.end)]
    root = list(range(len(pts)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i
    for i in range(len(pts)):
        for j in range(i):
            if np.linalg.norm(pts[i] - pts[j]) <= tol:
                root[find(i)] = find(j)
    base = sum(len(p.ports) for p in parts)
    for m in range(len(joints)):
        root[find(base + 2 * m + 1)] = find(base + 2 * m)
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
                f"a tee, a tap or a wye")
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
    pieces = _pieces(comps, tol)
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
                                        f"built from a network (decision 0023)")
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
            f"must be one connected piece" + hint())


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


def _end_names(parts, nodes) -> dict[int, str | None]:
    """Open-end node → ``<network>_end<k>`` (model order), None for a part
    in no network."""
    ends = sorted((k, q, n) for n, at in enumerate(nodes) if len(at) == 1
                  for k, q in at)
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


def _choose_root(parts, nodes, names, inlet, tol):
    from ..assembly import AssemblyError
    ends = sorted((k, q, n) for n, at in enumerate(nodes) if len(at) == 1
                  for k, q in at)
    if not ends:
        raise AssemblyError("the network has no open end to start from")
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
                                + (f" (open ends: {known})" if known else ""))
        bad = _entries(parts, nodes, pick[0][:2])
        if bad:
            raise AssemblyError(f"from inlet {inlet!r}, {bad}")
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
                        f"{first_bad}")


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


# --- insulation (decision 0023, task 0038) -----------------------------------

#: Name of the shell ``to_assembly(insulation=True)`` adds.
INSULATION = "insulation"


def _resolve_insulation(model: NetworkModel, comps: list[_Comp]) -> None:
    """Set ``ins`` (thickness at each end, 0 = bare) and ``ins_junction`` on
    every component.  Insulated only where the part's insulation is on; a
    port's own status overrides that end.  The thickness is the network's."""
    from ..assembly import AssemblyError
    for c in comps:
        label = c.label
        def thick(status):
            if status != "ON":
                return 0.0
            net = model.networks.get(c.system)
            t = net.insulation_thickness if net is not None else None
            if not t:
                kind = net.kind if net is not None else "network"
                raise AssemblyError(
                    f"{kind} {c.system or '(none)'!r}: {_describe(c, label)} is "
                    f"insulated but the {kind} has no insulation thickness")
            return t
        own = c.insulation
        c.ins = tuple(thick(e or own) for e in c.end_insulation)
        legs = [own] + [b or own for b in c.branch_insulation]
        c.ins_junction = (_junction_thickness(
            [thick(x) for x in legs + [e or own for e in c.end_insulation]],
            _describe(c, label)) if c.kind in ("tee", "seton", "ypiece") else 0.0)


def _junction_thickness(ts, what: str) -> float:
    """The insulation thickness through a junction: that of its insulated
    legs (0 if none).  The insulation runs through the junction (task 0054);
    a bare leg ends it one cell into its first straight."""
    from ..assembly import AssemblyError
    found = sorted({t for t in ts if t > 0})
    if len(found) > 1:
        raise AssemblyError(f"{what}: its legs have insulation {found[0]:.4g} m and "
                            f"{found[-1]:.4g} m; a junction carries one thickness")
    return found[0] if found else 0.0


def _dressed(spec, t: float, nrad: int):
    """*spec* without its ``insulation`` shell, plus one of thickness *t*
    (none if ``t`` is 0)."""
    shells = spec.shells
    if shells and shells[-1].name == INSULATION:
        shells = shells[:-1]
    bare = spec.with_radii([spec.core_shape.radius] + [sh.dR for sh in shells])
    return bare.shell(INSULATION, dR=t, nrad=nrad) if t > 0 else bare


def _thickness(spec) -> float:
    sh = spec.shells
    return sh[-1].dR if sh and sh[-1].name == INSULATION else 0.0


def _straight_like(c: _Comp, tol: float) -> bool:
    return c.kind in ("pipe", "fitting") and float(np.linalg.norm(c.end - c.start)) > tol


def _plan_insulation(comps, labels, t_in, to_junction, tol):
    """Insulation switches along a run of oriented two-port components.

    *t_in* is the thickness of the interface the run starts from;
    *to_junction* is the thickness of the junction the run ends at (None:
    an open end).  Returns, per
    component, ``(t_inlet, t_outlet, cell_pattern)``: the thickness at its
    ports and, for a straight that hosts a switch, the per-cell thickness
    as ``(first, middle_in, middle_out, last)``.  A switch sits one cell
    inside a straight neighbour, the bare one if both are straight."""
    from ..assembly import AssemblyError
    n = len(comps)
    a = [c.ins[0] for c in comps]
    b = [c.ins[1] for c in comps]
    straight = [_straight_like(c, tol) for c in comps]
    port_in, port_out = list(a), list(b)     # thickness at each port
    for k, c in enumerate(comps):
        if a[k] != b[k] and not straight[k]:
            raise AssemblyError(f"{labels[k]}: insulation changes inside it, and only "
                                f"a straight component can hold the change")
        if a[k] > 0 and b[k] > 0 and a[k] != b[k]:
            raise AssemblyError(f"{labels[k]}: insulation thickness changes inside it")

    def host(k_left, k_right, t_left, t_right, where):
        """Boundary between *k_left* (outlet) and *k_right* (inlet); either
        may be None (fixed: the interface or a junction)."""
        if t_left == t_right:
            return
        if t_left > 0 and t_right > 0:
            name = labels[k_left if k_left is not None else k_right]
            raise AssemblyError(f"{name}: insulation thickness changes from "
                                f"{t_left:.4g} m to {t_right:.4g} m at {where}; only "
                                f"a layer that ends or starts is supported")
        options = [k for k in (k_left, k_right) if k is not None and straight[k]]
        options.sort(key=lambda k: (t_left if k == k_left else t_right) > 0)  # bare first
        if not options:
            name = labels[k_left if k_left is not None else k_right]
            raise AssemblyError(f"{name}: insulation starts or stops at {where}, and "
                                f"no straight component next to it can hold the change")
        k = options[0]
        if k == k_left:                       # the left one takes the right's status
            port_out[k] = t_right
        else:
            port_in[k] = t_left

    host(None, 0, t_in, a[0], "its inlet")
    for k in range(n - 1):
        host(k, k + 1, b[k], a[k + 1], f"its joint with {labels[k + 1]}")
    if to_junction is not None:
        host(n - 1, None, b[-1], to_junction, "the junction after it")
    return [(port_in[k], port_out[k], (port_in[k], a[k], b[k], port_out[k]))
            for k in range(n)]


def _stack_changes(pattern, length, axial_cell, base, nrad):
    """``(n_layers, stack_changes)`` for a straight with per-cell pattern
    ``(first, middle_in, middle_out, last)`` (thickness, m); None if
    uniform."""
    first, mid_a, mid_b, last = pattern
    if first == mid_a == mid_b == last:
        return None
    n = max(1, math.ceil(length / axial_cell - 1e-9))
    need = 1 + (first != mid_a) + (last != mid_b) + (mid_a != mid_b)
    n = max(n, need, 4 if mid_a != mid_b and need > 2 else 0)
    cells = [mid_a] * (n // 2) + [mid_b] * (n - n // 2)
    cells[0], cells[-1] = first, last
    changes, cur = [], cells[0]
    for i, t in enumerate(cells):
        if i and t != cur:
            changes.append((i, _dressed(base, t, nrad)))
            cur = t
    return n, tuple(changes)


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
                f"{np.linalg.norm(point - nz_point):.3g} m apart")
        at = point if point is not None else nz_point
        if at is None:
            raise AssemblyError(f"{what}: no position to attach it by")
        if not ends:
            raise AssemblyError(f"{what}: the network has no open end")
        d, k, q, n = min((float(np.linalg.norm(parts[k].ports[q] - at)), k, q, n)
                         for k, q, n in ends)
        if d > tol:
            raise AssemblyError(
                f"{what} at {np.round(at, 4)}: no open pipe end there; the nearest, "
                f"{describe(parts[k])}, is {d:.3g} m away")
        if n in marked:
            raise AssemblyError(f"{what}: that end is already attached to {marked[n]}")
        if label in marked.values():
            raise AssemblyError(f"{what}: two ends would be named {label!r}")
        marked[n] = label
        names[n] = label
    return set(marked)


def _reject_unsupported(comps: list[_Comp]) -> None:
    """Raise for the parts the importer read but marked unbuildable
    (``Part.reject``), and for crosses."""
    from ..assembly import AssemblyError
    for c in comps:
        if c.part is not None and c.part.reject:
            raise AssemblyError(f"{_describe(c, c.label)}: {c.part.reject}")
        if c.kind == "junction?":
            raise AssemblyError(f"{_describe(c, c.label)}: crosses are not supported "
                                f"(decision 0023)")


def _pieces(comps: list[_Comp], tol: float) -> list[list[int]]:
    """The connected pieces, as component indices in model order, pieces in
    the order of their first component.  Components connect where their
    points meet within *tol*; a tap or wye also connects to a pipe its
    centre lies on."""
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


def build(model: NetworkModel, spec, selection=None, *, axial_cell: float | None = None,
          kinks: str = "error", tol: float | None = None, lc: float | None = None,
          inlet=None, insulation: bool = False, insulation_nrad: int = 2):
    """Build an ``hexmesh.assembly.Assembly`` from a network model.

    The parts form a graph, joined where their ports meet (within *tol*),
    across every network.  It must be one tree: three parts at one point,
    a disconnected part or a loop raises ``AssemblyError`` naming a part
    (a model of several unconnected pieces: ``build_pieces``).  The network
    is placed from a root open end, depth first.  Each part is placed from
    the previous outlet, and its port positions are then checked against
    the placed ports; a gap or a change of direction larger than *tol*
    raises ``AssemblyError`` naming the part (nothing is snapped).

    Mapping: ``Straight``, ``InlineEquipment`` → ``Straight``; ``Bend`` →
    ``Bend`` from its corner (``stated_angle`` / ``stated_radius`` are
    cross-checked); ``Reducer`` → ``Reducer``; ``Junction`` "tee" →
    ``Tee``, "tap" → the host straight split into straight + ``Tee`` +
    straight, "wye" → the end of its stem straight + ``Wye``; ``Joint`` →
    absorbed into the adjacent straight run; ``Polyline`` → straights (or a
    ``SplinePipe`` with ``kinks="spline"``); ``Terminal`` → the name and
    equipment mark of the open end at its port.  A part with ``reject``
    set, or a junction outside its fitting's limits, raises
    ``AssemblyError`` naming the part.

    Root: every junction must be entered through its inlet (a tee's run
    end, a wye's stem).  By default the root is the first open end, in
    model order, from which that holds; ends whose port declares
    ``flow="in"`` are tried first.

    Names: each fitting is labelled with its part's ``name``; open ends
    are ``<network>_end<k>`` (``k`` counts the network's open ends in model
    order), or a terminal's name.

    *spec*: a ``PipeSpec``, or a callable of a ``Section`` (first
    parameter named ``section`` or annotated ``Section``), or of the
    nominal size in metres (``spec(bore)``).  *selection*: part ids to
    build (default all); terminals outside it are ignored.  The other
    options are as for ``NetworkSpec.to_assembly``.  ``model.report``
    records the tolerance, the joints absorbed and the largest lateral
    offset.
    """
    if kinks not in ("error", "spline"):
        raise ValueError(f"kinks must be 'error' or 'spline', got {kinks!r}")
    comps = _comps(model, None if selection is None else set(selection))
    if not comps:
        raise ValueError("the network model has no parts to build.")
    if tol is None:
        tol = _model_tolerance(comps)
    _reject_unsupported(comps)
    terminals = [t for t in model.parts.values() if isinstance(t, Terminal)
                 and (selection is None or t.id in selection)]
    asm, report = _build(model, comps, terminals, spec, axial_cell, kinks, tol, lc, inlet,
                         insulation, insulation_nrad)
    model.report = report
    return asm


def build_pieces(model: NetworkModel, spec, *, axial_cell: float | None = None,
                 kinks: str = "error", tol: float | None = None, lc: float | None = None,
                 insulation: bool = False, insulation_nrad: int = 2) -> dict:
    """One ``Assembly`` per connected piece of *model*: ``build`` with a
    selection per piece (same options; the root is chosen per piece).

    Returns ``{name: Assembly}`` in model order (of each piece's first
    part), named after the piece's first network (``piece<k>`` without
    one; a repeat gets ``_2``, …).  Fittings keep their part names.  A
    terminal goes to the piece whose open end it sits at (one with no
    position, to every piece).  ``model.report["pieces"]`` holds each
    piece's report.  Rejected parts raise before any piece is built.
    """
    from ..assembly import AssemblyError
    comps = _comps(model, None)
    if not comps:
        raise ValueError("the network model has no parts to build.")
    if tol is None:
        tol = _model_tolerance(comps)
    _reject_unsupported(comps)
    ignored = model.report.get("ignored", {})
    terminals = [t for t in model.parts.values() if isinstance(t, Terminal)]
    out, reports = {}, {}
    for k, ks in enumerate(_pieces(comps, tol), start=1):
        sub = [comps[i] for i in ks]
        ids = {c.part.id for c in sub}
        pts = [x for c in sub for x in (c.start, c.end, c.branch, c.branch2) if x is not None]
        terms = [t for t in terminals if model.ports[t.ports[0]].position is None
                 or min(np.linalg.norm(x - model.ports[t.ports[0]].position) for x in pts) <= tol]
        pipe = next((_name(c.system) for c in sub if _name(c.system)), "")
        name, n = pipe or f"piece{k}", 2
        while name in out:
            name, n = f"{pipe or f'piece{k}'}_{n}", n + 1
        try:
            out[name], reports[name] = _build(
                model, _comps(model, ids), terms, spec, axial_cell, kinks, tol, lc, None,
                insulation, insulation_nrad, ignored={})
        except AssemblyError as e:
            raise AssemblyError(f"{name}: {e}") from None
    model.report = {"ignored": ignored, "tolerance": tol, "pieces": reports}
    return out


def _build(model, comps, terminals, spec, axial_cell, kinks, tol, lc, inlet, insulation,
           insulation_nrad, ignored=None):
    """Build *comps* (from ``_comps``; checked) and return ``(Assembly, report)``."""
    report = {"ignored": model.report.get("ignored", {}) if ignored is None else ignored}
    spec = _section_spec(spec)
    if insulation:
        sample = spec(comps[0].sec if comps[0].bore else Section(nominal=0.1)) \
            if callable(spec) else spec
        if any(sh.name == INSULATION for sh in sample.shells):
            raise ValueError(f"insulation=True adds a shell named {INSULATION!r}; the "
                             f"spec already has one")
        _resolve_insulation(model, comps)
    else:
        for c in comps:
            c.ins, c.ins_junction = (0.0, 0.0), 0.0

    def seton_run(j_c, host, t_j):
        """The Tee's default run for a set-on on *host* (task 0054)."""
        from ..assembly import Tee
        from ..assembly.interface import Frame
        base = spec(host.sec) if callable(spec) else spec
        main = _dressed(base, t_j, insulation_nrad) if insulation else base
        R = _radius(main)
        rb = _branch_radius(spec, R, j_c.branch_sec, host.bore)
        if not rb < R:             # the junction rejects it, naming the radii
            return j_c.branch_bore
        tee = Tee(None, 10 * R, rb).resolve(
            Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0])), main)
        return tee.run_length

    whole = comps
    comps, labels = _split_hosts([replace(c, start=c.start.copy(), end=c.end.copy())
                                  for c in comps], [c.label for c in comps], tol, seton_run)
    joints = [c for c in comps if c.kind == "joint"]
    parts = [_Part(c, l, _ports(c)) for c, l in zip(comps, labels) if c.kind != "joint"]
    if not parts:
        raise ValueError("the network model has only joints.")
    nodes, at_node = _graph(parts, joints, tol)
    _check_tree(parts, nodes, lambda: _pieces_hint(model, whole, tol))
    names = _end_names(parts, nodes)
    equipment = _equipment_ends(model, terminals, parts, nodes, names, tol,
                                lambda p: _describe(p.comp, p.label))
    root = _choose_root(parts, nodes, names, inlet, tol)
    ins = {"on": bool(insulation), "nrad": insulation_nrad, "equipment": equipment}

    roll = 0.0
    for _ in range(2):
        try:
            asm = _place(report, parts, nodes, at_node, names, root, spec, axial_cell,
                         kinks, tol, lc, roll, reroll=(roll == 0.0), ins=ins)
            return asm, report
        except _Reroll as r:
            roll = r.miss
    raise AssertionError("unreachable")


def _place(report, parts, nodes, at_node, names, root, spec, axial_cell, kinks, tol, lc,
           roll, reroll, ins):
    """Place the network from *root* (part, port, node), depth first."""
    from ..assembly import Assembly, AssemblyError, Tee, Wye
    from ..assembly.interface import outer_radius, rotate, toward_roll

    report.update({"tolerance": tol, "joints": [], "max_offset": 0.0})
    k0, q0, n0 = root
    first = _orient(parts[k0].comp, q0)
    current = base = spec(first.sec) if callable(spec) else spec
    if ins["on"]:
        t0 = first.ins_junction if first.kind in ("tee", "wye") else first.ins[0]
        current = _dressed(current, t0, ins["nrad"])
    d0 = (_unit(first.end - first.start) if first.kind == "tee"
          else _unit(first.centre - first.start) if first.kind == "wye"
          else _start_direction(first))
    up0 = rotate(_perpendicular(d0), d0, math.radians(roll))
    asm = Assembly(current, position=first.start, direction=d0, up=up0, lc=lc,
                   axial_cell=axial_cell or outer_radius(base),
                   **({"inlet_name": names[n0]} if names.get(n0) else {}))
    asm.inlet.equipment = n0 in ins["equipment"]
    state = {"junctions": 0, "tail": None}

    def check(what, frame, end):
        if np.linalg.norm(frame.position - end) > tol:
            raise AssemblyError(
                f"{what}: placed port {np.round(frame.position, 6)} misses its "
                f"port {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m")

    def joints_at(n, x):
        return [(j, None) for j in _joints_from(at_node.get(n, []), x)]

    def walk(iface, k, q, start_node):
        """From *iface*, entering part *k* at port *q*: the run of two-port
        parts, with the joints at the nodes it crosses, up to a junction or
        an open end."""
        chain = joints_at(start_node, iface.frame.position)
        while parts[k].kind not in ("tee", "wye"):
            p = parts[k]
            c = _orient(p.comp, q)
            chain.append((c, p.label))
            n = p.nodes[1 - q]
            chain += joints_at(n, c.end)
            nxt = [(j, s) for j, s in nodes[n] if j != k]
            if not nxt:
                return chain, None, n
            k, q = nxt[0]
        return chain, (k, q), None

    def junction(iface, k, q):
        p = parts[k]
        c = _orient(p.comp, q)
        what = _describe(p.comp, p.label)
        frame = iface.frame
        if ins["on"] and abs(_thickness(iface.spec) - c.ins_junction) > 1e-12:
            raise AssemblyError(
                f"{what}: arrives with insulation {_thickness(iface.spec):.4g} m but "
                f"carries {c.ins_junction:.4g} m, and no straight component before "
                f"it can hold the change")
        check(what, frame, c.start)
        centre = c.centre
        axis = _unit(centre - c.start)
        if np.linalg.norm(np.cross(axis, frame.normal)) > 1e-3 or np.dot(axis, frame.normal) < 0:
            raise AssemblyError(f"{what}: its inlet run is not along the incoming pipe")
        run = float(np.linalg.norm(centre - c.start))
        main_bore = c.bore
        if p.kind == "tee":
            b = c.branch - centre
            blen = float(np.linalg.norm(b))
            tilt = math.degrees(math.asin(min(1.0, abs(float(np.dot(_unit(b), axis))))))
            if tilt > 1.0:
                raise AssemblyError(f"{what}: branch at {90 - tilt:.4g}° to the run; a Tee "
                                    f"branch is perpendicular (angled tees are not supported)")
            if abs(float(np.linalg.norm(c.end - centre)) - run) > tol:
                raise AssemblyError(f"{what}: run ports are not symmetric about "
                                    f"its centre")
            if not (c.branch_bore and main_bore):
                raise AssemblyError(f"{what}: needs sizes on its run and branch points")
            R = _radius(iface.spec)
            rb = _branch_radius(spec, R, c.branch_sec, main_bore)
            if not rb < R:
                raise AssemblyError(f"{what}: equal tees (branch radius {rb:.4g}, main "
                                    f"radius {R:.4g}) are planned through the wye-family "
                                    f"layout; not available yet")
            fitting = Tee(run, blen, rb, toward=tuple(_unit(b)))
            outs_at = [c.end, c.branch]
        else:
            d1, d2 = _unit(c.branch - centre), _unit(c.branch2 - centre)
            h1 = math.degrees(math.acos(float(np.clip(np.dot(d1, axis), -1, 1))))
            h2 = math.degrees(math.acos(float(np.clip(np.dot(d2, axis), -1, 1))))
            l1 = float(np.linalg.norm(c.branch - centre))
            l2 = float(np.linalg.norm(c.branch2 - centre))
            coplanar = abs(float(np.dot(axis, np.cross(d1, d2))))
            if abs(h1 - h2) > 0.1 or abs(l1 - l2) > tol or coplanar > 1e-3:
                raise AssemblyError(f"{what}: asymmetric Y piece (daughters at {h1:.4g}° "
                                    f"and {h2:.4g}°, {l1:.4g} and {l2:.4g} m); a Wye "
                                    f"is symmetric and coplanar")
            for bb in (c.branch_bore, c.branch2_bore):
                if bb is not None and main_bore and abs(bb - main_bore) > 1e-9:
                    raise AssemblyError(f"{what}: daughters must have the stem's size "
                                        f"(Wye daughters keep the inlet's spec)")
            side = d1 - np.dot(d1, axis) * axis            # BRANCH1 is the "right" daughter
            fitting = Wye(h1 + h2, run, l1, toward=tuple(_unit(side)))
            outs_at = [c.branch2, c.branch]                # [left, right]
        if reroll and state["junctions"] == 0:
            offset = 0.0 if p.kind == "tee" else 90.0
            want = toward_roll(frame, fitting.toward) - offset
            miss = math.remainder(want, 90.0)
            if abs(miss) > 1e-9:
                raise _Reroll(miss)
        state["junctions"] += 1
        try:
            fitting.resolve(frame, iface.spec).check(iface.spec)
        except ValueError as e:
            raise AssemblyError(f"{what}: {e}") from None
        outs = asm.add(iface, fitting, label=p.label)
        for o, x in zip(outs, outs_at):
            check(what, o.frame, x)
        return outs, outs_at

    def end_of(iface, n):
        if names.get(n):
            iface.name = names[n]
        iface.equipment = n in ins["equipment"]
        if state["tail"] is None:
            state["tail"] = iface

    def run_from(iface, k, q, start_node):
        chain, jn, end_node = walk(iface, k, q, start_node)
        end_dir = None
        if jn is not None:
            jc = _orient(parts[jn[0]].comp, jn[1])
            end_dir = _unit(jc.centre - jc.start)
        to_junction = None if jn is None else _orient(parts[jn[0]].comp, jn[1]).ins_junction
        iface = _place_chain(asm, iface, chain, end_dir, spec, kinks, tol, ins, to_junction,
                             report)
        if jn is None:
            end_of(iface, end_node)
            return
        outs, _ = junction(iface, *jn)
        p = parts[jn[0]]
        out_ports = [1, 2] if p.kind == "tee" else [2, 1]
        if p.kind == "tee" and jn[1] == 1:
            out_ports = [0, 2]
        for o, r in zip(outs, out_ports):
            n = p.nodes[r]
            nxt = [(j, s) for j, s in nodes[n] if j != jn[0]]
            if nxt:
                run_from(o, *nxt[0], n)
            else:
                end_of(o, n)

    if parts[k0].kind in ("tee", "wye"):
        outs, _ = junction(asm.inlet, k0, q0)
        p = parts[k0]
        out_ports = ([1, 2] if q0 == 0 else [0, 2]) if p.kind == "tee" else [2, 1]
        for o, r in zip(outs, out_ports):
            n = p.nodes[r]
            nxt = [(j, s) for j, s in nodes[n] if j != k0]
            run_from(o, *nxt[0], n) if nxt else end_of(o, n)
    else:
        run_from(asm.inlet, k0, q0, n0)
    if state["tail"] is not None:
        asm._tail = state["tail"]
    return asm


def _place_chain(asm, iface, chain, end_dir, spec, kinks, tol, ins, to_junction, report):
    """Place a run of two-port components (oriented, with labels) from
    *iface*; return the last interface.  *end_dir* is the direction of the
    junction that follows, if any (a spline's end tangent)."""
    from ..assembly import AssemblyError, Bend, Reducer, SplinePipe, Straight

    comps = [c for c, _ in chain]
    labels = {id(c): l for c, l in chain if l is not None}
    comps = _absorb_joints(comps, report)
    if not comps:
        return iface

    def label(k):
        c = comps[k]
        return _describe(c, labels.get(id(c), c.kind))

    plan = (_plan_insulation(comps, [label(k) for k in range(len(comps))],
                             _thickness(iface.spec), to_junction, tol)
            if ins["on"] else None)

    def uniform(k):
        return plan is None or len(set(plan[k][2])) == 1

    def check(k, frame, end):
        if np.linalg.norm(frame.position - end) > tol:
            raise AssemblyError(
                f"{label(k)}: placed outlet {np.round(frame.position, 6)} misses its "
                f"end point {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m"
            )

    def along(frame, end):
        """(axial length, lateral offset) of *end* from the outlet *frame*."""
        d = end - frame.position
        ax = float(np.dot(d, frame.normal))
        return ax, float(np.linalg.norm(d - ax * frame.normal))

    def straight_on(k, frame):
        ax, lat = along(frame, comps[k].end)
        return ax > tol and lat <= tol

    k = 0
    while k < len(comps):
        c = comps[k]
        frame = iface.frame
        lab = labels.get(id(c))
        if np.linalg.norm(c.start - frame.position) > tol:
            raise AssemblyError(
                f"{label(k)}: starts {np.linalg.norm(c.start - frame.position):.3g} m "
                f"from the previous outlet"
            )
        length = float(np.linalg.norm(c.end - c.start))
        if c.kind in ("pipe", "fitting"):
            if length <= tol:
                k += 1
                continue
            if not straight_on(k, frame):
                if kinks == "error" or c.kind != "pipe":
                    raise AssemblyError(
                        f"{label(k)}: changes direction without a fitting "
                        f"(use kinks='spline' for routes)"
                    )
                # maximal run of pipes from here, joined by one spline
                j = k
                while j + 1 < len(comps) and comps[j + 1].kind == "pipe":
                    j += 1
                if not all(uniform(i) for i in range(k, j + 1)):
                    raise AssemblyError(f"{label(k)}: insulation starts or stops inside a "
                                        f"spline run; it needs a straight component")
                pts = [frame.position] + [comps[i].end for i in range(k, j + 1)]
                nxt = comps[j + 1] if j + 1 < len(comps) else None
                end_t = (tuple(_start_direction(nxt)) if nxt is not None
                         else None if end_dir is None else tuple(end_dir))
                iface = asm.add(iface, SplinePipe(tuple(map(tuple, pts)), end_tangent=end_t),
                                label=lab)
                check(j, iface.frame, comps[j].end)
                k = j + 1
                continue
            # from the placed outlet to the part's end port: gaps never accumulate
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            switch = None if uniform(k) else _stack_changes(
                plan[k][2], ax, asm.axial_cell, iface.spec, ins["nrad"])
            if switch is None:
                iface = asm.add(iface, Straight(ax), label=lab)
            else:
                n, changes = switch
                iface = asm.add(iface, Straight(ax, n, stack_changes=changes), label=lab)
            check(k, iface.frame, c.end)
        elif c.kind == "elbow":
            try:
                g = _elbow_params(c)
            except ValueError as e:
                raise AssemblyError(f"{label(k)}: {e}") from None
            leg = float(np.linalg.norm(c.centre - c.start))
            if np.linalg.norm(np.cross(g.incoming, frame.normal)) * leg > tol \
                    or np.dot(g.incoming, frame.normal) < 0:
                raise AssemblyError(
                    f"{label(k)}: bend's incoming leg (start → corner) is not "
                    f"along the incoming pipe")
            _cross_check_elbow(c, g, label(k))
            roll = math.degrees(math.atan2(np.dot(g.turn, frame.right),
                                           np.dot(g.turn, frame.up)))
            iface = asm.add(iface, Bend(g.radius, g.angle, roll=roll), label=lab)
            check(k, iface.frame, c.end)
        elif c.kind == "reducer":
            if c.eccentric:
                raise AssemblyError(f"{label(k)}: eccentric reducers are not supported")
            if not c.end_bore or not c.bore:
                raise AssemblyError(f"{label(k)}: reducer needs both bores")
            if callable(spec):
                outlet = spec(c.end_sec)
                if ins["on"]:
                    outlet = _dressed(outlet, _thickness(iface.spec), ins["nrad"])
            else:
                cur = iface.spec
                radii = [cur.core_shape.radius * c.end_bore / c.bore] + [sh.dR for sh in cur.shells]
                outlet = cur.with_radii(radii)
            if not straight_on(k, frame):
                raise AssemblyError(f"{label(k)}: reducer axis is not the incoming direction")
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            iface = asm.add(iface, Reducer(outlet, ax), label=lab)
            check(k, iface.frame, c.end)
        else:
            raise AssemblyError(f"{label(k)}: unsupported kind {c.kind!r}")
        k += 1
    return iface


# Cross-check tolerances: a stated angle to 0.05° (PCF gives hundredths of
# a degree); radii from nD × nominal size are exact for standard elbows.
ANGLE_TOL = 0.05       # degrees
RADIUS_TOL = 0.01      # relative


def _cross_check_elbow(c: _Comp, g: ElbowGeometry, label: str) -> None:
    """A bend's stated angle and radius (when its source states them)
    against those from its corner geometry."""
    from ..assembly import AssemblyError
    part = c.part
    if not isinstance(part, Bend):
        return
    said = part.stated_names
    geometry = said.get("geometry", "its ports and corner point")
    if part.stated_angle is not None and abs(part.stated_angle - g.angle) > ANGLE_TOL:
        what = said.get("angle", f"stated angle {part.stated_angle:g}°")
        raise AssemblyError(f"{label}: {what} disagrees with the {g.angle:.4g}° "
                            f"from {geometry}")
    r = part.stated_radius
    if r is not None and abs(r - g.radius) > RADIUS_TOL * g.radius:
        what = said.get("radius", "stated radius")
        raise AssemblyError(f"{label}: {what} ({r:.6g} m) disagrees "
                            f"with the {g.radius:.6g} m from {geometry}")


BUILDERS.update(build=build, build_pieces=build_pieces)
