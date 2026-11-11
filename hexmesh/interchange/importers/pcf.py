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
PCF (Piping Component File) reader.

Parses an Isogen PCF file and returns a NetworkSpec: the file's records.
``NetworkSpec.to_model()`` translates them into the format-neutral network
model (``hexmesh.interchange``, decision 0032); ``to_assembly()`` builds
that with ``hexmesh.interchange.build``.  The PCF facts the builder needs
(stated bend angles, offset set-ons, FLOW, equipment connections) reach
it as model content, and messages name components through this module's
formatter.

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

from ...errors import HexmeshWarning, ReaderError, ReaderFileNotFound
from .. import model as _m
from ..build import INSULATION, TOL_FLOOR, TOL_RELATIVE  # noqa: F401  (re-exported)
from ..operations import import_entry
from ...units import inch as INCH, mm

#: ``UNITS-CO-ORDS`` → metres per unit
COORD_UNITS = {"MM": mm, "MM-HUNDREDTHS": mm / 100, "INCH": INCH}
#: ``UNITS-BORE`` → metres per unit (nominal size)
BORE_UNITS = {"MM": mm, "INCH": INCH, "INCH-SIXTEENTH": INCH / 16}

#: Joints (couplings, gaskets, welds) up to this length are absorbed: just
#: above the 1/16" weld root gap that exporters model (pcf2iso's choice;
#: the guide gives no value).
JOINT_MAX = 1.6e-3
_NON_COMPONENTS = {"PIPELINE-REFERENCE", "END-CONNECTION-PIPELINE",
                   "END-CONNECTION-EQUIPMENT", "EQUIPMENT-REFERENCE", "MATERIALS",
                   "NOZZLE"}       # column-1 NOZZLE: the guide's equipment connection form

#: Information items of the PCF guide ("Information Items", "End Connection
#: and Position Types"): drawing annotations with no geometry.  Read and
#: ignored quietly, counted in ``NetworkSpec.report["ignored"]``.  A WELD
#: given only by ``CO-ORDS`` (a weld marker, no END-POINTs) counts too.
ANNOTATION_TYPES = {
    "MESSAGE", "MESSAGE-SQUARE", "MESSAGE-POINTED", "MESSAGE-ROUND", "MESSAGE-CIRCLE",
    "MESSAGE-TRIANGLE", "MESSAGE-DIAMOND", "MESSAGE-DOUBLE-CIRCLE", "MESSAGE-ELLIPSE",
    "TEXT", "REFERENCE-DIMENSION", "TML", "FLOOR-SYMBOL", "WALL-SYMBOL", "FLOW-ARROW",
    "INSULATION-SYMBOL", "INDUCTION-START", "INDUCTION-END", "ISO-SPLIT-POINT",
    "LOCATION-POINT", "PIPE-BREAK", "SPOOL-IDENTIFIER", "SYSTEM-SPLIT",
    "END-POSITION-OPEN", "END-POSITION-CLOSED", "END-POSITION-VENT",
    "END-POSITION-DRAIN", "END-POSITION-NULL",
}
#: An unknown inline component whose legs (END-POINT → CENTRE-POINT →
#: END-POINT) turn by more than this, in degrees, is rejected (angle valves).
INLINE_ANGLE_TOL = 1.0


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
    line : int or None
        The 1-based line of its record keyword in that file.
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
    line:     int | None = None # 1-based line of the record keyword (task 0096)
    index:    int = -1          # position in NetworkSpec.components (to_assembly)
    insulation: str | None = None           # INSULATION ON / OFF, None if absent
    end_insulation: tuple = (None, None)    # INSULATION-ON/-SINGLE → "ON", -OFF → "OFF"
    branch_insulation: tuple = (None, None) # on BRANCH1-POINT / BRANCH2-POINT
    ins: tuple = (0.0, 0.0)     # insulation thickness at (start, end), m (to_assembly)
    ins_junction: float = 0.0   # insulation through a junction, m; 0 bare (to_assembly)


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
        ``"ignored"``: record type → count of the non-geometric records
        read and ignored (annotations, supports, …).  ``to_assembly`` adds
        the tolerance used, the joints absorbed or dropped, and the largest
        lateral offset absorbed.
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
    #: how ``read_pcf`` was called (``{"source": [...], "options": {...}}``),
    #: for the model's import log entry (task 0066)
    read_args:  dict = field(default_factory=dict)
    #: ``read_pcf``'s *snap_tolerance*, for the model (task 0138)
    snap_tolerance: float = TOL_FLOOR

    def to_assembly(self, spec, *, axial_cell: float | None = None,
                    kinks: str = "error", tol: float | None = None,
                    lc: float | None = None, inlet=None, insulation: bool = False,
                    insulation_nrad: int = 2):
        """Build an ``hexmesh.assembly.Assembly`` from the components.

        The components form a graph, joined where their end points meet
        (within *tol*), across every pipeline and file.  It must be one
        tree: three components at one point, a disconnected part or a loop
        raises ``AssemblyError`` naming a component (a file of several
        unconnected pipelines: ``to_assemblies``).  The network is placed
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
            Default: ``TOL_RELATIVE`` × the model diagonal, at least the
            snap tolerance ``read_pcf`` was given (default ``TOL_FLOOR``,
            0.11").
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
        from ..build import build
        model = self.to_model()
        try:
            return build(model, spec, axial_cell=axial_cell, kinks=kinks, tol=tol, lc=lc,
                         inlet=inlet, insulation=insulation, insulation_nrad=insulation_nrad)
        finally:
            self.report = model.report

    def to_assemblies(self, spec, *, axial_cell: float | None = None,
                      kinks: str = "error", tol: float | None = None,
                      lc: float | None = None, insulation: bool = False,
                      insulation_nrad: int = 2) -> dict:
        """One ``Assembly`` per connected piece, for a file holding several
        pipelines that don't connect: ``hexmesh.interchange.build_pieces``
        on ``to_model()``.

        Returns ``{name: Assembly}`` in file order (of each piece's first
        component), named after the piece's first ``PIPELINE-REFERENCE``
        (``piece<k>`` without one; a repeat gets ``_2``, …).  Each piece is
        built as ``to_assembly`` builds a whole file (same arguments; the
        root is chosen per piece), and fittings keep their whole-file
        labels.  Equipment connections go to the piece whose open end they
        sit at.  ``self.report["pieces"]`` holds each piece's report.  The
        file's unsupported components (crosses, angled inline components)
        raise before any piece is built.
        """
        from ..build import build_pieces
        model = self.to_model()
        try:
            return build_pieces(model, spec, axial_cell=axial_cell, kinks=kinks, tol=tol,
                                lc=lc, insulation=insulation, insulation_nrad=insulation_nrad)
        finally:
            self.report = model.report

    def to_model(self) -> "_m.NetworkModel":
        """The file as a ``hexmesh.interchange.NetworkModel`` (decision 0032):
        what ``to_assembly`` builds.  A fresh model on each call, from the
        components as they are now."""
        return _to_model(self)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def read_pcf(
    path:          str | Path | list,
    unit_scale:    float | None = None,
    ignore_types:  set[str] | None = None,
    joint_max:     float = JOINT_MAX,
    snap_tolerance: float = TOL_FLOOR,
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
    snap_tolerance : float
        Ends closer than this (metres) are one point when the network is
        built (GUIDE, *How ends are connected: the snap tolerance*).
        Default ``TOL_FLOOR``, 0.11" (2.79 mm): pcf2iso's, just above the
        1/16" weld gap of plant isometrics.  Set it smaller for small
        bores, or to an exporter's own gap.  The model keeps it
        (``NetworkModel.snap_tolerance``).

    Returns
    -------
    NetworkSpec
    """
    called = _read_args(path, unit_scale, ignore_types, joint_max, snap_tolerance)  # as given
    if not (isinstance(snap_tolerance, (int, float)) and math.isfinite(snap_tolerance)
            and snap_tolerance > 0):
        raise ReaderError(f"read_pcf: snap_tolerance must be a positive length in metres, "
                          f"got {snap_tolerance!r}", code="size_not_positive",
                          where={"field": "snap_tolerance"}, value=repr(snap_tolerance),
                          hint=f"the default is {TOL_FLOOR:g} m (0.11 inch)")
    if isinstance(path, (list, tuple)):
        if not path:
            raise ReaderError("read_pcf: empty list of files",
                              code="pcf_no_files", where={"field": "path"})
        parts = [read_pcf(p, unit_scale, ignore_types, joint_max, snap_tolerance) for p in path]
        net = NetworkSpec(source=", ".join(n.source for n in parts),
                          header=dict(parts[0].header), coord_scale=parts[0].coord_scale)
        ignored = net.report["ignored"] = {}
        for n in parts:
            net.components += n.components
            net.skipped += n.skipped
            for t, k in n.report["ignored"].items():
                ignored[t] = ignored.get(t, 0) + k
            net.pipelines.update(n.pipelines)
            net.insulation_thickness.update(n.insulation_thickness)
            net.connections += n.connections
        net.read_args = called
        net.snap_tolerance = snap_tolerance
        return net
    path = Path(path)
    if not path.exists():
        raise ReaderFileNotFound(f"PCF file not found: {path}", code="pcf_file_not_found",
                                 where={"source": {"file": str(path)}},
                                 hint="check the path; relative paths are from the working "
                                      "directory")

    if ignore_types is None:
        ignore_types = {"SUPPORT", "BOLT", "INSTRUMENT-COMPONENT", "PIPE-DIRECTION-BREAK"}

    spec = NetworkSpec(source=str(path))
    records = list(_iter_records(path, spec))
    spec.coord_scale = scale = _coord_scale(spec.header, unit_scale)
    bore_scale = _bore_scale(spec.header)
    ignored = spec.report["ignored"] = {}
    inline_warned: set[str] = set()

    for record_type, attrs, pipeline, line in records:
        rtype = record_type.upper()
        n_end = len(attrs.get("END-POINT", []))
        if rtype in ignore_types or rtype in ANNOTATION_TYPES \
                or (rtype == "WELD" and n_end == 0 and "CO-ORDS" in attrs):
            ignored[rtype] = ignored.get(rtype, 0) + 1
            continue
        kind = _classify(rtype)
        if kind is None and n_end == 2:
            kind = _inline_kind(rtype, attrs, inline_warned)
        if kind is None:
            spec.skipped.append((record_type, attrs))
            warnings.warn(HexmeshWarning(
                f"Unsupported PCF component type '{record_type}' — skipped.",
                code="pcf_component_unsupported",
                where={"source": {"file": str(path), "record": record_type, "line": line}}),
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
            warnings.warn(HexmeshWarning(
                f"Component {record_type} has < 2 END-POINTs — skipped.",
                code="pcf_component_incomplete",
                where={"source": {"file": str(path), "record": record_type, "line": line}}),
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
            skey=str(attrs.get("SKEY", "")).strip().upper(), source=str(path), line=line,
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
    spec.read_args = called
    spec.snap_tolerance = snap_tolerance
    return spec


def _read_args(path, unit_scale, ignore_types, joint_max, snap_tolerance) -> dict:
    """``read_pcf``'s arguments as JSON data: the import log entry.  A log
    without ``snap_tolerance`` (before task 0138) re-reads with the default."""
    paths = path if isinstance(path, (list, tuple)) else [path]
    return {"source": [str(p) for p in paths],
            "options": {"unit_scale": unit_scale, "joint_max": joint_max,
                        "ignore_types": None if ignore_types is None else sorted(ignore_types),
                        "snap_tolerance": snap_tolerance}}


def _reread(source, options: dict) -> "_m.NetworkModel":
    """``model.IMPORTERS["pcf"]``: the model of a logged import."""
    opts = dict(options)
    if opts.get("ignore_types") is not None:
        opts["ignore_types"] = set(opts["ignore_types"])
    return read_pcf(source[0] if len(source) == 1 else list(source), **opts).to_model()


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
        raise ReaderError(f"UNITS-CO-ORDS {unit!r} not recognised; known: "
                          f"{', '.join(COORD_UNITS)}",
                          code="pcf_unit_unknown", where={"field": "UNITS-CO-ORDS"}, value=unit,
                          limit=sorted(COORD_UNITS))
    from_header = COORD_UNITS[unit.upper()] if unit else None
    if unit_scale is not None:
        if from_header is not None and not math.isclose(unit_scale, from_header):
            warnings.warn(HexmeshWarning(f"unit_scale={unit_scale} overrides UNITS-CO-ORDS {unit} "
                                         f"({from_header} m)",
                                         code="pcf_unit_scale_override",
                                         where={"field": "unit_scale"}, value=unit_scale,
                                         limit=from_header), stacklevel=3)
        return unit_scale
    if from_header is None:
        warnings.warn(HexmeshWarning("PCF has no UNITS-CO-ORDS header; reading coordinates and "
                                     "bore as millimetres",
                                     code="pcf_units_missing",
                                     where={"field": "UNITS-CO-ORDS"}), stacklevel=3)
        return 1e-3
    return from_header


def _bore_scale(header: dict) -> float:
    unit = header.get("UNITS-BORE")
    if unit is None:
        return 1e-3            # the missing header has already warned, or coords are mm
    if unit.upper() not in BORE_UNITS:
        raise ReaderError(f"UNITS-BORE {unit!r} not recognised; known: "
                          f"{', '.join(BORE_UNITS)}",
                          code="pcf_unit_unknown", where={"field": "UNITS-BORE"}, value=unit,
                          limit=sorted(BORE_UNITS))
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

#: Set-on SKEYs whose branch is tangential or offset (RESEARCH §3.1).  Offset ones
#: (TOSO, TORF) build as offset taps; tangential ones (TTSO, TTRF) fail the
#: offset range (decision 0031, task 0061).
OFFSET_SKEYS = {"TTSO", "TTRF", "TOSO", "TORF"}


def _classify(record_type: str) -> str | None:
    return _COMPONENT_MAP.get(record_type.upper())


def _inline_kind(rtype: str, attrs: dict, warned: set[str]) -> str:
    """The kind of an unknown record with two END-POINTs: an inline
    straight (same sizes), a reducer (different sizes), or ``"angled"``
    when its legs turn at CENTRE-POINT (rejected by ``to_assembly``).  One
    warning per type, in *warned*."""
    a, b = (np.array(e[:3], dtype=float) for e in attrs["END-POINT"])
    c = attrs.get("CENTRE-POINT")
    if c is not None and len(c) >= 3:
        c = np.array(c[:3], dtype=float)
        u, v = c - a, b - c
        if np.linalg.norm(u) > 1e-12 and np.linalg.norm(v) > 1e-12 \
                and _angle(u, v) > INLINE_ANGLE_TOL:
            return "angled"
    sizes = [e[3] if len(e) > 3 else None for e in attrs["END-POINT"]]
    kind = "reducer" if None not in sizes and not math.isclose(*sizes) else "fitting"
    if rtype not in warned:
        warned.add(rtype)
        what = "a reducer" if kind == "reducer" else "an inline straight"
        warnings.warn(HexmeshWarning(f"{rtype} treated as {what} (not a PCF type hexmesh knows; "
                                     f"two END-POINTs)",
                                     code="pcf_type_inferred", where={"source": {"record": rtype}},
                                     value=kind), stacklevel=3)
    return kind


def _angle(u: np.ndarray, v: np.ndarray) -> float:
    """Angle between *u* and *v*, degrees."""
    cos = float(np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v)))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


# A signed decimal number; the keywords themselves contain hyphens
# ("END-POINT"), so a bare character class would match them.
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _iter_records(path: Path, net: NetworkSpec) -> Iterator[tuple[str, dict, str, int]]:
    """Yield ``(record_type, attrs, pipeline, line)`` for each component
    record, *line* the 1-based line of its keyword.

    Header keywords go to ``net.header``, ``PIPELINE-REFERENCE`` blocks to
    ``net.pipelines``, connection and equipment blocks to
    ``net.connections`` (their attributes with ``_source`` and ``_line``);
    everything from ``MATERIALS`` on is skipped.
    """
    block: tuple[str, str] | None = None   # (kind, name): "component" | "pipeline" | "other"
    attrs: dict = {}
    endpoints: list[list[float]] = []
    epwords: list[list[str]] = []           # the words on each END-POINT line
    pipeline = ""
    in_header = True
    start = 0                               # the current block's keyword line

    def flush():
        if block is None:
            return
        kind, name = block
        a = dict(attrs)
        if endpoints:
            a["END-POINT"] = list(endpoints)
            a["END-POINT-WORDS"] = list(epwords)
        if kind == "component":
            yield name, a, pipeline, start
        elif kind == "pipeline":
            net.pipelines[name] = a
        elif kind == "other":
            a["_source"], a["_line"] = str(path), start
            net.connections.append((name, a))

    with path.open(encoding="utf-8") as fh:
        for number, raw_line in enumerate(fh, 1):
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
                    block, attrs, endpoints, start = ("pipeline", value), {}, [], number
                    continue
                if in_header and key not in _COMPONENT_MAP and key not in _NON_COMPONENTS \
                        and key not in ANNOTATION_TYPES:
                    net.header[key] = value
                    continue
                yield from flush()
                in_header = False
                kind = "other" if key in _NON_COMPONENTS else "component"
                block, attrs, endpoints, epwords = (kind, words[0]), {}, [], []
                start = number
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


# ---------------------------------------------------------------------------
# PCF records → the network model (decision 0032, task 0065)
# ---------------------------------------------------------------------------

FORMAT = "pcf"


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


def _file_line(prov) -> str:
    """``<file name>:<line>`` when the provenance has both, else ""."""
    return f"{Path(prov.source).name}:{prov.line}" if prov.source and prov.line else ""


def _format(part, at, name) -> str:
    """How messages name a PCF part: ``component <index> (<TYPE> <label>[,
    SKEY …] at <point>, <file>:<line>)``; an equipment connection by its
    record and ``CONNECTION-REFERENCE`` (and ``(<file>:<line>)``)."""
    prov = part.provenance
    at_line = _file_line(prov)
    if isinstance(part, _m.Terminal):
        return (f"{prov.record} {prov.record_id or '(no CONNECTION-REFERENCE)'}"
                + (f" ({at_line})" if at_line else ""))
    skey = dict(prov.attributes).get("skey")
    skey = f", SKEY {skey}" if skey else ""
    where = "" if at is None else f" at {np.round(at, 4)}"
    at_line = f", {at_line}" if at_line else ""
    return f"component {prov.record_id} ({part.type} {name}{skey}{where}{at_line})"


_m.register_formatter(FORMAT, _format)
_m.IMPORTERS[FORMAT] = _reread


def _bend_radius_attr(value: str, bore: float, coord_scale: float) -> float | None:
    """``BEND-RADIUS``: ``nD`` (multiple of nominal size) or an absolute
    radius in coordinate units; metres."""
    m = re.fullmatch(r"\s*([0-9.]+)\s*D\s*", value, re.I)
    if m:
        return float(m.group(1)) * bore if bore else None
    m = _NUMBER.match(value.strip())
    return float(m.group()) * coord_scale if m else None


def _stated(c: ComponentSpec, coord_scale: float) -> dict:
    """An elbow's ``ANGLE`` (hundredths of a degree) and ``BEND-RADIUS``,
    as ``Bend`` keywords; the builder cross-checks them."""
    out = {"stated_names": {"geometry": "its END-POINTs and CENTRE-POINT"}}
    m = _NUMBER.match(c.raw["ANGLE"].strip()) if "ANGLE" in c.raw else None
    if m:
        out["stated_angle"] = angle = float(m.group()) / 100.0
        out["stated_names"]["angle"] = f"ANGLE {angle:g}°"
    if "BEND-RADIUS" in c.raw:
        r = _bend_radius_attr(c.raw["BEND-RADIUS"], c.bore, coord_scale)
        if r is not None:
            out["stated_radius"] = r
            out["stated_names"]["radius"] = f"BEND-RADIUS {c.raw['BEND-RADIUS']}"
    return out


_PARTS = {"pipe": _m.Straight, "fitting": _m.InlineEquipment, "angled": _m.InlineEquipment,
          "elbow": _m.Bend, "reducer": _m.Reducer, "joint": _m.Joint,
          "tee": _m.Junction, "seton": _m.Junction, "ypiece": _m.Junction,
          "junction?": _m.Junction}
_JUNCTION_FORMS = {"tee": "tee", "seton": "tap", "ypiece": "wye", "junction?": "cross"}


def _to_model(net: NetworkSpec) -> "_m.NetworkModel":
    """*net*'s records as a ``NetworkModel``: one part per component (id =
    its index in the file), one ``Terminal`` per equipment connection, and
    the ``END-CONNECTION-PIPELINE`` points as declared connections."""
    model = _m.NetworkModel(report={"ignored": net.report.get("ignored", {})},
                            snap_tolerance=net.snap_tolerance, snap_source=FORMAT)
    if net.read_args:
        import_entry(model, FORMAT, net.read_args["source"], net.read_args["options"])
    for name, a in net.pipelines.items():
        model.networks[name] = _m.Network(
            name, kind="pipeline", insulation_thickness=net.insulation_thickness.get(name),
            attributes=dict(a))
    low = lambda status: status.lower() if status else None     # noqa: E731
    for i, (c, label) in enumerate(zip(net.components, _labels(net.components))):
        c.index = i
        prov = _m.Provenance(source=c.source or net.source, format=FORMAT,
                             record=c.record_type, record_id=str(i), line=c.line,
                             attributes=(("skey", c.skey),))

        def port(x, bore, status=None, flow=None):
            return model.add_port(x, section=_m.Section(nominal=bore) if bore else None,
                                  insulation=low(status), flow=flow, provenance=prov)
        flow = {"1": ("in", "out"), "2": ("out", "in")}.get(
            str(c.raw.get("FLOW", "")).strip(), (None, None))
        e_ins, b_ins = c.end_insulation, c.branch_insulation
        ports = [port(c.start, c.bore, e_ins[0], flow[0])]
        if c.kind in ("tee", "junction?") or c.kind not in _JUNCTION_FORMS:
            end_bore = c.end_bore if c.kind == "reducer" else c.bore
            ports.append(port(c.end, end_bore, e_ins[1], flow[1]))
        kw = {}
        if c.kind in _JUNCTION_FORMS:
            ports.append(port(c.branch, c.branch_bore, b_ins[0]))
            if c.branch2 is not None:
                ports.append(port(c.branch2, c.branch2_bore, b_ins[1]))
            kw = dict(form=_JUNCTION_FORMS[c.kind], centre=c.centre,
                      offset=c.kind == "seton" and c.skey in OFFSET_SKEYS)
        elif c.kind == "elbow":
            kw = dict(corner=c.centre, **_stated(c, net.coord_scale))
        elif c.kind == "reducer":
            kw = dict(eccentric=c.record_type == "REDUCER-ECCENTRIC")
        elif c.kind == "angled":
            kw = dict(reject=f"its ends turn {_angle(c.centre - c.start, c.end - c.centre):.1f}° "
                             f"at CENTRE-POINT; angle valves and other angled inline "
                             f"components are out of scope")
        if c.kind == "junction?":
            kw["reject"] = "crosses and Y-PIECE-FITTING are not supported (decision 0023)"
        model.add_part(_PARTS[c.kind], ports, id=str(i), name=label, type=c.record_type,
                       system=c.pipeline, insulation=low(c.insulation), attributes=c.raw,
                       provenance=prov, **kw)
    _terminals(net, model)
    _declared_connections(net, model)
    return model


def _terminals(net: NetworkSpec, model) -> None:
    """A ``Terminal`` per ``END-CONNECTION-EQUIPMENT`` (and column-1
    ``NOZZLE``) record, named ``<equipment>_<nozzle>``.  Its
    ``CONNECTION-REFERENCE`` is a nozzle ``REFERENCE`` of an
    ``EQUIPMENT-REFERENCE`` block (whose ``CO-ORDS`` the builder checks
    against the connection's), or ``<equipment>/<nozzle>``."""
    nozzles = {}
    for kind, a in net.connections:
        if kind.upper() == "EQUIPMENT-REFERENCE":
            for nz in a.get("NOZZLES", []):
                if nz.get("REFERENCE"):
                    nozzles[nz["REFERENCE"].strip()] = (a.get("EQUIPMENT-REFERENCE", ""), nz)
    for j, (kind, a) in enumerate(net.connections):
        if kind.upper() not in ("END-CONNECTION-EQUIPMENT", "NOZZLE"):
            continue
        ref = str(a.get("CONNECTION-REFERENCE", "")).strip()
        nz_point, eq, nozzle = None, "", ref
        if ref in nozzles:
            eq, nz = nozzles[ref]
            label = f"{_name(eq)}_{_name(ref)}" if _name(eq) else _name(ref)
            nz_point = nz.get("_point")
        elif "/" in ref:
            eq, nozzle = ref.split("/", 1)
            label = f"{_name(eq)}_{_name(nozzle)}"
        else:
            label = _name(ref) or "equipment"
        prov = _m.Provenance(source=a.get("_source", net.source), format=FORMAT,
                             record=kind.upper(), record_id=ref, line=a.get("_line"))
        port = model.add_port(a.get("_point"), equipment={"tag": eq, "nozzle": nozzle},
                              provenance=prov)
        model.add_part(_m.Terminal, [port], id=f"connection{j}", name=label,
                       type=kind.upper(), check_point=nz_point, provenance=prov)


def _declared_connections(net: NetworkSpec, model) -> None:
    """``END-CONNECTION-PIPELINE`` (at a point where two parts' ports meet,
    within the model's snap tolerance) → a declared ``Connection``.  The builder still
    joins parts by position; the record says the source meant it."""
    for kind, a in net.connections:
        x = a.get("_point")
        if kind.upper() != "END-CONNECTION-PIPELINE" or x is None:
            continue
        near = sorted((float(np.linalg.norm(p.position - x)), p.id)
                      for p in model.ports.values()
                      if p.position is not None and p.equipment is None
                      and np.linalg.norm(p.position - x) <= model.snap_tolerance)
        if len(near) >= 2:
            a_id, b_id = near[0][1], near[1][1]
            model.connections.append(_m.Connection(
                a_id, b_id, origin="declared",
                provenance=_m.Provenance(source=a.get("_source", net.source), format=FORMAT,
                                         record=kind.upper(), line=a.get("_line")),
                distance=float(np.linalg.norm(model.ports[a_id].position
                                              - model.ports[b_id].position))))
