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
Equipment nozzles as network boundaries (decision 0002, docs/tasks/0010).

A ``Drum`` is an Intent-layer node: it owns nozzle *poses* and builds no
geometry.  ``Drum.frame(name)`` gives the interface frame of a nozzle face,
and ``Assembly.from_nozzle(drum, name)`` starts a network there.

Conventions
-----------
* The drum axis runs from the **first** tangent plane (at ``position``) to
  the **second** (at ``position + length · axis``).  The first head lies
  beyond the first tangent plane (``-axis``), the second beyond the second.
* Angular positions are measured about ``axis`` from ``up``, right-handed:
  the radial direction at ``angle`` is ``cos·up + sin·(axis × up)``.
  Angles are in degrees, as in ``Bend``.
* A nozzle frame's ``normal`` points away from the drum, the direction a
  pipe leaves in.  Its ``up`` is the drum axis for a shell nozzle, and the
  head's radial direction for a head nozzle (the drum ``up`` when the
  nozzle is centred).

Head profiles
-------------
The height ``h(ρ)`` of the head surface above its tangent plane, at
distance ``ρ`` from the axis (``R = diameter / 2``):

* ``"ellipsoidal_2_1"``: semi-axes ``R`` and ``R / 2`` (depth D/4),
  ``h = (R/2)·sqrt(1 − ρ²/R²)``;
* ``"hemispherical"``: depth R, ``h = sqrt(R² − ρ²)``;
* ``"torispherical"``: a crown sphere of radius ``crown_radius`` joined
  tangentially to a knuckle torus of radius ``knuckle_radius``.  There is
  no default for either: the proportions depend on the design code
  (ASME VIII, EN 13445, …), so both must be given.

All lengths are in the user's unit, inside dimensions, no wall thickness.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

from ..errors import HexmeshError, InternalError
from ..core.params import param
from ..core.spec import PipeSpec
from .interface import Frame, outer_radius

HEADS = ("ellipsoidal_2_1", "hemispherical", "torispherical")


class EquipmentError(HexmeshError):
    """Invalid equipment or nozzle; the message names the drum and nozzle."""


def _safe_name(name, fallback: str) -> str:
    """*name* with every character a patch name can't hold made ``_``."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name) if isinstance(name, str) and name else fallback


@dataclass(frozen=True)
class OnShell:
    """Radial nozzle on the cylindrical shell.

    *axial*: distance of the nozzle axis from the first tangent plane;
    *angle*: degrees about the drum axis from the drum ``up``;
    *projection*: distance from the drum axis to the nozzle face.
    """

    axial:      float = param("length", "nozzle axis from the first tangent plane")
    angle:      float = param("deg", "about the drum axis, from the drum's up")
    projection: float = param("length", "drum axis to the nozzle face", exclusiveMinimum=0)


@dataclass(frozen=True)
class OnHead:
    """Nozzle on a head, parallel to the drum axis.

    *head*: ``"first"`` or ``"second"``;
    *offset*: distance of the nozzle axis from the drum axis;
    *angle*: degrees about the drum axis from the drum ``up`` (ignored for
    a centred nozzle);
    *projection*: distance from the head's tangent plane to the nozzle
    face.
    """

    head:       str = param("-", "the head the nozzle is on", enum=["first", "second"])
    offset:     float = param("length", "nozzle axis from the drum axis", minimum=0)
    angle:      float = param("deg",
                              "about the drum axis, from the drum's up (ignored if centred)")
    projection: float = param("length", "head's tangent plane to the nozzle face",
                              exclusiveMinimum=0)


@dataclass(frozen=True)
class Nozzle:
    """A named nozzle with the cross-section of the pipe it connects to."""

    name:     str = param("-", "nozzle name, unique on its drum")
    spec:     PipeSpec = param("-", "cross-section of the pipe it connects to")
    location: OnShell | OnHead = param("-", "where on the drum: on the shell or on a head")


@dataclass(frozen=True)
class Drum:
    """Horizontal or vertical drum: a cylinder between two heads.

    *diameter* is the inside diameter, *length* the tangent-to-tangent
    length, *position* the centre of the first tangent plane.  *axis* and
    *up* are normalised, and *up* is made perpendicular to *axis*.
    """

    name:      str = param("-", "drum name: letters, digits and _ (part of patch names)")
    diameter:  float = param("length", "inside diameter", exclusiveMinimum=0)
    length:    float = param("length", "tangent-to-tangent length", exclusiveMinimum=0)
    position:  tuple = param("length", "centre of the first tangent plane",
                             default=(0.0, 0.0, 0.0))
    axis:      tuple = param("direction", "drum axis direction", default=(1.0, 0.0, 0.0))
    up:        tuple = param("direction", "up direction, made perpendicular to axis",
                             default=(0.0, 0.0, 1.0))
    head:      str = param("-", "head type", default="ellipsoidal_2_1", enum=list(HEADS))
    crown_radius:   float | None = param("length", "torispherical heads: crown radius",
                                         default=None, exclusiveMinimum=0)
    knuckle_radius: float | None = param("length", "torispherical heads: knuckle radius",
                                         default=None, exclusiveMinimum=0)
    nozzles:   tuple = param("-", "the drum's nozzles", default=())
    _frame:    Frame = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", self.name or ""):
            raise EquipmentError(
                f"drum name {self.name!r} must be letters, digits and _ only "
                "(it becomes part of a patch name)",
                code="drum_name_invalid", where={"part": self.name, "field": "name"},
                value=self.name, hint=f"e.g. name={_safe_name(self.name, 'drum_1')!r}")
        if self.diameter <= 0 or self.length <= 0:
            raise EquipmentError(f"drum {self.name}: diameter and length must be positive",
                                 code="size_not_positive",
                                 where={"part": self.name, "field": "diameter, length"},
                                 value=(self.diameter, self.length), limit={"min_exclusive": 0})
        if self.head not in HEADS:
            raise EquipmentError(f"drum {self.name}: head must be one of {HEADS}, "
                                 f"got {self.head!r}",
                                 code="option_invalid", where={"part": self.name, "field": "head"},
                                 value=self.head, limit=list(HEADS))
        if self.head == "torispherical":
            self._check_torispherical()
        elif self.crown_radius is not None or self.knuckle_radius is not None:
            raise EquipmentError(f"drum {self.name}: crown_radius and knuckle_radius "
                                 "apply to torispherical heads only",
                                 code="drum_head_args_invalid",
                                 where={"part": self.name, "field": "crown_radius"},
                                 hint="drop crown_radius and knuckle_radius, or use "
                                      "head='torispherical'")
        a = np.asarray(self.axis, dtype=float)
        u = np.asarray(self.up, dtype=float)
        if np.linalg.norm(a) == 0:
            raise EquipmentError(f"drum {self.name}: axis is zero",
                                 code="drum_axis_zero", where={"part": self.name, "field": "axis"})
        a = a / np.linalg.norm(a)
        u = u - np.dot(u, a) * a
        if np.linalg.norm(u) < 1e-9:
            e = np.zeros(3)
            e[int(np.argmin(np.abs(a)))] = 1
            raise EquipmentError(f"drum {self.name}: up is parallel to the axis",
                                 code="drum_up_parallel", where={"part": self.name, "field": "up"},
                                 hint=f"e.g. up={tuple(int(x) for x in e)}")
        object.__setattr__(self, "_frame", Frame(
            np.asarray(self.position, dtype=float), a, u / np.linalg.norm(u)))
        object.__setattr__(self, "nozzles", tuple(self.nozzles))
        names = [n.name for n in self.nozzles]
        for n in names:
            if not re.fullmatch(r"[A-Za-z0-9_]+", n or ""):
                raise EquipmentError(f"drum {self.name}: nozzle name {n!r} must be "
                                     "letters, digits and _ only",
                                     code="nozzle_name_invalid",
                                     where={"part": self.name, "field": "nozzles"}, value=n,
                                     hint=f"e.g. {_safe_name(n, 'N1')!r}")
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise EquipmentError(f"drum {self.name}: duplicate nozzle names {dup}",
                                 code="nozzle_name_duplicate",
                                 where={"part": self.name, "field": "nozzles"}, value=dup,
                                 hint=f"rename one of each, e.g. {dup[0]}_2")
        for n in self.nozzles:                  # the schema's ranges (task 0095)
            loc = n.location
            checks = [("projection", loc.projection, {"min_exclusive": 0})]
            if isinstance(loc, OnHead):
                checks.append(("offset", loc.offset, {"min": 0}))
            for field_, v, lim in checks:
                if not (v > 0 if "min_exclusive" in lim else v >= 0):
                    raise EquipmentError(
                        f"drum {self.name}: nozzle {n.name} {field_} must be "
                        f"{'positive' if 'min_exclusive' in lim else 'non-negative'}, got {v!r}",
                        code="size_not_positive",
                        where={"part": self.name, "nozzle": n.name, "field": field_},
                        value=v, limit=lim)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    @property
    def radius(self) -> float:
        return self.diameter / 2.0

    def _check_torispherical(self) -> None:
        R, L, r = self.radius, self.crown_radius, self.knuckle_radius
        if L is None or r is None:
            raise EquipmentError(
                f"drum {self.name}: a torispherical head needs crown_radius and "
                "knuckle_radius (no default: they depend on the design code)",
                code="drum_head_args_invalid", where={"part": self.name, "field": "crown_radius"},
                hint=f"e.g. a Klöpper head (DIN 28011): crown_radius={2 * R:g}, "
                     f"knuckle_radius={0.2 * R:g}")
        if not (0 < r < R < L):
            raise EquipmentError(
                f"drum {self.name}: torispherical head needs 0 < knuckle_radius "
                f"< D/2 < crown_radius, got {r}, {R}, {L}",
                code="drum_head_args_invalid",
                where={"part": self.name, "field": "knuckle_radius"}, value=(r, R, L),
                hint="; ".join([f"knuckle_radius in (0, {R:g})"] * (not 0 < r < R)
                               + [f"crown_radius above {R:g}"] * (not R < L)))

    @property
    def crown_limit(self) -> float:
        """Largest radius of the head's main (crown) region.

        The crown/knuckle junction for a torispherical head; ``D/2``
        otherwise.
        """
        if self.head != "torispherical":
            return self.radius
        R, L, r = self.radius, self.crown_radius, self.knuckle_radius
        return (R - r) * L / (L - r)

    def head_height(self, rho: float) -> float:
        """Height of the head surface above its tangent plane at radius *rho*."""
        R = self.radius
        rho = abs(rho)
        if rho > R:
            raise InternalError(f"radius {rho} is outside the drum (R = {R})")
        if self.head == "ellipsoidal_2_1":
            return 0.5 * R * math.sqrt(max(0.0, 1.0 - (rho / R) ** 2))
        if self.head == "hemispherical":
            return math.sqrt(max(0.0, R * R - rho * rho))
        L, r = self.crown_radius, self.knuckle_radius
        if rho <= self.crown_limit:
            z0 = -math.sqrt((L - r) ** 2 - (R - r) ** 2)   # crown centre, inside the drum
            return z0 + math.sqrt(L * L - rho * rho)
        return math.sqrt(max(0.0, r * r - (rho - (R - r)) ** 2))

    def radial(self, angle: float) -> np.ndarray:
        """Unit radial direction at *angle* degrees about the axis from ``up``."""
        f = self._frame
        t = math.radians(angle)
        return math.cos(t) * f.up + math.sin(t) * np.cross(f.normal, f.up)

    def nozzle(self, name: str) -> Nozzle:
        for n in self.nozzles:
            if n.name == name:
                return n
        raise EquipmentError(f"drum {self.name} has no nozzle {name!r}; "
                             f"it has {[n.name for n in self.nozzles]}",
                             code="nozzle_unknown", where={"part": self.name}, value=name,
                             limit=[n.name for n in self.nozzles])

    def frame(self, name: str) -> Frame:
        """Interface frame of nozzle *name*'s face (see module conventions)."""
        loc = self.nozzle(name).location
        f = self._frame
        if isinstance(loc, OnShell):
            e = self.radial(loc.angle)
            return Frame(f.position + loc.axial * f.normal + loc.projection * e,
                         e, f.normal.copy())
        if loc.head == "first":
            base, out = f.position, -f.normal
        elif loc.head == "second":
            base, out = f.position + self.length * f.normal, f.normal.copy()
        else:
            raise EquipmentError(f"drum {self.name}, nozzle {name}: head must be "
                                 f"'first' or 'second', got {loc.head!r}",
                                 code="option_invalid",
                                 where={"part": self.name, "label": name, "field": "head"},
                                 value=loc.head, limit=["first", "second"])
        e = self.radial(loc.angle)
        up = e if loc.offset > 0 else f.up.copy()
        return Frame(base + loc.projection * out + loc.offset * e, out, up)

    # ------------------------------------------------------------------
    # Validation (no GMSH)
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Check every nozzle; raise EquipmentError naming drum and nozzle."""
        R = self.radius
        for n in self.nozzles:
            where = f"drum {self.name}, nozzle {n.name}"
            for i, (lname, o) in enumerate(zip(n.spec.layer_names, n.spec.outlines)):
                if not o.is_round:
                    raise EquipmentError(f"{where}: drum nozzles are circular pipes, "
                                         f"layer `{lname}` is a {type(o).__name__}",
                                         code="nozzle_not_circular",
                                         where={"part": self.name, "label": n.name},
                                         hint=f"give layer `{lname}` "
                                              f"{'dR=' if i else 'radius='} (a circle)")
            r = outer_radius(n.spec)
            if r >= R:
                raise EquipmentError(f"{where}: outer radius {r} is not below the "
                                     f"drum radius {R}",
                                     code="nozzle_too_large",
                                     where={"part": self.name, "label": n.name}, value=r,
                                     limit={"max_exclusive": R},
                                     hint=f"a nozzle outer radius below {R:g}, or a drum "
                                          f"diameter above {2 * r:g}")
            loc = n.location
            if isinstance(loc, OnShell):
                # The intersection with the shell reaches at most R along
                # the nozzle axis (RESEARCH §3.1).
                if loc.projection <= R:
                    raise EquipmentError(f"{where}: projection {loc.projection} must "
                                         f"exceed the drum radius {R}, or the face "
                                         "is inside the shell",
                                         code="nozzle_projection_too_short",
                                         where={"part": self.name, "label": n.name,
                                                "field": "projection"},
                                         value=loc.projection, limit={"min_exclusive": R})
                if loc.axial - r < 0 or loc.axial + r > self.length:
                    raise EquipmentError(f"{where}: footprint (axial {loc.axial} ± {r}) "
                                         f"crosses a tangent line (0 … {self.length})",
                                         code="nozzle_footprint_outside",
                                         where={"part": self.name, "label": n.name,
                                                "field": "axial"},
                                         value=loc.axial,
                                         hint=(f"axial between {r:g} and {self.length - r:g}"
                                               if self.length >= 2 * r else
                                               f"a drum length of at least {2 * r:g}"))
            elif isinstance(loc, OnHead):
                self.frame(n.name)                      # checks loc.head
                if loc.offset < 0:
                    raise EquipmentError(f"{where}: offset must be >= 0",
                                         code="nozzle_footprint_outside",
                                         where={"part": self.name, "label": n.name,
                                                "field": "offset"},
                                         value=loc.offset, limit={"min": 0})
                if loc.offset + r > self.crown_limit:
                    region = "crown region" if self.head == "torispherical" else "head"
                    raise EquipmentError(f"{where}: footprint (offset {loc.offset} + {r}) "
                                         f"leaves the {region} (radius {self.crown_limit:.6g})",
                                         code="nozzle_footprint_outside",
                                         where={"part": self.name, "label": n.name,
                                                "field": "offset"},
                                         value=loc.offset, limit={"max": self.crown_limit - r},
                                         hint=(f"offset at most {self.crown_limit - r:.6g}"
                                               if self.crown_limit >= r else
                                               f"a nozzle outer radius below "
                                               f"{self.crown_limit:.6g}, or OnShell"))
                # h(ρ) falls with ρ, so the highest point of the footprint
                # is at its innermost radius.
                top = self.head_height(max(0.0, loc.offset - r))
                if loc.projection <= top:
                    raise EquipmentError(f"{where}: projection {loc.projection} must "
                                         f"exceed the head height {top:.6g} over the "
                                         "footprint, or the face is inside the head",
                                         code="nozzle_projection_too_short",
                                         where={"part": self.name, "label": n.name,
                                                "field": "projection"},
                                         value=loc.projection, limit={"min_exclusive": float(top)})
            else:
                raise EquipmentError(f"{where}: unknown location {loc!r}",
                                     code="nozzle_location_unknown",
                                     where={"part": self.name, "label": n.name},
                                     hint="OnShell(axial=, angle=, projection=) or "
                                          "OnHead(head=, offset=, angle=, projection=)")
        self._check_overlaps()

    def _check_overlaps(self) -> None:
        shell = [n for n in self.nozzles if isinstance(n.location, OnShell)]
        for i, a in enumerate(shell):
            for b in shell[i + 1:]:
                if self._shell_overlap(a, b):
                    gap = outer_radius(a.spec) + outer_radius(b.spec)
                    raise EquipmentError(f"drum {self.name}: footprints of nozzles "
                                         f"{a.name} and {b.name} overlap",
                                         code="nozzle_footprints_overlap",
                                         where={"part": self.name}, value=[a.name, b.name],
                                         hint=f"axial positions at least {gap:g} apart (now "
                                              f"{abs(a.location.axial - b.location.axial):g}), "
                                              "or their angles further apart")
        for head in ("first", "second"):
            on = [n for n in self.nozzles
                  if isinstance(n.location, OnHead) and n.location.head == head]
            for i, a in enumerate(on):
                for b in on[i + 1:]:
                    # Axis-parallel nozzles: footprints are discs in the
                    # tangent-plane projection.
                    ca = a.location.offset * self.radial(a.location.angle)
                    cb = b.location.offset * self.radial(b.location.angle)
                    gap = outer_radius(a.spec) + outer_radius(b.spec)
                    if np.linalg.norm(ca - cb) < gap:
                        raise EquipmentError(f"drum {self.name}: footprints of nozzles "
                                             f"{a.name} and {b.name} overlap",
                                             code="nozzle_footprints_overlap",
                                             where={"part": self.name}, value=[a.name, b.name],
                                             hint=f"nozzle axes at least {gap:g} apart (now "
                                                  f"{np.linalg.norm(ca - cb):.6g})")

    def _shell_overlap(self, a: Nozzle, b: Nozzle, n: int = 720) -> bool:
        """Do two radial shell footprints overlap?

        A point (s, θ) of the shell lies in the footprint of a nozzle at
        (s0, θ0) with radius r when (s − s0)² + (R sin(θ − θ0))² < r² on
        the near side, cos(θ − θ0) > 0.  The footprints overlap when a
        boundary point of one lies inside the other.
        """
        R = self.radius

        def boundary(z):
            r = outer_radius(z.spec)
            phi = np.linspace(0, 2 * np.pi, n, endpoint=False)
            return (z.location.axial + r * np.cos(phi),
                    math.radians(z.location.angle) + np.arcsin(r * np.sin(phi) / R))

        def inside(z, s, t):
            r = outer_radius(z.spec)
            d = t - math.radians(z.location.angle)
            return ((s - z.location.axial) ** 2 + (R * np.sin(d)) ** 2 < r * r) & (np.cos(d) > 0)

        return bool(inside(b, *boundary(a)).any() or inside(a, *boundary(b)).any())

    # ------------------------------------------------------------------
    # Serialisation (docs/tasks/0006)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        def loc(l):
            if isinstance(l, OnShell):
                return {"type": "shell", "axial": l.axial, "angle": l.angle,
                        "projection": l.projection}
            return {"type": "head", "head": l.head, "offset": l.offset,
                    "angle": l.angle, "projection": l.projection}
        return {
            "name": self.name, "diameter": self.diameter, "length": self.length,
            "position": [float(x) for x in self.position],
            "axis": [float(x) for x in self.axis], "up": [float(x) for x in self.up],
            "head": self.head, "crown_radius": self.crown_radius,
            "knuckle_radius": self.knuckle_radius,
            "nozzles": [{"name": n.name, "spec": n.spec.to_dict(),
                         "location": loc(n.location)} for n in self.nozzles],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Drum":
        def loc(l):
            l = dict(l)
            kind = l.pop("type")
            return OnShell(**l) if kind == "shell" else OnHead(**l)
        d = dict(d)
        nozzles = tuple(Nozzle(n["name"], PipeSpec.from_dict(n["spec"]), loc(n["location"]))
                        for n in d.pop("nozzles", []))
        for k in ("position", "axis", "up"):
            d[k] = tuple(d[k])
        return cls(**d, nozzles=nozzles)
