"""
Tee — perpendicular, centred side-branch junction as a block layout
(DESIGN.md §6.1 "Blocks", §7; geometry in docs/RESEARCH.md §3).

Topology
--------
The O-grid ring layer is continuous around the junction: it is an offset
of the whole tee wall.  Main-pipe ring blocks next to the hole turn the
corner into the branch instead of ending at a station:

* approach top ring  → branch −x ring    (turn face = approach station N patch)
* departure top ring → branch +x ring    (turn face = departure station N patch)
* junction side rings S± → branch ±y ring
* junction core C links the main cores (−x, +x) with the branch core (up)

Each turn face runs from a saddle arc to the branch core, bisecting the
270° re-entrant corner, so every block keeps a proper hex shape.  The
saddle corners are the branch OH corners (diagonals), at ±t = ±r/√2 along
both the main axis and the transverse direction.

Blocks: approach slab 5, departure slab 5, junction 9 (C, S+, S−, bottom
ring Bb, branch core + 4 branch rings), branch run 5.  All three ports keep
the standard OH pattern.

Shells (decision 0028, task 0052)
---------------------------------
Each shell adds a corner level l: the level-1 construction with R and r
grown by the cumulative thickness T_l.  The outward offset of the two
cylinders is the two cylinders R + T_l and r + T_l, so the saddle corners
sit on their intersection, at x = ±(r + T_l)/√2.  Every ring block
(S±, Bb, the turn blocks, the slab and branch-run ring patches) gets one
block per shell between levels l − 1 and l.  The turning station rises to
R + T + (r + T)/2 (T the total thickness).  Branch shells copy the main's.

Scope: circular layers, ``rot = 0``, ``n_outer = 4``, branch radius
``r < R``.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np

from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, OH_RATIO, Spline, bind_face, corner_shift,
    face_patches, face_vertices,
)
from .interface import Frame, junction_roll, junction_toward, outer_radius, rolled
from .signature import check_port_pairs

_SAMPLES = 9   # interior points per spline edge


def thicknesses(spec: PipeSpec) -> list[float]:
    """Cumulative shell thickness at each level ≥ 1 (0 at the wall)."""
    R = spec.core_shape.radius
    return [o.radius - R for o in spec.outlines]


def branch_spec(spec: PipeSpec, radius: float) -> PipeSpec:
    """Branch spec: *spec* with core radius *radius* and the same shells
    (names, thicknesses, ``nrad``, ``mprg``)."""
    name, shape = spec._core
    out = (PipeSpec(nang=spec.nang, n_outer=spec.n_outer, rot=spec.rot, mbmp=spec.mbmp)
           .core(name, CircleShape(radius=radius, nang=shape.nang),
                 nrad=spec._core_nrad, mprg=spec._core_mprg))
    T = thicknesses(spec)
    for sh, t0, t1 in zip(spec.shells, T, T[1:]):
        out.shell(sh.name, dR=t1 - t0, nrad=sh.nrad, mprg=sh.mprg)
    return out


def tee_wall(o, ex, ez, R: float, r: float):
    """Projection onto the tee wall: the main cylinder (axis ``o + x ex``,
    radius *R*) united with the branch cylinder (axis ``o + z ez``, z ≥ 0,
    radius *r*).  The nearer cylinder's radial projection that is not
    inside the other cylinder."""
    def main(p):
        a = (p - o) @ ex
        w = p - o - a * ex
        return o + a * ex + R * w / np.linalg.norm(w)

    def branch(p):
        h = max((p - o) @ ez, 0.0)
        w = p - o - h * ez
        return o + h * ez + r * w / np.linalg.norm(w)

    def d_main(q):
        v = q - o
        return np.linalg.norm(v - (v @ ex) * ex)

    def d_branch(q):
        v = q - o
        return np.linalg.norm(v - max(v @ ez, 0.0) * ez)

    def to_wall(p):
        p = np.asarray(p, dtype=float)
        pm, pb = main(p), branch(p)
        tol = 1e-12 * R
        ok = [q for q, outside in ((pm, d_branch(pm) >= r - tol),
                                   (pb, d_main(pb) >= R - tol)) if outside]
        return min(ok or [pm, pb], key=lambda q: np.linalg.norm(q - p))
    return to_wall


def _check_circle(spec: PipeSpec) -> None:
    if not isinstance(spec.core_shape, CircleShape):
        raise ValueError("Tee supports circular pipes only; no rectangular "
                         "tees yet (decision 0009)")
    for sh, o in zip(spec.shells, spec.outlines[1:]):
        if not isinstance(o, CircleShape):
            raise ValueError(f"Tee: shell `{sh.name}` is not circular; junction "
                             f"shells are circular only (decisions 0026, 0028)")


def turning_height(R: float, r: float, T: float) -> float:
    """Height of the branch turning station above the main axis: clear of
    the outer main shell by half the outer branch radius."""
    return R + T + 0.5 * (r + T)


@dataclass(frozen=True)
class Tee:
    """Perpendicular side-branch tee.

    Parameters
    ----------
    run_length : float
        Distance from the T-point to each main port (inlet and outlet).
    branch_length : float
        Distance from the main axis to the branch port.
    branch_radius : float
        Branch radius; must be below the main radius.
    n_run, n_branch : int
        Axial layers of the approach/departure runs and of the branch run.
    n_turn : int
        Layers of the junction's turning blocks (into the branch).
    roll : float
        Branch direction about the main axis in degrees, from the inlet's
        ``up`` (0: the branch points along ``up``; 90: along ``right``).
        A multiple of the section's period (90° for a circle), so the
        junction's corners land on the inlet face's (decision 0024).
    toward : 3-vector, optional
        Absolute branch direction, instead of *roll*: resolved to the
        nearest allowed roll when the tee is added; more than
        ``limits.JUNCTION_TOWARD_TOL`` off it is an error.

    Ports are ``main`` (the run outlet, keeping the inlet's ``up``) and
    ``branch``: ``add(…, names={"main": …, "branch": …})``.
    """

    strategies = frozenset({0})   # both port pairs: main in → main out, → branch
    port_names = ("main", "branch")

    run_length:    float
    branch_length: float
    branch_radius: float
    n_run:    int = 3
    n_branch: int = 3
    n_turn:   int = 2
    roll:     float = 0.0
    toward:   tuple | None = field(default=None, metadata={"input": True})

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell=None, outlet=None) -> "Tee":
        return junction_toward(self, inlet, spec)     # counts keep their defaults

    # -- ports --------------------------------------------------------

    def _origin_basis(self, inlet: Frame):
        inlet = rolled(inlet, self.roll)        # the branch points along this up
        ex, ez = inlet.normal, inlet.up
        ey = np.cross(ez, ex)
        o = inlet.position + self.run_length * ex
        return o, ex, ey, ez

    def ports(self, inlet: Frame, spec: PipeSpec):
        _check_circle(spec)       # the branch spec needs a radius
        o, ex, ey, ez = self._origin_basis(inlet)
        main = Frame(o + self.run_length * ex, ex, inlet.up)
        branch = Frame(o + self.branch_length * ez, ez, ex)
        return [(main, spec), (branch, branch_spec(spec, self.branch_radius))]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        _check_circle(spec)
        R, r = spec.core_shape.radius, self.branch_radius
        T = thicknesses(spec)[-1]
        if spec.rot != 0 or spec.n_outer != 4:
            raise ValueError("Tee prototype requires rot = 0 and n_outer = 4")
        if self.toward is not None:
            raise ValueError("Tee: toward is resolved by Assembly.add(); add the "
                             "fitting to an assembly")
        junction_roll(self, spec)
        if not 0 < r < R:
            raise ValueError(f"branch radius {r} must be in (0, main radius {R})")
        if self.run_length <= r + T:
            raise ValueError(f"run_length must exceed the branch's outer radius "
                             f"{r + T:.4g} (branch radius + shells)")
        if self.branch_length <= turning_height(R, r, T):
            raise ValueError(
                f"branch_length must exceed the turning station's height "
                f"{turning_height(R, r, T):.4g} (outer main radius + outer branch "
                f"radius / 2)"
            )
        for n in (self.n_run, self.n_branch, self.n_turn):
            if n < 1:
                raise ValueError("layer counts must be >= 1")

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        # Declared in the rolled frame; fill() binds the main ports' faces
        # (built in the unrolled one) with the corner shift between them.
        A, B, E = rolled(frames[0], self.roll), rolled(frames[1], self.roll), frames[2]
        R, r = spec.core_shape.radius, self.branch_radius
        bspec = branch_spec(spec, r)
        o, ex, ey, ez = self._origin_basis(frames[0])
        names = spec.layer_names
        levels = range(1, len(names) + 1)            # wall and shell boundaries
        Ts = thicknesses(spec)
        Rl = {l: R + Ts[l - 1] for l in levels}      # main radius at level l
        rl = {l: r + Ts[l - 1] for l in levels}      # branch radius at level l

        def P(x, y, z):
            return o + x * ex + y * ey + z * ez

        t = r / math.sqrt(2)                 # saddle corner offset (wall)
        ci = OH_RATIO * t                    # branch inner-square corner offset
        si = OH_RATIO * R / math.sqrt(2)     # main inner-square corner offset
        zq = si                              # junction core top height
        z1 = turning_height(R, r, Ts[-1])    # branch turning-station height

        lay = BlockLayout()
        face_vertices(lay, "A", A, spec)
        face_vertices(lay, "B", B, spec)
        face_vertices(lay, "E", E, bspec)

        # Stations Sa (approach end, x<0) and Sd (departure end, x>0); level
        # l at x = ±(r + T_l)/√2, so its top corners are on the offset saddle.
        # Corner order follows the main frame: 0 (−y,+z) 1 (+y,+z) 2 (+y,−z) 3 (−y,−z).
        for name, sx in (("Sa", -1.0), ("Sd", 1.0)):
            lay.vertex((name, 0, 0), P(sx * ci, -ci, zq))
            lay.vertex((name, 0, 1), P(sx * ci, +ci, zq))
            lay.vertex((name, 0, 2), P(sx * ci, +si, -si))
            lay.vertex((name, 0, 3), P(sx * ci, -si, -si))
            for l in levels:
                tl, Rk = rl[l] / math.sqrt(2), Rl[l]
                zs = math.sqrt(Rk * Rk - tl * tl)            # saddle corner height
                lay.vertex((name, l, 0), P(sx * tl, -tl, zs))
                lay.vertex((name, l, 1), P(sx * tl, +tl, zs))
                lay.vertex((name, l, 2), P(sx * tl, +Rk / math.sqrt(2), -Rk / math.sqrt(2)))
                lay.vertex((name, l, 3), P(sx * tl, -Rk / math.sqrt(2), -Rk / math.sqrt(2)))
                centre = tuple(P(sx * tl, 0, 0))
                for k0, k1 in ((1, 2), (2, 3), (3, 0)):
                    lay.edge((name, l, k0), (name, l, k1), ArcAbout(centre))

        # Saddle arcs: exact cylinder–cylinder intersection, branch angle φ.
        def saddle(l, phi0, phi1):
            Rk, rk = Rl[l], rl[l]
            phis = np.linspace(phi0, phi1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(rk * math.cos(f), rk * math.sin(f),
                                        math.sqrt(Rk * Rk - (rk * math.sin(f)) ** 2)))
                                for f in phis))
        q = math.pi / 4
        for l in levels:
            lay.edge(("Sa", l, 0), ("Sa", l, 1), saddle(l, 5 * q, 3 * q))   # through −x tip
            lay.edge(("Sd", l, 0), ("Sd", l, 1), saddle(l, -q, q))          # through +x tip
            lay.edge(("Sa", l, 1), ("Sd", l, 1), saddle(l, 3 * q, q))       # through +y side
            lay.edge(("Sa", l, 0), ("Sd", l, 0), saddle(l, 5 * q, 7 * q))   # through −y side

        # Main wall edges from the ports to the stations: on the cylinder.
        def on_cylinder(p0, p1, Rk):
            (x0, y0, z0), (x1, y1, z1_) = (np.linalg.solve(
                np.column_stack([ex, ey, ez]), p - o) for p in (p0, p1))
            a0, a1 = math.atan2(z0, y0), math.atan2(z1_, y1)
            s = np.linspace(0, 1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(x0 + (x1 - x0) * u,
                                        Rk * math.cos(a0 + (a1 - a0) * u),
                                        Rk * math.sin(a0 + (a1 - a0) * u))) for u in s))
        for port, st in (("A", "Sa"), ("B", "Sd")):
            for k in range(4):
                lay.edge((port, 0, k), (st, 0, k), divisions=self.n_run)
                for l in levels:
                    pa, ps = lay.coords[(port, l, k)], lay.coords[(st, l, k)]
                    geom = on_cylinder(pa, ps, Rl[l]) if k in (0, 1) else None
                    lay.edge((port, l, k), (st, l, k), geom, divisions=self.n_run)

        # Branch turning station Z (internal) at height z1; frame as port E.
        Z = Frame(o + z1 * ez, ez, ex)
        face_vertices(lay, "Z", Z, bspec, port=False)
        for l in levels:
            for k in range(4):
                lay.edge(("Z", l, k), ("Z", l, (k + 1) % 4), ArcAbout(tuple(Z.position)))
        # Branch corners k (frame: 0 (+x,+y) 1 (+x,−y) 2 (−x,−y) 3 (−x,+y)) meet:
        q_of = [("Sd", 0, 1), ("Sd", 0, 0), ("Sa", 0, 0), ("Sa", 0, 1)]

        def s_of(l):            # station top corners at level l, in branch order
            return [("Sd", l, 1), ("Sd", l, 0), ("Sa", l, 0), ("Sa", l, 1)]
        for k in range(4):
            lay.edge(q_of[k], ("Z", 0, k), divisions=self.n_turn)
            for l in levels:
                lay.edge(s_of(l)[k], ("Z", l, k), divisions=self.n_turn)
            for lvl in (0, *levels):
                lay.edge(("Z", lvl, k), ("E", lvl, k), divisions=self.n_branch)

        fluid = names[0]
        sa = lambda l, k: ("Sa", l, k)
        sd = lambda l, k: ("Sd", l, k)

        # Approach and departure slabs: port patch → station patch.
        for port, st in (("A", "Sa"), ("B", "Sd")):
            for material, cyc in face_patches(port, spec):
                lay.block(list(cyc) + [(st, l, k) for (_, l, k) in cyc], material)

        # Junction: core C, rings one per layer (between levels l − 1 and l),
        # branch core, turn blocks per layer.  Block order fixes the curve
        # order, so a single-layer tee keeps its node numbering.
        lay.block([sa(0, 3), sd(0, 3), sd(0, 2), sa(0, 2),
                   sa(0, 0), sd(0, 0), sd(0, 1), sa(0, 1)], fluid)            # C
        for l, material in zip(levels, names):
            i = l - 1
            lay.block([sa(i, 2), sd(i, 2), sd(l, 2), sa(l, 2),
                       sa(i, 1), sd(i, 1), sd(l, 1), sa(l, 1)], material)    # S+
            lay.block([sa(i, 3), sd(i, 3), sd(l, 3), sa(l, 3),
                       sa(i, 0), sd(i, 0), sd(l, 0), sa(l, 0)], material)    # S−
            lay.block([sa(i, 3), sd(i, 3), sd(i, 2), sa(i, 2),
                       sa(l, 3), sd(l, 3), sd(l, 2), sa(l, 2)], material)    # Bb
        lay.block(q_of + [("Z", 0, k) for k in range(4)], fluid)             # branch core
        for l, material in zip(levels, names):
            i = l - 1
            inner = q_of if i == 0 else s_of(i)
            for k in range(4):
                j = (k + 1) % 4
                lay.block([inner[k], inner[j], s_of(l)[j], s_of(l)[k],
                           ("Z", i, k), ("Z", i, j), ("Z", l, j), ("Z", l, k)], material)

        # Branch run Z → E.
        for material, cyc in face_patches("E", bspec):
            lay.block([("Z", l, k) for (_, l, k) in cyc] + list(cyc), material)
        # wall and shell boundaries on the offset cylinders (tasks 0051, 0052)
        lay.walls = {l: tee_wall(o, ex, ez, Rl[l], rl[l]) for l in levels}
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
                raise ValueError("port interface does not match Tee geometry")
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise ValueError(f"block layout invalid: {e}") from None

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count of the block layout (pure; DESIGN P4)."""
        return self.layout(frames, spec).cell_count()

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        for prefix, face, frame in zip("AB", faces, frames):
            bind_face(lay, prefix, face,
                      corner_shift(rolled(frame, self.roll), frame, spec))
        bind_face(lay, "E", faces[2])
        return lay.realise(spec.layer_names)
