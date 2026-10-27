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

from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .interface import Frame, outer_radius

HEADS = ("ellipsoidal_2_1", "hemispherical", "torispherical")


class EquipmentError(ValueError):
    """Invalid equipment or nozzle; the message names the drum and nozzle."""


@dataclass(frozen=True)
class OnShell:
    """Radial nozzle on the cylindrical shell.

    *axial*: distance of the nozzle axis from the first tangent plane;
    *angle*: degrees about the drum axis from the drum ``up``;
    *projection*: distance from the drum axis to the nozzle face.
    """

    axial:      float
    angle:      float
    projection: float


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

    head:       str
    offset:     float
    angle:      float
    projection: float


@dataclass(frozen=True)
class Nozzle:
    """A named nozzle with the cross-section of the pipe it connects to."""

    name:     str
    spec:     PipeSpec
    location: OnShell | OnHead


@dataclass(frozen=True)
class Drum:
    """Horizontal or vertical drum: a cylinder between two heads.

    *diameter* is the inside diameter, *length* the tangent-to-tangent
    length, *position* the centre of the first tangent plane.  *axis* and
    *up* are normalised, and *up* is made perpendicular to *axis*.
    """

    name:      str
    diameter:  float
    length:    float
    position:  tuple = (0.0, 0.0, 0.0)
    axis:      tuple = (1.0, 0.0, 0.0)
    up:        tuple = (0.0, 0.0, 1.0)
    head:      str = "ellipsoidal_2_1"
    crown_radius:   float | None = None
    knuckle_radius: float | None = None
    nozzles:   tuple = ()
    _frame:    Frame = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", self.name or ""):
            raise EquipmentError(
                f"drum name {self.name!r} must be letters, digits and _ only "
                "(it becomes part of a patch name)")
        if self.diameter <= 0 or self.length <= 0:
            raise EquipmentError(f"drum {self.name}: diameter and length must be positive")
        if self.head not in HEADS:
            raise EquipmentError(f"drum {self.name}: head must be one of {HEADS}, "
                                 f"got {self.head!r}")
        if self.head == "torispherical":
            self._check_torispherical()
        elif self.crown_radius is not None or self.knuckle_radius is not None:
            raise EquipmentError(f"drum {self.name}: crown_radius and knuckle_radius "
                                 "apply to torispherical heads only")
        a = np.asarray(self.axis, dtype=float)
        u = np.asarray(self.up, dtype=float)
        if np.linalg.norm(a) == 0:
            raise EquipmentError(f"drum {self.name}: axis is zero")
        a = a / np.linalg.norm(a)
        u = u - np.dot(u, a) * a
        if np.linalg.norm(u) < 1e-9:
            raise EquipmentError(f"drum {self.name}: up is parallel to the axis")
        object.__setattr__(self, "_frame", Frame(
            np.asarray(self.position, dtype=float), a, u / np.linalg.norm(u)))
        object.__setattr__(self, "nozzles", tuple(self.nozzles))
        names = [n.name for n in self.nozzles]
        for n in names:
            if not re.fullmatch(r"[A-Za-z0-9_]+", n or ""):
                raise EquipmentError(f"drum {self.name}: nozzle name {n!r} must be "
                                     "letters, digits and _ only")
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise EquipmentError(f"drum {self.name}: duplicate nozzle names {dup}")

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
                "knuckle_radius (no default: they depend on the design code)")
        if not (0 < r < R < L):
            raise EquipmentError(
                f"drum {self.name}: torispherical head needs 0 < knuckle_radius "
                f"< D/2 < crown_radius, got {r}, {R}, {L}")

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
            raise ValueError(f"radius {rho} is outside the drum (R = {R})")
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
                             f"it has {[n.name for n in self.nozzles]}")

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
                                 f"'first' or 'second', got {loc.head!r}")
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
            if not isinstance(n.spec.core_shape, CircleShape):
                raise EquipmentError(f"{where}: drum nozzles are circular pipes, "
                                     f"got a {type(n.spec.core_shape).__name__} core")
            r = outer_radius(n.spec)
            if r >= R:
                raise EquipmentError(f"{where}: outer radius {r} is not below the "
                                     f"drum radius {R}")
            loc = n.location
            if isinstance(loc, OnShell):
                # The intersection with the shell reaches at most R along
                # the nozzle axis (RESEARCH §3.1).
                if loc.projection <= R:
                    raise EquipmentError(f"{where}: projection {loc.projection} must "
                                         f"exceed the drum radius {R}, or the face "
                                         "is inside the shell")
                if loc.axial - r < 0 or loc.axial + r > self.length:
                    raise EquipmentError(f"{where}: footprint (axial {loc.axial} ± {r}) "
                                         f"crosses a tangent line (0 … {self.length})")
            elif isinstance(loc, OnHead):
                self.frame(n.name)                      # checks loc.head
                if loc.offset < 0:
                    raise EquipmentError(f"{where}: offset must be >= 0")
                if loc.offset + r > self.crown_limit:
                    region = "crown region" if self.head == "torispherical" else "head"
                    raise EquipmentError(f"{where}: footprint (offset {loc.offset} + {r}) "
                                         f"leaves the {region} (radius {self.crown_limit:.6g})")
                # h(ρ) falls with ρ, so the highest point of the footprint
                # is at its innermost radius.
                top = self.head_height(max(0.0, loc.offset - r))
                if loc.projection <= top:
                    raise EquipmentError(f"{where}: projection {loc.projection} must "
                                         f"exceed the head height {top:.6g} over the "
                                         "footprint, or the face is inside the head")
            else:
                raise EquipmentError(f"{where}: unknown location {loc!r}")
        self._check_overlaps()

    def _check_overlaps(self) -> None:
        shell = [n for n in self.nozzles if isinstance(n.location, OnShell)]
        for i, a in enumerate(shell):
            for b in shell[i + 1:]:
                if self._shell_overlap(a, b):
                    raise EquipmentError(f"drum {self.name}: footprints of nozzles "
                                         f"{a.name} and {b.name} overlap")
        for head in ("first", "second"):
            on = [n for n in self.nozzles
                  if isinstance(n.location, OnHead) and n.location.head == head]
            for i, a in enumerate(on):
                for b in on[i + 1:]:
                    # Axis-parallel nozzles: footprints are discs in the
                    # tangent-plane projection.
                    ca = a.location.offset * self.radial(a.location.angle)
                    cb = b.location.offset * self.radial(b.location.angle)
                    if np.linalg.norm(ca - cb) < outer_radius(a.spec) + outer_radius(b.spec):
                        raise EquipmentError(f"drum {self.name}: footprints of nozzles "
                                             f"{a.name} and {b.name} overlap")

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
