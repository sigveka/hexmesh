"""
PCF (Piping Component File) reader.

Parses an Isogen PCF file and returns a NetworkSpec — a declarative
description of the pipe network that can be converted to an assembly via
``NetworkSpec.to_assembly()``.

PCF format summary
------------------
ASCII text, one record per component.  Each record starts with a
component-type keyword (PIPE, ELBOW, REDUCER-CONCENTRIC, …) followed by
attribute lines.  Coordinates appear on END-POINT and CENTRE-POINT lines.

Supported component types
--------------------------
PIPE                     → ComponentSpec(kind="pipe")
ELBOW                    → ComponentSpec(kind="elbow")
REDUCER-CONCENTRIC       → ComponentSpec(kind="reducer")
FLANGE, VALVE, INSTRUMENT→ ComponentSpec(kind="fitting", ignored=True):
                            no fitting geometry of their own; meshed as
                            straight runs by ``to_assembly``.

Unsupported types (TEE, CROSS, …) are collected in ``NetworkSpec.skipped``
with a warning rather than raising an exception.

References
----------
Isogen PCF format specification:
    AVEVA Plant (formerly CADMATIC / Intergraph I-Configure) documentation.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ComponentSpec:
    """One piping component parsed from a PCF file.

    Attributes
    ----------
    kind : str
        Normalised type: "pipe", "elbow", "reducer", "fitting".
    start : ndarray, shape (3,)
        Start end-point coordinates (mm in PCF, converted to metres).
    end : ndarray, shape (3,)
        End end-point coordinates.
    centre : ndarray or None
        Centre point (present for elbows).
    bore : float
        Nominal bore (metres).
    end_bore : float or None
        Outlet bore for reducers (metres).
    ignored : bool
        True for component types that are parsed but not meshed.
    raw : dict
        All raw attribute key→value pairs from the PCF record.
    record_type : str
        PCF component keyword (e.g. ``"REDUCER-ECCENTRIC"``).
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


@dataclass
class NetworkSpec:
    """Declarative description of a pipe network parsed from an external file.

    Attributes
    ----------
    components : list[ComponentSpec]
        Ordered list of components (topologically sorted by connectivity).
    skipped : list[tuple[str, dict]]
        Component records that could not be mapped to a supported type.
    source : str
        Path or description of the source file.
    """

    components: list[ComponentSpec] = field(default_factory=list)
    skipped:    list[tuple[str, dict]] = field(default_factory=list)
    source:     str = ""

    def to_assembly(self, spec, *, axial_cell: float | None = None,
                    kinks: str = "error", tol: float = 1e-4, lc: float | None = None):
        """Build an ``hexmesh.assembly.Assembly`` from the components.

        Each component is placed from the previous outlet and its PCF end
        point is then checked against the placed outlet; a gap or a change of
        direction larger than *tol* raises ``AssemblyError`` naming the
        component (nothing is snapped).  *tol* (metres) absorbs PCF
        coordinate rounding.

        Mapping: ``pipe`` and ``fitting`` (flange, valve, …) → ``Straight``;
        ``elbow`` → ``Bend`` in the plane of its centre point;
        ``reducer`` (concentric) → ``Reducer``.  Ignored fittings are meshed
        as straight runs, since they occupy pipe length.

        Parameters
        ----------
        spec : PipeSpec or callable
            Cross-section of the first component, or ``bore -> PipeSpec``.
            With a single spec, a reducer's outlet keeps the shells and
            scales the core radius by ``end_bore / bore``.
        axial_cell : float, optional
            Target axial cell length; default the outer radius.
        kinks : {"error", "spline"}
            Consecutive pipes that change direction without a fitting (e.g.
            bathymetry routes) raise an error, or are joined into one
            ``SplinePipe`` through their end points.
        tol : float
            Position tolerance in metres; directions to ``tol`` per metre.
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
    unit_scale:    float = 1e-3,   # PCF coordinates in mm → metres
    ignore_types:  set[str] | None = None,
) -> NetworkSpec:
    """Parse a PCF file and return a NetworkSpec.

    Parameters
    ----------
    path : str or Path
        Path to the ``.pcf`` file.
    unit_scale : float
        Multiply all coordinates by this factor.  Default 1e-3 converts
        millimetres (PCF default) to metres.
    ignore_types : set[str], optional
        Component-type keywords to silently ignore (e.g. {"SUPPORT", "WELD"}).
        Defaults to a standard set of non-geometric types.

    Returns
    -------
    NetworkSpec
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PCF file not found: {path}")

    if ignore_types is None:
        ignore_types = {
            "SUPPORT", "WELD", "GASKET", "BOLT", "INSTRUMENT-COMPONENT",
            "PIPE-DIRECTION-BREAK",
        }

    spec = NetworkSpec(source=str(path))

    for record_type, attrs in _iter_records(path):
        kind = _classify(record_type)
        if record_type in ignore_types:
            continue
        if kind is None:
            spec.skipped.append((record_type, attrs))
            warnings.warn(
                f"Unsupported PCF component type '{record_type}' — skipped.",
                stacklevel=2,
            )
            continue

        endpoints = attrs.get("END-POINT", [])
        if len(endpoints) < 2:
            warnings.warn(
                f"Component {record_type} has < 2 END-POINTs — skipped.",
                stacklevel=2,
            )
            continue

        start  = np.array(endpoints[0][:3], dtype=float) * unit_scale
        end    = np.array(endpoints[1][:3], dtype=float) * unit_scale
        bore   = float(endpoints[0][3]) * unit_scale if len(endpoints[0]) > 3 else 0.0

        centre = None
        if "CENTRE-POINT" in attrs:
            cp = attrs["CENTRE-POINT"]
            centre = np.array(cp[:3], dtype=float) * unit_scale

        end_bore = None
        if kind == "reducer" and len(endpoints) >= 2 and len(endpoints[1]) > 3:
            end_bore = float(endpoints[1][3]) * unit_scale

        ignored = kind == "fitting"

        spec.components.append(ComponentSpec(
            kind=kind, start=start, end=end,
            centre=centre, bore=bore, end_bore=end_bore,
            ignored=ignored, raw=attrs, record_type=record_type.upper(),
        ))

    return spec


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
    "VALVE":                 "fitting",
    "TEE":                   None,    # not yet supported
    "CROSS":                 None,
    "CAP":                   "fitting",
    "OLET":                  None,
    "INSTRUMENT-COMPONENT":  "fitting",
}


def _classify(record_type: str) -> str | None:
    return _COMPONENT_MAP.get(record_type.upper())


# A signed decimal number; the keywords themselves contain hyphens
# ("END-POINT"), so a bare character class would match them.
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _iter_records(path: Path) -> Iterator[tuple[str, dict]]:
    """Yield (record_type, attrs_dict) for each PCF component record."""
    current_type: str | None = None
    current_attrs: dict = {}
    endpoints: list[list[float]] = []

    def _flush():
        if current_type is not None:
            attrs = dict(current_attrs)
            if endpoints:
                attrs["END-POINT"] = list(endpoints)
            yield current_type, attrs

    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.rstrip()
            if not line or line.startswith(";"):
                continue

            # Component-type lines start at column 0 with no leading whitespace
            if not line[0].isspace() and not line[0].isdigit():
                yield from _flush()
                current_type   = line.strip().split()[0]
                current_attrs  = {}
                endpoints      = []
            elif "END-POINT" in line:
                nums = [float(x) for x in _NUMBER.findall(line)]
                endpoints.append(nums)
            elif "CENTRE-POINT" in line:
                nums = [float(x) for x in _NUMBER.findall(line)]
                current_attrs["CENTRE-POINT"] = nums
            else:
                # Generic attribute line
                parts = line.split(None, 1)
                if len(parts) == 2:
                    current_attrs[parts[0].strip()] = parts[1].strip()

    yield from _flush()


def _sort_by_connectivity(comps: list[ComponentSpec]) -> list[ComponentSpec]:
    """Topological sort: order components by endpoint connectivity."""
    if not comps:
        return []
    # Simple greedy chain: start from the first component, follow end-points
    tol    = 1e-4
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
    v = comp.end - comp.start
    if comp.kind == "elbow" and comp.centre is not None:
        r = _unit(comp.start - comp.centre)
        v = v - np.dot(v, r) * r
    return _unit(v)


def _elbow_params(comp: ComponentSpec) -> tuple[float, float]:
    """Estimate bend radius and angle from an elbow ComponentSpec."""
    if comp.centre is None:
        length = float(np.linalg.norm(comp.end - comp.start))
        return length * 0.5, 90.0   # fallback

    v1 = _unit(comp.start  - comp.centre)
    v2 = _unit(comp.end    - comp.centre)
    radius = float(np.linalg.norm(comp.start - comp.centre))
    cos_a  = float(np.clip(np.dot(v1, v2), -1.0, 1.0))
    import math
    angle  = math.degrees(math.acos(cos_a))
    return radius, angle


# ---------------------------------------------------------------------------
# Assembly builder
# ---------------------------------------------------------------------------

def _build_assembly(net: NetworkSpec, spec, axial_cell, kinks, tol, lc):
    import math
    from ...assembly import Assembly, AssemblyError, Bend, Reducer, SplinePipe, Straight
    from ...assembly.fittings import _with_radii
    from ...assembly.interface import outer_radius

    if kinks not in ("error", "spline"):
        raise ValueError(f"kinks must be 'error' or 'spline', got {kinks!r}")
    comps = _sort_by_connectivity(net.components)
    if not comps:
        raise ValueError("NetworkSpec has no components to build.")
    spec_for = spec if callable(spec) else None
    first = comps[0]
    current = spec_for(first.bore) if spec_for else spec
    cell = axial_cell or outer_radius(current)

    def layers(length: float) -> int:
        return max(1, math.ceil(length / cell - 1e-9))

    d0 = _unit(first.end - first.start)
    asm = Assembly(current, position=first.start, direction=d0,
                   up=_perpendicular(d0), lc=lc)

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

    def straight_on(k, frame):
        c = comps[k]
        d = c.end - c.start
        L = float(np.linalg.norm(d))
        return L > tol and np.linalg.norm(_unit(d) - frame.normal) <= tol

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
                run = sum(float(np.linalg.norm(comps[i].end - comps[i].start))
                          for i in range(k, j + 1))
                out = asm.add(SplinePipe(tuple(map(tuple, pts)), layers(run),
                                         end_tangent=end_t))
                check(j, out.frame, comps[j].end)
                k = j + 1
                continue
            out = asm.add(Straight(length, layers(length)))
            check(k, out.frame, c.end)
        elif c.kind == "elbow":
            if c.centre is None:
                raise AssemblyError(f"{label(k)}: elbow has no CENTRE-POINT")
            to_c = c.centre - c.start
            radius = float(np.linalg.norm(to_c))
            if abs(np.dot(_unit(to_c), frame.normal)) > tol:
                raise AssemblyError(f"{label(k)}: elbow is not tangent to the incoming pipe")
            b = _unit(to_c)
            roll = math.degrees(math.atan2(np.dot(b, frame.right), np.dot(b, frame.up)))
            _, angle = _elbow_params(c)
            out = asm.add(Bend(radius, angle, layers(radius * math.radians(angle)), roll))
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
            out = asm.add(Reducer(outlet, length, layers(length)))
            check(k, out.frame, c.end)
        else:
            raise AssemblyError(f"{label(k)}: unsupported kind {c.kind!r}")
        k += 1
    return asm
