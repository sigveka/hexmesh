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
Task 0116, route A: today's wye hub generalised to an angle and a radius
per daughter (decision 0043).  A measurement prototype: not exported, not
in ``__all__``, and ``Wye`` itself is untouched.

``WyeProbe(theta_left, theta_right, r_left, r_right, …)``: the daughters
leave O at *theta_left* to the left and *theta_right* to the right of the
inlet axis, in the inlet's (normal, right) plane, with core radii
``r_* · R``.  Each daughter's spec is the inlet's with its core radius
(``PipeSpec.with_radii``; the shells keep their thickness).  The included
angle is ``theta_left + theta_right``; the crotch is built about the
daughters' bisector exactly as ``Wye`` builds it about the inlet axis, so
``WyeProbe(30, 30, 1, 1)`` is today's 60° wye, edge for edge.

What is generalised, and how (each reduces to ``Wye``'s for a symmetric
wye with r = R):
- the axes: d_i from θ_i;
- the inlet station: ``R · inlet_clearance(max θ_i)``, unless
  *inlet_station* (× R) is given (the equal tee: tan 90° is infinite);
- crotch placement (``t_apex``, ``t_crotch``, the hub's front, the bulge)
  from the half included angle and the daughters' radius;
- the daughter stations, crotch corners and their shells at the
  daughter's radii;
- the wall: tubes of the inlet's and each daughter's radius
  (``TubeUnion``), and a skeleton whose level set takes each ray's own
  radius.

Unequal daughters (r_left ≠ r_right) are not built: the crotch crease
between unequal cylinders isn't symmetric about the bisector, and none of
the task's cases needs it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..core.spec import PipeSpec
from ..errors import InternalError
from ..sections import oh
from . import limits, wye as W
from .blocks import (ArcAbout, BlockLayout, Polyline, Spline, face_patches, face_vertices)
from .errors import AssemblyError
from .interface import Frame, rolled
from .projection import Tube, TubeUnion
from .tee import thicknesses


class _Skeleton:
    """``wye.Skeleton`` with a radius per ray: the wall at level l is
    {p : min_i (dist_i(p) − ρ_i) = 0}."""

    def __init__(self, origin, inlet, daughters):
        self.o = np.asarray(origin, dtype=float)
        self.rays = [-np.asarray(inlet, dtype=float)] + [np.asarray(d, float) for d in daughters]

    def _f(self, p, radii):
        best = (math.inf, self.o)
        for d, rho in zip(self.rays, radii):
            q = self.o + max(0.0, float(np.dot(p - self.o, d))) * d
            f = float(np.linalg.norm(p - q)) - rho
            if f < best[0]:
                best = (f, q)
        return best

    def to_wall(self, p, radii) -> np.ndarray:
        _, c = self._f(p, radii)
        v = p - c
        v = v / np.linalg.norm(v)
        step = max(radii) / 16
        lo = 0.0
        while self._f(c + (lo + step) * v, radii)[0] < 0:
            lo += step
            if lo > 20 * max(radii):
                raise InternalError("wall projection: ray does not leave the wye")
        hi = lo + step
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self._f(c + mid * v, radii)[0] < 0:
                lo = mid
            else:
                hi = mid
        return c + 0.5 * (lo + hi) * v

    def curve(self, points, radii) -> Spline:
        return Spline(tuple(tuple(self.to_wall(p, radii)) for p in points))


@dataclass(frozen=True)
class WyeProbe(W.Wye):
    """A wye with an angle and a radius ratio per daughter (route A)."""

    angle:         float = 60.0          # set from the thetas in __post_init__
    run_length:    float = 0.4
    branch_length: float = 0.7
    theta_left:  float = 30.0
    theta_right: float = 30.0
    r_left:      float = 1.0
    r_right:     float = 1.0
    inlet_station: float | None = None   # × R; None: inlet_clearance(max θ)

    def __post_init__(self):
        object.__setattr__(self, "angle", self.theta_left + self.theta_right)

    # -- geometry -----------------------------------------------------

    def _axes(self, inlet: Frame):
        inlet = rolled(inlet, self.roll)
        n, u, r = inlet.normal, inlet.up, inlet.right
        o = inlet.position + self.run_length * n
        tl, tr = math.radians(self.theta_left), math.radians(self.theta_right)
        d_left = math.cos(tl) * n - math.sin(tl) * r
        d_right = math.cos(tr) * n + math.sin(tr) * r
        return o, n, u, d_left, d_right

    def _ratio(self) -> float:
        if not math.isclose(self.r_left, self.r_right):
            raise InternalError("WyeProbe: unequal daughters are not built (task 0116)")
        return self.r_left

    def daughter_spec(self, spec: PipeSpec) -> PipeSpec:
        q = self._ratio()
        if q == 1.0:
            return spec
        R = spec.core_shape.max_extent
        return spec.with_radii([q * R] + [sh.dR for sh in spec.shells])

    def placement(self, radius: float, inlet_radius: float | None = None) -> dict[str, float]:
        """``Wye.placement`` about the bisector: *radius* the daughters',
        the inlet station from the inlet's radius and the widest θ."""
        h = math.radians(self.angle) / 2
        c, s = math.cos(h), math.sin(h)
        Rin = radius if inlet_radius is None else inlet_radius
        t_apex = radius * c / s
        t_crotch = radius * (W._W_OFFSET + c / math.sqrt(2)) / s
        widest = math.radians(max(self.theta_left, self.theta_right))
        s_in = (Rin * self.inlet_station if self.inlet_station is not None
                else Rin * W.inlet_clearance(widest))
        return {"s_in": s_in,
                "s_out": t_apex + radius * W._OUT_MARGIN,
                "t_crotch": t_crotch,
                "t_bulge": max(t_crotch, t_apex) + radius * W._BULGE,
                "t_hub": W._F_FRACTION * t_apex,
                "t_apex": t_apex}

    def wall(self, inlet: Frame, spec: PipeSpec, radius: float | None = None) -> TubeUnion:
        """The union of the inlet's and the daughters' tubes; *radius*, an
        offset level: the inlet's radius there (the daughters' offset by
        the same thickness)."""
        o, n, _, dl, dr = self._axes(inlet)
        R = spec.core_shape.max_extent
        rho = R if radius is None else radius
        rd = self._ratio() * R + (rho - R)
        return TubeUnion([Tube(tuple(o), tuple(-n), rho), Tube(tuple(o), tuple(dl), rd),
                          Tube(tuple(o), tuple(dr), rd)])

    def ports(self, inlet: Frame, spec: PipeSpec):
        o, _, u, dl, dr = self._axes(inlet)
        ds = self.daughter_spec(spec)
        return [(Frame(o + self.branch_length * d, d, u), ds) for d in (dl, dr)]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        """``Wye.check`` without its angle range and symmetric placement:
        the probe's own placement."""
        if not spec.core_shape.is_round:
            raise AssemblyError("WyeProbe: circular cores only", code="wye_needs_circle")
        self._ratio()
        R = spec.core_shape.max_extent
        g = self.placement(self._ratio() * R, inlet_radius=R)
        if not math.isfinite(g["s_in"]) or self.run_length <= g["s_in"]:
            raise AssemblyError(f"WyeProbe: run_length must exceed s_in {g['s_in']:.4g}",
                                code="run_length_too_short", value=self.run_length,
                                limit={"min_exclusive": float(g["s_in"])})
        if self.branch_length <= g["s_out"]:
            raise AssemblyError(f"WyeProbe: branch_length must exceed s_out {g['s_out']:.4g}",
                                code="branch_length_too_short", value=self.branch_length,
                                limit={"min_exclusive": float(g["s_out"])})
        for name in W._COUNTS:
            if getattr(self, name) is None:
                raise AssemblyError(f"WyeProbe: {name}=None is resolved by Assembly.add()",
                                    code="fitting_not_resolved")

    def resolve(self, inlet, spec, axial_cell=None, outlet=None):
        return super().resolve(inlet, spec, axial_cell, outlet)

    def validate(self, frames, spec) -> list[str]:
        """The layout's own checks only (inversion), and the predictions."""
        self.check(spec)
        lay = self.layout(frames, spec)
        sj = lay.validate()["min_corner_sj"]
        return [] if sj >= limits.PREDICTED_SJ_MIN else [f"predicted min corner SJ {sj:.3g}"]

    def _layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        # Wye._layout, generalised (see the module docstring); comments
        # there.  Inlet quantities: R, Rl; daughters': r, rl.
        A, L, Rp = rolled(frames[0], self.roll), frames[1], frames[2]
        ds = self.daughter_spec(spec)
        R = spec.core_shape.max_extent
        r = ds.core_shape.max_extent
        names = spec.layer_names
        levels = range(1, len(names) + 1)
        Rl = {l: R + t for l, t in zip(levels, thicknesses(spec))}
        rl = {l: r + t for l, t in zip(levels, thicknesses(ds))}
        radii = {l: (Rl[l], rl[l], rl[l]) for l in levels}
        o, n, u, dl, dr = self._axes(frames[0])
        g = self.placement(r, inlet_radius=R)
        sk = _Skeleton(o, n, (dl, dr))
        right_l, right_r = np.cross(dl, u), np.cross(dr, u)
        sa = Frame(o - g["s_in"] * n, n, u)
        sl = Frame(o + g["s_out"] * dl, dl, u)
        sr = Frame(o + g["s_out"] * dr, dr, u)

        lay = BlockLayout()
        face_vertices(lay, "A", A, spec)
        face_vertices(lay, "L", L, ds)
        face_vertices(lay, "R", Rp, ds)
        for name, fr, s_ in (("Sa", sa, spec), ("SL", sl, ds), ("SR", sr, ds)):
            face_vertices(lay, name, fr, s_, port=False)
            for l in levels:
                for k in range(4):
                    lay.edge((name, l, k), (name, l, (k + 1) % 4),
                             ArcAbout(tuple(fr.position)))

        for lvl in (0, *levels):
            for k in range(4):
                lay.edge(("A", lvl, k), ("Sa", lvl, k), divisions=self.n_run)
                lay.edge(("SL", lvl, k), ("L", lvl, k), divisions=self.n_branch)
                lay.edge(("SR", lvl, k), ("R", lvl, k), divisions=self.n_branch)

        t, tf = g["t_crotch"], g["t_hub"]
        crotch = {0: (dr, -right_r, +1), 3: (dr, -right_r, -1),
                  1: (dl, +right_l, +1), 2: (dl, +right_l, -1)}
        for k, (d, side, z) in crotch.items():
            radial = (side + z * u) / math.sqrt(2)
            lay.vertex(("F", 0, k), o + tf * d + oh.inner_radius(r) * radial)
            for l in levels:
                lay.vertex(("W", l, k), o + t * d + rl[l] * radial)
                lay.edge(("F", 0, k) if l == 1 else ("W", l - 1, k), ("W", l, k))

        P = lambda v: lay.coords[v]
        s_ = lambda name: (lambda l, k: (name, l, k))
        a, l_, r_ = s_("Sa"), s_("SL"), s_("SR")
        F = lambda k: ("F", 0, k)
        Wv = lambda k, l=1: ("W", l, k)

        for (d, st, outer, crotch_k) in ((dr, r_, ((0, 0), (3, 3)), ((0, 1), (3, 2))),
                                         (dl, l_, ((1, 1), (2, 2)), ((1, 0), (2, 3)))):
            for ka, ks in outer:
                lay.edge(a(0, ka), st(0, ks), Spline(tuple(map(tuple, W._hermite(
                    P(a(0, ka)), P(st(0, ks)), n, d)))), divisions=self.n_split)
                for l in levels:
                    lay.edge(a(l, ka), st(l, ks), sk.curve(W._hermite(
                        P(a(l, ka)), P(st(l, ks)), n, d), radii[l]))
            for kf, ks in crotch_k:
                lay.edge(F(kf), st(0, ks))
                for l in levels:
                    lay.edge(Wv(kf, l), st(l, ks))

        for l in levels:
            for k in range(4):
                lay.edge(a(l, k), Wv(k, l), sk.curve(
                    np.linspace(P(a(l, k)), P(Wv(k, l)), W._SAMPLES + 2)[1:-1], radii[l]))

        def on_daughter(d, side, t_, phi, rho):
            return o + t_ * d + rho * (math.cos(phi) * side + math.sin(phi) * u)
        m = W._SAMPLES // 2
        h = math.radians(self.angle) / 2
        for l in levels:
            rho = rl[l]
            t_apex = rho * math.cos(h) / math.sin(h)
            for k0, k1, z in ((0, 1, +1), (3, 2, -1)):
                phi_k = z * math.radians(W._KINK)
                t_k = t_apex * math.cos(phi_k)
                frac = np.linspace(0.0, 1.0, m + 2)[1:]
                ts = t + (t_k - t) * frac
                ps = z * math.pi / 4 + (phi_k - z * math.pi / 4) * frac
                half_r = [on_daughter(dr, -right_r, a_, b_, rho) for a_, b_ in zip(ts, ps)]
                half_l = [on_daughter(dl, right_l, a_, b_, rho)
                          for a_, b_ in zip(ts, ps)][:-1]
                lay.edge(Wv(k0, l), Wv(k1, l),
                         Polyline(tuple(map(tuple, half_r + half_l[::-1]))))
            t_mid = max(t, t_apex) + r * W._BULGE
            for k0, k1, d, side in ((0, 3, dr, -right_r), (1, 2, dl, right_l)):
                phi = np.linspace(-np.pi / 4, np.pi / 4, W._SAMPLES + 2)[1:-1]
                tt = t + (t_mid - t) * np.cos(2 * phi)
                pts = [on_daughter(d, side, ti, f, rho) for ti, f in zip(tt, phi)]
                lay.edge(Wv(k0, l), Wv(k1, l), sk.curve(pts[::-1], radii[l]))

        fluid = names[0]
        for mat, cyc in face_patches("A", spec):
            lay.block(list(cyc) + [a(lv, k) for (_, lv, k) in cyc], mat)
        for st, port in ((l_, "L"), (r_, "R")):
            for mat, cyc in face_patches(port, ds):
                lay.block([st(lv, k) for (_, lv, k) in cyc] + list(cyc), mat)

        lay.block([a(0, 0), a(0, 1), a(0, 2), a(0, 3), F(0), F(1), F(2), F(3)], fluid)
        lay.block([a(0, 0), a(0, 3), F(3), F(0), r_(0, 0), r_(0, 3), r_(0, 2), r_(0, 1)], fluid)
        lay.block([a(0, 1), a(0, 2), F(2), F(1), l_(0, 1), l_(0, 2), l_(0, 3), l_(0, 0)], fluid)

        def lift(v, l):
            return (v[0], l, v[2]) if v[0] in ("Sa", "SL", "SR") else Wv(v[2], l)
        rings = [
            (a(0, 0), a(0, 1), F(1), F(0)), (a(0, 3), a(0, 2), F(2), F(3)),
            (F(0), F(1), F(2), F(3)),
            (a(0, 0), a(0, 3), r_(0, 3), r_(0, 0)), (a(0, 0), F(0), r_(0, 1), r_(0, 0)),
            (F(0), F(3), r_(0, 2), r_(0, 1)), (a(0, 3), F(3), r_(0, 2), r_(0, 3)),
            (a(0, 1), a(0, 2), l_(0, 2), l_(0, 1)), (a(0, 1), F(1), l_(0, 0), l_(0, 1)),
            (F(1), F(2), l_(0, 3), l_(0, 0)), (a(0, 2), F(2), l_(0, 3), l_(0, 2)),
        ]
        for quad in rings:
            lay.block(list(quad) + [lift(v, 1) for v in quad], fluid)
            for l, material in zip(levels[1:], names[1:]):
                lay.block([lift(v, l - 1) for v in quad] + [lift(v, l) for v in quad],
                          material)
        lay.filling = "Stretch"
        lay.walls = {l: self.wall(frames[0], spec, radius=Rl[l]) for l in levels}
        lay.pin_walls = False
        return lay
