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
The builder (decision 0032): a network model → an ``Assembly``.

Format-neutral: it never branches on the source format (decision 0032,
constraint 1).  Format facts reach it only as model content (stated bend
angles, rejections, flow directions, equipment tags) and through the
importer's message formatter (``model.register_formatter``).

Moved from the PCF reader (task 0065) without changing its behaviour:
the connection graph within a tolerance, joint absorption, the tree check,
root choice, junction entry, insulation planning, equipment ends and
placement.

Task 0066 split it along its concerns: ``graph`` (the parts graph, the
pieces, roots and open ends), ``insulation`` (insulation planning) and
this module (the mapping to fittings, and placement).
"""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, replace

import numpy as np

from .model import BUILDERS, Bend, NetworkModel, Reducer, Section, Straight, Terminal
from .graph import (
    TOL_FLOOR, TOL_RELATIVE, _Comp, _comps, _unit, _model_tolerance, _name, _Part, _ports,
    _source, _part_id, _describe, _graph, _joints_from, _pieces_hint, _check_tree,
    _end_names, _choose_root, _orient, _equipment_ends, _reject_unsupported, _pieces,
)
from .insulation import (
    INSULATION, _radius, _resolve_insulation, _junction_thickness, _dressed, _thickness,
    _plan_insulation, _stack_changes,
)


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
                    f"{c.type}); there is no straight run to absorb it",
                    code="joint_between_fittings", where={"source": _source(pending[0])})
            pending = []
        out.append(c)
    report["joints"].extend((j.type, "dropped") for j in pending)
    return out


class _Reroll(Exception):
    """Raised at the first junction: rebuild with the root rolled by *miss*."""

    def __init__(self, miss: float):
        self.miss = miss


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
                                f"supported; a Tee branch is perpendicular and centred",
                                code="seton_offset_unsupported",
                                where={"part": _part_id(j_c), "source": _source(j_c)})
        if j_c.centre is None or j_c.branch is None:
            raise AssemblyError(f"{what}: needs a centre and a branch point",
                                code="junction_points_missing",
                                where={"part": _part_id(j_c), "source": _source(j_c)})
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
                                    f"(the branch must be centred on a straight pipe)",
                                    code="seton_host_missing",
                                    where={"part": _part_id(j_c), "source": _source(j_c)})
            h, t, L = inside[0]
            host = comps[h]
            axis = (host.end - host.start) / L
            if not j_c.branch_bore:
                raise AssemblyError(f"{what}: needs a size on its branch",
                                    code="junction_size_missing",
                                    where={"part": _part_id(j_c), "source": _source(j_c)})
            t_j = _junction_thickness([j_c.ins_junction, *host.ins], what)
            run = seton_run(j_c, host, t_j)
            if t - run <= tol or t + run >= L - tol:
                raise AssemblyError(
                    f"{what}: host pipe {labels[h]} is too short around the branch; "
                    f"the tee needs {run:.4g} m on each side of its centre",
                    code="seton_host_too_short", where={"part": _part_id(j_c), "source": _source(j_c)},
                    value=float(min(t, L - t)), limit={"min_exclusive": float(run)})
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
                                    f"centre, and two branch points",
                                    code="ypiece_stem_missing",
                                    where={"part": _part_id(j_c), "source": _source(j_c)})
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
                    f"{run:.4g} m the Wye's inlet run needs",
                    code="ypiece_stem_too_short",
                    where={"part": _part_id(j_c), "source": _source(j_c)}, value=L,
                    limit={"min_exclusive": float(run)})
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
    from ..assembly import AssemblyError
    if kinks not in ("error", "spline"):
        raise AssemblyError(f"kinks must be 'error' or 'spline', got {kinks!r}",
                            code="option_invalid", where={"field": "kinks"}, value=kinks,
                            limit=["error", "spline"])
    comps = _comps(model, None if selection is None else set(selection))
    if not comps:
        raise AssemblyError("the network model has no parts to build.", code="network_empty")
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
        raise AssemblyError("the network model has no parts to build.", code="network_empty")
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
            raise AssemblyError.wrap(e, f"{name}: {e}",
                                     code="network_piece_invalid", label=name) from None
    model.report = {"ignored": ignored, "tolerance": tol, "pieces": reports}
    return out


def _build(model, comps, terminals, spec, axial_cell, kinks, tol, lc, inlet, insulation,
           insulation_nrad, ignored=None):
    """Build *comps* (from ``_comps``; checked) and return ``(Assembly, report)``."""
    from ..assembly import AssemblyError
    report = {"ignored": model.report.get("ignored", {}) if ignored is None else ignored}
    spec = _section_spec(spec)
    if insulation:
        sample = spec(comps[0].sec if comps[0].bore else Section(nominal=0.1)) \
            if callable(spec) else spec
        if any(sh.name == INSULATION for sh in sample.shells):
            raise AssemblyError(f"insulation=True adds a shell named {INSULATION!r}; the "
                                f"spec already has one",
                                code="insulation_shell_exists", where={"field": "insulation"})
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
        raise AssemblyError("the network model has only joints.", code="network_only_joints")
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

    def check(what, frame, end, piece):
        if np.linalg.norm(frame.position - end) > tol:
            raise AssemblyError(
                f"{what}: placed port {np.round(frame.position, 6)} misses its "
                f"port {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m",
                code="port_placement_mismatch",
                where={"part": _part_id(piece), "source": _source(piece)},
                value=float(np.linalg.norm(frame.position - end)), limit={"max": tol})

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
                f"it can hold the change",
                code="junction_insulation_differs", where={"part": _part_id(p), "source": _source(p)})
        check(what, frame, c.start, p)
        centre = c.centre
        axis = _unit(centre - c.start)
        if np.linalg.norm(np.cross(axis, frame.normal)) > 1e-3 or np.dot(axis, frame.normal) < 0:
            raise AssemblyError(f"{what}: its inlet run is not along the incoming pipe",
                                code="junction_run_not_along_pipe",
                                where={"part": _part_id(p), "source": _source(p)})
        run = float(np.linalg.norm(centre - c.start))
        main_bore = c.bore
        if p.kind == "tee":
            b = c.branch - centre
            blen = float(np.linalg.norm(b))
            tilt = math.degrees(math.asin(min(1.0, abs(float(np.dot(_unit(b), axis))))))
            if tilt > 1.0:
                raise AssemblyError(f"{what}: branch at {90 - tilt:.4g}° to the run; a Tee "
                                    f"branch is perpendicular (angled tees are not supported)",
                                    code="tee_branch_angled",
                                    where={"part": _part_id(p), "source": _source(p)}, value=90 - tilt,
                                    limit=90)
            if abs(float(np.linalg.norm(c.end - centre)) - run) > tol:
                raise AssemblyError(f"{what}: run ports are not symmetric about "
                                    f"its centre",
                                    code="tee_run_asymmetric",
                                    where={"part": _part_id(p), "source": _source(p)})
            if not (c.branch_bore and main_bore):
                raise AssemblyError(f"{what}: needs sizes on its run and branch points",
                                    code="junction_size_missing",
                                    where={"part": _part_id(p), "source": _source(p)})
            R = _radius(iface.spec)
            rb = _branch_radius(spec, R, c.branch_sec, main_bore)
            if not rb < R:
                raise AssemblyError(f"{what}: equal tees (branch radius {rb:.4g}, main "
                                    f"radius {R:.4g}) are planned through the wye-family "
                                    f"layout; not available yet",
                                    code="equal_tee_unsupported",
                                    where={"part": _part_id(p), "source": _source(p)}, value=rb,
                                    limit={"max_exclusive": R})
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
                                    f"is symmetric and coplanar",
                                    code="ypiece_asymmetric",
                                    where={"part": _part_id(p), "source": _source(p)})
            for bb in (c.branch_bore, c.branch2_bore):
                if bb is not None and main_bore and abs(bb - main_bore) > 1e-9:
                    raise AssemblyError(f"{what}: daughters must have the stem's size "
                                        f"(Wye daughters keep the inlet's spec)",
                                        code="ypiece_daughter_size",
                                        where={"part": _part_id(p), "source": _source(p)})
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
            raise AssemblyError.wrap(e, f"{what}: {e}",
                                     code="fitting_invalid", part=_part_id(p),
                                     source=_source(p)) from None
        outs = asm.add(iface, fitting, label=p.label, origin=_source(p) or None)
        for o, x in zip(outs, outs_at):
            check(what, o.frame, x, p)
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
                f"end point {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m",
                code="port_placement_mismatch",
                where={"part": _part_id(comps[k]), "source": _source(comps[k])},
                value=float(np.linalg.norm(frame.position - end)), limit={"max": tol}
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
                f"from the previous outlet",
                code="chain_gap", where={"part": _part_id(c), "source": _source(c)},
                value=float(np.linalg.norm(c.start - frame.position)), limit={"max": tol}
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
                        f"(use kinks='spline' for routes)",
                        code="kink_without_fitting",
                        where={"part": _part_id(c), "source": _source(c)},
                        hint="use kinks='spline' for routes"
                    )
                # maximal run of pipes from here, joined by one spline
                j = k
                while j + 1 < len(comps) and comps[j + 1].kind == "pipe":
                    j += 1
                if not all(uniform(i) for i in range(k, j + 1)):
                    raise AssemblyError(f"{label(k)}: insulation starts or stops inside a "
                                        f"spline run; it needs a straight component",
                                        code="insulation_change_in_spline",
                                        where={"part": _part_id(c), "source": _source(c)})
                pts = [frame.position] + [comps[i].end for i in range(k, j + 1)]
                nxt = comps[j + 1] if j + 1 < len(comps) else None
                end_t = (tuple(_start_direction(nxt)) if nxt is not None
                         else None if end_dir is None else tuple(end_dir))
                iface = asm.add(iface, SplinePipe(tuple(map(tuple, pts)), end_tangent=end_t),
                                label=lab, origin=_source(c) or None)   # its first pipe
                check(j, iface.frame, comps[j].end)
                k = j + 1
                continue
            # from the placed outlet to the part's end port: gaps never accumulate
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            switch = None if uniform(k) else _stack_changes(
                plan[k][2], ax, asm.axial_cell, iface.spec, ins["nrad"])
            if switch is None:
                iface = asm.add(iface, Straight(ax), label=lab, origin=_source(c) or None)
            else:
                n, changes = switch
                iface = asm.add(iface, Straight(ax, n, stack_changes=changes), label=lab,
                                origin=_source(c) or None)
            check(k, iface.frame, c.end)
        elif c.kind == "elbow":
            try:
                g = _elbow_params(c)
            except ValueError as e:
                raise AssemblyError.wrap(e, f"{label(k)}: {e}",
                                         code="bend_geometry_invalid", part=_part_id(c),
                                         source=_source(c)) from None
            leg = float(np.linalg.norm(c.centre - c.start))
            if np.linalg.norm(np.cross(g.incoming, frame.normal)) * leg > tol \
                    or np.dot(g.incoming, frame.normal) < 0:
                raise AssemblyError(
                    f"{label(k)}: bend's incoming leg (start → corner) is not "
                    f"along the incoming pipe",
                    code="bend_leg_not_along_pipe", where={"part": _part_id(c), "source": _source(c)})
            _cross_check_elbow(c, g, label(k))
            roll = math.degrees(math.atan2(np.dot(g.turn, frame.right),
                                           np.dot(g.turn, frame.up)))
            iface = asm.add(iface, Bend(g.radius, g.angle, roll=roll), label=lab,
                            origin=_source(c) or None)
            check(k, iface.frame, c.end)
        elif c.kind == "reducer":
            if c.eccentric:
                raise AssemblyError(f"{label(k)}: eccentric reducers are not supported",
                                    code="reducer_eccentric",
                                    where={"part": _part_id(c), "source": _source(c)})
            if not c.end_bore or not c.bore:
                raise AssemblyError(f"{label(k)}: reducer needs both bores",
                                    code="reducer_sizes_missing",
                                    where={"part": _part_id(c), "source": _source(c)})
            if callable(spec):
                outlet = spec(c.end_sec)
                if ins["on"]:
                    outlet = _dressed(outlet, _thickness(iface.spec), ins["nrad"])
            else:
                cur = iface.spec
                radii = [_radius(cur) * c.end_bore / c.bore] + [sh.dR for sh in cur.shells]
                outlet = cur.with_radii(radii)
            if not straight_on(k, frame):
                raise AssemblyError(f"{label(k)}: reducer axis is not the incoming direction",
                                    code="reducer_axis_not_along_pipe",
                                    where={"part": _part_id(c), "source": _source(c)})
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            iface = asm.add(iface, Reducer(outlet, ax), label=lab, origin=_source(c) or None)
            check(k, iface.frame, c.end)
        else:
            raise AssemblyError(f"{label(k)}: unsupported kind {c.kind!r}",
                                code="part_kind_unsupported",
                                where={"part": _part_id(c), "source": _source(c)}, value=c.kind)
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
                            f"from {geometry}",
                            code="stated_angle_disagrees",
                            where={"part": _part_id(c), "source": _source(c)}, value=part.stated_angle,
                            limit=g.angle)
    r = part.stated_radius
    if r is not None and abs(r - g.radius) > RADIUS_TOL * g.radius:
        what = said.get("radius", "stated radius")
        raise AssemblyError(f"{label}: {what} ({r:.6g} m) disagrees "
                            f"with the {g.radius:.6g} m from {geometry}",
                            code="stated_radius_disagrees",
                            where={"part": _part_id(c), "source": _source(c)}, value=r, limit=g.radius)


BUILDERS.update(build=build, build_pieces=build_pieces)
