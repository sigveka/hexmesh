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

Duct taps (decision 0033, task 0070)
------------------------------------
On a rectangular main the tee is a **duct tap**: the branch (``branch=``,
a ``RectShape`` or a ``CircleShape``) leaves a flat face (``face=``),
narrower than it, with the pillowed layout of ``duct_tap.DuctTap``.  The
branch keeps the main's counts per side (a class-0 port); its frame's
``up`` is the main's axis for a tap on an up/down face and the main's
``up`` for one on a right/left face, so its ``half_w``/``nang_w`` run
along the main's ``right`` or along the main's axis respectively.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, replace

import numpy as np

from ..core.shape import CircleShape, RectShape
from ..core.spec import PipeSpec
from . import limits
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, OH_RATIO, Spline, bind_face, corner_shift,
    face_patches, face_vertices,
)
from .duct_tap import DuctTap
from .interface import Frame, junction_roll, junction_toward, outer_radius, rolled
from .limits import PREDICTED_SJ_MIN, PREDICTED_SJ_WARN
from .projection import Tube, TubeUnion
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


def tee_wall(o, ex, ez, R: float, r: float) -> TubeUnion:
    """The tee wall: the main cylinder (axis ``o + x ex``, radius *R*)
    united with the branch cylinder (axis ``o + z ez``, z ≥ 0, radius *r*),
    as a wall projector (decision 0029)."""
    return TubeUnion([Tube(tuple(o), tuple(ex), R, ray=False),
                      Tube(tuple(o), tuple(ez), r)])


def _is_duct(spec: PipeSpec) -> bool:
    return isinstance(spec.core_shape, RectShape)


def _check_circle(spec: PipeSpec) -> None:
    if not isinstance(spec.core_shape, CircleShape):
        raise ValueError("Tee: a pipe tee needs a circular main; a rectangular "
                         "main is a duct tap (branch=, face=; decision 0033)")
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
    run_length : float, optional
        Distance from the T-point to each main port (inlet and outlet).
        ``None`` (the default) is resolved when the tee is added:
        ``r + T + 0.5 R`` (T the total shell thickness), or the shortest
        run whose predicted corner scaled Jacobian reaches
        ``PREDICTED_SJ_WARN``, whichever is longer (task 0052).
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
        ``limits.JUNCTION_TOWARD_TOL`` off it is an error.  Pipe tees only.
    branch : RectShape or CircleShape, optional
        The branch section on a rectangular main (a duct tap, decision
        0033); on a circular main a ``CircleShape`` is the same as
        ``branch_radius``.  Its counts must be the main's (module notes).
    face : "wide" or "narrow", optional
        Duct taps: the face the branch leaves (default "wide"); ``roll``
        0 or 180 picks which of the two.
    margin, dome, sheet : float, optional
        Duct taps: layout tunables (``duct_tap.DuctTap``), resolved when
        the tee is added to the best predicted quality; give them to
        override.
    n_wall : int, optional
        Duct taps: cells from a station to the hole, resolved when the tee
        is added (``DuctTap.wall_cells``).

    Ports are ``main`` (the run outlet, keeping the inlet's ``up``) and
    ``branch``: ``add(…, names={"main": …, "branch": …})``.
    """

    strategies = frozenset({0})   # both port pairs: main in → main out, → branch
    port_names = ("main", "branch")

    run_length:    float | None = None
    branch_length: float | None = None      # required
    branch_radius: float | None = field(default=None, metadata={"input": True})   # or branch
    n_run:    int = 3
    n_branch: int = 3
    n_turn:   int = 2
    roll:     float = 0.0
    toward:   tuple | None = field(default=None, metadata={"input": True})
    # duct taps only (absent from a pipe tee's JSON)
    branch:   CircleShape | RectShape | None = field(default=None, metadata={"input": True})
    face:     str | None = field(default=None, metadata={"input": True})
    margin:   float | None = field(default=None, metadata={"input": True})
    dome:     float | None = field(default=None, metadata={"input": True})
    sheet:    float | None = field(default=None, metadata={"input": True})
    n_wall:   int | None = field(default=None, metadata={"input": True})

    def __post_init__(self):
        missing = ["branch_length"] if self.branch_length is None else []
        if self.branch_radius is None and self.branch is None:
            missing.append("branch_radius (or branch)")
        if missing:
            raise TypeError(f"Tee: missing required argument(s): {', '.join(missing)}")
        if self.branch_radius is not None and self.branch is not None:
            raise TypeError("Tee: give branch_radius or branch, not both")

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell=None, outlet=None) -> "Tee":
        if _is_duct(spec):
            return self._resolve_duct(inlet, spec)
        if isinstance(self.branch, CircleShape):       # the shorthand's long form
            if self.branch.nang != spec.core_shape.nang:
                raise ValueError(f"Tee: branch nang {self.branch.nang} must be the main's "
                                 f"{spec.core_shape.nang}")
            self = replace(self, branch_radius=self.branch.radius, branch=None)
        tee = junction_toward(self, inlet, spec)      # counts keep their defaults
        if tee.run_length is None:
            _check_circle(spec)
            R, r, T = spec.core_shape.radius, tee.branch_radius, thicknesses(spec)[-1]
            run = r + T + 0.5 * R
            if r < R:              # else check() rejects it, naming the radius
                need = tee.shortest_run(inlet, spec, PREDICTED_SJ_WARN)
                run = max(run, need or 0.0)
            tee = replace(tee, run_length=run)
        return tee

    # -- predicted quality (task 0052) ----------------------------------

    def predicted_sj(self, inlet: Frame, spec: PipeSpec, run_length: float | None = None) -> float:
        """Min corner scaled Jacobian of the block layout, with
        *run_length* if given (pure)."""
        tee = self if run_length is None else replace(self, run_length=run_length)
        frames = [inlet] + [f for f, _ in tee.ports(inlet, spec)]
        return float(tee.layout(frames, spec).corner_jacobians().min())

    def shortest_run(self, inlet: Frame, spec: PipeSpec, tier: float) -> float | None:
        """Shortest ``run_length`` (to 1e-3 R, rounded up) whose predicted
        corner scaled Jacobian reaches *tier*; ``None`` if no length does:
        the branch ratio limits the junction core.  Bisection on the pure
        layout; the SJ rises with the run up to a plateau about 1.5 R long."""
        R, r, T = spec.core_shape.radius, self.branch_radius, thicknesses(spec)[-1]
        lo, hi = r + T, r + T + 2 * R
        if self.predicted_sj(inlet, spec, hi) < tier:
            return None
        q = 1e-3 * R
        while hi - lo > q:
            mid = 0.5 * (lo + hi)
            if self.predicted_sj(inlet, spec, mid) >= tier:
                hi = mid
            else:
                lo = mid
        return round(math.ceil(hi / q - 1e-9) * q, 12)

    def _quality(self, inlet: Frame, spec: PipeSpec) -> list[str]:
        """Apply the predicted-SJ tiers: raise below ``PREDICTED_SJ_MIN``,
        return a warning below ``PREDICTED_SJ_WARN``.  Each names the
        predicted SJ and the shortest run that reaches the tier."""
        sj = self.predicted_sj(inlet, spec)
        for tier, name in ((PREDICTED_SJ_MIN, "PREDICTED_SJ_MIN"),
                           (PREDICTED_SJ_WARN, "PREDICTED_SJ_WARN")):
            if sj >= tier:
                continue
            need = self.shortest_run(inlet, spec, tier)
            if need is None:
                hint = (f"no run_length reaches it: the branch ratio r/R "
                        f"{self.branch_radius / spec.core_shape.radius:.3g} limits the "
                        f"junction core")
            else:
                hint = f"run_length {need:.4g} or more reaches it (now {self.run_length:.4g})"
            msg = (f"predicted corner scaled Jacobian {sj:.3f} is below {name} "
                   f"{tier:g}; {hint}")
            if tier == PREDICTED_SJ_MIN:
                raise ValueError(msg)
            return [msg]
        return []

    # -- ports --------------------------------------------------------

    def _origin_basis(self, inlet: Frame):
        inlet = rolled(inlet, self.roll)        # the branch points along this up
        ex, ez = inlet.normal, inlet.up
        ey = np.cross(ez, ex)
        o = inlet.position + self.run_length * ex
        return o, ex, ey, ez

    def ports(self, inlet: Frame, spec: PipeSpec):
        if _is_duct(spec):
            return self._tap(inlet, spec).ports(inlet, spec)
        _check_circle(spec)       # the branch spec needs a radius
        o, ex, ey, ez = self._origin_basis(inlet)
        main = Frame(o + self.run_length * ex, ex, inlet.up)
        branch = Frame(o + self.branch_length * ez, ez, ex)
        return [(main, spec), (branch, branch_spec(spec, self.branch_radius))]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        if _is_duct(spec):
            return self._check_duct(spec)
        _check_circle(spec)
        duct_only = [n for n in ("branch", "face", "margin", "dome", "sheet", "n_wall")
                     if getattr(self, n) is not None]
        if duct_only:
            raise ValueError(f"Tee: {', '.join(duct_only)} are for a duct tap (a "
                             f"rectangular main); on a pipe give branch_radius")
        if self.run_length is None:
            raise ValueError("Tee: run_length=None is resolved by Assembly.add(); "
                             "add the fitting to an assembly")
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
        if _is_duct(spec):
            return self._tap(frames[0], spec).layout(frames, spec)
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

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """Raise ValueError if invalid; return warnings (predicted quality
        below ``PREDICTED_SJ_WARN``)."""
        self.check(spec)
        check_port_pairs(self, [spec] + [s for _, s in self.ports(frames[0], spec)])
        expected = [f for f, _ in self.ports(frames[0], spec)]
        for want, got in zip(expected, frames[1:]):
            if (np.linalg.norm(want.position - got.position) > 1e-9 * self.run_length
                    or np.dot(want.normal, got.normal) < 1 - 1e-9
                    or np.dot(want.up, got.up) < 1 - 1e-9):
                raise ValueError("port interface does not match Tee geometry")
        found = (self._duct_quality(frames, spec) if _is_duct(spec)
                 else self._quality(frames[0], spec))      # before the layout's own
        try:                                        # inversion check: names a run
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise ValueError(f"block layout invalid: {e}") from None
        return found

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count of the block layout (pure; DESIGN P4)."""
        return self.layout(frames, spec).cell_count()

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        if _is_duct(spec):          # declared in the ports' own frames
            for prefix, face in zip("ABE", faces):
                bind_face(lay, prefix, face)
            return lay.realise(spec.layer_names)
        for prefix, face, frame in zip("AB", faces, frames):
            bind_face(lay, prefix, face,
                      corner_shift(rolled(frame, self.roll), frame, spec))
        bind_face(lay, "E", faces[2])
        return lay.realise(spec.layer_names)

    # -- duct taps (decision 0033, task 0070) ---------------------------

    def meshed_sj_check(self, spec: PipeSpec) -> bool:
        """Whether ``Assembly.mesh()`` checks this tee's meshed corner SJ
        on the predicted-SJ tiers: round duct taps, whose prediction (from
        straight block edges) overestimates by up to 0.11 (task 0069)."""
        return _is_duct(spec) and isinstance(self.branch, CircleShape)

    def _duct_geometry(self, spec: PipeSpec):
        """(on_U, a, b, along, across, reach_x, reach_y): the face's
        half-width a and depth b, the branch's half-extents along the main
        and across the face, and the hole's reach along and across."""
        sh, face = spec.core_shape, self.face or "wide"
        on_U = (sh.half_w >= sh.half_h) == (face == "wide")
        a, b = (sh.half_w, sh.half_h) if on_U else (sh.half_h, sh.half_w)
        br = self.branch
        if isinstance(br, CircleShape):
            return on_U, a, b, None, None, br.radius, br.radius
        along, across = (br.half_h, br.half_w) if on_U else (br.half_w, br.half_h)
        return on_U, a, b, along, across, along, across

    def _tap(self, inlet: Frame, spec: PipeSpec, **tuning):
        _, _, _, along, across, _, _ = self._duct_geometry(spec)
        side = 1 if abs(math.remainder(self.roll, 360.0)) < 1e-9 else -1
        kw = {k: getattr(self, k) for k in ("margin", "dome", "sheet", "n_wall")}
        kw.update(tuning)
        return DuctTap(run_length=self.run_length, branch_length=self.branch_length,
                       along=along, across=across,
                       radius=self.branch.radius if isinstance(self.branch, CircleShape) else None,
                       face=self.face or "wide", side=side, n_run=self.n_run,
                       n_branch=self.n_branch, **kw)

    def _resolve_duct(self, inlet: Frame, spec: PipeSpec) -> "Tee":
        if self.toward is not None:
            raise ValueError("Tee: toward= is for pipe tees; a duct tap takes face= "
                             "and roll= (0 or 180)")
        if self.branch is None:
            raise ValueError("Tee: a rectangular main needs branch=RectShape(…) or "
                             "CircleShape(…); branch_radius= is the shorthand for pipes")
        tee = replace(self, face=self.face or "wide")
        if tee.run_length is None:
            on_U, a, b, *_, reach_x, _ = tee._duct_geometry(spec)
            t = (1 - OH_RATIO) * min(a, b)
            run = reach_x + (max(DuctTap.TUNING["margin"]) + 1) * t
            tee = replace(tee, run_length=run)
        tee._check_duct(spec, tuned=False)
        tap = tee._tap(inlet, spec).tuned(inlet, spec)
        return replace(tee, margin=tap.margin, dome=tap.dome, sheet=tap.sheet,
                       n_wall=tee.n_wall or tap.wall_cells(spec))

    def _check_duct(self, spec: PipeSpec, tuned: bool = True) -> None:
        sh = spec.core_shape
        if self.run_length is None or (tuned and None in (self.margin, self.dome, self.sheet,
                                                          self.n_wall)):
            raise ValueError("Tee: run_length and the duct-tap tunables are resolved "
                             "by Assembly.add(); add the fitting to an assembly")
        if spec.shells:
            raise ValueError("Tee: duct taps are single-layer; shelled duct taps are "
                             "not supported yet (decisions 0026, 0028)")
        if spec.rot != 0 or spec.n_outer != 4:
            raise ValueError("Tee: a duct tap requires rot = 0 and n_outer = 4")
        if self.branch is None:
            raise ValueError("Tee: a rectangular main needs branch=RectShape(…) or "
                             "CircleShape(…); branch_radius= is the shorthand for pipes")
        if self.face not in (None, "wide", "narrow"):
            raise ValueError(f"Tee: face must be 'wide' or 'narrow', got {self.face!r}")
        if min(abs(math.remainder(self.roll - r, 360.0)) for r in (0, 180)) > 1e-9:
            raise ValueError(f"Tee: a duct tap's roll is 0 or 180 (the side of the "
                             f"face), got {self.roll:g}; face= picks wide or narrow")
        br = self.branch
        if isinstance(br, CircleShape):
            if not (sh.nang_w == sh.nang_h == br.nang):
                raise ValueError(
                    f"Tee: a round duct tap needs equal counts per side: main "
                    f"(nang_w, nang_h) = ({sh.nang_w}, {sh.nang_h}), branch nang {br.nang}")
        elif (br.nang_w, br.nang_h) != (sh.nang_w, sh.nang_h):
            raise ValueError(
                f"Tee: branch counts (nang_w, nang_h) = ({br.nang_w}, {br.nang_h}) must "
                f"be the main's ({sh.nang_w}, {sh.nang_h}): the branch keeps the main's "
                f"counts per side (module notes)")
        on_U, a, b, along, across, reach_x, reach_y = self._duct_geometry(spec)
        face = self.face or "wide"
        ratio = reach_y / a
        if isinstance(br, RectShape) and abs(ratio - 1) < 1e-9:
            raise ValueError(f"Tee: a tap as wide as the {face} face (across ratio 1) is "
                             f"a full-width tap: task 0057, not yet supported")
        if ratio > limits.DUCT_TAP_MAX_RATIO:
            raise ValueError(
                f"Tee: the tap reaches {reach_y:.4g} across the {face} face of "
                f"half-width {a:.4g}: ratio {ratio:.3g} exceeds DUCT_TAP_MAX_RATIO "
                f"{limits.DUCT_TAP_MAX_RATIO:g}; a tap up to "
                f"{limits.DUCT_TAP_MAX_RATIO * a:.4g}, or a full-width tap (task 0057)")
        t = (1 - OH_RATIO) * min(a, b)
        need = reach_x + (self.margin or min(DuctTap.TUNING["margin"])) * t
        if self.run_length <= need:
            raise ValueError(f"Tee: run_length must exceed {need:.4g}: the tap's reach "
                             f"along the main {reach_x:.4g} plus the station margin")
        if self.branch_length <= b:
            raise ValueError(f"Tee: branch_length must exceed the {face} face's "
                             f"distance from the axis, {b:.4g}")
        for n in (self.n_run, self.n_branch, self.n_wall or 1):
            if n < 1:
                raise ValueError("layer counts must be >= 1")

    def _duct_quality(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """The predicted-SJ tiers (task 0052) for a duct tap, and the
        narrow-face warning on deep ducts (decision 0033)."""
        sj = self._tap(frames[0], spec).predicted_sj(frames, spec)
        on_U, a, b, *_ = self._duct_geometry(spec)
        face = self.face or "wide"
        hint = ("on the wide face it is better" if face == "narrow"
                else "a smaller tap, or a longer tap along the main, may do better")
        found = []
        for tier, name in ((PREDICTED_SJ_MIN, "PREDICTED_SJ_MIN"),
                           (PREDICTED_SJ_WARN, "PREDICTED_SJ_WARN")):
            if sj >= tier:
                continue
            msg = (f"predicted corner scaled Jacobian {sj:.3f} is below {name} "
                   f"{tier:g} (duct tap, {face} face); {hint}")
            if tier == PREDICTED_SJ_MIN:
                raise ValueError(msg)
            found.append(msg)
            break
        if face == "narrow" and b / a >= limits.DUCT_TAP_NARROW_ASPECT_WARN:
            found.append(
                f"a tap on the narrow face of a duct of aspect {b / a:.3g} (≥ "
                f"DUCT_TAP_NARROW_ASPECT_WARN {limits.DUCT_TAP_NARROW_ASPECT_WARN:g}): "
                f"the dome reaches into a deep, thin core (min corner SJ about 0.13, "
                f"non-orthogonality to 82°, task 0069); the wide face is better")
        return found
