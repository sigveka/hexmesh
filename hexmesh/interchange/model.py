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
The network model (decision 0032, item 3): a format-neutral description of
pipe and duct networks, between the importers and the builder.

A model is a graph of **ports** (points where parts meet, with an id),
**parts** (a closed set of types, each referencing its ports in order),
**connections** (port ↔ port, declared by the source or inferred) and
named **networks** (sets of parts).  Every node can carry **provenance**,
which error messages use to name the source of a problem.

The part classes share names with ``hexmesh.assembly``'s fittings
(``Straight``, ``Bend``, ``Reducer``); the module namespace tells them
apart: ``interchange.Straight`` is a part of a network, ``assembly.Straight``
a fitting of an assembly.  ``hexmesh`` itself doesn't re-export them.

Build an ``Assembly`` with ``hexmesh.interchange.build`` (or the
``to_assembly`` shorthand).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


# ---------------------------------------------------------------------------
# Sections and provenance
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Section:
    """A cross-section: a circle (nominal size and/or actual diameter) or a
    rectangle (width × height), metres.  ``bore`` is the nominal size, the
    one number PCF gives."""

    shape:    str = "circle"           # "circle" | "rect"
    nominal:  float | None = None      # nominal size (PCF bore)
    diameter: float | None = None      # actual outside diameter, if known
    width:    float | None = None      # rect
    height:   float | None = None      # rect

    @property
    def bore(self) -> float | None:
        return self.nominal


@dataclass(frozen=True)
class Provenance:
    """Where a port or part came from: the source file, its format, the
    record (type and id) and line, and a source GUID where one exists."""

    source: str = ""
    format: str = ""
    record: str = ""                   # record type, e.g. "TEE"
    record_id: str = ""                # e.g. the component index in the file
    line: int | None = None
    guid: str | None = None
    attributes: tuple = ()             # (key, value) pairs a formatter may use


#: format → ``f(part, at, name) -> str``: how messages name a part of that
#: format (decision 0032, item 2).  ``at``: the point to report (metres) or
#: None; ``name``: the label to use (a piece of a split part has its own).
#: Importers register theirs.
FORMATTERS: dict[str, Callable] = {}


def register_formatter(fmt: str, fn: Callable) -> None:
    """Name parts whose provenance has format *fmt* with ``fn(part, at, name)``."""
    FORMATTERS[fmt] = fn


#: ``"build"`` and ``"build_pieces"``: the builder registers them when it is
#: imported (``hexmesh.interchange`` imports it), so the model doesn't
#: import the module that imports it (no module cycle; DESIGN §3.1).
BUILDERS: dict[str, Callable] = {}
#: the model operations (``select``, ``cut``, …), registered by
#: ``hexmesh.interchange.operations`` the same way
OPERATIONS: dict[str, Callable] = {}
#: importer name → ``f(source, options) -> NetworkModel``: how ``replay``
#: re-reads the model a merged log entry came from.  Importers register theirs.
IMPORTERS: dict[str, Callable] = {}


def describe(part: "Part", at=None, name: str | None = None) -> str:
    """The part as messages name it: by its importer's formatter, or
    ``part <id> (<type> <name> at <point>)``."""
    name = name or part.name
    fmt = part.provenance.format if part.provenance else ""
    if fmt in FORMATTERS:
        return FORMATTERS[fmt](part, at, name)
    where = "" if at is None else f" at {np.round(at, 4)}"
    return f"part {part.id} ({part.type} {name}{where})"


# ---------------------------------------------------------------------------
# Ports, parts, connections, networks
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class Port:
    """A point where a part meets another, or an open end.

    ``flow``: "in" (flow enters the part here) or "out", when the source
    says; None otherwise.  ``insulation``: "on" / "off" overrides the
    part's status at this port; None follows the part.  ``equipment``: a
    tag ``{"tag": …, "nozzle": …}`` (decision 0032, item 7).  ``tag``: the
    name of the open end this port becomes at a cut or a selection's
    boundary (task 0066); None: ``<network>_<port id>``."""

    id:         str
    position:   np.ndarray | None
    direction:  np.ndarray | None = None
    flow:       str | None = None
    section:    Section | None = None
    insulation: str | None = None
    equipment:  dict | None = None
    provenance: Provenance | None = None
    tag:        str | None = None


@dataclass(eq=False)
class Part:
    """A part of a network, referencing its ports (by id) in order.

    ``name`` labels the fitting it becomes; ``type`` is the source's type
    name (e.g. "VALVE"); ``system`` the network (PCF pipeline) it belongs
    to, which names its open ends.  ``insulation``: "on" / "off" / None
    (absent: bare).  ``reject``: why the builder must refuse it (the
    importer read it, but hexmesh can't build it), or None."""

    id:         str
    ports:      list[str]
    name:       str = ""
    type:       str = ""
    system:     str = ""
    insulation: str | None = None
    attributes: dict = field(default_factory=dict)
    provenance: Provenance | None = None
    reject:     str | None = None


@dataclass(eq=False)
class Straight(Part):
    """A straight run between its two ports."""


@dataclass(eq=False)
class InlineEquipment(Part):
    """A valve, flange, instrument, …: meshed as a straight run."""


@dataclass(eq=False)
class Bend(Part):
    """A bend between its two ports.  ``corner``: where the tangent legs
    meet (PCF's CENTRE-POINT).  ``stated_angle`` (degrees) and
    ``stated_radius`` (metres), when the source states them, are checked
    against the corner geometry; ``stated_names`` says how messages name
    them (e.g. ``{"radius": "BEND-RADIUS 3D"}``)."""

    corner:        np.ndarray | None = None
    stated_angle:  float | None = None
    stated_radius: float | None = None
    stated_names:  dict = field(default_factory=dict)


@dataclass(eq=False)
class Reducer(Part):
    """A change of size between its two ports (their sections)."""

    eccentric: bool = False


@dataclass(eq=False)
class Transition(Reducer):
    """A change of shape (circle ↔ rectangle) between its two ports."""


@dataclass(eq=False)
class Junction(Part):
    """Three or more legs meeting at ``centre``.  ``form``:

    - "tee": ports (run in, run out, branch);
    - "tap": a branch set on a straight (set-on, stub, olet): ports (the
      point on the host straight, the branch);
    - "wye": at the end of its stem straight: ports (stem, branch 1,
      branch 2), branch 1 the "right" daughter;
    - "cross": read, not buildable.

    ``offset``: a tap whose branch is tangential or off-centre (not
    buildable: a Tee branch is perpendicular and centred)."""

    form:   str = "tee"
    centre: np.ndarray | None = None
    offset: bool = False


@dataclass(eq=False)
class Joint(Part):
    """A weld, gasket, coupling or gap: absorbed into the adjacent run."""


@dataclass(eq=False)
class Terminal(Part):
    """An open end attached to equipment: one port, carrying the tag
    (``Port.equipment``), and the patch name in ``name``.  The builder
    attaches it to the open end at its port within the tolerance.
    ``check_point``: a second position the source gives (a nozzle's
    coordinates), which must agree."""

    check_point: np.ndarray | None = None


@dataclass(eq=False)
class Polyline(Part):
    """A route through its ports in order (bathymetry routes, centrelines):
    built as straights between consecutive ports, joined by splines where
    they turn (``kinks="spline"``)."""


PART_TYPES = (Straight, InlineEquipment, Bend, Reducer, Transition, Junction, Joint,
              Terminal, Polyline)


@dataclass(eq=False)
class Connection:
    """Port ↔ port.  ``origin``: "declared" by the source (or a user), or
    "inferred" from positions within ``distance``; ``provenance``: the
    record that declared it."""

    a:        str
    b:        str
    origin:   str = "inferred"
    distance: float = 0.0
    provenance: Provenance | None = None


@dataclass(eq=False)
class Cut:
    """Ports *a* and *b*, which meet, are not connected (task 0066): the
    builder leaves both as open ends.  Made by ``NetworkModel.cut`` and
    ``cut_at``, undone by ``join``."""

    a: str
    b: str


class Selection(frozenset):
    """Part ids to build (``NetworkModel.select``; ``build`` takes it like
    any set of ids).  ``how``: the arguments that made it, by id, which
    ``build`` records in ``model.report["selection"]``."""

    how: dict

    def __new__(cls, ids, how: dict | None = None):
        self = super().__new__(cls, ids)
        self.how = dict(how or {})
        return self


@dataclass(eq=False)
class Network:
    """A named set of parts (a PCF pipeline, an IFC system).  ``kind``:
    what the source calls it ("pipeline", "system"), for messages.
    ``insulation_thickness``: metres, for its insulated parts."""

    name:  str
    parts: set = field(default_factory=set)
    kind:  str = "network"
    insulation_thickness: float | None = None
    attributes: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class NetworkModel:
    """Ports, parts (in source order), connections and networks.

    ``report`` collects what the importer and the builder found (records
    ignored, the tolerance used, joints absorbed, …).  ``cuts``: the
    ``Cut``s made.  ``log``: the operations applied, in order (task 0066;
    decision 0032, settled 2026-10-29).  The importer writes the first
    entry, and ``cut``, ``cut_at``, ``join`` and ``merge`` append theirs.
    Each entry has ``op``, ``args`` (by id), ``time`` and ``version``."""

    ports:       dict = field(default_factory=dict)       # id → Port
    parts:       dict = field(default_factory=dict)       # id → Part, source order
    connections: list = field(default_factory=list)
    networks:    dict = field(default_factory=dict)       # name → Network
    report:      dict = field(default_factory=dict)
    cuts:        list = field(default_factory=list)
    log:         list = field(default_factory=list)

    # --- construction ------------------------------------------------------

    def add_port(self, position, **kw) -> Port:
        """A new port with a fresh id (``p<n>``), or ``id=`` given."""
        pid = kw.pop("id", None) or self._fresh("p", self.ports)
        port = Port(pid, None if position is None else np.asarray(position, dtype=float), **kw)
        if pid in self.ports:
            from ..assembly import AssemblyError
            raise AssemblyError(f"port id {pid!r} is already used",
                                code="model_id_duplicate", where={"field": "id"}, value=pid)
        self.ports[pid] = port
        return port

    def add_part(self, cls, positions_or_ports, **kw) -> Part:
        """A new part of class *cls* (``Straight``, ``Bend``, …) through new
        ports at *positions* (or existing ``Port``s), in order.  Keywords
        go to the part; ``id=`` sets its id (default ``<n>``)."""
        if cls not in PART_TYPES:
            from ..assembly import AssemblyTypeError
            raise AssemblyTypeError(f"{cls!r} is not a network-model part type",
                                    code="model_part_type_unknown", value=repr(cls))
        ports = [p if isinstance(p, Port) else self.add_port(p)
                 for p in positions_or_ports]
        pid = kw.pop("id", None) or self._fresh("", self.parts)
        if pid in self.parts:
            from ..assembly import AssemblyError
            raise AssemblyError(f"part id {pid!r} is already used",
                                code="model_id_duplicate", where={"field": "id"}, value=pid)
        part = cls(pid, [p.id for p in ports], **kw)
        if not part.type:
            part.type = cls.__name__.upper()
        if not part.name:
            part.name = f"{part.type}_{pid}"
        self.parts[pid] = part
        if part.system:
            self.networks.setdefault(part.system, Network(part.system)).parts.add(pid)
        return part

    @staticmethod
    def _fresh(prefix: str, used: dict) -> str:
        for n in itertools.count(len(used)):
            if f"{prefix}{n}" not in used:
                return f"{prefix}{n}"

    # --- access ------------------------------------------------------------

    def port(self, pid: str) -> Port:
        return self.ports[pid]

    def positions(self, part: Part) -> list:
        return [self.ports[p].position for p in part.ports]

    # --- operations (task 0066; hexmesh.interchange.operations) --------------

    def select(self, parts=None, *, network: str | None = None, from_port: str | None = None,
               up_to=()) -> Selection:
        """The parts to build, as a ``Selection``: give one of *parts* (ids),
        *network* (a name) or *from_port*.

        *from_port*: the parts reachable from that port, starting with its
        own part and never crossing back through it.  *up_to*: port ids
        not crossed, and part ids that are included but not crossed.
        Attached terminals come with the parts.  Not logged; ``build``
        records it in ``model.report["selection"]``.

        >>> side = model.select(from_port="p0", up_to=["7"])   # up to the valve
        >>> asm = build(model, spec, side)
        """
        return OPERATIONS["select"](self, parts, network, from_port, up_to)

    def cut(self, connection) -> Cut:
        """Disconnect two ports that meet: *connection* is a ``Connection``
        or a pair of port ids.  Both become open ends, named by their
        ``tag`` or ``<network>_<port id>``.  Logged.

        >>> model.cut(("p13", "p14"))
        """
        return OPERATIONS["cut"](self, connection)

    def cut_at(self, port: str, names: tuple | None = None) -> list:
        """Disconnect *port* from every port it meets, and return the
        ``Cut``s.  *names*: tags for (*port*, the other port), with one
        other port only.  Logged.

        >>> model.cut_at("p14", names=("to_valve", "from_valve"))
        """
        return OPERATIONS["cut_at"](self, port, names)

    def join(self, port_a: str, port_b: str, *, tol: float | None = None) -> Connection:
        """Connect two open ports, and return the declared ``Connection``.

        The ports must lie within *tol* (default: the builder's tolerance
        for this model), point in opposite directions (within
        ``JOIN_ANGLE_TOL`` degrees) and have the same section; otherwise
        ``AssemblyError`` gives the numbers.  A cut between them is undone.
        The builder joins ports within its own tolerance, so a *tol* above
        it needs ``build(..., tol=...)`` too.  Logged.

        >>> model.join("p13", "p14")
        """
        return OPERATIONS["join"](self, port_a, port_b, tol)

    @staticmethod
    def merge(a: "NetworkModel", b: "NetworkModel", *, prefix: str | None = None,
              infer: bool = False, tol: float | None = None) -> "NetworkModel":
        """A new model: the union of *a* and *b*, which aren't changed.

        Ids are kept.  A port or part id in both raises ``AssemblyError``
        listing them, unless *prefix* is given: then *b*'s ids get it.
        Networks of one name are united.  *infer*: add an inferred
        ``Connection`` between each open port of *a* and one of *b* within
        *tol*; otherwise connect them with ``join``.  The log is *a*'s, then
        a ``merge`` entry holding *b*'s log.

        >>> line = NetworkModel.merge(sheet1, sheet2, prefix="s2_")
        >>> line.join("p9", "s2_p0")
        """
        return OPERATIONS["merge"](a, b, prefix, infer, tol)

    def replay(self, source: "NetworkModel") -> "NetworkModel":
        """Apply this model's logged operations (after its import entry) to
        *source*, a fresh import of the same file, in place; return it.  A
        ``merge`` entry re-reads its other model through its importer.

        >>> fresh = read_pcf("line.pcf").to_model()
        >>> model.replay(fresh)
        """
        return OPERATIONS["replay"](self, source)

    def undo(self) -> None:
        """Undo the last logged operation: the model as it was before it, by
        replaying all but the last entry on the state before the first."""
        OPERATIONS["undo"](self)

    # --- building ----------------------------------------------------------

    def to_assembly(self, spec, **options):
        """``hexmesh.interchange.build(self, spec, **options)``."""
        return BUILDERS["build"](self, spec, **options)

    def to_assemblies(self, spec, **options) -> dict:
        """``hexmesh.interchange.build_pieces(self, spec, **options)``: one
        ``Assembly`` per connected piece."""
        return BUILDERS["build_pieces"](self, spec, **options)
