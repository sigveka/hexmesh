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

Scope of this prototype: single-layer specs, ``rot = 0``, ``n_outer = 4``,
branch radius ``r < R``.
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


def branch_spec(spec: PipeSpec, radius: float) -> PipeSpec:
    """Single-layer branch spec: *spec* with core radius *radius*."""
    name, shape = spec._core
    return (PipeSpec(nang=spec.nang, n_outer=spec.n_outer, rot=spec.rot, mbmp=spec.mbmp)
            .core(name, CircleShape(radius=radius, nang=shape.nang),
                  nrad=spec._core_nrad, mprg=spec._core_mprg))


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
        if spec.shells:
            raise ValueError("Tee prototype supports single-layer specs only")
        if spec.rot != 0 or spec.n_outer != 4:
            raise ValueError("Tee prototype requires rot = 0 and n_outer = 4")
        if self.toward is not None:
            raise ValueError("Tee: toward is resolved by Assembly.add(); add the "
                             "fitting to an assembly")
        junction_roll(self, spec)
        if not 0 < r < R:
            raise ValueError(f"branch radius {r} must be in (0, main radius {R})")
        if self.run_length <= r:
            raise ValueError(f"run_length must exceed the branch radius {r}")
        if self.branch_length <= R + 0.5 * r:
            raise ValueError(
                f"branch_length must exceed main radius + branch radius / 2 "
                f"({R + 0.5 * r:.4g})"
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

        def P(x, y, z):
            return o + x * ex + y * ey + z * ez

        t = r / math.sqrt(2)                 # saddle corner offset
        ci = OH_RATIO * t                    # branch inner-square corner offset
        si = OH_RATIO * R / math.sqrt(2)     # main inner-square corner offset
        zs = math.sqrt(R * R - t * t)        # saddle corner height
        zq = si                              # junction core top height
        z1 = R + 0.5 * r                     # branch turning-station height

        lay = BlockLayout()
        face_vertices(lay, "A", A, spec)
        face_vertices(lay, "B", B, spec)
        face_vertices(lay, "E", E, bspec)

        # Stations Sa (approach end, x<0) and Sd (departure end, x>0).
        # Corner order follows the main frame: 0 (−y,+z) 1 (+y,+z) 2 (+y,−z) 3 (−y,−z).
        for name, sx in (("Sa", -1.0), ("Sd", 1.0)):
            lay.vertex((name, 0, 0), P(sx * ci, -ci, zq))
            lay.vertex((name, 0, 1), P(sx * ci, +ci, zq))
            lay.vertex((name, 0, 2), P(sx * ci, +si, -si))
            lay.vertex((name, 0, 3), P(sx * ci, -si, -si))
            lay.vertex((name, 1, 0), P(sx * t, -t, zs))
            lay.vertex((name, 1, 1), P(sx * t, +t, zs))
            lay.vertex((name, 1, 2), P(sx * t, +R / math.sqrt(2), -R / math.sqrt(2)))
            lay.vertex((name, 1, 3), P(sx * t, -R / math.sqrt(2), -R / math.sqrt(2)))
            centre = tuple(P(sx * t, 0, 0))
            for k0, k1 in ((1, 2), (2, 3), (3, 0)):
                lay.edge((name, 1, k0), (name, 1, k1), ArcAbout(centre))

        # Saddle arcs: exact cylinder–cylinder intersection, branch angle φ.
        def saddle(phi0, phi1):
            phis = np.linspace(phi0, phi1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(r * math.cos(f), r * math.sin(f),
                                        math.sqrt(R * R - (r * math.sin(f)) ** 2)))
                                for f in phis))
        q = math.pi / 4
        lay.edge(("Sa", 1, 0), ("Sa", 1, 1), saddle(5 * q, 3 * q))   # through −x tip
        lay.edge(("Sd", 1, 0), ("Sd", 1, 1), saddle(-q, q))          # through +x tip
        lay.edge(("Sa", 1, 1), ("Sd", 1, 1), saddle(3 * q, q))       # through +y side
        lay.edge(("Sa", 1, 0), ("Sd", 1, 0), saddle(5 * q, 7 * q))   # through −y side

        # Main wall edges from the ports to the stations: on the cylinder.
        def on_cylinder(p0, p1):
            (x0, y0, z0), (x1, y1, z1_) = (np.linalg.solve(
                np.column_stack([ex, ey, ez]), p - o) for p in (p0, p1))
            a0, a1 = math.atan2(z0, y0), math.atan2(z1_, y1)
            s = np.linspace(0, 1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(x0 + (x1 - x0) * u,
                                        R * math.cos(a0 + (a1 - a0) * u),
                                        R * math.sin(a0 + (a1 - a0) * u))) for u in s))
        for port, st in (("A", "Sa"), ("B", "Sd")):
            for k in range(4):
                lay.edge((port, 0, k), (st, 0, k), divisions=self.n_run)
                pa, ps = lay.coords[(port, 1, k)], lay.coords[(st, 1, k)]
                geom = on_cylinder(pa, ps) if k in (0, 1) else None
                lay.edge((port, 1, k), (st, 1, k), geom, divisions=self.n_run)

        # Branch turning station Z (internal) at height z1; frame as port E.
        Z = Frame(o + z1 * ez, ez, ex)
        face_vertices(lay, "Z", Z, bspec, port=False)
        for k in range(4):
            lay.edge(("Z", 1, k), ("Z", 1, (k + 1) % 4), ArcAbout(tuple(Z.position)))
        # Branch corners k (frame: 0 (+x,+y) 1 (+x,−y) 2 (−x,−y) 3 (−x,+y)) meet:
        q_of = [("Sd", 0, 1), ("Sd", 0, 0), ("Sa", 0, 0), ("Sa", 0, 1)]
        s_of = [("Sd", 1, 1), ("Sd", 1, 0), ("Sa", 1, 0), ("Sa", 1, 1)]
        for k in range(4):
            lay.edge(q_of[k], ("Z", 0, k), divisions=self.n_turn)
            lay.edge(s_of[k], ("Z", 1, k), divisions=self.n_turn)
            for lvl in (0, 1):
                lay.edge(("Z", lvl, k), ("E", lvl, k), divisions=self.n_branch)

        fluid = spec.layer_names[0]
        sa = lambda l, k: ("Sa", l, k)
        sd = lambda l, k: ("Sd", l, k)

        # Approach and departure slabs: port patch → station patch.
        for port, st in (("A", "Sa"), ("B", "Sd")):
            for _, cyc in face_patches(port, spec):
                lay.block(list(cyc) + [(st, l, k) for (_, l, k) in cyc], fluid)

        # Junction.
        lay.block([sa(0, 3), sd(0, 3), sd(0, 2), sa(0, 2),
                   sa(0, 0), sd(0, 0), sd(0, 1), sa(0, 1)], fluid)            # C
        lay.block([sa(0, 2), sd(0, 2), sd(1, 2), sa(1, 2),
                   sa(0, 1), sd(0, 1), sd(1, 1), sa(1, 1)], fluid)            # S+
        lay.block([sa(0, 3), sd(0, 3), sd(1, 3), sa(1, 3),
                   sa(0, 0), sd(0, 0), sd(1, 0), sa(1, 0)], fluid)            # S−
        lay.block([sa(0, 3), sd(0, 3), sd(0, 2), sa(0, 2),
                   sa(1, 3), sd(1, 3), sd(1, 2), sa(1, 2)], fluid)            # Bb
        lay.block(q_of + [("Z", 0, k) for k in range(4)], fluid)             # branch core
        for k in range(4):
            j = (k + 1) % 4
            lay.block([q_of[k], q_of[j], s_of[j], s_of[k],
                       ("Z", 0, k), ("Z", 0, j), ("Z", 1, j), ("Z", 1, k)], fluid)

        # Branch run Z → E.
        for _, cyc in face_patches("E", bspec):
            lay.block([("Z", l, k) for (_, l, k) in cyc] + list(cyc), fluid)
        lay.wall = tee_wall(o, ex, ez, R, r)    # wall faces on the cylinders (task 0051)
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
