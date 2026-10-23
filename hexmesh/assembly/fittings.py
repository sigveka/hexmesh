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

A fitting may create internal station faces (e.g. inside a bend) but must
never create, modify or duplicate a port face.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np
import gmsh

from ..core.cross_section import LayeredCrossSection
from ..core.cursor import _rodrigues
from ..core.spec import PipeSpec
from ..connectors.fittings import _connect_layer
from .interface import Frame, build_face, outer_radius, roll_mismatch


@dataclass
class FillResult:
    """Entities created by one fitting fill."""

    volumes:    dict[str, list[int]] = field(default_factory=dict)
    walls:      list[int]            = field(default_factory=list)
    interfaces: dict[str, list[int]] = field(default_factory=dict)
    curves:     list[tuple[int, int]] = field(default_factory=list)
    surfaces:   list[int]            = field(default_factory=list)
    mesh_vols:  list[int]            = field(default_factory=list)

    def merge(self, other: "FillResult") -> None:
        for k, v in other.volumes.items():
            self.volumes.setdefault(k, []).extend(v)
        self.walls.extend(other.walls)
        for k, v in other.interfaces.items():
            self.interfaces.setdefault(k, []).extend(v)
        self.curves.extend(other.curves)
        self.surfaces.extend(other.surfaces)
        self.mesh_vols.extend(other.mesh_vols)


def _fill_slab(
    in_face:       LayeredCrossSection,
    out_face:      LayeredCrossSection,
    n_layers:      int,
    axial_curve=None,
    planar_radial: bool = True,
) -> FillResult:
    """Fill all concentric layers between two existing faces."""
    result = FillResult()
    names = in_face.interface_names()
    prev_axial = prev_side = None
    for idx, ((name, in_cs), (_, out_cs)) in enumerate(
        zip(in_face.layers, out_face.layers)
    ):
        vols, side, axial, deferred = _connect_layer(
            in_cs, out_cs, n_layers,
            prev_outer_axial=prev_axial,
            prev_outer_side_surfs=prev_side,
            planar_radial=planar_radial,
            axial_curve=axial_curve,
        )
        result.volumes.setdefault(name, []).extend(vols)
        if prev_side is not None:
            result.interfaces.setdefault(names[idx - 1], []).extend(prev_side)
        result.curves.extend((c, n_layers + 1) for c in deferred["curves"])
        result.curves.extend(deferred["arc_curves"])
        result.surfaces.extend(deferred["surfaces"])
        result.mesh_vols.extend(deferred["volumes"])
        prev_axial, prev_side = axial, side
    result.walls.extend(prev_side)
    return result


# ---------------------------------------------------------------------------
# Straight
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Straight:
    """Straight pipe run between two parallel interfaces."""

    length:   float
    n_layers: int

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal,
                    inlet.normal, inlet.up)
        return [(out, spec)]

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        if self.length <= 0:
            raise ValueError(f"length must be positive, got {self.length!r}")
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")
        a, b = frames
        tol = 1e-9 * max(1.0, self.length)
        if np.linalg.norm(b.position - (a.position + self.length * a.normal)) > tol:
            raise ValueError(
                f"outlet is not {self.length} along the inlet axis"
            )
        if np.dot(a.normal, b.normal) < 1 - 1e-9:
            raise ValueError("inlet and outlet directions differ")
        if abs(roll_mismatch(a.up, b.up, b.normal, spec.n_outer)) > 1e-9:
            raise ValueError("Straight cannot twist: inlet and outlet roll differ")

    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        return _fill_slab(faces[0], faces[1], self.n_layers)


# ---------------------------------------------------------------------------
# Bend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Bend:
    """Circular-arc bend whose mesh nodes lie exactly on the true geometry.

    An internal station face is placed at every axial layer and stations are
    joined by circular arcs about the bend axis.  Every mesh node therefore
    lies on a station face or an axial arc, so wall and material-interface
    nodes are exactly on their tori.  OCC filled side surfaces only carry
    the element faces between nodes; their shape is never sampled.

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
        (0 = bend toward ``up``; same convention as ``connectors.Bend``).
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
            centre + _rodrigues(inlet.position - centre, axis, a),
            _rodrigues(inlet.normal, axis, a),
            _rodrigues(inlet.up, axis, a),
        )

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        return [(self._rotated(inlet, self.angle), spec)]

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")
        if not 0 < abs(self.angle) < 360:
            raise ValueError(f"angle must be in (0, 360) degrees, got {self.angle!r}")
        R = outer_radius(spec)
        if self.radius <= R:
            raise ValueError(
                f"bend radius {self.radius} must exceed pipe outer radius {R}"
            )
        expected = self._rotated(frames[0], self.angle)
        b = frames[1]
        if (np.linalg.norm(expected.position - b.position) > 1e-9 * self.radius
                or np.dot(expected.normal, b.normal) < 1 - 1e-9
                or abs(roll_mismatch(expected.up, b.up, b.normal, spec.n_outer)) > 1e-9):
            raise ValueError("outlet interface does not match bend geometry")

    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        inlet = frames[0]
        axis, centre = self._axis_centre(inlet)
        geo = gmsh.model.occ

        def arc(pt_in: int, pt_out: int) -> int:
            p = np.asarray(gmsh.model.getValue(0, pt_in, []))
            c = centre + axis * np.dot(p - centre, axis)
            ct = geo.addPoint(*c)
            tag = geo.addCircleArc(pt_in, ct, pt_out)
            geo.remove([(0, ct)])
            return tag

        # Internal stations, one per axial layer — owned by this fitting,
        # not interfaces.
        n = self.n_layers
        stations = [faces[0]]
        for k in range(1, n):
            fr = self._rotated(inlet, self.angle * k / n)
            stations.append(build_face(spec, fr, lc))
        stations.append(faces[1])
        geo.synchronize()

        result = FillResult()
        for k in range(n):
            result.merge(_fill_slab(
                stations[k], stations[k + 1], 1,
                axial_curve=arc, planar_radial=False,
            ))
        return result


# ---------------------------------------------------------------------------
# Closure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Closure:
    """Smooth run between two *existing* interfaces — closes loops.

    Only usable through ``Assembly.close()``: both ports are given, so
    ``ports()`` is undefined.  The centreline is a cubic Hermite curve that
    leaves the source along its normal and arrives at the target along its
    normal.  Cross-section frames are parallel-transported (no spurious
    twist) and the residual roll mismatch — modulo the ``2π / n_outer``
    symmetry of the cross-section — is distributed linearly by arc length.

    Every station face is internal to the fitting and consecutive stations
    are one axial layer apart, so all mesh nodes lie on station faces
    (DESIGN.md §6, exactness).

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

    _SAMPLES = 2000

    def ports(self, inlet: Frame, spec: PipeSpec):
        raise TypeError("Closure joins two existing interfaces; use Assembly.close()")

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
        targets = np.linspace(0.0, s[-1], self.n_layers + 1)
        ts = np.interp(targets, s, t)
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
                u = _rodrigues(u, axis / n, math.atan2(n, np.dot(T[k - 1], T[k])))
            u = u - np.dot(u, T[k]) * T[k]
            ups.append(u / np.linalg.norm(u))

        twist = roll_mismatch(ups[-1], b.up, b.normal, n_outer)
        frames = []
        for k in range(len(T)):
            u = _rodrigues(ups[k], T[k], twist * targets[k] / targets[-1])
            frames.append(Frame(P[k], T[k], u))
        frames[0], frames[-1] = a, Frame(b.position, b.normal, frames[-1].up)
        return frames, twist

    # -- contract -------------------------------------------------------

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")
        if self.tension <= 0:
            raise ValueError(f"tension must be positive, got {self.tension!r}")
        a, b = frames
        if np.linalg.norm(b.position - a.position) < 1e-12:
            raise ValueError("source and target interfaces coincide")
        R = outer_radius(spec)
        rmin = self._min_bend_radius(a, b)
        if rmin <= R:
            raise ValueError(
                f"closure path bends with radius {rmin:.4g}, tighter than the "
                f"pipe outer radius {R}; move the interfaces apart or adjust tension"
            )

    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        stations, _ = self.stations(frames[0], frames[1], spec.n_outer)
        lcs = [faces[0]]
        for fr in stations[1:-1]:
            lcs.append(build_face(spec, fr, lc))
        lcs.append(faces[1])
        gmsh.model.occ.synchronize()

        result = FillResult()
        for k in range(self.n_layers):
            result.merge(_fill_slab(lcs[k], lcs[k + 1], 1, planar_radial=False))
        return result
