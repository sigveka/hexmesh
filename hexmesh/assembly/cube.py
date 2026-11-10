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
Equal tees: the oriented junction cube (Bošnjak et al. 2024, Sect. 3.1,
Fig. 8; RESEARCH §4.3; decision 0043, amendment 2026-11-10; tasks 0118,
0122).  ``Tee`` routes a branch as wide as the main here
(:class:`CubeTee`) and delegates, as it does to ``duct_tap.TapTemplate``
on a rectangular main.  Square only (``EQUAL_LATERAL_ANGLE_MIN``): the
layout and :func:`orient` handle a lean, but equal laterals' meshed
quality falls as ``nang`` rises (task 0122).

- **The cube.**  Axes e1, e2, e3 from :func:`orient`: the rotation that
  maximises the smallest angle between a pipe (the inlet, the run, the
  branch) and the plane of the side it is assigned to (the paper's
  heuristic).  At 90° it is the inlet's own frame.  The cube's eight
  corners lie on the wall, along the diagonals ±e1 ± e2 ± e3 from the
  T-point O; its centre hex has the same corners scaled by ``hub``
  towards O.
- **Ports.**  A side a pipe is assigned to becomes five blocks, from the
  centre hex's face and the side's four cube edges straight to that
  pipe's station: an O-H face of the pipe's section, ``station`` × the
  pipe's outer radius beyond the farthest cube corner and the other
  pipes' tubes.  The station's run to the port is a plain swept block.
  The other three sides keep one block each, whose outer face lies on
  the wall.
- **Counts.**  Cube and centre-hex edges carry ``nang``; the diagonals
  the ring's ``nrad``; a port's split edges ``n_turn``; the runs
  ``n_run`` and the branch ``n_branch``.
- **The wall.**  Cube edges and the edges from a cube corner to its
  station are splines through points on the wall, the main cylinder
  united with the branch's (``tee.tee_wall``); wall faces are filled and
  their nodes projected (decision 0029), recorded in
  ``Assembly.projection_report``.  Shells are offset levels.
- **The crease** where the branch meets the main lies on cube edges only
  on the main's two sides; elsewhere it crosses faces, and its chord
  error is first order in ``nang``: 3.7 % R at nang 8, 2.0 at 16, 1.4 at
  24, 1.1 at 32 (task 0122; decision 0043 keeps the 1 % R gate and
  states the miss).
- **Refinement.**  The wall sides' flat block faces sit up to 0.18 R
  inside the curved wall, and projection moves their nodes that far
  whatever ``nang`` is, so finer meshes crush more, thinner cells: the
  meshed min SJ is 0.511, 0.399, 0.353, 0.330 and 0.305 at nang 8, 16,
  24, 32 and 48.  First order only: second-order hexes invert near the
  wall, so ``mesh(order=2)`` rejects the equal tee (``Tee``'s
  ``second_order_limitation``).

Every block is a 6-faced hex: gmsh's transfinite path meshes every
element (decision 0046).
"""

from __future__ import annotations

import copy
import itertools
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from ..core.spec import PipeSpec
from ..errors import InternalError
from .blocks import ArcAbout, BlockLayout, LayoutError, Spline, face_patches, face_vertices
from .errors import AssemblyError
from .interface import Frame, outer_radius, rolled
from .junction_quality import CUBE_BLOCKS, CUBE_HINT, _layout_key, nonorth_tiers, predicted_angle
from .limits import (EQUAL_LATERAL_ANGLE_MIN, EQUAL_TEE_NANG_CLEAN, PREDICTED_SJ_MIN,
                     PREDICTED_SJ_WARN)

#: The square tee's measured meshed min SJ by nang, single and shelled
#: (task 0127; validation/tools/equal_tee.json).  The predicted SJ doesn't
#: see this fall, so validate() reads it here: measured values only.
_MEASURED_SJ = {8: 0.511, 16: 0.399, 24: 0.353, 32: 0.330, 48: 0.305, 64: 0.293}
from .projection import Tube, TubeUnion

_SIDES = [(i, s) for i in range(3) for s in (1, -1)]          # (axis, sign)
_PERMS = None                                                 # assignments, built on first use
_SAMPLES = 7                                                  # points per wall spline
_PIPES = "ABE"                                                # inlet, run outlet, branch

#: the cube's shape per angle: (angle, hub, station), interpolated in
#: angle.  Task 0122: at 90° the meshed SJ doesn't depend on the hub
#: (0.4–0.8) or the station (0.25–4, bare and insulated 0.25 R and 0.5 R,
#: nang 8 and 16), so the station is the shortest measured, which fits
#: the shortest runs.  Equal laterals (``EQUAL_LATERAL_ANGLE_MIN``)
#: measured 0.5 at 75°, 2 at 60° and 3 at 45° and 40°.
SHAPE = ((90.0, 0.6, 0.25),)

#: an inlet frame for what doesn't depend on where the tee is: the
#: stations' distances (the layout is rigid in the inlet's frame)
_CANON = Frame(np.zeros(3), np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0]))

LAYOUT_CACHE_SIZE = 16
_LAYOUTS: OrderedDict = OrderedDict()
_LOCK = threading.Lock()


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
    and its side's plane (the paper's heuristic), each ray's side and its
    cosine to the side's normal.

    Searched over rotations of *frame* (rows: a right-handed start, e.g.
    the inlet's normal, right, up): a deterministic grid of rotation
    vectors, then Nelder–Mead from the best few.  The cube's 24
    symmetries make angles up to about 63° enough.  The identity is tried
    first and kept when nothing beats it."""
    from scipy.optimize import minimize
    rays = np.asarray(rays, dtype=float)
    frame = np.asarray(frame, dtype=float)
    f = lambda w: -_assign(_rotation(w) @ frame, rays)[0]
    n_axes = 120
    i = np.arange(n_axes) + 0.5
    phi, z = np.pi * (1 + 5 ** 0.5) * i, 1 - 2 * i / n_axes
    axes = np.column_stack([np.sqrt(1 - z ** 2) * np.cos(phi),
                            np.sqrt(1 - z ** 2) * np.sin(phi), z])
    cands = [np.zeros(3)] + [a * ang for a in axes
                             for ang in np.radians([7.5, 15, 22.5, 30, 37.5, 45, 52.5, 60])]
    best = np.zeros(3)
    if f(best) > -1 + 1e-12:                    # not already square to every pipe
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
            raise InternalError("junction cube: a ray does not leave the junction")
    hi = lo + step
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        if union.signed_distance((p0 + mid * v)[None])[0] < 0:
            lo = mid
        else:
            hi = mid
    return p0 + 0.5 * (lo + hi) * v


def shape(angle: float) -> tuple[float, float]:
    """(hub, station) at *angle*, interpolated in :data:`SHAPE`."""
    a = np.array([s[0] for s in SHAPE])
    order = np.argsort(a)
    return (float(np.interp(angle, a[order], np.array([s[1] for s in SHAPE])[order])),
            float(np.interp(angle, a[order], np.array([s[2] for s in SHAPE])[order])))


@dataclass(frozen=True)
class CubeTee:
    """An equal ``Tee``: its geometry, checks, layout, quality and fill
    (``Tee`` delegates here when the branch is as wide as the main).
    *hub* and *station* override :func:`shape` (measurements only)."""

    tee: object
    hub: float | None = None
    station: float | None = None

    def _shape(self) -> tuple[float, float]:
        h, s = shape(self.tee.angle)
        return (h if self.hub is None else self.hub, s if self.station is None else self.station)

    # -- geometry -----------------------------------------------------

    def rays(self, inlet: Frame):
        """(O, {pipe: unit direction from O}): the inlet ("A"), the run's
        outlet ("B") and the branch ("E")."""
        o, ex, _, _ = self.tee._origin_basis(inlet)
        _, d, _ = self.tee._branch_axes(inlet)
        return o, {"A": -ex, "B": ex, "E": d}

    def wall(self, inlet: Frame, spec: PipeSpec, radius: float | None = None) -> TubeUnion:
        """The main cylinder united with the branch's, at *radius* (an
        offset level; default the core's)."""
        o, rays = self.rays(inlet)
        rho = spec.core_shape.max_extent if radius is None else radius
        return TubeUnion([Tube(tuple(o), tuple(rays["B"]), rho, ray=False),
                          Tube(tuple(o), tuple(rays["E"]), rho)])

    def cube(self, inlet: Frame):
        """(axes as rows, {pipe: (axis, sign)}, {pipe: cosine to its side})."""
        _, rays = self.rays(inlet)
        r_in = rolled(inlet, self.tee.roll)
        frame = np.array([r_in.normal, r_in.right, r_in.up])
        E, sides, align = orient([rays[k] for k in _PIPES], frame)
        return E, dict(zip(_PIPES, sides)), dict(zip(_PIPES, (float(a) for a in align)))

    def corners(self, inlet: Frame, spec: PipeSpec, radius: float):
        """{signs: the cube corner on the wall at *radius*}."""
        o, _ = self.rays(inlet)
        E, _, _ = self.cube(inlet)
        union = self.wall(inlet, spec, radius)
        return {c: _exit(union, o, c[0] * E[0] + c[1] * E[1] + c[2] * E[2],
                         spec.core_shape.max_extent)
                for c in itertools.product((1, -1), repeat=3)}

    def stations(self, inlet: Frame, spec: PipeSpec, corner=None) -> dict[str, float]:
        """{pipe: distance of its station from O}: beyond the farthest cube
        corner of its side, along its axis, and beyond the other pipes'
        tubes (the station circle 0.02 R clear of them), plus ``station`` ×
        the outer radius."""
        R, rho = spec.core_shape.max_extent, outer_radius(spec)
        o, rays = self.rays(inlet)
        E, sides, _ = self.cube(inlet)
        if corner is None:
            cs = self.corners(inlet, spec, rho)
            corner = cs.__getitem__
        tubes = dict(zip("BE", self.wall(inlet, spec, rho).tubes))
        tubes["A"] = tubes["B"]                       # the main is one whole line
        _, station = self._shape()
        out = {}
        for p, d in rays.items():
            i, s = sides[p]
            far = max(float((corner(c) - o) @ d) for c in itertools.product((1, -1), repeat=3)
                      if c[i] == s)
            a = np.cross(d, E[(i + 1) % 3])
            a /= np.linalg.norm(a)
            b = np.cross(d, a)
            phis = np.linspace(0, 2 * np.pi, 48, endpoint=False)
            ring = rho * (np.outer(np.cos(phis), a) + np.outer(np.sin(phis), b))
            others = [tubes["E"]] if p != "E" else [tubes["B"]]
            sc = 0.0
            while sc < 20 * R:
                if min(float((t.distance(o + sc * d + ring) - t.radius).min())
                       for t in others) > 0.02 * R:
                    break
                sc += 0.01 * R
            out[p] = max(far, sc) + station * rho
        return out

    # -- resolve and checks -------------------------------------------------

    def run_needed(self, spec: PipeSpec) -> tuple[float, float]:
        """(run_length, branch_length) the stations need: each must exceed
        its station.  Measured in :data:`_CANON` with a placeholder run
        (the stations sit at distances from O, wherever the tee is)."""
        from dataclasses import replace
        probe = CubeTee(replace(self.tee, run_length=1.0), self.hub, self.station)
        st = probe.stations(_CANON, spec)
        return max(st["A"], st["B"]), st["E"]

    def resolve(self, inlet: Frame, spec: PipeSpec) -> float:
        """The default ``run_length``: the stations' plus half a radius."""
        return self.run_needed(spec)[0] + 0.5 * spec.core_shape.max_extent

    def check(self, spec: PipeSpec) -> None:
        tee = self.tee
        if tee.angle < EQUAL_LATERAL_ANGLE_MIN:
            raise AssemblyError(
                f"Tee: an equal lateral ({tee.angle:g}°): equal tees are square only "
                f"(EQUAL_LATERAL_ANGLE_MIN {EQUAL_LATERAL_ANGLE_MIN:g}°)",
                code="equal_lateral_angle_below_min", where={"field": "angle"},
                value=tee.angle, limit="EQUAL_LATERAL_ANGLE_MIN",
                hint="equal laterals aren't supported yet; a reduced branch "
                     "(branch_radius <= TEE_MAX_RATIO R) builds at this angle")
        run, branch = self.run_needed(spec)
        if tee.run_length <= run:
            raise AssemblyError(f"run_length must exceed the equal tee's stations {run:.4g}",
                                code="run_length_too_short", where={"field": "run_length"},
                                value=tee.run_length, limit={"min_exclusive": run},
                                hint=f"run_length > {run:.4g}, or run_length=None to resolve it")
        if tee.branch_length <= branch:
            raise AssemblyError(f"branch_length must exceed the equal tee's branch station "
                                f"{branch:.4g}",
                                code="branch_length_too_short", where={"field": "branch_length"},
                                value=tee.branch_length, limit={"min_exclusive": branch},
                                hint=f"branch_length > {branch:.4g}")

    # -- layout -----------------------------------------------------------

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        """The layout at *frames* (inlet, run outlet, branch), cached by
        value as ``Wye.layout`` caches (the orientation search and the wall
        curves cost about a second); each call gets its own copy."""
        key = (_layout_key(self.tee, frames, spec), self.hub, self.station)
        with _LOCK:
            hit = _LAYOUTS.get(key)
            if hit is not None:
                _LAYOUTS.move_to_end(key)
        if hit is None:
            hit = self._layout(frames, spec)
            with _LOCK:
                _LAYOUTS[key] = hit
                while len(_LAYOUTS) > LAYOUT_CACHE_SIZE:
                    _LAYOUTS.popitem(last=False)
        return copy.deepcopy(hit)

    def _layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        tee = self.tee
        # declared in the rolled frame, as Tee's; fill() binds the main ports
        A, B, Eb = rolled(frames[0], tee.roll), rolled(frames[1], tee.roll), frames[2]
        R = spec.core_shape.max_extent
        names = spec.layer_names
        levels = list(range(1, len(names) + 1))
        Rl = {l: o.max_extent for l, o in zip(levels, spec.outlines)}
        o, rays = self.rays(frames[0])
        E, sides, _ = self.cube(frames[0])
        unions = {l: self.wall(frames[0], spec, radius=Rl[l]) for l in levels}
        hub, _ = self._shape()

        def corner_at(c, l):
            return _exit(unions[l], o, c[0] * E[0] + c[1] * E[1] + c[2] * E[2], R)
        signs = list(itertools.product((1, -1), repeat=3))
        C = {(l, c): corner_at(c, l) for l in levels for c in signs}
        st = self.stations(frames[0], spec, lambda c: C[(levels[-1], c)])

        lay = BlockLayout()
        ports = {"A": A, "B": B, "E": Eb}
        ups = {"A": A.up, "B": A.up, "E": Eb.up}
        counts = {"A": tee.n_run, "B": tee.n_run, "E": tee.n_branch}
        for p in _PIPES:
            face_vertices(lay, p, ports[p], spec)
            # stations face downstream, as the ports do: the inlet's against its ray
            sf = Frame(o + st[p] * rays[p], -rays[p] if p == "A" else rays[p], ups[p])
            face_vertices(lay, "S" + p, sf, spec, port=False)
            for l in levels:
                for k in range(4):
                    lay.edge(("S" + p, l, k), ("S" + p, l, (k + 1) % 4),
                             ArcAbout(tuple(sf.position)))
            for lvl in (0, *levels):
                for k in range(4):
                    lay.edge((p, lvl, k), ("S" + p, lvl, k), divisions=counts[p])
            for mat, cyc in face_patches(p, spec):
                lay.block(list(cyc) + [("S" + p, lv, k) for (_, lv, k) in cyc], mat)

        for c in signs:
            lay.vertex(("F", 0, c), o + hub * (C[(1, c)] - o))
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
        frac = np.linspace(0.0, 1.0, _SAMPLES + 2)[1:-1]
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
                lay.edge(F(c), (sp, 0, kk), divisions=tee.n_turn)
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

    # -- quality ------------------------------------------------------------

    def predicted_sj(self, frames: list[Frame], spec: PipeSpec) -> float:
        return float(self.layout(frames, spec).corner_jacobians().min())

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """The predicted-SJ tiers (raise below ``PREDICTED_SJ_MIN``, warn
        below ``PREDICTED_SJ_WARN``), the layout's own check, and the
        non-orthogonality tiers."""
        sj = self.predicted_sj(frames, spec)
        found = []
        for tier, name in ((PREDICTED_SJ_MIN, "PREDICTED_SJ_MIN"),
                           (PREDICTED_SJ_WARN, "PREDICTED_SJ_WARN")):
            if sj >= tier:
                continue
            hint = "a branch radius <= TEE_MAX_RATIO R"
            msg = (f"equal tee at {self.tee.angle:g}°: predicted corner scaled Jacobian "
                   f"{sj:.3f} is below {name} {tier:g}; {hint}")
            if tier == PREDICTED_SJ_MIN:
                raise AssemblyError(msg, code="predicted_sj_below_minimum", value=sj,
                                    limit="PREDICTED_SJ_MIN", hint=hint)
            found.append(msg)
            break
        found += self._nang_tier(spec)
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise AssemblyError.wrap(e, f"block layout invalid: {e}",
                                     code="block_layout_invalid") from None
        return found + nonorth_tiers(self.tee, frames, spec, lambda: self.layout(frames, spec),
                                     CUBE_BLOCKS, CUBE_HINT)

    @staticmethod
    def _nang_tier(spec: PipeSpec) -> list[str]:
        """Above ``EQUAL_TEE_NANG_CLEAN``, the measured SJ at the next
        measured nang, or, past the last, that it is unmeasured."""
        nang = spec.nang
        if nang is None or nang <= EQUAL_TEE_NANG_CLEAN:
            return []
        hint = f"nang <= EQUAL_TEE_NANG_CLEAN ({EQUAL_TEE_NANG_CLEAN}) builds without a warning"
        above = [n for n in sorted(_MEASURED_SJ) if n >= nang]
        last = max(_MEASURED_SJ)
        if above:
            n = above[0]
            told = (f"meshed corner scaled Jacobian measured {_MEASURED_SJ[n]:.3f} "
                    f"at nang {n}, below PREDICTED_SJ_WARN {PREDICTED_SJ_WARN:g}")
        else:
            told = (f"meshed quality is unmeasured above nang {last} "
                    f"({_MEASURED_SJ[last]:.3f} there, falling as nang rises)")
        return [f"equal tee at nang {nang}: {told}; {hint}"]

    def predicted_nonorth(self, frames: list[Frame], spec: PipeSpec) -> float:
        return predicted_angle(self.tee, frames, spec, lambda: self.layout(frames, spec))
