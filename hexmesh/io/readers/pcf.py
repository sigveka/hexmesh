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

TEE                           → "tee": run END-POINTs, CENTRE-POINT,
                                BRANCH1-POINT (or a third END-POINT, a
                                real-file dialect)
TEE-SET-ON, TEE-STUB, OLET    → "seton": CENTRE-POINT on a PIPE that the PCF
                                does not split, and BRANCH1-POINT
Y-PIECE-FABRICATED            → "ypiece": CENTRE-POINT at the end of its
                                stem PIPE, BRANCH1-POINT, BRANCH2-POINT
CROSS, CROSS-SET-ON, CROSS-STUB, Y-PIECE-FITTING
                              → "junction?": read, and rejected by
                                ``to_assembly`` naming the component

Joints are absorbed into the adjacent straight runs by ``to_assembly``,
never meshed (they would be sliver cells).  Other types are collected in
``NetworkSpec.skipped`` with one warning each.

Several files can be read into one network: ``read_pcf([a, b])``
(decision 0023).
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
                   "END-CONNECTION-EQUIPMENT", "EQUIPMENT-REFERENCE", "MATERIALS",
                   "NOZZLE"}       # column-1 NOZZLE: the guide's equipment connection form


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
    branch, branch2 : ndarray or None
        ``BRANCH1-POINT`` / ``BRANCH2-POINT`` in metres (junctions).
    branch_bore, branch2_bore : float or None
        Their nominal sizes, metres.
    skey : str
        The component's ``SKEY`` ("" if none).
    insulation : str or None
        ``"ON"`` / ``"OFF"`` from the component's ``INSULATION``; None if
        absent (read as off).
    end_insulation, branch_insulation : tuple
        Per-keypoint overrides (``INSULATION-ON`` / ``-SINGLE`` → ``"ON"``,
        ``INSULATION-OFF`` → ``"OFF"``, else None) on the two END-POINTs and
        on BRANCH1-POINT / BRANCH2-POINT.
    source : str
        The file it was read from.
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
    branch:   np.ndarray | None = None
    branch_bore: float | None = None
    branch2:  np.ndarray | None = None
    branch2_bore: float | None = None
    skey:     str = ""
    source:   str = ""
    index:    int = -1          # position in NetworkSpec.components (to_assembly)
    insulation: str | None = None           # INSULATION ON / OFF, None if absent
    end_insulation: tuple = (None, None)    # INSULATION-ON/-SINGLE → "ON", -OFF → "OFF"
    branch_insulation: tuple = (None, None) # on BRANCH1-POINT / BRANCH2-POINT
    ins: tuple = (0.0, 0.0)     # insulation thickness at (start, end), m (to_assembly)
    ins_junction: bool = False  # a junction with any insulated leg (to_assembly)


@dataclass
class NetworkSpec:
    """Declarative description of a pipe network parsed from an external file.

    Attributes
    ----------
    components : list[ComponentSpec]
        Components in file order (``to_assembly`` joins them into a
        graph by their end points).
    skipped : list[tuple[str, dict]]
        Component records that could not be mapped to a supported type.
    source : str
        Path or description of the source file.
    header : dict
        PCF header keywords (``UNITS-CO-ORDS`` → ``"MM"``, …).
    pipelines : dict[str, dict]
        ``PIPELINE-REFERENCE`` name → its attributes.
    connections : list[tuple[str, dict]]
        ``END-CONNECTION-*``, ``EQUIPMENT-REFERENCE`` and column-1
        ``NOZZLE`` blocks.  Repeated nozzle entries are a list under
        ``"NOZZLES"``; a block's (or nozzle's) position, in metres, is
        under ``"_point"``.
    insulation_thickness : dict[str, float]
        Pipeline → ``INSULATION-THICKNESS`` in metres.
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
    insulation_thickness: dict = field(default_factory=dict)
    coord_scale: float = 1e-3
    report:     dict = field(default_factory=dict)

    def to_assembly(self, spec, *, axial_cell: float | None = None,
                    kinks: str = "error", tol: float | None = None,
                    lc: float | None = None, inlet=None, insulation: bool = False,
                    insulation_nrad: int = 2):
        """Build an ``hexmesh.assembly.Assembly`` from the components.

        The components form a graph, joined where their end points meet
        (within *tol*), across every pipeline and file.  It must be one
        tree: three components at one point, a disconnected part or a loop
        raises ``AssemblyError`` naming a component.  The network is placed
        from a root open end, depth first.  Each component is placed from
        the previous outlet, and its PCF end points (and branch points) are
        then checked against the placed ports; a gap or a change of
        direction larger than *tol* raises ``AssemblyError`` naming the
        component (nothing is snapped).

        Mapping: ``pipe`` and ``fitting`` (flange, valve, …) → ``Straight``;
        ``elbow`` → ``Bend``, from its corner point (radius and angle are
        cross-checked against ``BEND-RADIUS`` and ``ANGLE`` when given);
        ``reducer`` (concentric) → ``Reducer``; ``TEE`` → ``Tee``;
        ``TEE-SET-ON`` / ``TEE-STUB`` / ``OLET`` → the host pipe split into
        straight + ``Tee`` (run length = the branch diameter) + straight;
        ``Y-PIECE-FABRICATED`` → the end of its stem pipe + ``Wye``.  A
        junction outside its fitting's limits (equal, angled, offset or
        tangential tees, crosses, asymmetric Y pieces, layered specs) raises
        ``AssemblyError`` naming the component and the limit.

        Root: every junction must be entered through its inlet (a tee's
        run end, a Y piece's stem).  By default the root is the first open
        end, in file order, from which that holds; ends that a component's
        ``FLOW`` attribute marks as upstream are tried first.  The root's
        ``up`` is chosen so the first junction's branch lands on an allowed
        roll (a multiple of 90°).

        Names: each fitting is labelled ``<TYPE>_<n>`` (``n`` counts that
        type in file order) or ``<TYPE>_<COMPONENT-IDENTIFIER>``; open ends
        are ``<pipeline>_end<k>`` (``k`` counts the pipeline's open ends in
        file order), so the same file gives the same assembly.  Without a
        pipeline reference the inlet keeps ``inlet`` and other ends the
        assembly's defaults.

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
        inlet : str or 3-vector, optional
            The root: an open end's name or its point (metres).
        insulation : bool
            Add a shell named ``insulation`` (the pipeline's
            ``INSULATION-THICKNESS``, ``insulation_nrad`` cells) to the
            spec of insulated components (``INSULATION ON``, or an
            ``INSULATION-ON`` / ``-SINGLE`` keypoint).  Where it starts or
            stops, the change is placed one cell inside the neighbouring
            straight component, the bare one if both are straight (a bare
            valve or flange: insulation stops one cell into it).  No
            straight neighbour, a junction that is insulated, or an
            insulated pipeline without ``INSULATION-THICKNESS`` raises
            ``AssemblyError``.  Off (the default), the spec alone decides.
        insulation_nrad : int
            Radial cells across the insulation shell.

        Equipment: an open end at an ``END-CONNECTION-EQUIPMENT`` (or
        column-1 ``NOZZLE``) is named ``<equipment>_<nozzle>`` and marked
        as an equipment end (``Interface.equipment``), which
        ``extend_open_ends`` never extends.  A nozzle whose ``CO-ORDS``
        disagree with the connection, or a connection with no open end
        within *tol*, raises ``AssemblyError``.

        Returns
        -------
        Assembly
        """
        return _build_assembly(self, spec, axial_cell, kinks, tol, lc, inlet,
                               insulation, insulation_nrad)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def read_pcf(
    path:          str | Path | list,
    unit_scale:    float | None = None,
    ignore_types:  set[str] | None = None,
    joint_max:     float = JOINT_MAX,
) -> NetworkSpec:
    """Parse a PCF file, or several into one network, and return a
    NetworkSpec.

    Parameters
    ----------
    path : str, Path or list of them
        Path to the ``.pcf`` file, or a list of files read into one
        network (components in list, then file, order; each file keeps
        its own units).
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
    if isinstance(path, (list, tuple)):
        if not path:
            raise ValueError("read_pcf: empty list of files")
        parts = [read_pcf(p, unit_scale, ignore_types, joint_max) for p in path]
        net = NetworkSpec(source=", ".join(n.source for n in parts),
                          header=dict(parts[0].header), coord_scale=parts[0].coord_scale)
        for n in parts:
            net.components += n.components
            net.skipped += n.skipped
            net.pipelines.update(n.pipelines)
            net.insulation_thickness.update(n.insulation_thickness)
            net.connections += n.connections
        return net
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

        endpoints = list(attrs.get("END-POINT", []))
        epwords = list(attrs.get("END-POINT-WORDS", [[]] * len(endpoints)))
        bwords = [attrs.get(k + "-WORDS", []) for k in ("BRANCH1-POINT", "BRANCH2-POINT")]
        centre = None
        if "CENTRE-POINT" in attrs:
            centre = np.array(attrs["CENTRE-POINT"][:3], dtype=float) * scale
        branches = [attrs.get(k) for k in ("BRANCH1-POINT", "BRANCH2-POINT")]
        if kind == "tee" and len(endpoints) >= 3 and branches[0] is None:
            branches[0] = endpoints.pop(2)    # real-file dialect: branch as END-POINT 3
            bwords[0] = epwords.pop(2)
        if kind in ("seton", "ypiece", "junction?"):
            first = endpoints[0] if endpoints else (attrs.get("CENTRE-POINT") or
                                                    branches[0] or [0, 0, 0])
            endpoints = [first, first]
        elif len(endpoints) < 2:
            warnings.warn(f"Component {record_type} has < 2 END-POINTs — skipped.",
                          stacklevel=2)
            continue

        def point(v):
            return None if v is None else np.array(v[:3], dtype=float) * scale

        def size(v):
            return float(v[3]) * bore_scale if v is not None and len(v) > 3 else None

        start = point(endpoints[0])
        end   = point(endpoints[1])
        bore  = size(endpoints[0]) or 0.0
        if kind in ("seton", "ypiece"):
            bore = 0.0                         # the host pipe's
        end_bore = None
        if kind == "reducer" and len(endpoints[1]) > 3:
            end_bore = float(endpoints[1][3]) * bore_scale
        if kind == "joint?":
            kind = "joint" if np.linalg.norm(end - start) <= joint_max else "fitting"

        spec.components.append(ComponentSpec(
            kind=kind, start=start, end=end, centre=centre, bore=bore,
            end_bore=end_bore, ignored=kind == "fitting", raw=attrs,
            record_type=rtype, pipeline=pipeline,
            branch=point(branches[0]), branch_bore=size(branches[0]),
            branch2=point(branches[1]), branch2_bore=size(branches[1]),
            skey=str(attrs.get("SKEY", "")).strip().upper(), source=str(path),
            insulation=_on_off(attrs.get("INSULATION")),
            end_insulation=tuple(_keypoint_insulation(w) for w in (epwords + [[], []])[:2]),
            branch_insulation=tuple(_keypoint_insulation(w) for w in bwords),
        ))

    for name, a in spec.pipelines.items():   # INSULATION-THICKNESS in coordinate units
        nums = _NUMBER.findall(str(a.get("INSULATION-THICKNESS", "")))
        if nums:
            spec.insulation_thickness[name] = float(nums[0]) * scale
    for _, a in spec.connections:       # positions in metres, this file's units
        for n in [a] + a.get("NOZZLES", []):
            pt = n.get("CO-ORDS")
            nums = ([float(x) for x in _NUMBER.findall(pt)] if isinstance(pt, str)
                    else (n.get("END-POINT") or [None])[0])
            if nums and len(nums) >= 3:
                n["_point"] = np.array(nums[:3], dtype=float) * scale
    return spec


def _on_off(value) -> str | None:
    v = str(value or "").strip().upper()
    return v if v in ("ON", "OFF") else None


def _keypoint_insulation(words: list[str]) -> str | None:
    """A keypoint's insulation override from the words on its line."""
    for w in words:
        w = w.upper()
        if w in ("INSULATION-ON", "INSULATION-SINGLE"):
            return "ON"
        if w == "INSULATION-OFF":
            return "OFF"
    return None


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
    "TEE":                   "tee",
    "TEE-SET-ON":            "seton",
    "TEE-STUB":              "seton",
    "OLET":                  "seton",
    "Y-PIECE-FABRICATED":    "ypiece",
    "CROSS":                 "junction?",   # read, rejected by to_assembly
    "CROSS-SET-ON":          "junction?",
    "CROSS-STUB":            "junction?",
    "Y-PIECE-FITTING":       "junction?",
}

#: Set-on SKEYs whose branch is tangential or offset (RESEARCH §3.1): rejected.
OFFSET_SKEYS = {"TTSO", "TTRF", "TOSO", "TORF"}


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
    epwords: list[list[str]] = []           # the words on each END-POINT line
    pipeline = ""
    in_header = True

    def flush():
        if block is None:
            return
        kind, name = block
        a = dict(attrs)
        if endpoints:
            a["END-POINT"] = list(endpoints)
            a["END-POINT-WORDS"] = list(epwords)
        if kind == "component":
            yield name, a, pipeline
        elif kind == "pipeline":
            net.pipelines[name] = a
        elif kind == "other":
            net.connections.append((name, a))

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
                if in_header and key not in _COMPONENT_MAP and key not in _NON_COMPONENTS:
                    net.header[key] = value
                    continue
                yield from flush()
                in_header = False
                kind = "other" if key in _NON_COMPONENTS else "component"
                block, attrs, endpoints, epwords = (kind, words[0]), {}, [], []
                if kind == "other" and value:
                    attrs[key] = value                 # EQUIPMENT-REFERENCE <name>
            elif "END-POINT" in line.split(None, 1)[0]:
                endpoints.append([float(x) for x in _NUMBER.findall(line)])
                epwords.append(line.split()[1:])
            elif line.split(None, 1)[0] in ("CENTRE-POINT", "BRANCH1-POINT",
                                            "BRANCH2-POINT"):
                key, *rest = line.split(None, 1)      # "BRANCH1" holds a digit
                attrs[key] = [float(x) for x in _NUMBER.findall(rest[0] if rest else "")]
                attrs[key + "-WORDS"] = rest[0].split() if rest else []
            elif block is not None and block[1].upper() == "EQUIPMENT-REFERENCE" \
                    and (line.split()[0] == "NOZZLE" or "NOZZLES" in attrs):
                # repeated NOZZLE entries, each with its own attributes
                parts = line.split(None, 1)
                if parts[0] == "NOZZLE":
                    attrs.setdefault("NOZZLES", []).append({})
                else:
                    attrs["NOZZLES"][-1][parts[0]] = parts[1].strip() if len(parts) == 2 else ""
            else:
                parts = line.split(None, 1)
                attrs[parts[0].strip()] = parts[1].strip() if len(parts) == 2 else ""

    yield from flush()


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


# --- graph (decision 0023) ---------------------------------------------------

class _Reroll(Exception):
    """Raised at the first junction: rebuild with the root rolled by *miss*."""

    def __init__(self, miss: float):
        self.miss = miss


def _name(text: str) -> str:
    """*text* as a patch-name / label fragment: letters, digits and ``_``."""
    return re.sub(r"[^A-Za-z0-9_]+", "_", text).strip("_")


def _labels(comps: list[ComponentSpec]) -> list[str]:
    """``<TYPE>_<n>`` per component (n counts its type in file order), or
    ``<TYPE>_<COMPONENT-IDENTIFIER>``; unique."""
    seen: dict[str, int] = {}
    used: set[str] = set()
    out = []
    for c in comps:
        t = _name(c.record_type or c.kind).upper() or "COMPONENT"
        seen[t] = seen.get(t, 0) + 1
        ident = _name(str(c.raw.get("COMPONENT-IDENTIFIER", "")))
        label = f"{t}_{ident}" if ident else f"{t}_{seen[t]}"
        base, k = label, 2
        while label in used:
            label, k = f"{base}_{k}", k + 1
        used.add(label)
        out.append(label)
    return out


@dataclass
class _Part:
    """A component in the graph: its ports' points (entry candidates)."""

    comp:  ComponentSpec
    label: str
    ports: list                              # points, metres
    nodes: list = field(default_factory=list)

    @property
    def kind(self) -> str:
        return self.comp.kind


def _ports(c: ComponentSpec) -> list:
    if c.kind == "tee":
        return [c.start, c.end, c.branch]
    if c.kind == "wye":
        return [c.start, c.branch, c.branch2]
    return [c.start, c.end]


def _describe(c: ComponentSpec, label: str) -> str:
    """``component <index> (<TYPE> <label>[, SKEY …] at <point>)``."""
    skey = f", SKEY {c.skey}" if c.skey else ""
    at = c.centre if c.kind in ("seton", "ypiece", "tee", "wye") else c.start
    return (f"component {c.index} ({c.record_type or c.kind} {label}{skey} "
            f"at {np.round(at, 4)})")


def _radius(spec) -> float:
    return spec.core_shape.radius


def _split_hosts(comps, labels, tol):
    """Replace each set-on and Y piece by a ``tee`` / ``wye`` with explicit
    ports, splitting its host pipe (pure).  The split is set from nominal
    sizes, not the spec, so it is the same for every spec: a set-on's run
    is its branch's nominal bore (a diameter) each side of CENTRE-POINT; a
    Y piece's inlet run is ``r·(tan h + margin + 0.5)``, ``r`` the stem's
    nominal radius and ``h`` half the daughters' angle."""
    from ...assembly import AssemblyError
    from ...assembly.wye import _IN_MARGIN
    comps, labels = list(comps), list(labels)
    while True:
        todo = [i for i, c in enumerate(comps) if c.kind in ("seton", "ypiece")]
        if not todo:
            return comps, labels
        i = todo[0]
        j_c = comps[i]
        what = _describe(j_c, labels[i])
        if j_c.kind == "seton" and j_c.skey in OFFSET_SKEYS:
            raise AssemblyError(f"{what}: tangential and offset set-ons are not "
                                f"supported; a Tee branch is perpendicular and centred")
        if j_c.centre is None or j_c.branch is None:
            raise AssemblyError(f"{what}: needs CENTRE-POINT and BRANCH1-POINT")
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
                raise AssemblyError(f"{what}: no PIPE passes through its CENTRE-POINT "
                                    f"(the branch must be centred on a straight pipe)")
            h, t, L = inside[0]
            host = comps[h]
            axis = (host.end - host.start) / L
            if not j_c.branch_bore:
                raise AssemblyError(f"{what}: needs a size on BRANCH1-POINT")
            run = j_c.branch_bore              # the branch diameter
            if t - run <= tol or t + run >= L - tol:
                raise AssemblyError(
                    f"{what}: host pipe {labels[h]} is too short around the branch; "
                    f"the tee needs {run:.4g} m on each side of CENTRE-POINT")
            a, b = c - run * axis, c + run * axis
            tee = ComponentSpec(**{**j_c.__dict__, "kind": "tee", "start": a, "end": b,
                                   "bore": host.bore,
                                   "ins_junction": j_c.ins_junction or max(host.ins) > 0})
            pieces = [ComponentSpec(**{**host.__dict__, "start": host.start.copy(), "end": a,
                                       "ins": (host.ins[0],) * 2}),
                      tee,
                      ComponentSpec(**{**host.__dict__, "start": b, "end": host.end.copy(),
                                       "ins": (host.ins[1],) * 2})]
            names = [f"{labels[h]}_1", labels[i], f"{labels[h]}_2"]
        else:
            ends = [x for x in hosts if x[1] <= tol or x[1] >= x[2] - tol]
            if not ends or j_c.branch2 is None:
                raise AssemblyError(f"{what}: needs a stem PIPE ending at its "
                                    f"CENTRE-POINT, BRANCH1-POINT and BRANCH2-POINT")
            h, t, L = ends[0]
            host = comps[h]
            far = host.start if t >= L - tol else host.end
            n = _unit(c - far)
            d1, d2 = _unit(j_c.branch - c), _unit(j_c.branch2 - c)
            half = math.acos(float(np.clip(np.dot(d1, n), -1, 1)))
            R = 0.5 * host.bore
            run = R * (math.tan(half) + _IN_MARGIN + 0.5)
            if run >= L - tol:
                raise AssemblyError(
                    f"{what}: stem pipe {labels[h]} ({L:.4g} m) is shorter than the "
                    f"{run:.4g} m the Wye's inlet run needs")
            a = c - run * n
            wye = ComponentSpec(**{**j_c.__dict__, "kind": "wye", "start": a, "end": a,
                                   "bore": host.bore,
                                   "ins_junction": j_c.ins_junction or max(host.ins) > 0})
            stem = ComponentSpec(**{**host.__dict__, "start": far.copy(), "end": a})
            pieces, names = [stem, wye], [labels[h], labels[i]]
        # the pieces take the host's place in file order; the junction's
        # own record goes
        comps[h:h + 1], labels[h:h + 1] = pieces, names
        k = next(m for m, c in enumerate(comps) if c is j_c)
        del comps[k], labels[k]


def _graph(parts: list[_Part], joints: list[ComponentSpec], tol: float):
    """Cluster port points into nodes: node → [(part, port)], and node →
    the joints at it.  A joint's two ends are one node (it is absorbed,
    never a part), so a zero-length weld does not count as a component."""
    from ...assembly import AssemblyError
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
                f"a TEE, set-on or Y piece")
    return nodes, at_node


def _joints_from(joints: list[ComponentSpec], x: np.ndarray) -> list[ComponentSpec]:
    """*joints* (at one node) in order away from point *x*, each oriented so
    it starts at the end nearer the previous one."""
    left, out = list(joints), []
    while left:
        j = min(left, key=lambda j: min(np.linalg.norm(j.start - x), np.linalg.norm(j.end - x)))
        left.remove(j)
        j = ComponentSpec(**{**j.__dict__, "start": j.start.copy(), "end": j.end.copy()})
        if np.linalg.norm(j.end - x) < np.linalg.norm(j.start - x):
            j.start, j.end = j.end, j.start
        out.append(j)
        x = j.end
    return out


def _check_tree(parts, nodes) -> None:
    from ...assembly import AssemblyError
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
                                        f"read from PCF (decision 0023)")
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
            f"must be one connected piece")


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
    """Open-end node → ``<pipeline>_end<k>`` (file order), None without a
    pipeline reference."""
    ends = sorted((k, q, n) for n, at in enumerate(nodes) if len(at) == 1
                  for k, q in at)
    count: dict[str, int] = {}
    out = {}
    for k, q, n in ends:
        pipe = _name(parts[k].comp.pipeline)
        if not pipe:
            out[n] = None
            continue
        count[pipe] = count.get(pipe, 0) + 1
        out[n] = f"{pipe}_end{count[pipe]}"
    return out


def _choose_root(parts, nodes, names, inlet, tol):
    from ...assembly import AssemblyError
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

    def upstream(e):
        flow = str(parts[e[0]].comp.raw.get("FLOW", "")).strip()
        return (flow == "1" and e[1] == 0) or (flow == "2" and e[1] == 1)
    first_bad = None
    for e in sorted(ends, key=lambda e: not upstream(e)):
        bad = _entries(parts, nodes, e[:2])
        if bad is None:
            return e
        first_bad = first_bad or bad
    raise AssemblyError(f"no open end enters every junction through its inlet: "
                        f"{first_bad}")


def _orient(c: ComponentSpec, port: int) -> ComponentSpec:
    """*c* entered at *port*: start is the entry (2-port parts)."""
    c = ComponentSpec(**{**c.__dict__, "start": c.start.copy(), "end": c.end.copy()})
    if port == 1 and c.kind not in ("tee", "wye"):
        c.start, c.end = c.end, c.start
        c.ins = c.ins[::-1]
        if c.kind == "reducer":
            c.bore, c.end_bore = c.end_bore, c.bore
    elif port == 1 and c.kind == "tee":
        c.start, c.end = c.end, c.start
    return c


# --- insulation (decision 0023, task 0038) -----------------------------------

#: Name of the shell ``to_assembly(insulation=True)`` adds.
INSULATION = "insulation"


def _resolve_insulation(net: NetworkSpec, labels: list[str]) -> None:
    """Set ``ins`` (thickness at each end, 0 = bare) and ``ins_junction`` on
    every component.  Insulated only with ``INSULATION ON``; a keypoint's
    ``INSULATION-ON/-SINGLE/-OFF`` overrides that end."""
    from ...assembly import AssemblyError
    for c, label in zip(net.components, labels):
        def thick(status):
            if status != "ON":
                return 0.0
            t = net.insulation_thickness.get(c.pipeline)
            if not t:
                raise AssemblyError(
                    f"pipeline {c.pipeline or '(none)'!r}: {_describe(c, label)} is "
                    f"insulated but the pipeline has no INSULATION-THICKNESS")
            return t
        own = c.insulation
        c.ins = tuple(thick(e or own) for e in c.end_insulation)
        legs = [own] + [b or own for b in c.branch_insulation]
        c.ins_junction = c.kind in ("tee", "seton", "ypiece") and any(
            thick(x) > 0 for x in legs + [e or own for e in c.end_insulation])


def _dressed(spec, t: float, nrad: int):
    """*spec* without its ``insulation`` shell, plus one of thickness *t*
    (none if ``t`` is 0)."""
    from ...assembly.fittings import _with_radii
    shells = spec.shells
    if shells and shells[-1].name == INSULATION:
        shells = shells[:-1]
    bare = _with_radii(spec, [spec.core_shape.radius] + [sh.dR for sh in shells])
    return bare.shell(INSULATION, dR=t, nrad=nrad) if t > 0 else bare


def _thickness(spec) -> float:
    sh = spec.shells
    return sh[-1].dR if sh and sh[-1].name == INSULATION else 0.0


def _straight_like(c: ComponentSpec, tol: float) -> bool:
    return c.kind in ("pipe", "fitting") and float(np.linalg.norm(c.end - c.start)) > tol


def _plan_insulation(comps, labels, t_in, to_junction, tol):
    """Insulation switches along a run of oriented two-port components.

    *t_in* is the thickness of the interface the run starts from;
    *to_junction* says the run ends at a (bare) junction.  Returns, per
    component, ``(t_inlet, t_outlet, cell_pattern)``: the thickness at its
    ports and, for a straight that hosts a switch, the per-cell thickness
    as ``(first, middle_in, middle_out, last)``.  A switch sits one cell
    inside a straight neighbour, the bare one if both are straight."""
    from ...assembly import AssemblyError
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
    if to_junction:
        host(n - 1, None, b[-1], 0.0, "the junction after it")
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


def _equipment_ends(net, parts, nodes, names, tol, describe) -> set[int]:
    """Name the open ends attached to equipment ``<equipment>_<nozzle>``
    and return their nodes.  ``END-CONNECTION-EQUIPMENT`` (and column-1
    ``NOZZLE``) records attach by position; their ``CONNECTION-REFERENCE``
    is a nozzle ``REFERENCE`` of an ``EQUIPMENT-REFERENCE`` block (whose
    ``CO-ORDS`` must then agree), or ``<equipment>/<nozzle>``."""
    from ...assembly import AssemblyError
    nozzles = {}
    for kind, a in net.connections:
        if kind.upper() == "EQUIPMENT-REFERENCE":
            for nz in a.get("NOZZLES", []):
                if nz.get("REFERENCE"):
                    nozzles[nz["REFERENCE"].strip()] = (a.get("EQUIPMENT-REFERENCE", ""), nz)
    ends = [(k, q, n) for n, at in enumerate(nodes) if len(at) == 1 for k, q in at]
    marked: dict[int, str] = {}
    for kind, a in net.connections:
        if kind.upper() not in ("END-CONNECTION-EQUIPMENT", "NOZZLE"):
            continue
        ref = str(a.get("CONNECTION-REFERENCE", "")).strip()
        what = f"{kind.upper()} {ref or '(no CONNECTION-REFERENCE)'}"
        nz_point = None
        if ref in nozzles:
            eq, nz = nozzles[ref]
            label = f"{_name(eq)}_{_name(ref)}" if _name(eq) else _name(ref)
            nz_point = nz.get("_point")
        elif "/" in ref:
            eq, nzr = ref.split("/", 1)
            label = f"{_name(eq)}_{_name(nzr)}"
        else:
            label = _name(ref) or "equipment"
        point = a.get("_point")
        if point is not None and nz_point is not None \
                and np.linalg.norm(point - nz_point) > tol:
            raise AssemblyError(
                f"{what}: nozzle {ref} is at {np.round(nz_point, 4)} but the connection "
                f"is at {np.round(point, 4)}, "
                f"{np.linalg.norm(point - nz_point):.3g} m apart")
        at = point if point is not None else nz_point
        if at is None:
            raise AssemblyError(f"{what}: no CO-ORDS or END-POINT to attach it by")
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


def _build_assembly(net: NetworkSpec, spec, axial_cell, kinks, tol, lc, inlet=None,
                    insulation=False, insulation_nrad=2):
    from ...assembly import AssemblyError

    if kinks not in ("error", "spline"):
        raise ValueError(f"kinks must be 'error' or 'spline', got {kinks!r}")
    if not net.components:
        raise ValueError("NetworkSpec has no components to build.")
    if tol is None:
        tol = _model_tolerance(net.components)
    labels = _labels(net.components)
    for i, c in enumerate(net.components):
        c.index = i
    for c, l in zip(net.components, labels):
        if c.kind == "junction?":
            raise AssemblyError(
                f"{_describe(c, l)}: crosses and Y-PIECE-FITTING are not supported "
                f"(decision 0023)")
    if insulation:
        sample = spec(net.components[0].bore or 0.1) if callable(spec) else spec
        if any(sh.name == INSULATION for sh in sample.shells):
            raise ValueError(f"insulation=True adds a shell named {INSULATION!r}; the "
                             f"spec already has one")
        _resolve_insulation(net, labels)
    else:
        for c in net.components:
            c.ins, c.ins_junction = (0.0, 0.0), False

    comps, labels = _split_hosts(
        [ComponentSpec(**{**c.__dict__, "start": c.start.copy(), "end": c.end.copy()})
         for c in net.components], labels, tol)
    joints = [c for c in comps if c.kind == "joint"]
    parts = [_Part(c, l, _ports(c)) for c, l in zip(comps, labels) if c.kind != "joint"]
    if not parts:
        raise ValueError("NetworkSpec has only joints.")
    nodes, at_node = _graph(parts, joints, tol)
    _check_tree(parts, nodes)
    names = _end_names(parts, nodes)
    equipment = _equipment_ends(net, parts, nodes, names, tol,
                                lambda p: _describe(p.comp, p.label))
    root = _choose_root(parts, nodes, names, inlet, tol)
    ins = {"on": bool(insulation), "nrad": insulation_nrad, "equipment": equipment}

    roll = 0.0
    for _ in range(2):
        try:
            asm = _place(net, parts, nodes, at_node, names, root, spec, axial_cell,
                         kinks, tol, lc, roll, reroll=(roll == 0.0), ins=ins)
            return asm
        except _Reroll as r:
            roll = r.miss
    raise AssertionError("unreachable")


def _place(net, parts, nodes, at_node, names, root, spec, axial_cell, kinks, tol, lc,
           roll, reroll, ins):
    """Place the network from *root* (part, port, node), depth first."""
    from ...assembly import Assembly, AssemblyError, Tee, Wye
    from ...assembly.interface import outer_radius, rotate, toward_roll

    report = net.report = {"tolerance": tol, "joints": [], "max_offset": 0.0}
    k0, q0, n0 = root
    first = _orient(parts[k0].comp, q0)
    current = base = spec(first.bore) if callable(spec) else spec
    if ins["on"]:
        t0 = 0.0 if first.kind in ("tee", "wye") else first.ins[0]
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
                f"PCF point {np.round(end, 6)} by {np.linalg.norm(frame.position - end):.3g} m")

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
        if c.ins_junction:
            raise AssemblyError(f"{what}: insulated junction; the reader can't "
                                f"carry insulation through a junction yet (task 0054), "
                                f"so insulation must stop before it")
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
                raise AssemblyError(f"{what}: run END-POINTs are not symmetric about "
                                    f"CENTRE-POINT")
            if not (c.branch_bore and main_bore):
                raise AssemblyError(f"{what}: needs sizes on its run and branch points")
            R = _radius(iface.spec)
            rb = (_radius(spec(c.branch_bore)) if callable(spec)
                  else R * c.branch_bore / main_bore)        # scaled like a Reducer
            if not rb < R:
                raise AssemblyError(f"{what}: equal tees are not supported (branch "
                                    f"radius {rb:.4g} must be below the main radius "
                                    f"{R:.4g})")
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
        iface = _place_chain(asm, iface, chain, end_dir, spec, kinks, tol, ins, jn is not None,
                             report, net.coord_scale)
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


def _place_chain(asm, iface, chain, end_dir, spec, kinks, tol, ins, to_junction, report,
                 coord_scale):
    """Place a run of two-port components (oriented, with labels) from
    *iface*; return the last interface.  *end_dir* is the direction of the
    junction that follows, if any (a spline's end tangent)."""
    from ...assembly import AssemblyError, Bend, Reducer, SplinePipe, Straight
    from ...assembly.fittings import _with_radii

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
            # from the placed outlet to the PCF end point: gaps never accumulate
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
                    f"{label(k)}: elbow's incoming leg (start → CENTRE-POINT) is not "
                    f"along the incoming pipe")
            _cross_check_elbow(c, g, coord_scale, label(k))
            roll = math.degrees(math.atan2(np.dot(g.turn, frame.right),
                                           np.dot(g.turn, frame.up)))
            iface = asm.add(iface, Bend(g.radius, g.angle, roll=roll), label=lab)
            check(k, iface.frame, c.end)
        elif c.kind == "reducer":
            if c.record_type == "REDUCER-ECCENTRIC":
                raise AssemblyError(f"{label(k)}: eccentric reducers are not supported")
            if not c.end_bore or not c.bore:
                raise AssemblyError(f"{label(k)}: reducer needs both bores")
            if callable(spec):
                outlet = spec(c.end_bore)
                if ins["on"]:
                    outlet = _dressed(outlet, _thickness(iface.spec), ins["nrad"])
            else:
                cur = iface.spec
                radii = [cur.core_shape.radius * c.end_bore / c.bore] + [sh.dR for sh in cur.shells]
                outlet = _with_radii(cur, radii)
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
