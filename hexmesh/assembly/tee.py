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
from dataclasses import dataclass

import numpy as np

from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, OH_RATIO, Spline, bind_face, face_patches,
    face_vertices,
)
from .interface import Frame, outer_radius

_SAMPLES = 9   # interior points per spline edge


def branch_spec(spec: PipeSpec, radius: float) -> PipeSpec:
    """Single-layer branch spec: *spec* with core radius *radius*."""
    name, shape = spec._core
    return (PipeSpec(nang=spec.nang, n_outer=spec.n_outer, rot=spec.rot, mbmp=spec.mbmp)
            .core(name, CircleShape(radius=radius, nang=shape.nang),
                  nrad=spec._core_nrad, mprg=spec._core_mprg))


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
    """

    run_length:    float
    branch_length: float
    branch_radius: float
    n_run:    int = 3
    n_branch: int = 3
    n_turn:   int = 2

    # -- ports --------------------------------------------------------

    def _origin_basis(self, inlet: Frame):
        ex, ez = inlet.normal, inlet.up
        ey = np.cross(ez, ex)
        o = inlet.position + self.run_length * ex
        return o, ex, ey, ez

    def ports(self, inlet: Frame, spec: PipeSpec):
        o, ex, ey, ez = self._origin_basis(inlet)
        main = Frame(o + self.run_length * ex, ex, ez)
        branch = Frame(o + self.branch_length * ez, ez, ex)
        return [(main, spec), (branch, branch_spec(spec, self.branch_radius))]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        R, r = spec.core_shape.radius, self.branch_radius
        if spec.shells:
            raise ValueError("Tee prototype supports single-layer specs only")
        if spec.rot != 0 or spec.n_outer != 4:
            raise ValueError("Tee prototype requires rot = 0 and n_outer = 4")
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
        A, B, E = frames
        R, r = spec.core_shape.radius, self.branch_radius
        bspec = branch_spec(spec, r)
        o, ex, ey, ez = self._origin_basis(A)

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
        return lay

    # -- contract -----------------------------------------------------

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        self.check(spec)
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

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        for prefix, face in zip("ABE", faces):
            bind_face(lay, prefix, face)
        return lay.realise()
