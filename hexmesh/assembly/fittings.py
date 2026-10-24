"""
Fittings — fills between existing interface faces (DESIGN.md §6, rule A2).

Every fitting implements the contract:

``ports(inlet, spec)``      Topology.  Poses and types of the outlet ports,
                            computed from the inlet frame.  Pure numpy.
``validate(frames, spec)``  Topology.  Raise ``ValueError`` if the fitting
                            cannot be built between these frames.
``fill(faces, frames, spec, lc)``
                            Realisation.  Build *internal* entities only,
                            between the given existing port faces.

The single-path fittings here are sweeps (DESIGN.md §6.1): each describes
its ``Path`` and inherits ``validate`` / ``fill`` from ``Sweep``.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

import numpy as np

from ..core.spec import PipeSpec
from .interface import Frame, outer_radius, roll_mismatch, rotate
from .sweep import Arc, FillResult, Path, Sweep

__all__ = ["Straight", "Bend", "MiterBend", "Elbow", "Closure", "FillResult"]


# ---------------------------------------------------------------------------
# Straight
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Straight(Sweep):
    """Straight pipe run between two parallel interfaces."""

    length:   float
    n_layers: int

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal,
                    inlet.normal, inlet.up)
        return [(out, spec)]

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if self.length <= 0:
            raise ValueError(f"length must be positive, got {self.length!r}")

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        return Path([a, b], [self.n_layers])


# ---------------------------------------------------------------------------
# Bend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Bend(Sweep):
    """Circular-arc bend whose mesh nodes lie exactly on the true geometry.

    A station is placed at every axial layer and stations are joined by
    circular arcs about the bend axis, so every mesh node lies on a station
    face or an axial arc and wall nodes are exactly on the torus.

    (Exact OCC side surfaces via trimmed revolutions were tried and rejected:
    OCC fails to trim revolutions of the off-centre inner-square arcs and,
    at large angles, re-creates boundary curves instead of reusing them.)

    Parameters
    ----------
    radius : float
        Centreline bend radius [m]; must exceed the pipe outer radius.
    angle : float
        Bend angle in degrees.
    n_layers : int
        Total hex layers along the arc.
    roll : float
        Bend-plane rotation about the pipe axis in degrees
        (0 = bend toward ``up``).
    """

    radius:   float
    angle:    float
    n_layers: int
    roll:     float = 0.0

    def _axis_centre(self, inlet: Frame) -> tuple[np.ndarray, np.ndarray]:
        phi = math.radians(self.roll)
        axis = math.cos(phi) * inlet.right - math.sin(phi) * inlet.up
        centre = inlet.position + self.radius * (
            math.cos(phi) * inlet.up + math.sin(phi) * inlet.right
        )
        return axis, centre

    def _rotated(self, inlet: Frame, angle_deg: float) -> Frame:
        axis, centre = self._axis_centre(inlet)
        a = math.radians(angle_deg)
        return Frame(
            centre + rotate(inlet.position - centre, axis, a),
            rotate(inlet.normal, axis, a),
            rotate(inlet.up, axis, a),
        )

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        return [(self._rotated(inlet, self.angle), spec)]

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if not 0 < abs(self.angle) < 360:
            raise ValueError(f"angle must be in (0, 360) degrees, got {self.angle!r}")

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        n = self.n_layers
        inner = [self._rotated(a, self.angle * k / n) for k in range(1, n)]
        axis, centre = self._axis_centre(a)
        return Path([a, *inner, b], [1] * n, axial=Arc(axis, centre),
                    min_radius=self.radius)


# ---------------------------------------------------------------------------
# Miter bend
# ---------------------------------------------------------------------------

# Direction change allowed at one miter cut.  Hexes next to a cut are skewed
# by half the cut angle; a single 90° cut keeps minSICN ≈ 0.19, and below
# 1° the legs collapse to sliver cells (measured, docs/tasks/0012).
MAX_MITER_CUT = 90.0   # degrees
MIN_MITER_CUT = 1.0    # degrees


@dataclass(frozen=True)
class MiterBend(Sweep):
    """Segmented (mitred) bend: straight pipe pieces joined at planar cuts.

    The centreline is the tangent polygon of the smooth bend with the same
    *radius* and *angle*: ``n_cuts`` cuts each turn ``angle / n_cuts``, the
    end legs are half segments, and the ports are exactly those of
    ``Bend(radius, angle, roll=roll)``.  Each cut face lies in the plane
    bisecting its turn; it is the station face stretched into the exact
    ellipse where the two cylinders meet, so wall nodes on a cut lie on
    both pipes.

    Parameters
    ----------
    radius : float
        Centreline radius of the equivalent smooth bend; must exceed the pipe
        outer radius (the end legs are ``radius * tan(cut / 2)`` long).
    angle : float
        Total bend angle in degrees.
    n_cuts : int
        Number of cuts (welds); 1 is a single miter joint.
    n_layers : int
        Axial layers of each end leg; inner segments, twice as long, get
        ``2 * n_layers``.  Every layer is its own station (see ``path``).
    roll : float
        Bend-plane rotation about the pipe axis in degrees, as for ``Bend``.
    """

    radius:   float
    angle:    float
    n_cuts:   int = 1
    n_layers: int = 2
    roll:     float = 0.0

    @property
    def _arc(self) -> Bend:
        return Bend(self.radius, self.angle, 1, self.roll)

    @property
    def cut_angle(self) -> float:
        return self.angle / self.n_cuts

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        return self._arc.ports(inlet, spec)

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if self.n_cuts < 1:
            raise ValueError(f"n_cuts must be >= 1, got {self.n_cuts!r}")
        if not 0 < abs(self.angle) < 360:
            raise ValueError(f"angle must be in (0, 360) degrees, got {self.angle!r}")
        if abs(self.cut_angle) < MIN_MITER_CUT:
            raise ValueError(
                f"each cut turns {abs(self.cut_angle):.4g}°, below "
                f"{MIN_MITER_CUT:.0f}°; use fewer cuts or a Straight"
            )
        if abs(self.cut_angle) > MAX_MITER_CUT:
            raise ValueError(
                f"each cut turns {abs(self.cut_angle):.4g}° (limit "
                f"{MAX_MITER_CUT:.0f}°); use n_cuts >= "
                f"{math.ceil(abs(self.angle) / MAX_MITER_CUT)}"
            )

    def corners(self, inlet: Frame) -> list[np.ndarray]:
        """Centreline polygon from the inlet: inlet position, then each cut."""
        arc = self._arc
        _, centre = arc._axis_centre(inlet)
        half = math.radians(self.cut_angle) / 2
        out = [inlet.position]
        for j in range(self.n_cuts):
            f = arc._rotated(inlet, self.cut_angle * (j + 0.5))
            out.append(centre + (f.position - centre) / math.cos(half))
        return out

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        """Tangent polygon with one station per axial layer.

        Along a segment, station planes tilt about the bend axis from one
        cut plane to the next.  Each is the segment's circular section
        projected along the segment axis onto that plane, i.e. the station
        face stretched by ``1 / cos(tilt)``, so every wall node lies on an
        exact station curve and every axial edge runs parallel to the axis.
        """
        arc, n = self._arc, self.n_cuts
        axis, _ = arc._axis_centre(a)
        beta = math.radians(self.cut_angle)
        corners = self.corners(a) + [b.position]

        frames, stretch = [], []
        for j in range(n + 1):                       # segment j, after j cuts
            seg = arc._rotated(a, self.cut_angle * j)
            t0 = 0.0 if j == 0 else -beta / 2        # tilt at the segment ends
            t1 = 0.0 if j == n else beta / 2
            m = self.n_layers * (1 if j in (0, n) else 2)
            for k in range(m + 1):
                if k == 0 and j > 0:
                    continue                         # shared with the previous segment
                u = k / m
                tilt = t0 + (t1 - t0) * u
                pos = corners[j] + (corners[j + 1] - corners[j]) * u
                normal = rotate(seg.normal, axis, tilt)
                frames.append(Frame(pos, normal, rotate(seg.up, axis, tilt)))
                stretch.append(None if tilt == 0.0 else
                               (np.cross(axis, normal), 1.0 / math.cos(tilt)))
        frames[0], frames[-1] = a, b
        return Path(frames, [1] * (len(frames) - 1), min_radius=self.radius,
                    stretch=stretch, prism=True)


# ---------------------------------------------------------------------------
# Elbow
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Elbow(Sweep):
    """Standard butt-weld elbow: a ``Bend`` whose radius follows the pipe.

    ``schedule="long"`` gives a centreline radius of 1.5 D, ``"short"`` 1 D
    (ASME B16.9 long- and short-radius elbows), with D the outer diameter
    of the inlet spec.  The radius therefore needs the spec and is resolved
    in ``ports`` / ``validate``.
    """

    angle:    float = 90.0
    schedule: str = "long"
    n_layers: int = 8
    roll:     float = 0.0

    FACTORS = {"long": 1.5, "short": 1.0}

    def radius(self, spec: PipeSpec) -> float:
        return self.FACTORS[self.schedule] * 2 * outer_radius(spec)

    def bend(self, spec: PipeSpec) -> Bend:
        return Bend(self.radius(spec), self.angle, self.n_layers, self.roll)

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        return self.bend(spec).ports(inlet, spec)

    def check(self, spec: PipeSpec) -> None:
        if self.schedule not in self.FACTORS:
            raise ValueError(
                f"schedule must be one of {sorted(self.FACTORS)}, got {self.schedule!r}"
            )
        self.bend(spec).check(spec)

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        return self.bend(spec).path(a, b, spec)


# ---------------------------------------------------------------------------
# Closure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Closure(Sweep):
    """Smooth run between two *existing* interfaces — closes loops.

    Only usable through ``Assembly.close()``: both ports are given, so
    ``ports()`` is undefined.  The centreline is a cubic Hermite curve that
    leaves the source along its normal and arrives at the target along its
    normal.  Stations equidistribute arc length plus turning angle, so
    sharp turns get more stations.  Cross-section frames are
    parallel-transported (no spurious twist) and the residual roll mismatch
    — modulo the ``2π / n_outer`` symmetry of the cross-section — is
    distributed linearly by arc length.

    Parameters
    ----------
    n_layers : int
        Hex layers along the run.
    tension : float
        End-tangent magnitude as a multiple of the chord length.  Larger
        values keep the run straighter near its ends.
    """

    n_layers: int
    tension:  float = 1.0

    places_outlet = False
    _SAMPLES = 2000

    def ports(self, inlet: Frame, spec: PipeSpec):
        raise TypeError("Closure joins two existing interfaces; use Assembly.close()")

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if self.tension <= 0:
            raise ValueError(f"tension must be positive, got {self.tension!r}")

    # -- centreline -----------------------------------------------------

    def _hermite(self, a: Frame, b: Frame, t: np.ndarray):
        """Position, first and second derivative at parameters *t*."""
        p0, p1 = a.position, b.position
        L = np.linalg.norm(p1 - p0)
        m0 = self.tension * L * a.normal
        m1 = self.tension * L * b.normal
        t = t[:, None]
        t2, t3 = t * t, t * t * t
        pos = ((2*t3 - 3*t2 + 1) * p0 + (t3 - 2*t2 + t) * m0
               + (-2*t3 + 3*t2) * p1 + (t3 - t2) * m1)
        d1 = ((6*t2 - 6*t) * p0 + (3*t2 - 4*t + 1) * m0
              + (-6*t2 + 6*t) * p1 + (3*t2 - 2*t) * m1)
        d2 = ((12*t - 6) * p0 + (6*t - 4) * m0
              + (-12*t + 6) * p1 + (6*t - 2) * m1)
        return pos, d1, d2

    def _min_bend_radius(self, a: Frame, b: Frame) -> float:
        t = np.linspace(0.0, 1.0, self._SAMPLES)
        _, d1, d2 = self._hermite(a, b, t)
        speed = np.linalg.norm(d1, axis=1)
        if speed.min() < 1e-12:
            return 0.0
        kappa = np.linalg.norm(np.cross(d1, d2), axis=1) / speed**3
        return float(1.0 / kappa.max()) if kappa.max() > 0 else math.inf

    def stations(self, a: Frame, b: Frame, n_outer: int) -> tuple[list[Frame], float]:
        """Station frames (inclusive of both ends) and the absorbed twist."""
        t = np.linspace(0.0, 1.0, self._SAMPLES)
        pos, d1, _ = self._hermite(a, b, t)
        seg = np.linalg.norm(np.diff(pos, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        # Stations equidistribute arc length + turning angle (equal weight),
        # so sharp turns get proportionally more stations.
        td = d1 / np.linalg.norm(d1, axis=1)[:, None]
        dtheta = np.arccos(np.clip(np.sum(td[:-1] * td[1:], axis=1), -1, 1))
        theta = np.concatenate([[0.0], np.cumsum(dtheta)])
        m = s / s[-1] + (theta / theta[-1] if theta[-1] > 1e-12 else 0.0)
        ts = np.interp(np.linspace(0.0, m[-1], self.n_layers + 1), m, t)
        targets = np.interp(ts, t, s)          # arc length at each station
        P, D, _ = self._hermite(a, b, ts)
        T = D / np.linalg.norm(D, axis=1)[:, None]
        T[0], T[-1] = a.normal, b.normal

        # Parallel transport of up (Bishop frame).
        ups = [a.up]
        for k in range(1, len(T)):
            axis = np.cross(T[k - 1], T[k])
            n = np.linalg.norm(axis)
            u = ups[-1]
            if n > 1e-14:
                u = rotate(u, axis / n, math.atan2(n, np.dot(T[k - 1], T[k])))
            u = u - np.dot(u, T[k]) * T[k]
            ups.append(u / np.linalg.norm(u))

        twist = roll_mismatch(ups[-1], b.up, b.normal, n_outer)
        frames = []
        for k in range(len(T)):
            u = rotate(ups[k], T[k], twist * targets[k] / targets[-1])
            frames.append(Frame(P[k], T[k], u))
        frames[0], frames[-1] = a, b
        return frames, twist

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        if np.linalg.norm(b.position - a.position) < 1e-12:
            raise ValueError("source and target interfaces coincide")
        frames, _ = self.stations(a, b, spec.n_outer)
        return Path(frames, [1] * self.n_layers,
                    min_radius=self._min_bend_radius(a, b))
