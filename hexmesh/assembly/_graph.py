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
Building an assembly's graph: its fittings and interfaces (task 0136).
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, replace
from pathlib import PurePath
from typing import Iterable

from .errors import AssemblyError, AssemblyTypeError
from ..core.spec import PipeSpec
from .fittings import Straight
from . import limits
from .interface import Frame, Interface, check_supported, hydraulic_diameter, rolled, toward_roll


def _at(origin: dict | None) -> str:
    """``", <file name>:<line>"`` for an *origin* with both, else ""."""
    if not origin or not origin.get("file") or not origin.get("line"):
        return ""
    return f", {PurePath(origin['file']).name}:{origin['line']}"


@dataclass(eq=False)
class Edge:
    """A fitting placed between its port interfaces (ports[0] = inlet).

    ``origin``: where an importer read the fitting from (``file``,
    ``line``, ``record``, ``record_id``; task 0096).  Diagnostic only: its
    errors carry it in ``where["source"]`` and name ``<file>:<line>``; it
    is never saved (``to_dict``, the ``.msh`` recipe) or compared."""

    index:   int
    fitting: object
    ports:   list[Interface]
    kind:    str = "add"     # "add", "close" or "prepend": how it entered the graph
    label:   str | None = None
    origin:  dict | None = None

    @property
    def name(self) -> str:
        """``label``, or ``<Type><index>`` (``Bend3``): used in wall patch names."""
        return self.label or f"{type(self.fitting).__name__}{self.index}"

    @property
    def at(self) -> str:
        """``", <file>:<line>"`` from ``origin``, or ""."""
        return _at(self.origin)

    @property
    def where(self) -> dict:
        """The fitting's location for an error's ``where``."""
        return {"fitting": self.index, "label": self.name,
                **({"source": dict(self.origin)} if self.origin else {})}

    def __repr__(self) -> str:
        return f"fitting #{self.index} {self.fitting!r}{self.at}"


def add(asm, source, fitting=None, names: Iterable[str] | dict | None = None,
        label: str | None = None, origin: dict | None = None):
    if asm._faces_built:
        raise AssemblyError("cannot add fittings after the assembly is built",
                            code="assembly_already_built")
    if fitting is None:
        source, fitting, update_tail = asm._tail, source, True
    else:
        update_tail = False
    if source is None:
        raise AssemblyError("the tail was closed; pass the interface to add from",
                            code="tail_closed", hint="pass the interface to add from")
    if not isinstance(source, Interface):
        raise AssemblyTypeError(f"source must be an Interface, got {type(source).__name__}",
                                code="source_not_interface", where={"field": "source"})
    _check_degree(asm, source, "inlet", fitting)
    origin = None if origin is None else dict(origin)
    asm._twist_for_toward(fitting, source)
    fitting = _resolved(asm, fitting, source, origin=origin)

    port_list = fitting.ports(source.frame, source.spec)
    names = _port_names(fitting, names, len(port_list))
    outlets = [
        asm._new_interface(frame, spec, name)
        for (frame, spec), name in zip(port_list, names)
    ]
    _check_label(asm, label)
    edge = Edge(len(asm._edges), fitting, [source, *outlets], label=label, origin=origin)
    asm._edges.append(edge)
    for iface in edge.ports:
        iface.edges.append(edge)

    if update_tail:
        asm._tail = outlets[0]
    return outlets[0] if len(outlets) == 1 else outlets


def close(asm, source: Interface, target: Interface, fitting,
          label: str | None = None, origin: dict | None = None) -> None:
    if asm._faces_built:
        raise AssemblyError("cannot add fittings after the assembly is built",
                            code="assembly_already_built")
    for iface in (source, target):
        if not any(iface is i for i in asm._interfaces):
            raise AssemblyError(f"{iface} does not belong to this assembly",
                                code="interface_not_in_assembly",
                                where={"interface": iface.index})
        if not iface.is_open:
            raise AssemblyError(f"{iface} is not an open interface",
                                code="interface_not_open", where={"interface": iface.index})
    if source is target:
        raise AssemblyError("cannot close an interface onto itself",
                            code="close_onto_itself", where={"interface": source.index})
    if source.edges[0].ports[0] is source:
        raise AssemblyError(f"source {source} is an upstream end, not an outlet",
                            code="close_source_not_outlet", where={"interface": source.index})
    if target.edges[0].ports[0] is not target:
        raise AssemblyError(f"target {target} is a downstream end, not an inlet",
                            code="close_target_not_inlet", where={"interface": target.index})
    _check_degree(asm, source, "inlet", fitting)
    _check_degree(asm, target, "outlet", fitting)
    origin = None if origin is None else dict(origin)
    fitting = _resolved(asm, fitting, source, target, origin=origin)

    _check_label(asm, label)
    edge = Edge(len(asm._edges), fitting, [source, target], kind="close", label=label,
                origin=origin)
    asm._edges.append(edge)
    source.edges.append(edge)
    target.edges.append(edge)
    if asm._tail is source:
        asm._tail = None


def prepend(asm, fitting: Straight, label: str | None = None,
            origin: dict | None = None) -> Interface:
    if asm._faces_built:
        raise AssemblyError("cannot add fittings after the assembly is built",
                            code="assembly_already_built")
    if type(fitting) is not Straight:
        raise AssemblyTypeError(
            f"prepend places a Straight only, got {type(fitting).__name__}",
            code="prepend_needs_straight")
    old = asm.inlet
    if not old.is_open:
        raise AssemblyError(f"the inlet {old} is not an open end",
                            code="interface_not_open", where={"interface": old.index})
    if old.equipment:
        raise AssemblyError(f"the inlet {old} is an equipment end (a drum nozzle or "
                            "a PCF equipment connection); "
                            "nothing can be placed upstream of it",
                            code="prepend_at_equipment_end", where={"interface": old.index})
    _check_degree(asm, old, "outlet", fitting)
    origin = None if origin is None else dict(origin)
    fitting = _resolved(asm, fitting, old, origin=origin)   # the length: not the frame
    f = old.frame
    frame = Frame(f.position - fitting.length * f.normal, f.normal, f.up)
    new = asm._new_interface(frame, old.spec, old.name)
    old.name = None
    _check_label(asm, label)
    edge = Edge(len(asm._edges), fitting, [new, old], kind="prepend", label=label,
                origin=origin)
    asm._edges.append(edge)
    new.edges.append(edge)
    old.edges.append(edge)
    asm.inlet = new
    return new


def extend_open_ends(asm, upstream: float = 5.0, downstream: float = 10.0,
                     cells_per_diameter: float = 4.0) -> None:
    if asm._faces_built:
        raise AssemblyError("cannot add fittings after the assembly is built",
                            code="assembly_already_built")
    if upstream < 0 or downstream < 0 or cells_per_diameter <= 0:
        raise AssemblyError("upstream and downstream must be >= 0, "
                            "and cells_per_diameter > 0",
                            code="extend_args_invalid",
                            value={"upstream": upstream, "downstream": downstream,
                                   "cells_per_diameter": cells_per_diameter})

    def run(iface, diameters):
        d = hydraulic_diameter(iface.spec)
        n = max(1, round(diameters * cells_per_diameter))
        return Straight(diameters * d, n_layers=n)

    outlets = [i for i in asm.open_interfaces()
               if i is not asm.inlet and not i.equipment]
    names = {i.index: asm.patch_name(i) for i in outlets}
    if downstream > 0:
        for iface in outlets:
            out = asm.add(iface, run(iface, downstream))
            out.name, iface.name = names[iface.index], None
            if asm._tail is iface:
                asm._tail = out
    if upstream > 0 and asm.inlet.is_open and not asm.inlet.equipment:
        asm.prepend(run(asm.inlet, upstream))


def _check_label(asm, label: str | None) -> None:
    if label is None:
        return
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_]+", label):
        raise AssemblyError(
            f"fitting label {label!r} must be letters, digits and _ only "
            "(it becomes part of a patch name)", code="label_invalid", where={"label": label})
    if any(e.name == label for e in asm._edges):
        raise AssemblyError(f"fitting label {label!r} is already used",
                            code="label_duplicate", where={"label": label})


def _twist_for_toward(asm, fitting, source: Interface) -> None:
    """A junction's ``toward`` between its allowed rolls (task 0062):
    twist the ``Straight`` that ends at *source* by the remainder, so
    the junction's roll is a multiple of the period.  Only an untwisted
    straight added before it, whose outlet is *source*; otherwise
    raises, naming the twist and where to put it."""
    offset = getattr(fitting, "toward_offset", None)
    if offset is None or getattr(fitting, "toward", None) is None or fitting.roll != 0:
        return                  # not a junction's toward, or junction_toward rejects it
    P = math.degrees(source.spec.period)
    rest = math.remainder(toward_roll(source.frame, fitting.toward) - offset, P)
    if abs(rest) <= limits.JUNCTION_TOWARD_TOL:
        return                  # junction_toward snaps it
    name = type(fitting).__name__
    edge = source.edges[0] if len(source.edges) == 1 else None
    if (edge is None or edge.kind != "add" or type(edge.fitting) is not Straight
            or edge.ports[-1] is not source or edge.fitting.twist):
        raise AssemblyError(
            f"{name}: toward is {abs(rest):.3g}° from the nearest allowed roll (rolls are "
            f"multiples of the section's period {P:g}°), and there is no untwisted "
            f"Straight ending at {source} to take the rest",
            code="toward_off_allowed", where={"field": "toward"}, value=abs(rest),
            limit="JUNCTION_TOWARD_TOL",
            hint=f"add Straight(…, twist={rest:.6g}) before the {name}")
    straight = replace(edge.fitting, twist=rest)
    try:
        straight.check(edge.ports[0].spec)
    except AssemblyError as e:
        raise AssemblyError.wrap(
            e, f"{name}: toward needs {edge} twisted by {rest:.4g}°: {e}",
            code="toward_off_allowed", edge=edge.index) from None
    edge.fitting = straight
    source.frame = rolled(source.frame, rest)


def _resolved(asm, fitting, source: Interface, target: Interface | None = None,
              origin: dict | None = None):
    """*fitting* with input-only fields resolved at *source* (and
    *target*, for ``close``).  Angled fittings warn from their
    ``resolve`` on an angle that looks like radians (decision 0024)."""
    resolve = getattr(fitting, "resolve", None)
    if resolve is not None:
        try:
            # before resolve(), which may build the fitting's block layout
            # (a Tee's shortest run): an unsupported section is named
            # first (task 0106)
            check_supported(source.spec)
            fitting = resolve(source.frame, source.spec, asm.axial_cell,
                              None if target is None else target.frame)
        except ValueError as e:
            raise AssemblyError.wrap(e, f"{fitting!r} at {source}{_at(origin)}: {e}",
                                     code="fitting_invalid", interface=source.index,
                                     **({"source": origin} if origin else {})) from None
    return fitting


def _port_names(fitting, names, n: int) -> list:
    """Outlet names as a list in port order, from a list or a dict keyed
    by ``fitting.port_names``."""
    if names is None:
        return [None] * n
    ports = tuple(getattr(fitting, "port_names", ()))
    if isinstance(names, dict):
        unknown = sorted(set(names) - set(ports))
        if unknown or len(ports) != n:
            raise AssemblyError(
                f"{type(fitting).__name__} has ports {', '.join(ports)}; "
                f"unknown port name(s) {', '.join(map(repr, unknown))}",
                code="port_name_unknown", value=unknown, limit=list(ports))
        return [names.get(k) for k in ports]
    names = list(names)
    if len(names) != n:
        raise AssemblyError(
            f"{type(fitting).__name__} has {n} outlet(s) "
            f"({', '.join(ports)}); got {len(names)} names",
            code="port_names_count", value=len(names), limit=n)
    return names


def _attached(iface: Interface, role: str) -> list[Edge]:
    """Fittings having *iface* as their inlet, or as one of their outlets."""
    if role == "inlet":
        return [e for e in iface.edges if e.ports[0] is iface]
    return [e for e in iface.edges if any(p is iface for p in e.ports[1:])]


def _check_degree(asm, iface: Interface, role: str, fitting) -> None:
    """An interface is the inlet of at most one fitting and the outlet of
    at most one (DESIGN §5: a face shared by two fittings at most)."""
    attached = _attached(iface, role)
    if attached:
        raise AssemblyError(
            f"{iface} (interface #{iface.index}) is already the {role} of "
            f"{attached[0]}; it cannot also be the {role} of {fitting!r}",
            code="interface_degree", where={"interface": iface.index})


def _new_interface(asm, frame: Frame, spec: PipeSpec, name: str | None) -> Interface:
    iface = Interface(len(asm._interfaces), frame, spec, name)
    asm._interfaces.append(iface)
    return iface
