"""
Wye — symmetric Y-junction as a block layout (DESIGN.md §6.1 "Blocks",
§7; decision 0017; geometry notes in docs/RESEARCH.md §4).

Geometry
--------
The inlet axis runs to the bifurcation point O; the daughters leave O along
d = cos(angle/2)·n ∓ sin(angle/2)·right, in the inlet's (normal, right)
plane.  That plane contains two arc midpoints of the O-H section, not two
corners (task 0030, Q1).  The intended wall is the canal surface of radius
R about this skeleton, {p : dist(p, skeleton) = R}: exact on the three
cylinders, a sphere about O at the outer knees, a crease at the crotch.
Wall curves are base curves pushed onto it.

Topology (symmetric hub; task 0030, Q2)
---------------------------------------
Marcinnó's butterfly folds each branch's core along its midline, which
transfinite blocks with 5-patch ports cannot follow (gmsh meshes 5- and
6-face volumes only).  Instead:

* hub H continues the inlet core from station Sa; its front face F0..F3
  sits at the daughters' crotch-side core corners;
* D_R, D_L: each daughter's core leaves a side face of H and turns into
  its station S_R, S_L;
* the ring layer is an offset of the wall: one ring block over every face
  of H ∪ D_R ∪ D_L that is not a station core patch (H's top, bottom and
  front, four per daughter);
* straight runs: port → Sa, S_R → port, S_L → port.

The radial edges at H's back corners have five blocks around them: the
wye's extraordinary vertices.

Scope of this prototype: single-layer circular specs, ``rot = 0``,
``n_outer = 4``, both daughters with the inlet's spec, angle 30°–120°.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np

from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, OH_RATIO, Polyline, Spline, bind_face,
    corner_shift, face_patches, face_vertices,
)
from .interface import Frame, junction_roll, junction_toward, rolled
from .signature import check_port_pairs

_SAMPLES = 9            # interior points per spline edge
ANGLE_RANGE = (30.0, 120.0)

# Closed-form placement, in units of R; h = angle / 2.
_IN_MARGIN = 0.1        # Sa behind O by R (tan h + margin): Sa is clear of the daughters
_OUT_MARGIN = 1.0       # S_* ahead of O by R (cot h + margin): clear of the other daughter
_W_OFFSET = 0.3         # wall crotch corners: this far from the mirror plane
_BULGE = 0.3            # crotch side edges: this far past the apex (or the corners)
_F_FRACTION = 0.65      # hub front corners at fraction · R cot h along d
_KINK = 45.0            # crotch top/bottom edges cross the crease this high (degrees)


def _hermite(p, q, tp, tq, n=_SAMPLES):
    """Interior points of the cubic Hermite curve p → q with unit end
    tangents *tp*, *tq* scaled by |q − p| (Marcinnó et al.)."""
    L = np.linalg.norm(q - p)
    t = np.linspace(0.0, 1.0, n + 2)[1:-1, None]
    return ((2 * t**3 - 3 * t**2 + 1) * p + (t**3 - 2 * t**2 + t) * L * tp
            + (-2 * t**3 + 3 * t**2) * q + (t**3 - t**2) * L * tq)


class Skeleton:
    """Inlet axis up to O and the daughter rays from O; the intended wall
    is the level set dist = R."""

    def __init__(self, origin, inlet, daughters, radius):
        self.o = np.asarray(origin, dtype=float)
        self.rays = [(-np.asarray(inlet, dtype=float))] + [np.asarray(d, dtype=float)
                                                           for d in daughters]
        self.R = radius

    def nearest(self, p) -> tuple[float, np.ndarray]:
        """(distance, nearest skeleton point) of the point *p*."""
        best = (math.inf, self.o)
        for d in self.rays:
            q = self.o + max(0.0, float(np.dot(p - self.o, d))) * d
            dist = float(np.linalg.norm(p - q))
            if dist < best[0]:
                best = (dist, q)
        return best

    def distance(self, points) -> np.ndarray:
        """Distance of every row of *points* to the skeleton."""
        p = np.atleast_2d(points) - self.o
        out = np.full(len(p), np.inf)
        for d in self.rays:
            t = np.clip(p @ d, 0.0, None)
            out = np.minimum(out, np.linalg.norm(p - t[:, None] * d, axis=1))
        return out

    def to_wall(self, p) -> np.ndarray:
        """Push *p* onto the wall along the ray from its nearest skeleton point."""
        _, c = self.nearest(p)
        v = p - c
        v = v / np.linalg.norm(v)
        # march to the first exit (another branch may lie further along
        # the ray), then bisect
        step = self.R / 16
        lo = 0.0
        while self.nearest(c + (lo + step) * v)[0] < self.R:
            lo += step
            if lo > 20 * self.R:
                raise ValueError("wall projection: ray does not leave the wye")
        hi = lo + step
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.nearest(c + mid * v)[0] < self.R:
                lo = mid
            else:
                hi = mid
        return c + 0.5 * (lo + hi) * v

    def curve(self, points) -> Spline:
        return Spline(tuple(tuple(self.to_wall(p)) for p in points))


@dataclass(frozen=True)
class Wye:
    """Symmetric Y-junction: one inlet, two daughters with the inlet's spec.

    Parameters
    ----------
    angle : float
        Angle between the daughters, degrees, split equally about the
        inlet direction in the inlet's (normal, right) plane.
    run_length : float
        Distance from the inlet port to the bifurcation point O.
    branch_length : float
        Distance from O to each outlet port, along the daughter axes.
    n_run, n_branch : int
        Axial layers of the inlet run and of each daughter run.
    n_split : int
        Layers of each daughter's turning block (hub → daughter station).

    roll : float
        Rotation of the daughters' plane about the inlet axis in degrees,
        from the inlet's (normal, right) plane.  A multiple of the
        section's period (90° for a circle), so the junction's corners land
        on the inlet face's (decision 0024).
    toward : 3-vector, optional
        Absolute direction the ``right`` daughter turns toward, instead of
        *roll*: resolved to the nearest allowed roll when the wye is added;
        more than ``limits.JUNCTION_TOWARD_TOL`` off it is an error.

    Ports are ``left`` and ``right``; ``right`` turns toward the (rolled)
    inlet's ``right``.  Outlet frames keep the (rolled) inlet's ``up``.
    ``add(…, names={"left": …, "right": …})``.
    """

    strategies = frozenset({0})   # both port pairs: inlet → each daughter
    port_names = ("left", "right")

    angle:         float
    run_length:    float
    branch_length: float
    n_run:    int = 3
    n_branch: int = 3
    n_split:  int = 3
    roll:     float = 0.0
    toward:   tuple | None = field(default=None, metadata={"input": True})

    def resolve(self, inlet: Frame, spec: PipeSpec) -> "Wye":
        # toward names the right daughter's side: the rolled frame's right,
        # 90° from its up.
        return junction_toward(self, inlet, spec, offset=90.0)

    # -- geometry (pure) ----------------------------------------------

    def _axes(self, inlet: Frame):
        inlet = rolled(inlet, self.roll)
        n, u, r = inlet.normal, inlet.up, inlet.right
        h = math.radians(self.angle) / 2
        o = inlet.position + self.run_length * n
        d_left = math.cos(h) * n - math.sin(h) * r
        d_right = math.cos(h) * n + math.sin(h) * r
        return o, n, u, d_left, d_right

    def placement(self, radius: float) -> dict[str, float]:
        """Station and crotch distances from O (closed form)."""
        h = math.radians(self.angle) / 2
        c, s = math.cos(h), math.sin(h)
        t_apex = radius * c / s                      # the crotch generators meet here
        t_crotch = radius * (_W_OFFSET + c / math.sqrt(2)) / s
        return {"s_in": radius * (s / c + _IN_MARGIN),
                "s_out": t_apex + radius * _OUT_MARGIN,
                "t_crotch": t_crotch,
                "t_bulge": max(t_crotch, t_apex) + radius * _BULGE,
                "t_hub": _F_FRACTION * t_apex,
                "t_apex": t_apex}

    def skeleton(self, inlet: Frame, spec: PipeSpec) -> Skeleton:
        o, n, _, dl, dr = self._axes(inlet)
        return Skeleton(o, n, (dl, dr), spec.core_shape.radius)

    # -- ports --------------------------------------------------------

    def ports(self, inlet: Frame, spec: PipeSpec):
        o, _, u, dl, dr = self._axes(inlet)
        return [(Frame(o + self.branch_length * d, d, u), spec) for d in (dl, dr)]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        if spec.shells:
            raise ValueError("Wye prototype supports single-layer specs only")
        if not isinstance(spec.core_shape, CircleShape):
            raise ValueError("Wye prototype supports circular cores only")
        if spec.rot != 0 or spec.n_outer != 4:
            raise ValueError("Wye prototype requires rot = 0 and n_outer = 4")
        if self.toward is not None:
            raise ValueError("Wye: toward is resolved by Assembly.add(); add the "
                             "fitting to an assembly")
        junction_roll(self, spec)
        lo, hi = ANGLE_RANGE
        if not lo <= self.angle <= hi:
            raise ValueError(
                f"Wye angle {self.angle:g}° is outside the prototype range "
                f"{lo:g}°–{hi:g}°")
        g = self.placement(spec.core_shape.radius)
        if self.run_length <= g["s_in"]:
            raise ValueError(
                f"run_length must exceed {g['s_in']:.4g} at {self.angle:g}° "
                f"(R·(tan(angle/2) + {_IN_MARGIN:g}): the inlet station clears "
                f"the daughters)")
        if self.branch_length <= g["s_out"]:
            raise ValueError(
                f"branch_length must exceed {g['s_out']:.4g} at {self.angle:g}° "
                f"(R·(cot(angle/2) + {_OUT_MARGIN:g}): the daughter stations "
                f"clear each other)")
        for n in (self.n_run, self.n_branch, self.n_split):
            if n < 1:
                raise ValueError("layer counts must be >= 1")

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        # Declared in the rolled inlet frame; fill() binds the inlet face
        # (built unrolled) with the corner shift.  Outlets are rolled already.
        A, L, Rp = rolled(frames[0], self.roll), frames[1], frames[2]
        R = spec.core_shape.radius
        o, n, u, dl, dr = self._axes(frames[0])
        g = self.placement(R)
        sk = self.skeleton(frames[0], spec)
        right_l, right_r = np.cross(dl, u), np.cross(dr, u)   # crotch side of d_L, outer side of d_R
        sa = Frame(o - g["s_in"] * n, n, u)
        sl = Frame(o + g["s_out"] * dl, dl, u)
        sr = Frame(o + g["s_out"] * dr, dr, u)

        lay = BlockLayout()
        face_vertices(lay, "A", A, spec)
        face_vertices(lay, "L", L, spec)
        face_vertices(lay, "R", Rp, spec)
        for name, fr in (("Sa", sa), ("SL", sl), ("SR", sr)):
            face_vertices(lay, name, fr, spec, port=False)
            for k in range(4):
                lay.edge((name, 1, k), (name, 1, (k + 1) % 4), ArcAbout(tuple(fr.position)))

        # Straight runs: generators of the cylinder are straight lines.
        for lvl in (0, 1):
            for k in range(4):
                lay.edge(("A", lvl, k), ("Sa", lvl, k), divisions=self.n_run)
                lay.edge(("SL", lvl, k), ("L", lvl, k), divisions=self.n_branch)
                lay.edge(("SR", lvl, k), ("R", lvl, k), divisions=self.n_branch)

        # Crotch corners: F on the core square at t_hub along each daughter;
        # W on the wall at t_crotch, _W_OFFSET·R from the mirror plane, both
        # 45° above or below the plane.  k follows the hub's back face.
        t, tf = g["t_crotch"], g["t_hub"]
        crotch = {0: (dr, -right_r, +1), 3: (dr, -right_r, -1),
                  1: (dl, +right_l, +1), 2: (dl, +right_l, -1)}
        for k, (d, side, z) in crotch.items():
            radial = (side + z * u) / math.sqrt(2)
            lay.vertex(("F", k), o + tf * d + OH_RATIO * R * radial)
            lay.vertex(("W", k), o + t * d + R * radial)
            lay.edge(("F", k), ("W", k))

        P = lambda v: lay.coords[v]
        s_ = lambda name: (lambda l, k: (name, l, k))
        a, l_, r_ = s_("Sa"), s_("SL"), s_("SR")
        F = lambda k: ("F", k)
        W = lambda k: ("W", k)

        # Daughter cores: outer edges bend from n to d (Hermite); crotch
        # edges run along d from the crotch corners.
        for (d, st, outer, crotch_k) in ((dr, r_, ((0, 0), (3, 3)), ((0, 1), (3, 2))),
                                         (dl, l_, ((1, 1), (2, 2)), ((1, 0), (2, 3)))):
            for ka, ks in outer:
                lay.edge(a(0, ka), st(0, ks), Spline(tuple(map(tuple, _hermite(
                    P(a(0, ka)), P(st(0, ks)), n, d)))), divisions=self.n_split)
                lay.edge(a(1, ka), st(1, ks), sk.curve(_hermite(
                    P(a(1, ka)), P(st(1, ks)), n, d)))
            for kf, ks in crotch_k:
                lay.edge(F(kf), st(0, ks))
                lay.edge(W(kf), st(1, ks))      # a cylinder generator: exact

        # Hub top and bottom: Sa corners to the crotch corners, the chord
        # pushed onto the wall (a Hermite arriving along d overshoots across
        # the mirror plane and crosses its mirror image).
        for k in range(4):
            lay.edge(a(1, k), W(k), sk.curve(
                np.linspace(P(a(1, k)), P(W(k)), _SAMPLES + 2)[1:-1]))

        # Crotch patch.  Top and bottom edges: from each W along its
        # daughter's cylinder to the crease at _KINK elevation, where the two
        # halves meet (C0, so a polyline).  Sides: around each daughter's
        # crotch side, bulging past the apex.
        def on_daughter(d, side, t_, phi):
            return o + t_ * d + R * (math.cos(phi) * side + math.sin(phi) * u)
        m = _SAMPLES // 2
        for k0, k1, z in ((0, 1, +1), (3, 2, -1)):
            # straight in (t, φ) on each daughter's cylinder, W → crease
            phi_k = z * math.radians(_KINK)
            t_k = g["t_apex"] * math.cos(phi_k)
            frac = np.linspace(0.0, 1.0, m + 2)[1:]
            ts = t + (t_k - t) * frac
            ps = z * math.pi / 4 + (phi_k - z * math.pi / 4) * frac
            half_r = [on_daughter(dr, -right_r, a_, b_) for a_, b_ in zip(ts, ps)]
            half_l = [on_daughter(dl, right_l, a_, b_) for a_, b_ in zip(ts, ps)][:-1]
            lay.edge(W(k0), W(k1), Polyline(tuple(map(tuple, half_r + half_l[::-1]))))
        t_mid = g["t_bulge"]
        for k0, k1, d, side in ((0, 3, dr, -right_r), (1, 2, dl, right_l)):
            phi = np.linspace(-np.pi / 4, np.pi / 4, _SAMPLES + 2)[1:-1]
            tt = t + (t_mid - t) * np.cos(2 * phi)
            pts = [o + ti * d + R * (math.cos(f) * side + math.sin(f) * u)
                   for ti, f in zip(tt, phi)]
            lay.edge(W(k0), W(k1), sk.curve(pts[::-1]))     # top → bottom

        fluid = spec.layer_names[0]

        # Runs.
        for _, cyc in face_patches("A", spec):
            lay.block(list(cyc) + [a(lv, k) for (_, lv, k) in cyc], fluid)
        for st, port in ((l_, "L"), (r_, "R")):
            for _, cyc in face_patches(port, spec):
                lay.block([st(lv, k) for (_, lv, k) in cyc] + list(cyc), fluid)

        # Hub and daughter cores.
        lay.block([a(0, 0), a(0, 1), a(0, 2), a(0, 3), F(0), F(1), F(2), F(3)], fluid)
        lay.block([a(0, 0), a(0, 3), F(3), F(0), r_(0, 0), r_(0, 3), r_(0, 2), r_(0, 1)], fluid)
        lay.block([a(0, 1), a(0, 2), F(2), F(1), l_(0, 1), l_(0, 2), l_(0, 3), l_(0, 0)], fluid)

        # Ring layer: core quad → its wall quad.
        def wall(v):
            return (v[0], 1, v[2]) if v[0] in ("Sa", "SL", "SR") else W(v[1])
        rings = [
            (a(0, 0), a(0, 1), F(1), F(0)),             # hub top
            (a(0, 3), a(0, 2), F(2), F(3)),             # hub bottom
            (F(0), F(1), F(2), F(3)),                   # crotch
            (a(0, 0), a(0, 3), r_(0, 3), r_(0, 0)),     # D_R outer
            (a(0, 0), F(0), r_(0, 1), r_(0, 0)),        # D_R top
            (F(0), F(3), r_(0, 2), r_(0, 1)),           # D_R crotch
            (a(0, 3), F(3), r_(0, 2), r_(0, 3)),        # D_R bottom
            (a(0, 1), a(0, 2), l_(0, 2), l_(0, 1)),     # D_L outer
            (a(0, 1), F(1), l_(0, 0), l_(0, 1)),        # D_L top
            (F(1), F(2), l_(0, 3), l_(0, 0)),           # D_L crotch
            (a(0, 2), F(2), l_(0, 3), l_(0, 2)),        # D_L bottom
        ]
        for quad in rings:
            lay.block(list(quad) + [wall(v) for v in quad], fluid)
        # Plate fillings of these long curved faces sag up to 0.66 R and
        # are not mirror-symmetric; pinned to points on the wall they are
        # fragile (OCC rebuilds shared edges).  Stretch B-spline fillings
        # are valid at every angle and symmetric (task 0030 notes).
        lay.filling = "Stretch"
        return lay

    # -- contract -----------------------------------------------------

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        self.check(spec)
        check_port_pairs(self, [spec] + [s for _, s in self.ports(frames[0], spec)])
        expected = [f for f, _ in self.ports(frames[0], spec)]
        for want, got in zip(expected, frames[1:]):
            if (np.linalg.norm(want.position - got.position) > 1e-9 * self.run_length
                    or np.dot(want.normal, got.normal) < 1 - 1e-9
                    or np.dot(want.up, got.up) < 1 - 1e-9):
                raise ValueError("port interface does not match Wye geometry")
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise ValueError(f"block layout invalid: {e}") from None

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count of the block layout (pure; DESIGN P4)."""
        return self.layout(frames, spec).cell_count()

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        shift = corner_shift(rolled(frames[0], self.roll), frames[0], spec)
        for prefix, face in zip("ALR", faces):
            bind_face(lay, prefix, face, shift if prefix == "A" else 0)
        return lay.realise(spec.layer_names)
