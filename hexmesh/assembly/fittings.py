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

from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .interface import Frame, outer_radius, roll_mismatch, rotate
from .sweep import Arc, FillResult, Path, Sweep, _radii

__all__ = ["Straight", "Bend", "MiterBend", "Elbow", "Reducer", "SplinePipe",
           "Closure", "FillResult"]


# ---------------------------------------------------------------------------
# Straight
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Straight(Sweep):
    """Straight pipe run between two parallel interfaces.

    *axial_grading* is the ratio of consecutive axial cell lengths, inlet →
    outlet (1 = uniform; > 1 refines toward the inlet).

    *stack_changes* ends or starts outer layers inside the run (decision
    0006): each ``(i, spec)`` gives the stack from axial cell *i* on
    (``0 < i < n_layers``).  ``((3, bare), (7, insulated))`` with
    ``n_layers=10`` leaves a bare gap of cells 3–6.  The outlet port carries
    the last stack.
    """

    strategies = frozenset({0, 1})   # switch classes it bridges (DESIGN A4)

    length:   float
    n_layers: int
    axial_grading: float = 1.0
    stack_changes: tuple = ()

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal,
                    inlet.normal, inlet.up)
        return [(out, self.outlet_spec(spec))]

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if self.length <= 0:
            raise ValueError(f"length must be positive, got {self.length!r}")

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        if not self.stack_changes:
            return Path([a, b], [self.n_layers], axial_grading=self.axial_grading)
        # A station at each change; graded sub-slabs continue the same
        # progression, so the nodes are those of the unsplit run.
        cuts = [0] + [i for i, _ in self.stack_changes] + [self.n_layers]
        u = self.fractions(self.n_layers)
        frames = [a] + [Frame(a.position + (b.position - a.position) * u[i],
                              a.normal, a.up) for i in cuts[1:-1]] + [b]
        path = Path(frames, list(np.diff(cuts)), axial_grading=self.axial_grading)
        return self.stacked(path, spec)


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
    axial_grading : float
        Ratio of consecutive axial cell lengths, inlet → outlet (1 =
        uniform; > 1 refines toward the inlet).  Stations are spaced accordingly.
    stack_changes : tuple
        ``(i, spec)`` pairs ending or starting outer layers from axial cell
        *i* on, as for ``Straight`` (decision 0006).
    """

    strategies = frozenset({0, 1})   # switch classes it bridges (DESIGN A4)

    radius:   float
    angle:    float
    n_layers: int
    roll:     float = 0.0
    axial_grading: float = 1.0
    stack_changes: tuple = ()

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
        return [(self._rotated(inlet, self.angle), self.outlet_spec(spec))]

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if not 0 < abs(self.angle) < 360:
            raise ValueError(f"angle must be in (0, 360) degrees, got {self.angle!r}")

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        n = self.n_layers
        u = self.fractions(n)
        inner = [self._rotated(a, self.angle * u[k]) for k in range(1, n)]
        axis, centre = self._axis_centre(a)
        return self.stacked(Path([a, *inner, b], [1] * n, axial=Arc(axis, centre),
                                 min_radius=self.radius), spec)


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

    strategies = frozenset({0})   # switch classes it bridges (DESIGN A4)

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

    strategies = frozenset({0})   # switch classes it bridges (DESIGN A4)

    angle:    float = 90.0
    schedule: str = "long"
    n_layers: int = 8
    roll:     float = 0.0
    axial_grading: float = 1.0

    FACTORS = {"long": 1.5, "short": 1.0}

    def radius(self, spec: PipeSpec) -> float:
        return self.FACTORS[self.schedule] * 2 * outer_radius(spec)

    def bend(self, spec: PipeSpec) -> Bend:
        return Bend(self.radius(spec), self.angle, self.n_layers, self.roll,
                    self.axial_grading)

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
# Reducer
# ---------------------------------------------------------------------------

def _with_radii(spec: PipeSpec, radii: list[float]) -> PipeSpec:
    """*spec* with core radius ``radii[0]`` and shell thicknesses ``radii[1:]``."""
    name, shape = spec._core
    out = (PipeSpec(nang=spec.nang, n_outer=spec.n_outer, rot=spec.rot, mbmp=spec.mbmp)
           .core(name, CircleShape(radius=radii[0], nang=shape.nang),
                 nrad=spec._core_nrad, mprg=spec._core_mprg))
    for sh, dR in zip(spec.shells, radii[1:]):
        out = out.shell(sh.name, dR=dR, nrad=sh.nrad, mprg=sh.mprg)
    return out


@dataclass(frozen=True)
class Reducer(Sweep):
    """Concentric reducer (or expander): a straight cone between two radii.

    *outlet* is the outlet spec.  It must equal the inlet spec in everything
    except its radii (core radius and shell thicknesses): the same layers,
    ``nrad``, ``nang``, gradings, ``n_outer`` and ``rot``, so that every
    axial edge joins matching nodes (rule A4).  A larger outlet makes it an
    expander.

    Every axial layer is a station whose radii interpolate linearly, and
    corresponding corners are joined by straight lines, which are generators
    of the cone; wall nodes therefore lie exactly on the cone.
    *axial_grading* spaces the stations as for ``Straight``.
    """

    strategies = frozenset({0})   # switch classes it bridges (DESIGN A4)

    outlet:   PipeSpec
    length:   float
    n_layers: int
    axial_grading: float = 1.0

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal,
                    inlet.normal, inlet.up)
        return [(out, self.outlet)]

    def check(self, spec: PipeSpec) -> None:
        super().check(spec)
        if self.length <= 0:
            raise ValueError(f"length must be positive, got {self.length!r}")
        # rot is placement, not connectivity (task 0019), so the signature
        # check in Sweep.validate does not see it; the cone needs it equal.
        if spec.rot != self.outlet.rot:
            raise ValueError(
                f"outlet spec differs from the inlet in rot ({spec.rot!r} vs "
                f"{self.outlet.rot!r}); a reducer may change radii only")
        if not isinstance(spec.core_shape, CircleShape):
            raise ValueError("Reducer supports circular cross-sections only")

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        n = self.n_layers
        u = self.fractions(n)
        r0, r1 = np.array(_radii(spec)), np.array(_radii(self.outlet))
        frames = [a] + [Frame(a.position + (b.position - a.position) * u[k],
                              a.normal, a.up) for k in range(1, n)] + [b]
        specs = [spec] + [_with_radii(spec, list(r0 + (r1 - r0) * u[k]))
                          for k in range(1, n)] + [self.outlet]
        return Path(frames, [1] * n, specs=specs)


# ---------------------------------------------------------------------------
# Curved centrelines (Closure, SplinePipe)
# ---------------------------------------------------------------------------

_SAMPLES = 2000   # dense samples per curve for arc length and curvature


def _min_radius(curve) -> float:
    """Smallest radius of curvature of *curve* (``t -> (pos, d1, d2)``)."""
    _, d1, d2 = curve(np.linspace(0.0, 1.0, _SAMPLES))
    speed = np.linalg.norm(d1, axis=1)
    if speed.min() < 1e-12:
        return 0.0
    kappa = np.linalg.norm(np.cross(d1, d2), axis=1) / speed**3
    return float(1.0 / kappa.max()) if kappa.max() > 0 else math.inf


def _transported_stations(curve, n_layers: int, start: Frame,
                          end: Frame | None = None,
                          n_outer: int = 4,
                          fractions: np.ndarray | None = None,
                          ) -> tuple[list[Frame], float]:
    """Station frames along *curve* for ``t`` in [0, 1], both ends included.

    Stations equidistribute arc length + turning angle (equal weight), so
    sharp turns get proportionally more stations; *fractions*
    (``station_fractions``) grade that measure instead of splitting it
    evenly.  ``up`` is parallel
    transported from *start* (Bishop frame, no spurious twist).  With *end*
    given, the last frame is *end* and the residual roll mismatch, modulo
    the ``2π / n_outer`` symmetry, is distributed linearly by arc length;
    it is returned as the absorbed twist.  Without *end* the last frame is
    the transported one and the twist is 0.
    """
    t = np.linspace(0.0, 1.0, _SAMPLES)
    pos, d1, _ = curve(t)
    seg = np.linalg.norm(np.diff(pos, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    td = d1 / np.linalg.norm(d1, axis=1)[:, None]
    dtheta = np.arccos(np.clip(np.sum(td[:-1] * td[1:], axis=1), -1, 1))
    theta = np.concatenate([[0.0], np.cumsum(dtheta)])
    m = s / s[-1] + (theta / theta[-1] if theta[-1] > 1e-12 else 0.0)
    if fractions is None:
        fractions = np.linspace(0.0, 1.0, n_layers + 1)
    ts = np.interp(np.asarray(fractions) * m[-1], m, t)
    targets = np.interp(ts, t, s)          # arc length at each station
    P, D, _ = curve(ts)
    T = D / np.linalg.norm(D, axis=1)[:, None]
    T[0] = start.normal
    if end is not None:
        T[-1] = end.normal

    ups = [start.up]
    for k in range(1, len(T)):
        axis = np.cross(T[k - 1], T[k])
        n = np.linalg.norm(axis)
        u = ups[-1]
        if n > 1e-14:
            u = rotate(u, axis / n, math.atan2(n, np.dot(T[k - 1], T[k])))
        u = u - np.dot(u, T[k]) * T[k]
        ups.append(u / np.linalg.norm(u))

    twist = 0.0 if end is None else roll_mismatch(ups[-1], end.up, end.normal, n_outer)
    frames = [Frame(P[k], T[k], rotate(ups[k], T[k], twist * targets[k] / targets[-1]))
              for k in range(len(T))]
    frames[0] = start
    if end is not None:
        frames[-1] = end
    return frames, twist


def _cubic_spline(points: np.ndarray, d0: np.ndarray, d1: np.ndarray | None = None):
    """Cubic spline through *points*, chord-length parametrised, as
    ``t -> (pos, first, second derivative)`` for ``t`` in [0, 1].

    The start derivative (per unit chord length) is clamped to *d0*; the end
    to *d1*, or natural (zero curvature) when *d1* is ``None``.
    """
    P = np.asarray(points, dtype=float)
    h = np.linalg.norm(np.diff(P, axis=0), axis=1)
    knots = np.concatenate([[0.0], np.cumsum(h)])
    n, L = len(h), knots[-1]
    A = np.zeros((n + 1, n + 1))
    rhs = np.zeros((n + 1, 3))
    slope = np.diff(P, axis=0) / h[:, None]
    A[0, 0], A[0, 1] = 2 * h[0], h[0]
    rhs[0] = 6 * (slope[0] - d0)
    for i in range(1, n):
        A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        rhs[i] = 6 * (slope[i] - slope[i - 1])
    if d1 is None:
        A[n, n] = 1.0
    else:
        A[n, n - 1], A[n, n] = h[n - 1], 2 * h[n - 1]
        rhs[n] = 6 * (d1 - slope[n - 1])
    M = np.linalg.solve(A, rhs)

    def curve(u: np.ndarray):
        x = np.clip(np.asarray(u, dtype=float) * L, 0.0, L)
        i = np.clip(np.searchsorted(knots, x, side="right") - 1, 0, n - 1)
        hi, a, b = h[i][:, None], (knots[i + 1] - x)[:, None], (x - knots[i])[:, None]
        Mi, Mj, Pi, Pj = M[i], M[i + 1], P[i], P[i + 1]
        pos = (Mi * a**3 + Mj * b**3) / (6 * hi) \
            + (Pi / hi - Mi * hi / 6) * a + (Pj / hi - Mj * hi / 6) * b
        der = (-Mi * a**2 + Mj * b**2) / (2 * hi) - (Pi / hi - Mi * hi / 6) \
            + (Pj / hi - Mj * hi / 6)
        sec = (Mi * a + Mj * b) / hi
        return pos, der * L, sec * L * L

    return curve


# ---------------------------------------------------------------------------
# Spline pipe
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SplinePipe(Sweep):
    """Pipe along a cubic spline through *points* (first point = inlet).

    The spline leaves the inlet along its normal; it ends along
    *end_tangent* if given, otherwise with zero curvature.  Stations are
    placed as for ``Closure`` (arc length + turning angle), one axial layer
    each, with parallel-transported (Bishop) frames, so the outlet roll
    follows from the curve and every wall node lies on a station circle.

    Parameters
    ----------
    points : sequence of 3-vectors
        At least two distinct consecutive points; ``points[0]`` must be
        the inlet position.
    n_layers : int
        Hex layers (= stations) along the curve.
    end_tangent : 3-vector, optional
        Outlet direction (normalised).
    axial_grading : float
        Ratio of consecutive station spacings (in arc length + turning
        angle), inlet → outlet; 1 = uniform.
    """

    strategies = frozenset({0})   # switch classes it bridges (DESIGN A4)

    points:      tuple
    n_layers:    int
    end_tangent: tuple | None = None
    axial_grading: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(tuple(map(float, p)) for p in self.points))
        if self.end_tangent is not None:
            object.__setattr__(self, "end_tangent", tuple(map(float, self.end_tangent)))

    def _curve(self, inlet: Frame):
        P = np.asarray(self.points)
        d1 = None
        if self.end_tangent is not None:
            d1 = np.asarray(self.end_tangent) / np.linalg.norm(self.end_tangent)
        return _cubic_spline(P, inlet.normal, d1)

    def _check_points(self, inlet: Frame) -> None:
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")
        if not self.axial_grading > 0:
            raise ValueError(f"axial_grading must be positive, got {self.axial_grading!r}")
        P = np.asarray(self.points)
        if P.ndim != 2 or P.shape[1] != 3 or len(P) < 2:
            raise ValueError("points must be at least two 3-vectors")
        scale = max(1.0, float(np.abs(P).max()))
        if np.linalg.norm(P[0] - inlet.position) > 1e-9 * scale:
            raise ValueError(
                f"points[0] {P[0]} is not the inlet position {inlet.position}"
            )
        if np.linalg.norm(np.diff(P, axis=0), axis=1).min() < 1e-12 * scale:
            raise ValueError("consecutive points coincide")
        if self.end_tangent is not None and np.linalg.norm(self.end_tangent) < 1e-12:
            raise ValueError("end_tangent must be non-zero")

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        self._check_points(inlet)
        frames, _ = _transported_stations(self._curve(inlet), self.n_layers, inlet,
                                          fractions=self.fractions(self.n_layers))
        return [(frames[-1], spec)]

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        self._check_points(a)
        curve = self._curve(a)
        frames, _ = _transported_stations(curve, self.n_layers, a,
                                          fractions=self.fractions(self.n_layers))
        frames[-1] = b
        return Path(frames, [1] * self.n_layers, min_radius=_min_radius(curve))


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
    axial_grading : float
        Ratio of consecutive station spacings, source → target, as for
        ``SplinePipe``; 1 = uniform.
    """

    strategies = frozenset({0})   # switch classes it bridges (DESIGN A4)

    n_layers: int
    tension:  float = 1.0
    axial_grading: float = 1.0

    places_outlet = False

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

    def _curve(self, a: Frame, b: Frame):
        return lambda t: self._hermite(a, b, t)

    def _min_bend_radius(self, a: Frame, b: Frame) -> float:
        return _min_radius(self._curve(a, b))

    def stations(self, a: Frame, b: Frame, n_outer: int) -> tuple[list[Frame], float]:
        """Station frames (inclusive of both ends) and the absorbed twist."""
        return _transported_stations(self._curve(a, b), self.n_layers, a,
                                     end=b, n_outer=n_outer,
                                     fractions=self.fractions(self.n_layers))

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        if np.linalg.norm(b.position - a.position) < 1e-12:
            raise ValueError("source and target interfaces coincide")
        frames, _ = self.stations(a, b, spec.n_outer)
        return Path(frames, [1] * self.n_layers,
                    min_radius=self._min_bend_radius(a, b))
