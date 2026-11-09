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
Task 0118: the oriented junction cube (Bošnjak et al. 2024, Sect. 3.1,
Fig. 8; RESEARCH §4.3), measured for decision 0043.  A measurement
prototype: not exported, not in ``__all__``; ``Wye`` is untouched.

``CubeProbe`` is ``_wye_probe.WyeProbe`` (its axes, daughters, wall and
counts) with the cube layout instead of the hub:

- **The cube.**  Axes e1, e2, e3 from :func:`orient`.  Its eight corners
  lie on the wall, along the diagonals ±e1 ± e2 ± e3 from O; its centre
  hex has the same corners scaled by ``hub`` towards O.  Each of its six
  sides is one block from the centre hex's face out to the corners'
  face.
- **Ports.**  A side a pipe (the inlet or a daughter) is assigned to
  becomes five blocks: from the centre hex's face and the side's four
  cube edges straight to that pipe's station, an O-H face of the pipe's
  section ``station`` × its radius beyond whatever else is in the way
  (the paper's port, joined to its cross-section in one step: the
  station is the cross-section).  A side with no pipe keeps its block,
  whose outer face lies on the wall.
- **Counts.**  Cube and centre-hex edges carry ``nang``; the diagonals
  (centre-hex corner to cube corner) the ring's ``nrad``; a port's axial
  edges ``n_split``.
- **The wall.**  Cube edges and the edges from a cube corner to its
  station are splines through points on the wall (the tube union, as the
  probe's); wall faces are filled and their nodes projected, as today's
  wye's.  Shells are offset levels: every wall vertex once per level.

Every block is a 6-faced hex, so the realisation is today's transfinite
path.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

from ..core.spec import PipeSpec
from ..errors import InternalError
from . import wye as W
from ._wye_probe import WyeProbe
from .blocks import ArcAbout, BlockLayout, Spline, face_patches, face_vertices
from .errors import AssemblyError
from .interface import Frame, rolled
from .projection import TubeUnion
from .tee import thicknesses

_SIDES = [(i, s) for i in range(3) for s in (1, -1)]          # (axis, sign)
_PERMS = None                                                 # assignments, built on first use


def _rotation(w) -> np.ndarray:
    """Rotation matrix of the rotation vector *w* (Rodrigues)."""
    w = np.asarray(w, dtype=float)
    a = float(np.linalg.norm(w))
    if a < 1e-15:
        return np.eye(3)
    k = w / a
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def _assign(E: np.ndarray, rays: np.ndarray):
    """(score, sides, alignments): the best assignment of the rays to
    distinct sides of the cube with axes E's rows; the score is the
    smallest cosine between a ray and its side's normal, then (1e-6) their
    sum, which prefers the most square of tied orientations."""
    global _PERMS
    if _PERMS is None or _PERMS.shape[1] != len(rays):
        _PERMS = np.array(list(itertools.permutations(range(6), len(rays))))
    normals = np.array([s * E[i] for i, s in _SIDES])           # (6, 3)
    A = rays @ normals.T                                        # (m, 6)
    vals = A[np.arange(len(rays)), _PERMS]                      # (P, m)
    score = vals.min(axis=1) + 1e-6 * vals.sum(axis=1)
    b = int(np.argmax(score))
    return float(score[b]), [_SIDES[j] for j in _PERMS[b]], vals[b]


def orient(rays, frame: np.ndarray):
    """The cube's axes (rows) maximising the smallest angle between a ray
    and its side's plane (the paper's heuristic), and each ray's side.

    Searched over rotations of *frame* (rows: a right-handed start, e.g.
    the inlet's normal, right, up): a deterministic grid of rotation
    vectors, then Nelder–Mead from the best few.  The cube's 24
    symmetries make angles up to about 63° enough."""
    from scipy.optimize import minimize
    rays = np.asarray(rays, dtype=float)
    frame = np.asarray(frame, dtype=float)
    f = lambda w: -_assign(_rotation(w) @ frame, rays)[0]
    n_axes = 120
    i = np.arange(n_axes) + 0.5
    phi, z = np.pi * (1 + 5 ** 0.5) * i, 1 - 2 * i / n_axes
    axes = np.column_stack([np.sqrt(1 - z ** 2) * np.cos(phi), np.sqrt(1 - z ** 2) * np.sin(phi), z])
    cands = [np.zeros(3)] + [a * ang for a in axes for ang in np.radians([7.5, 15, 22.5, 30, 37.5, 45, 52.5, 60])]
    scored = sorted(cands, key=f)[:6]
    best = min((minimize(f, w, method="Nelder-Mead",
                         options={"xatol": 1e-10, "fatol": 1e-12, "maxiter": 4000}).x
                for w in scored), key=f)
    E = _rotation(best) @ frame
    _, sides, align = _assign(E, rays)
    return E, sides, align


def _exit(union: TubeUnion, start, direction, reach: float) -> np.ndarray:
    """The first point where the ray from *start* (inside *union*) along
    *direction* leaves it."""
    v = np.asarray(direction, float) / np.linalg.norm(direction)
    p0 = np.asarray(start, float)
    step = reach / 32
    lo = 0.0
    while union.signed_distance((p0 + (lo + step) * v)[None])[0] < 0:
        lo += step
        if lo > 40 * reach:
            raise InternalError("cube probe: a ray does not leave the junction")
    hi = lo + step
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        if union.signed_distance((p0 + mid * v)[None])[0] < 0:
            lo = mid
        else:
            hi = mid
    return p0 + 0.5 * (lo + hi) * v


@dataclass(frozen=True)
class CubeProbe(WyeProbe):
    """The oriented junction cube (see the module docstring)."""

    hub:     float = 0.4      # centre hex corners: this fraction of the way to the cube's
    station: float = 0.5      # station beyond the last obstacle, × the pipe's outer radius

    # -- geometry -----------------------------------------------------

    def rays(self, inlet: Frame):
        """{name: unit direction from O}: the inlet's pipe ("A"), the left
        ("L") and right ("R") daughters'."""
        o, n, u, dl, dr = self._axes(inlet)
        return o, {"A": -n, "L": dl, "R": dr}

    def cube(self, inlet: Frame):
        """(axes as rows, {pipe: (axis, sign)}, {pipe: cosine to its side})."""
        o, rays = self.rays(inlet)
        r_in = rolled(inlet, self.roll)
        frame = np.array([r_in.normal, r_in.right, r_in.up])
        E, sides, align = orient([rays[k] for k in "ALR"], frame)
        return E, dict(zip("ALR", sides)), dict(zip("ALR", (float(a) for a in align)))

    def _stations(self, inlet: Frame, spec: PipeSpec, corner):
        """{pipe: distance of its station from O}: beyond the farthest cube
        corner of its side, along its axis, and beyond the other pipes'
        tubes (the station circle clear of them), plus ``station`` × the
        pipe's outer radius."""
        o, rays = self.rays(inlet)
        E, sides, _ = self.cube(inlet)
        R = spec.core_shape.max_extent
        T = thicknesses(spec)[-1] if spec.shells else 0.0
        rho = {"A": R + T, "L": self._ratio() * R + T, "R": self._ratio() * R + T}
        outer = self.wall(inlet, spec, radius=R + T)
        tubes = dict(zip("ALR", outer.tubes))
        out = {}
        for p, d in rays.items():
            i, s = sides[p]
            far = max(float((corner(c) - o) @ d) for c in itertools.product((1, -1), repeat=3)
                      if c[i] == s)
            # an in-plane basis about d
            a = np.cross(d, E[(i + 1) % 3]); a /= np.linalg.norm(a)
            b = np.cross(d, a)
            phis = np.linspace(0, 2 * np.pi, 48, endpoint=False)
            ring = rho[p] * (np.outer(np.cos(phis), a) + np.outer(np.sin(phis), b))
            others = [t for q, t in tubes.items() if q != p]
            sc = 0.0
            while sc < 20 * R:
                pts = o + sc * d + ring
                if min(float((t.distance(pts) - t.radius).min()) for t in others) > 0.02 * R:
                    break
                sc += 0.01 * R
            out[p] = max(far, sc) + self.station * rho[p]
        return out

    def check(self, spec: PipeSpec) -> None:
        if not spec.core_shape.is_round:
            raise AssemblyError("CubeProbe: circular cores only", code="wye_needs_circle")
        self._ratio()
        for name in W._COUNTS:
            if getattr(self, name) is None:
                raise AssemblyError(f"CubeProbe: {name}=None is resolved by Assembly.add()",
                                    code="fitting_not_resolved")

    def resolve(self, inlet, spec, axial_cell=None, outlet=None):
        """``Wye.resolve`` with sentinel counts, before which the room
        check is skipped (the stations depend on the cube)."""
        return super().resolve(inlet, spec, axial_cell, outlet)

    def _room(self, inlet, spec, st) -> None:
        if not (st["A"] < self.run_length and max(st["L"], st["R"]) < self.branch_length):
            raise AssemblyError(f"CubeProbe: stations {st} beyond run {self.run_length} / "
                                f"branch {self.branch_length}", code="run_length_too_short")

    # -- layout -------------------------------------------------------

    def _layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        A, L, Rp = rolled(frames[0], self.roll), frames[1], frames[2]
        ds = self.daughter_spec(spec)
        R = spec.core_shape.max_extent
        names = spec.layer_names
        levels = list(range(1, len(names) + 1))
        Rl = {l: R + t for l, t in zip(levels, thicknesses(spec))}
        o, rays = self.rays(frames[0])
        E, sides, _ = self.cube(frames[0])
        unions = {l: self.wall(frames[0], spec, radius=Rl[l]) for l in levels}

        def corner_at(c, l):
            return _exit(unions[l], o, c[0] * E[0] + c[1] * E[1] + c[2] * E[2], R)
        signs = list(itertools.product((1, -1), repeat=3))
        C = {(l, c): corner_at(c, l) for l in levels for c in signs}
        st = self._stations(frames[0], spec, lambda c: C[(levels[-1], c)])
        self._room(frames[0], spec, st)

        lay = BlockLayout()
        specs = {"A": spec, "L": ds, "R": ds}
        ports = {"A": A, "L": L, "R": Rp}
        u = A.up
        for p in "ALR":
            face_vertices(lay, p, ports[p], specs[p])
            # stations face downstream, as the ports do: the inlet's against its ray
            sf = Frame(o + st[p] * rays[p], -rays[p] if p == "A" else rays[p], u)
            face_vertices(lay, "S" + p, sf, specs[p], port=False)
            for l in levels:
                for k in range(4):
                    lay.edge(("S" + p, l, k), ("S" + p, l, (k + 1) % 4),
                             ArcAbout(tuple(sf.position)))
            count = self.n_run if p == "A" else self.n_branch
            for lvl in (0, *levels):
                for k in range(4):
                    lay.edge((p, lvl, k), ("S" + p, lvl, k), divisions=count)
            for mat, cyc in face_patches(p, specs[p]):
                lay.block(list(cyc) + [("S" + p, lv, k) for (_, lv, k) in cyc], mat)

        for c in signs:
            lay.vertex(("F", 0, c), o + self.hub * (C[(1, c)] - o))
            for l in levels:
                lay.vertex(("C", l, c), C[(l, c)])
                lay.edge(("F", 0, c) if l == 1 else ("C", l - 1, c), ("C", l, c))

        def on_wall(points, l, axis=None):
            """Points moved onto the level-l wall: from O, or from *axis*."""
            out = []
            for q in points:
                if axis is None:
                    out.append(_exit(unions[l], o, q - o, R))
                else:
                    a = o + max(0.0, float((q - o) @ axis)) * axis
                    out.append(_exit(unions[l], a, q - a, R))
            return Spline(tuple(map(tuple, out)))

        fluid = names[0]
        F = lambda c: ("F", 0, c)
        Cv = lambda c, l: ("C", l, c)
        lay.block([F(c) for c in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                                  (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))], fluid)
        port_of = {side: p for p, side in sides.items()}
        frac = np.linspace(0.0, 1.0, W._SAMPLES + 2)[1:-1]
        drawn = set()
        for i, s in _SIDES:
            j, k = (i + 1) % 3, (i + 2) % 3
            cyc = []
            for a, b in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                c = [0, 0, 0]
                c[i], c[j], c[k] = s, a, b
                cyc.append(tuple(c))
            for l in levels:                       # the side's cube edges on the wall
                for m in range(4):
                    c0, c1 = cyc[m], cyc[(m + 1) % 4]
                    if (l, frozenset((c0, c1))) in drawn:     # shared with the next side
                        continue
                    drawn.add((l, frozenset((c0, c1))))
                    lay.edge(Cv(c0, l), Cv(c1, l),
                             on_wall([C[(l, c0)] + f * (C[(l, c1)] - C[(l, c0)]) for f in frac], l))
            p = port_of.get((i, s))
            if p is None:                          # a wall side: one block, and its shells
                lay.block([F(c) for c in cyc] + [Cv(c, 1) for c in cyc], fluid)
                for l, mat in zip(levels[1:], names[1:]):
                    lay.block([Cv(c, l - 1) for c in cyc] + [Cv(c, l) for c in cyc], mat)
                continue
            d = rays[p]
            # pair the side's corners with the station's, in the same turn about d
            sp = "S" + p
            centre = o + st[p] * d
            ref = lay.coords[(sp, 1, 0)] - centre
            ref2 = np.cross(d, ref)
            ang = lambda v: math.atan2(float(v @ ref2), float(v @ ref)) % (2 * math.pi)
            ks = sorted(range(4), key=lambda kk: ang(lay.coords[(sp, 1, kk)] - centre))
            cs = sorted(cyc, key=lambda c: ang(C[(1, c)] - o - float((C[(1, c)] - o) @ d) * d))
            shift = min(range(4), key=lambda m: sum(
                abs(math.remainder(ang(C[(1, cs[(q + m) % 4])] - o)
                                   - ang(lay.coords[(sp, 1, ks[q])] - centre), 2 * math.pi))
                for q in range(4)))
            pair = [(ks[q], cs[(q + shift) % 4]) for q in range(4)]
            for kk, c in pair:
                lay.edge(F(c), (sp, 0, kk), divisions=self.n_split)
                for l in levels:
                    pts = [C[(l, c)] + f * (lay.coords[(sp, l, kk)] - C[(l, c)]) for f in frac]
                    lay.edge(Cv(c, l), (sp, l, kk), on_wall(pts, l, axis=d))
            lay.block([F(c) for _, c in pair] + [(sp, 0, kk) for kk, _ in pair], fluid)
            for q in range(4):
                (k0, c0), (k1, c1) = pair[q], pair[(q + 1) % 4]
                lay.block([F(c0), F(c1), (sp, 0, k1), (sp, 0, k0),
                           Cv(c0, 1), Cv(c1, 1), (sp, 1, k1), (sp, 1, k0)], fluid)
                for l, mat in zip(levels[1:], names[1:]):
                    lay.block([Cv(c0, l - 1), Cv(c1, l - 1), (sp, l - 1, k1), (sp, l - 1, k0),
                               Cv(c0, l), Cv(c1, l), (sp, l, k1), (sp, l, k0)], mat)
        lay.filling = "Stretch"
        lay.walls = {l: unions[l] for l in levels}
        lay.pin_walls = False
        return lay
