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
Model operations (task 0066; decision 0032, items 3 and 6): select, cut,
join and merge, and the operation log they write.

A network model connects parts where their ports meet, within the
builder's tolerance (``tolerance``).  These operations change which ports
are connected without moving anything:

- ``select`` chooses the parts to build (not logged);
- ``cut`` / ``cut_at`` record a ``Cut``: the builder leaves both ports as
  open ends;
- ``join`` connects two open ports (and undoes a cut between them);
- ``merge`` unites two models.

``cut``, ``cut_at``, ``join`` and ``merge`` append an entry to
``model.log``; ``replay`` re-applies a log to a fresh import, and ``undo``
replays all but the last entry.  They are the ``NetworkModel`` methods of
the same names, which document them.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timezone

import numpy as np

from ..assembly import AssemblyError
from ..version import __version__
from .graph import TOL_FLOOR, _comps, _model_tolerance
from .model import (
    IMPORTERS, OPERATIONS, Bend, Connection, Cut, Junction, NetworkModel, Network, Polyline,
    Selection, Terminal,
)

#: largest angle, degrees, between one port's outward direction and the
#: reverse of the other's for ``join``
JOIN_ANGLE_TOL = 1.0
#: relative tolerance for ``join``'s section comparison
SECTION_RTOL = 1e-6


def tolerance(model: NetworkModel) -> float:
    """The builder's connection tolerance for the whole of *model*."""
    comps = _comps(model, None)
    return _model_tolerance(comps) if comps else TOL_FLOOR


# --- who meets whom --------------------------------------------------------------

def _owners(model: NetworkModel) -> dict:
    return {q: part for part in model.parts.values() for q in part.ports}


def _port(model: NetworkModel, pid: str):
    if pid not in model.ports:
        raise AssemblyError(f"no port {pid!r} in the model", code="model_id_unknown",
                            where={"field": "port"}, value=pid)
    return model.ports[pid]


def _meets(model: NetworkModel, tol: float) -> list[tuple[str, str]]:
    """Pairs of ports of different parts (not terminals) within *tol*."""
    owner = _owners(model)
    ids = [q for q, p in model.ports.items()
           if p.position is not None and q in owner and not isinstance(owner[q], Terminal)]
    if not ids:
        return []
    pts = np.array([model.ports[q].position for q in ids])
    out = []
    for i in range(len(ids)):
        for j in np.flatnonzero(np.linalg.norm(pts[:i] - pts[i], axis=1) <= tol):
            if owner[ids[i]] is not owner[ids[j]]:
                out.append((ids[int(j)], ids[i]))
    return out


def _links(model: NetworkModel, tol: float) -> list[tuple[str, str]]:
    """The connected port pairs: those that meet, and the declared
    connections, less the cuts."""
    cut = {frozenset((c.a, c.b)) for c in model.cuts}
    pairs = {frozenset(p) for p in _meets(model, tol)}
    pairs |= {frozenset((c.a, c.b)) for c in model.connections if c.a in model.ports
              and c.b in model.ports}
    return [tuple(sorted(p)) for p in pairs - cut if len(p) == 2]


def _partners(model: NetworkModel, pid: str, tol: float) -> list[str]:
    return sorted(b if a == pid else a for a, b in _links(model, tol) if pid in (a, b))


# --- the log -----------------------------------------------------------------------

def _state(model: NetworkModel) -> NetworkModel:
    """A deep copy of *model* without its undo base."""
    base = model.__dict__.pop("_undo_base", None)
    try:
        return copy.deepcopy(model)
    finally:
        if base is not None:
            model._undo_base = base


def _begin(model: NetworkModel) -> None:
    """Before an operation changes *model*: the first keeps the state, which
    ``undo`` replays from."""
    if "_undo_base" not in model.__dict__:
        model._undo_base = (_state(model), len(model.log))


def _log(model: NetworkModel, op: str, args: dict) -> None:
    """Append an entry to *model*'s log."""
    _begin(model)
    model.log.append({"op": op, "args": args,
                      "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "version": __version__})


def _assign(dst: NetworkModel, src: NetworkModel) -> None:
    for name in ("ports", "parts", "connections", "networks", "report", "cuts", "log"):
        setattr(dst, name, getattr(src, name))


def import_entry(model: NetworkModel, importer: str, source, options: dict) -> None:
    """Start *model*'s log with the importer's entry: ``replay`` re-reads a
    merged model through ``IMPORTERS[importer](source, options)``."""
    model.log.insert(0, {"op": "import", "args": {"importer": importer, "source": source,
                                                  "options": options},
                         "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "version": __version__})


# --- select ------------------------------------------------------------------------

def select(model: NetworkModel, parts, network, from_port, up_to) -> Selection:
    given = [k for k, v in (("parts", parts), ("network", network), ("from_port", from_port))
             if v is not None]
    if len(given) != 1:
        raise AssemblyError(f"select: give one of parts, network and from_port, got "
                            f"{', '.join(given) or 'none'}", code="selection_invalid",
                            where={"field": "select"}, value=given)
    tol = tolerance(model)
    owner = _owners(model)
    if parts is not None:
        ids = set(parts)
        unknown = sorted(ids - set(model.parts))
        if unknown:
            raise AssemblyError(f"select: no part {', '.join(map(repr, unknown))} in the model",
                                code="model_id_unknown", where={"field": "parts"}, value=unknown)
        how = {"parts": sorted(ids)}
    elif network is not None:
        if network not in model.networks:
            raise AssemblyError(f"select: no network {network!r} (the model has "
                                f"{', '.join(sorted(model.networks)) or 'none'})",
                                code="model_id_unknown", where={"field": "network"},
                                value=network)
        ids = set(model.networks[network].parts)
        how = {"network": network}
    else:
        _port(model, from_port)
        stop_ports = {q for q in up_to if q in model.ports}
        stop_parts = {q for q in up_to if q in model.parts}
        unknown = sorted(set(up_to) - stop_ports - stop_parts)
        if unknown:
            raise AssemblyError(f"select: up_to names no port or part "
                                f"{', '.join(map(repr, unknown))}", code="model_id_unknown",
                                where={"field": "up_to"}, value=unknown)
        links: dict[str, list[str]] = {}
        for a, b in _links(model, tol):
            links.setdefault(a, []).append(b)
            links.setdefault(b, []).append(a)
        start = owner[from_port]
        ids, todo = {start.id}, [start]
        while todo:
            part = todo.pop()
            if part.id in stop_parts and part is not start:
                continue
            for q in part.ports:
                if q == from_port or q in stop_ports:
                    continue
                for r in links.get(q, ()):
                    nxt = owner[r]
                    if r in stop_ports or nxt.id in ids or isinstance(nxt, Terminal):
                        continue
                    ids.add(nxt.id)
                    todo.append(nxt)
        how = {"from_port": from_port, "up_to": sorted(up_to)}
    built = [model.parts[i] for i in ids if not isinstance(model.parts[i], Terminal)]
    pts = [model.ports[q].position for p in built for q in p.ports
           if model.ports[q].position is not None]
    for t in model.parts.values():
        x = model.ports[t.ports[0]].position if isinstance(t, Terminal) else None
        if x is not None and pts and min(np.linalg.norm(y - x) for y in pts) <= tol:
            ids.add(t.id)
    return Selection(ids, how)


# --- cut and join ------------------------------------------------------------------

def cut(model: NetworkModel, connection) -> Cut:
    a, b = (connection.a, connection.b) if isinstance(connection, Connection) else connection
    _port(model, a), _port(model, b)
    if b not in _partners(model, a, tolerance(model)):
        raise AssemblyError(f"cut: ports {a!r} and {b!r} aren't connected",
                            code="model_ports_not_met", where={"field": "connection"},
                            value=[a, b])
    _begin(model)
    c = _cut(model, a, b)
    _log(model, "cut", {"a": a, "b": b})
    return c


def _cut(model: NetworkModel, a: str, b: str) -> Cut:
    model.connections = [c for c in model.connections if {c.a, c.b} != {a, b}]
    c = Cut(a, b)
    model.cuts.append(c)
    return c


def cut_at(model: NetworkModel, port: str, names) -> list[Cut]:
    _port(model, port)
    others = _partners(model, port, tolerance(model))
    if not others:
        raise AssemblyError(f"cut_at: port {port!r} meets no other port; it is already an open end",
                            code="model_port_already_open", where={"field": "port"}, value=port)
    if names is not None:
        if len(others) != 1:
            raise AssemblyError(f"cut_at: port {port!r} meets {len(others)} ports "
                                f"({', '.join(others)}); names= needs exactly one",
                                code="cut_names_ambiguous", where={"field": "names"}, value=others)
    _begin(model)
    if names is not None:
        model.ports[port].tag, model.ports[others[0]].tag = names
    cuts = [_cut(model, port, q) for q in others]
    _log(model, "cut_at", {"port": port, "names": None if names is None else list(names)})
    return cuts


def _outward(model: NetworkModel, pid: str):
    """Unit vector out of the part at port *pid*, or None if unknown."""
    part = _owners(model)[pid]
    pos = [model.ports[q].position for q in part.ports]
    i = part.ports.index(pid)
    x = pos[i]
    if x is None:
        return None
    if isinstance(part, Terminal):
        return None
    if isinstance(part, Junction):
        ref = part.centre
    elif isinstance(part, Bend) and part.corner is not None:
        ref = part.corner
    elif isinstance(part, Polyline) or len(pos) == 2:
        ref = pos[1] if i == 0 else pos[-2] if i == len(pos) - 1 else None
    else:
        ref = None
    if ref is None:
        return None
    d = x - np.asarray(ref, dtype=float)
    n = float(np.linalg.norm(d))
    return d / n if n > 0 else None


def _same_section(s, t) -> bool:
    if s is None or t is None:
        return True
    if s.shape != t.shape:
        return False
    return all(u is None or v is None or math.isclose(u, v, rel_tol=SECTION_RTOL)
               for u, v in ((s.nominal, t.nominal), (s.diameter, t.diameter),
                            (s.width, t.width), (s.height, t.height)))


def join(model: NetworkModel, a: str, b: str, tol) -> Connection:
    pa, pb = _port(model, a), _port(model, b)
    tol = tolerance(model) if tol is None else float(tol)
    build_tol = tolerance(model)
    for p, other in ((a, b), (b, a)):
        met = [q for q in _partners(model, p, build_tol) if q != other]
        if met:
            raise AssemblyError(f"join: port {p!r} isn't open; it is connected to "
                                f"{', '.join(met)}", code="join_port_not_open",
                                where={"field": "port"}, value=p)
    if pa.position is None or pb.position is None:
        raise AssemblyError(f"join: ports {a!r} and {b!r} need positions", code="join_gap",
                            where={"field": "port"}, value=[a, b])
    gap = float(np.linalg.norm(pa.position - pb.position))
    if gap > tol:
        raise AssemblyError(f"join: ports {a!r} and {b!r} are {gap:.6g} m apart, more than the "
                            f"tolerance {tol:.6g} m", code="join_gap", where={"field": "port"},
                            value=gap, limit={"max": tol})
    da, db = _outward(model, a), _outward(model, b)
    if da is not None and db is not None:
        angle = math.degrees(math.acos(max(-1.0, min(1.0, float(-da @ db)))))
        if angle > JOIN_ANGLE_TOL:
            raise AssemblyError(f"join: ports {a!r} and {b!r} don't face each other: their "
                                f"directions {np.round(da, 4)} and {np.round(db, 4)} are "
                                f"{angle:.3g}° from opposed (tolerance {JOIN_ANGLE_TOL:g}°)",
                                code="join_direction", where={"field": "port"}, value=angle,
                                limit={"max": JOIN_ANGLE_TOL})
    if not _same_section(pa.section, pb.section):
        raise AssemblyError(f"join: ports {a!r} and {b!r} have different sections: {pa.section} "
                            f"and {pb.section}", code="join_section", where={"field": "port"},
                            value=[str(pa.section), str(pb.section)])
    _begin(model)
    model.cuts = [c for c in model.cuts if {c.a, c.b} != {a, b}]
    model.connections = [c for c in model.connections if {c.a, c.b} != {a, b}]
    conn = Connection(a, b, origin="declared", distance=gap)
    model.connections.append(conn)
    _log(model, "join", {"a": a, "b": b, "tol": None if tol == build_tol else tol})
    return conn


# --- merge -------------------------------------------------------------------------

def _prefixed(m: NetworkModel, prefix: str) -> NetworkModel:
    """A copy of *m* with every port and part id prefixed."""
    m = _state(m)
    m.ports = {prefix + q: p for q, p in m.ports.items()}
    for q, p in m.ports.items():
        p.id = q
    m.parts = {prefix + i: p for i, p in m.parts.items()}
    for i, p in m.parts.items():
        p.id, p.ports = i, [prefix + q for q in p.ports]
    for c in m.connections + m.cuts:
        c.a, c.b = prefix + c.a, prefix + c.b
    for n in m.networks.values():
        n.parts = {prefix + i for i in n.parts}
    return m


def merge(a: NetworkModel, b: NetworkModel, prefix, infer, tol) -> NetworkModel:
    b2 = _prefixed(b, prefix) if prefix else _state(b)
    clash = sorted(set(a.ports) & set(b2.ports)) + sorted(set(a.parts) & set(b2.parts))
    if clash:
        raise AssemblyError(f"merge: {len(clash)} ids are in both models ({', '.join(clash[:8])}"
                            f"{', …' if len(clash) > 8 else ''}); pass prefix= to rename the "
                            f"second's", code="merge_id_clash", where={"field": "ids"},
                            value=clash[:20])
    out = _state(a)
    out.ports.update(b2.ports)
    out.parts.update(b2.parts)
    out.connections += b2.connections
    out.cuts += b2.cuts
    for name, n in b2.networks.items():
        if name in out.networks:
            out.networks[name].parts |= n.parts
        else:
            out.networks[name] = Network(n.name, set(n.parts), n.kind, n.insulation_thickness,
                                         dict(n.attributes))
    out.report = {"merge": {"from": [len(a.parts), len(b.parts)]}}
    if infer:
        t = tolerance(out) if tol is None else float(tol)
        inner_a = {q for pair in _links(a, tolerance(a)) for q in pair}
        inner_b = {q for pair in _links(b2, tolerance(b2)) for q in pair}
        for p, q in _meets(out, t):
            if (p in a.ports) != (q in a.ports) and p not in inner_a | inner_b \
                    and q not in inner_a | inner_b:
                out.connections.append(Connection(
                    p, q, origin="inferred",
                    distance=float(np.linalg.norm(out.ports[p].position - out.ports[q].position))))
    base = a.__dict__.get("_undo_base") or (_state(a), len(a.log))
    out._undo_base = base
    out.log = copy.deepcopy(a.log)
    out.log.append({"op": "merge", "args": {"prefix": prefix, "infer": infer, "tol": tol,
                                            "other": copy.deepcopy(b.log)},
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "version": __version__})
    return out


# --- replay and undo ---------------------------------------------------------------

def _reimport(log: list) -> NetworkModel:
    """The model a log describes, re-read through its importer."""
    first = log[0] if log else {}
    importer = first.get("args", {}).get("importer") if first.get("op") == "import" else None
    if importer not in IMPORTERS:
        raise AssemblyError("replay: a merged model has no import entry that a registered "
                            f"importer can re-read (importer {importer!r}); merge it again "
                            "by hand", code="model_replay_needs_source",
                            where={"field": "log"}, value=importer)
    m = IMPORTERS[importer](first["args"]["source"], first["args"].get("options", {}))
    for entry in log[1:]:
        _apply(m, entry)
    return m


def _apply(model: NetworkModel, entry: dict) -> None:
    op, args = entry["op"], entry["args"]
    if op == "import":
        return
    if op == "cut":
        cut(model, (args["a"], args["b"]))
    elif op == "cut_at":
        cut_at(model, args["port"], None if args["names"] is None else tuple(args["names"]))
    elif op == "join":
        join(model, args["a"], args["b"], args.get("tol"))
    elif op == "merge":
        merged = merge(model, _reimport(args["other"]), args["prefix"], args["infer"],
                       args["tol"])
        base = model.__dict__.get("_undo_base") or merged._undo_base
        _assign(model, merged)
        model._undo_base = base
    else:
        raise AssemblyError(f"replay: unknown operation {op!r} in the log",
                            code="model_replay_needs_source", where={"field": "log"}, value=op)


def replay(model: NetworkModel, source: NetworkModel) -> NetworkModel:
    for entry in model.log:
        _apply(source, entry)
    return source


def undo(model: NetworkModel) -> None:
    base = model.__dict__.get("_undo_base")
    if base is None or len(model.log) <= base[1]:
        raise AssemblyError("undo: no logged operation to undo", code="model_undo_empty",
                            where={"field": "log"})
    state, n0 = base
    fresh = _state(state)
    for entry in model.log[n0:-1]:
        _apply(fresh, entry)
    _assign(model, fresh)
    model._undo_base = base


OPERATIONS.update(select=select, cut=cut, cut_at=cut_at, join=join, merge=merge,
                  replay=replay, undo=undo)
