"""
PCF (Piping Component File) reader.

Parses an Isogen PCF file and returns a NetworkSpec — a declarative
description of the pipe network that can be converted to an assembly via
``NetworkSpec.to_assembly()``.

Follows the *Piping Component File Reference Guide* (Alias/Isogen, 2016,
updated 2018); see ``docs/integrations/pcf.md`` for the facts used and the
deviations accepted.

File layout
-----------
* **Header** keywords in column 1 before the first ``PIPELINE-REFERENCE``
  (``ISOGEN-FILES``, ``UNITS-BORE``, ``UNITS-CO-ORDS``, …) →
  ``NetworkSpec.header``.
* ``PIPELINE-REFERENCE name`` with column-5 attributes →
  ``NetworkSpec.pipelines[name]``; components after it belong to it.
* Component identifiers in column 1, attributes in column 5.
* ``END-CONNECTION-PIPELINE``, ``END-CONNECTION-EQUIPMENT`` and
  ``EQUIPMENT-REFERENCE`` blocks are not components (kept in
  ``NetworkSpec.connections``).
* ``MATERIALS`` is the last section and is not read.  Non-spec dialect
  accepted: ``ITEM-CODE n`` in column 1 there (pcf2iso, Revit exports).

Units
-----
Coordinates and bore have independent units.  ``UNITS-CO-ORDS``: ``MM``,
``MM-HUNDREDTHS`` (0.01 mm), ``INCH``.  ``UNITS-BORE``: ``MM``, ``INCH``,
``INCH-SIXTEENTH``.  Bore is the **nominal size** in metres (4" → 0.1016),
not an inside diameter: map it to a cross-section with
``to_assembly(spec=lambda bore: ...)``.

Components
----------
PIPE                          → "pipe"
ELBOW, BEND                   → "elbow"; ``CENTRE-POINT`` is the corner
                                (intersection of the tangent legs)
REDUCER-CONCENTRIC/-ECCENTRIC → "reducer"
FLANGE, VALVE, CAP, INSTRUMENT→ "fitting", meshed as straight runs
GAP                           → "joint" (by spec)
WELD, COUPLING, GASKET        → "joint" when no longer than ``joint_max``
                                (zero-length welds by spec; ``COCP`` gap
                                couplings of the weld root gap, 1/16", as a
                                documented exporter dialect), else "fitting"

Joints are absorbed into the adjacent straight runs by ``to_assembly``,
never meshed (they would be sliver cells).  Other types (TEE, OLET, …) are
collected in ``NetworkSpec.skipped`` with one warning each.
"""

from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

INCH = 0.0254

#: ``UNITS-CO-ORDS`` → metres per unit
COORD_UNITS = {"MM": 1e-3, "MM-HUNDREDTHS": 1e-5, "INCH": INCH}
#: ``UNITS-BORE`` → metres per unit (nominal size)
BORE_UNITS = {"MM": 1e-3, "INCH": INCH, "INCH-SIXTEENTH": INCH / 16}

#: Joints (couplings, gaskets, welds) up to this length are absorbed: just
#: above the 1/16" weld root gap that exporters model (pcf2iso's choice;
#: the guide gives no value).
JOINT_MAX = 1.6e-3
#: Connectivity tolerance floor, just above the weld gap (pcf2iso: 0.11").
TOL_FLOOR = 0.11 * INCH
#: Connectivity tolerance relative to the model's bounding-box diagonal.
TOL_RELATIVE = 1e-4

_NON_COMPONENTS = {"PIPELINE-REFERENCE", "END-CONNECTION-PIPELINE",
                   "END-CONNECTION-EQUIPMENT", "EQUIPMENT-REFERENCE", "MATERIALS"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentSpec:
    """One piping component parsed from a PCF file.

    Attributes
    ----------
    kind : str
        Normalised type: "pipe", "elbow", "reducer", "fitting", "joint".
    start, end : ndarray, shape (3,)
        End-point coordinates in metres.
    centre : ndarray or None
        ``CENTRE-POINT`` in metres; for elbows the corner (tangent-leg
        intersection).
    bore : float
        Nominal size at the start, metres.
    end_bore : float or None
        Nominal size at the outlet of a reducer, metres.
    ignored : bool
        True for fittings meshed as plain straight runs.
    raw : dict
        Raw attribute key→value pairs from the PCF record.
    record_type : str
        PCF component keyword (e.g. ``"REDUCER-ECCENTRIC"``).
    pipeline : str
        The ``PIPELINE-REFERENCE`` it belongs to ("" before any).
    """

    kind:     str
    start:    np.ndarray
    end:      np.ndarray
    centre:   np.ndarray | None = None
    bore:     float = 0.0
    end_bore: float | None = None
    ignored:  bool = False
    raw:      dict = field(default_factory=dict)
    record_type: str = ""
    pipeline: str = ""


@dataclass
class NetworkSpec:
    """Declarative description of a pipe network parsed from an external file.

    Attributes
    ----------
    components : list[ComponentSpec]
        Components in file order (``to_assembly`` orders them by
        connectivity).
    skipped : list[tuple[str, dict]]
        Component records that could not be mapped to a supported type.
    source : str
        Path or description of the source file.
    header : dict
        PCF header keywords (``UNITS-CO-ORDS`` → ``"MM"``, …).
    pipelines : dict[str, dict]
        ``PIPELINE-REFERENCE`` name → its attributes.
    connections : list[tuple[str, dict]]
        ``END-CONNECTION-*`` and ``EQUIPMENT-REFERENCE`` blocks.
    coord_scale : float
        Metres per coordinate unit used.
    report : dict
        Filled by ``to_assembly``: the tolerance used, the joints absorbed
        or dropped, and the largest lateral offset absorbed.
    """

    components: list[ComponentSpec] = field(default_factory=list)
    skipped:    list[tuple[str, dict]] = field(default_factory=list)
    source:     str = ""
    header:     dict = field(default_factory=dict)
    pipelines:  dict = field(default_factory=dict)
    connections: list = field(default_factory=list)
    coord_scale: float = 1e-3
    report:     dict = field(default_factory=dict)

    def to_assembly(self, spec, *, axial_cell: float | None = None,
                    kinks: str = "error", tol: float | None = None,
                    lc: float | None = None):
        """Build an ``hexmesh.assembly.Assembly`` from the components.

        Each component is placed from the previous outlet and its PCF end
        point is then checked against the placed outlet; a gap or a change of
        direction larger than *tol* raises ``AssemblyError`` naming the
        component (nothing is snapped).

        Mapping: ``pipe`` and ``fitting`` (flange, valve, …) → ``Straight``;
        ``elbow`` → ``Bend``, from its corner point (radius and angle are
        cross-checked against ``BEND-RADIUS`` and ``ANGLE`` when given);
        ``reducer`` (concentric) → ``Reducer``.

        Joints (couplings, gaskets, welds up to ``joint_max``; ``GAP``) are
        absorbed: the preceding straight run is extended over them, or else
        the following one starts at them.  A joint at an open end next to a
        non-straight fitting is dropped.  A straight run goes from the
        placed outlet to its PCF end point, so gaps never accumulate;
        lateral offsets within *tol* are accepted (a documented deviation:
        exporters offset components by up to the weld gap).  ``self.report``
        records what was absorbed.

        Parameters
        ----------
        spec : PipeSpec or callable
            Cross-section of the first component, or ``bore -> PipeSpec``
            (*bore* is the nominal size in metres).  With a single spec, a
            reducer's outlet keeps the shells and scales the core radius by
            ``end_bore / bore``.
        axial_cell : float, optional
            Target axial cell length; default the outer radius.
        kinks : {"error", "spline"}
            Consecutive pipes that change direction without a fitting (e.g.
            bathymetry routes) raise an error, or are joined into one
            ``SplinePipe`` through their end points.
        tol : float, optional
            Position tolerance in metres; directions to ``tol`` per metre.
            Default: ``TOL_RELATIVE`` × the model diagonal, at least
            ``TOL_FLOOR`` (0.11").
        lc : float, optional
            Passed to ``Assembly``.

        Returns
        -------
        Assembly
        """
        return _build_assembly(self, spec, axial_cell, kinks, tol, lc)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def read_pcf(
    path:          str | Path,
    unit_scale:    float | None = None,
    ignore_types:  set[str] | None = None,
    joint_max:     float = JOINT_MAX,
) -> NetworkSpec:
    """Parse a PCF file and return a NetworkSpec.

    Parameters
    ----------
    path : str or Path
        Path to the ``.pcf`` file.
    unit_scale : float, optional
        Metres per coordinate unit.  Default: from ``UNITS-CO-ORDS``.  If
        given it wins, and a mismatch with the header warns.  A file with
        no ``UNITS-CO-ORDS`` is read as millimetres, with one warning.
    ignore_types : set[str], optional
        Component-type keywords to silently ignore.  Defaults to
        non-geometric types (supports, bolts, direction breaks).
    joint_max : float
        Couplings, gaskets and welds no longer than this (metres) are joints.

    Returns
    -------
    NetworkSpec
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PCF file not found: {path}")

    if ignore_types is None:
        ignore_types = {"SUPPORT", "BOLT", "INSTRUMENT-COMPONENT", "PIPE-DIRECTION-BREAK"}

    spec = NetworkSpec(source=str(path))
    records = list(_iter_records(path, spec))
    spec.coord_scale = scale = _coord_scale(spec.header, unit_scale)
    bore_scale = _bore_scale(spec.header)

    for record_type, attrs, pipeline in records:
        rtype = record_type.upper()
        if rtype in ignore_types:
            continue
        kind = _classify(rtype)
        if kind is None:
            spec.skipped.append((record_type, attrs))
            warnings.warn(f"Unsupported PCF component type '{record_type}' — skipped.",
                          stacklevel=2)
            continue

        endpoints = attrs.get("END-POINT", [])
        if len(endpoints) < 2:
            warnings.warn(f"Component {record_type} has < 2 END-POINTs — skipped.",
                          stacklevel=2)
            continue

        start = np.array(endpoints[0][:3], dtype=float) * scale
        end   = np.array(endpoints[1][:3], dtype=float) * scale
        bore  = float(endpoints[0][3]) * bore_scale if len(endpoints[0]) > 3 else 0.0
        centre = None
        if "CENTRE-POINT" in attrs:
            centre = np.array(attrs["CENTRE-POINT"][:3], dtype=float) * scale
        end_bore = None
        if kind == "reducer" and len(endpoints[1]) > 3:
            end_bore = float(endpoints[1][3]) * bore_scale
        if kind == "joint?":
            kind = "joint" if np.linalg.norm(end - start) <= joint_max else "fitting"

        spec.components.append(ComponentSpec(
            kind=kind, start=start, end=end, centre=centre, bore=bore,
            end_bore=end_bore, ignored=kind == "fitting", raw=attrs,
            record_type=rtype, pipeline=pipeline,
        ))

    return spec


def _coord_scale(header: dict, unit_scale: float | None) -> float:
    unit = header.get("UNITS-CO-ORDS")
    if unit is not None and unit.upper() not in COORD_UNITS:
        raise ValueError(f"UNITS-CO-ORDS {unit!r} not recognised; known: "
                         f"{', '.join(COORD_UNITS)}")
    from_header = COORD_UNITS[unit.upper()] if unit else None
    if unit_scale is not None:
        if from_header is not None and not math.isclose(unit_scale, from_header):
            warnings.warn(f"unit_scale={unit_scale} overrides UNITS-CO-ORDS {unit} "
                          f"({from_header} m)", stacklevel=3)
        return unit_scale
    if from_header is None:
        warnings.warn("PCF has no UNITS-CO-ORDS header; reading coordinates and "
                      "bore as millimetres", stacklevel=3)
        return 1e-3
    return from_header


def _bore_scale(header: dict) -> float:
    unit = header.get("UNITS-BORE")
    if unit is None:
        return 1e-3            # the missing header has already warned, or coords are mm
    if unit.upper() not in BORE_UNITS:
        raise ValueError(f"UNITS-BORE {unit!r} not recognised; known: "
                         f"{', '.join(BORE_UNITS)}")
    return BORE_UNITS[unit.upper()]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_COMPONENT_MAP = {
    "PIPE":                  "pipe",
    "ELBOW":                 "elbow",
    "BEND":                  "elbow",
    "REDUCER-CONCENTRIC":    "reducer",
    "REDUCER-ECCENTRIC":     "reducer",
    "FLANGE":                "fitting",
    "FLANGE-BLIND":          "fitting",
    "VALVE":                 "fitting",
    "CAP":                   "fitting",
    "INSTRUMENT":            "fitting",
    "INSTRUMENT-COMPONENT":  "fitting",
    "GAP":                   "joint",
    "WELD":                  "joint?",     # joint up to joint_max, else fitting
    "COUPLING":              "joint?",
    "GASKET":                "joint?",
    "TEE":                   None,    # not yet supported
    "CROSS":                 None,
    "OLET":                  None,
}


def _classify(record_type: str) -> str | None:
    return _COMPONENT_MAP.get(record_type.upper())


# A signed decimal number; the keywords themselves contain hyphens
# ("END-POINT"), so a bare character class would match them.
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _iter_records(path: Path, net: NetworkSpec) -> Iterator[tuple[str, dict, str]]:
    """Yield ``(record_type, attrs, pipeline)`` for each component record.

    Header keywords go to ``net.header``, ``PIPELINE-REFERENCE`` blocks to
    ``net.pipelines``, connection and equipment blocks to
    ``net.connections``; everything from ``MATERIALS`` on is skipped.
    """
    block: tuple[str, str] | None = None   # (kind, name): "component" | "pipeline" | "other"
    attrs: dict = {}
    endpoints: list[list[float]] = []
    pipeline = ""
    in_header = True

    def flush():
        if block is None:
            return
        kind, name = block
        if kind == "component":
            a = dict(attrs)
            if endpoints:
                a["END-POINT"] = list(endpoints)
            yield name, a, pipeline
        elif kind == "pipeline":
            net.pipelines[name] = dict(attrs)
        elif kind == "other":
            net.connections.append((name, dict(attrs)))

    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.rstrip().expandtabs()
            if not line or line.startswith(";"):
                continue
            if not line[0].isspace() and not line[0].isdigit():
                words = line.split(None, 1)
                key = words[0].upper()
                value = words[1].strip() if len(words) > 1 else ""
                if key == "MATERIALS":
                    yield from flush()
                    return
                if key == "PIPELINE-REFERENCE":
                    yield from flush()
                    in_header = False
                    pipeline = value
                    block, attrs, endpoints = ("pipeline", value), {}, []
                    continue
                if in_header and key not in _COMPONENT_MAP:
                    net.header[key] = value
                    continue
                yield from flush()
                in_header = False
                kind = "other" if key in _NON_COMPONENTS else "component"
                block, attrs, endpoints = (kind, words[0]), {}, []
            elif "END-POINT" in line.split(None, 1)[0]:
                endpoints.append([float(x) for x in _NUMBER.findall(line)])
            elif line.split(None, 1)[0] == "CENTRE-POINT":
                attrs["CENTRE-POINT"] = [float(x) for x in _NUMBER.findall(line)]
            else:
                parts = line.split(None, 1)
                attrs[parts[0].strip()] = parts[1].strip() if len(parts) == 2 else ""

    yield from flush()


def _sort_by_connectivity(comps: list[ComponentSpec], tol: float = 1e-4) -> list[ComponentSpec]:
    """Topological sort: order components by endpoint connectivity."""
    if not comps:
        return []
    # Simple greedy chain: start from the first component, follow end-points
    result = [comps[0]]
    remaining = list(comps[1:])

    while remaining:
        tail = result[-1].end
        found = False
        for i, c in enumerate(remaining):
            if np.linalg.norm(c.start - tail) < tol:
                result.append(remaining.pop(i))
                found = True
                break
            elif np.linalg.norm(c.end - tail) < tol:
                # Reversed orientation — flip
                c.start, c.end = c.end.copy(), c.start.copy()
                result.append(remaining.pop(i))
                found = True
                break
        if not found:
            # Disconnected component — append as-is
            result.append(remaining.pop(0))

    return result


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _perpendicular(v: np.ndarray) -> np.ndarray:
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(v, candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    return _unit(np.cross(v, candidate))


def _start_direction(comp: ComponentSpec) -> np.ndarray:
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


def _elbow_params(comp: ComponentSpec) -> ElbowGeometry:
    """Radius, angle and plane of an elbow whose ``CENTRE-POINT`` C is the
    intersection of its tangent legs: with a = start − C and b = end − C,
    θ = 180° − ∠(a, b), R = |a| / tan(θ/2), incoming direction −â."""
    if comp.centre is None:
        raise ValueError("elbow has no CENTRE-POINT")
    a, b = comp.start - comp.centre, comp.end - comp.centre
    la, lb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if la < 1e-12 or lb < 1e-12:
        raise ValueError("elbow CENTRE-POINT coincides with an end point")
    corner = math.degrees(math.acos(float(np.clip(np.dot(a, b) / (la * lb), -1, 1))))
    theta = 180.0 - corner
    if not 1e-6 < theta < 180.0 - 1e-6:
        raise ValueError(f"elbow legs give a bend angle of {theta:.4g}°")
    incoming = -a / la
    bu = b / lb
    turn = _unit(bu - np.dot(bu, incoming) * incoming)
    return ElbowGeometry(la / math.tan(math.radians(theta) / 2), theta, incoming, turn)


def _bend_radius_attr(value: str, bore: float, coord_scale: float) -> float | None:
    """``BEND-RADIUS``: ``nD`` (multiple of nominal size) or an absolute
    radius in coordinate units; metres."""
    m = re.fullmatch(r"\s*([0-9.]+)\s*D\s*", value, re.I)
    if m:
        return float(m.group(1)) * bore if bore else None
    m = _NUMBER.match(value.strip())
    return float(m.group()) * coord_scale if m else None


# ---------------------------------------------------------------------------
# Assembly builder
# ---------------------------------------------------------------------------

def _model_tolerance(comps: list[ComponentSpec]) -> float:
    pts = np.array([q for c in comps for q in (c.start, c.end)])
    diagonal = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 0.0
    return max(TOL_RELATIVE * diagonal, TOL_FLOOR)


def _straight_meshed(c: ComponentSpec) -> bool:
    return c.kind in ("pipe", "fitting")


def _absorb_joints(comps: list[ComponentSpec], report: dict) -> list[ComponentSpec]:
    """Remove joints, extending an adjacent straight run over each one.

    The preceding straight-meshed component is extended to the joint's end;
    otherwise the following one starts at the joint's start.  A joint at an
    open end with no straight neighbour is dropped.  Between two
    non-straight fittings it raises: there is no run to absorb it.
    """
    out: list[ComponentSpec] = []
    pending: list[ComponentSpec] = []          # joints waiting for a following run
    for c in comps:
        if c.kind == "joint":
            if out and _straight_meshed(out[-1]) and not pending:
                out[-1].end = c.end.copy()
                report["joints"].append((c.record_type, "absorbed"))
            else:
                pending.append(c)
            continue
        if pending:
            if _straight_meshed(c):
                c.start = pending[0].start.copy()
                report["joints"].extend((j.record_type, "absorbed") for j in pending)
            elif not out:
                report["joints"].extend((j.record_type, "dropped") for j in pending)
            else:
                from ...assembly import AssemblyError
                raise AssemblyError(
                    f"{pending[0].record_type} at {np.round(pending[0].start, 4)} sits "
                    f"between two non-straight fittings ({out[-1].record_type}, "
                    f"{c.record_type}); there is no straight run to absorb it")
            pending = []
        out.append(c)
    report["joints"].extend((j.record_type, "dropped") for j in pending)
    return out


def _build_assembly(net: NetworkSpec, spec, axial_cell, kinks, tol, lc):
    from ...assembly import Assembly, AssemblyError, Bend, Reducer, SplinePipe, Straight
    from ...assembly.fittings import _with_radii
    from ...assembly.interface import outer_radius

    if kinks not in ("error", "spline"):
        raise ValueError(f"kinks must be 'error' or 'spline', got {kinks!r}")
    if not net.components:
        raise ValueError("NetworkSpec has no components to build.")
    if tol is None:
        tol = _model_tolerance(net.components)
    report = net.report = {"tolerance": tol, "joints": [], "max_offset": 0.0}
    comps = _sort_by_connectivity(
        [ComponentSpec(**{**c.__dict__, "start": c.start.copy(), "end": c.end.copy()})
         for c in net.components], tol)
    comps = _absorb_joints(comps, report)
    if not comps:
        raise ValueError("NetworkSpec has only joints.")
    spec_for = spec if callable(spec) else None
    first = comps[0]
    current = spec_for(first.bore) if spec_for else spec
    # Layer counts come from the assembly's axial cell (n_layers=None,
    # decision 0024): ceil(centreline length / cell).
    d0 = _start_direction(first)
    asm = Assembly(current, position=first.start, direction=d0,
                   up=_perpendicular(d0), lc=lc,
                   axial_cell=axial_cell or outer_radius(current))

    def label(k):
        c = comps[k]
        return f"component {k} ({c.record_type or c.kind} at {np.round(c.start, 4)})"

    def check(k, frame, end, direction=None):
        if np.linalg.norm(frame.position - end) > tol:
            raise AssemblyError(
                f"{label(k)}: placed outlet {np.round(frame.position, 6)} misses its "
                f"end point {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m"
            )
        if direction is not None and np.linalg.norm(frame.normal - direction) > tol:
            raise AssemblyError(f"{label(k)}: outlet direction does not match")

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
        frame = asm.interfaces[-1].frame
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
                pts = [frame.position] + [comps[i].end for i in range(k, j + 1)]
                nxt = comps[j + 1] if j + 1 < len(comps) else None
                end_t = None if nxt is None else tuple(_start_direction(nxt))
                out = asm.add(SplinePipe(tuple(map(tuple, pts)), end_tangent=end_t))
                check(j, out.frame, comps[j].end)
                k = j + 1
                continue
            # from the placed outlet to the PCF end point: gaps never accumulate
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            out = asm.add(Straight(ax))
            check(k, out.frame, c.end)
        elif c.kind == "elbow":
            try:
                g = _elbow_params(c)
            except ValueError as e:
                raise AssemblyError(f"{label(k)}: {e}") from None
            leg = float(np.linalg.norm(c.centre - c.start))
            if np.linalg.norm(np.cross(g.incoming, frame.normal)) * leg > tol \
                    or np.dot(g.incoming, frame.normal) < 0:
                raise AssemblyError(
                    f"{label(k)}: elbow's incoming leg (start → CENTRE-POINT) is not "
                    f"along the incoming pipe")
            _cross_check_elbow(c, g, net.coord_scale, label(k))
            roll = math.degrees(math.atan2(np.dot(g.turn, frame.right),
                                           np.dot(g.turn, frame.up)))
            out = asm.add(Bend(g.radius, g.angle, roll=roll))
            check(k, out.frame, c.end)
        elif c.kind == "reducer":
            if c.record_type == "REDUCER-ECCENTRIC":
                raise AssemblyError(f"{label(k)}: eccentric reducers are not supported")
            if not c.end_bore or not c.bore:
                raise AssemblyError(f"{label(k)}: reducer needs both bores")
            if spec_for:
                outlet = spec_for(c.end_bore)
            else:
                cur = asm.interfaces[-1].spec
                radii = [cur.core_shape.radius * c.end_bore / c.bore] + [sh.dR for sh in cur.shells]
                outlet = _with_radii(cur, radii)
            if not straight_on(k, frame):
                raise AssemblyError(f"{label(k)}: reducer axis is not the incoming direction")
            ax, lat = along(frame, c.end)
            report["max_offset"] = max(report["max_offset"], lat)
            out = asm.add(Reducer(outlet, ax))
            check(k, out.frame, c.end)
        else:
            raise AssemblyError(f"{label(k)}: unsupported kind {c.kind!r}")
        k += 1
    return asm


# Cross-check tolerances: ANGLE is given in hundredths of a degree; radii
# from nD × nominal size are exact for standard elbows (1.5D: 4" → 6").
ANGLE_TOL = 0.05       # degrees
RADIUS_TOL = 0.01      # relative


def _cross_check_elbow(c: ComponentSpec, g: ElbowGeometry, coord_scale: float,
                       label: str) -> None:
    from ...assembly import AssemblyError
    if "ANGLE" in c.raw:
        m = _NUMBER.match(c.raw["ANGLE"].strip())
        if m:
            angle = float(m.group()) / 100.0
            if abs(angle - g.angle) > ANGLE_TOL:
                raise AssemblyError(
                    f"{label}: ANGLE {angle:g}° disagrees with the {g.angle:.4g}° "
                    f"from its END-POINTs and CENTRE-POINT")
    if "BEND-RADIUS" in c.raw:
        r = _bend_radius_attr(c.raw["BEND-RADIUS"], c.bore, coord_scale)
        if r is not None and abs(r - g.radius) > RADIUS_TOL * g.radius:
            raise AssemblyError(
                f"{label}: BEND-RADIUS {c.raw['BEND-RADIUS']} ({r:.6g} m) disagrees "
                f"with the {g.radius:.6g} m from its END-POINTs and CENTRE-POINT")
