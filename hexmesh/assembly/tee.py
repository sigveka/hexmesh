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
narrower than it, with the pillowed layout of ``duct_tap.DuctTap``.
``Tee`` picks the template (``duct_tap.TapTemplate``) and delegates.  The
branch keeps the main's counts per side (a class-0 port); its frame's
``up`` is the main's axis for a tap on an up/down face and the main's
``up`` for one on a right/left face, so its ``half_w``/``nang_w`` run
along the main's ``right`` or along the main's axis respectively.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, replace

import numpy as np

from .errors import AssemblyError, AssemblyTypeError
from ..core.shape import CircleShape, RectShape
from ..core.params import param
from ..core.spec import PipeSpec
from ..sections import oh
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, Spline, bind_face, corner_shift,
    face_patches, face_vertices,
)
from .duct_tap import TapTemplate
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


def _check_circle(spec: PipeSpec) -> None:
    if not spec.core_shape.is_round:
        raise AssemblyError("Tee: a pipe tee needs a circular main; a rectangular "
                            "main is a duct tap (branch=, face=; decision 0033)",
                            code="pipe_tee_needs_circle",
                            hint="a rectangular main is a duct tap (branch=, face=)")
    for sh, o in zip(spec.shells, spec.outlines[1:]):
        if not o.is_round:
            raise AssemblyError(f"Tee: shell `{sh.name}` is not circular; junction "
                                f"shells are circular only (decisions 0026, 0028)",
                                code="junction_shells_not_circular", where={"label": sh.name})


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
    nrad, mprg : int, float, optional
        Duct taps on an H main (task 0086): the radial cells and growth of
        the O-H ring inside the junction and its switch legs.  Derived when
        the tee is added (``sections.h.pillow_ring``: the H cells within a
        ring thickness of the wall, and the H face's wall cell) and stored;
        give them to override.  An O-H main's ring is its own: not allowed
        there.

    Ports are ``main`` (the run outlet, keeping the inlet's ``up``) and
    ``branch``: ``add(…, names={"main": …, "branch": …})``.
    """

    # both port pairs: main in → main out, → branch; class 1 (a pillow) for
    # a round branch on an H main, whose port is O-H (task 0086)
    strategies = frozenset({0, 1})
    pillows = True
    port_names = ("main", "branch")

    run_length:    float | None = param(
        "length", "T-point to each main port; None resolves when added", default=None,
        exclusiveMinimum=0, limit="PREDICTED_SJ_WARN")
    branch_length: float | None = param(
        "length", "main axis to the branch port (required)", default=None, exclusiveMinimum=0)
    branch_radius: float | None = param(
        "length", "branch radius, below the main radius (or branch)", input=True,
        exclusiveMinimum=0)
    n_run:    int = param(
        "cells", "axial layers of the approach and departure runs", default=3, minimum=1)
    n_branch: int = param("cells", "axial layers of the branch run", default=3, minimum=1)
    n_turn:   int = param("cells", "layers of the junction's turning blocks", default=2, minimum=1)
    roll:     float = param(
        "deg",
        "branch direction about the main axis from the inlet's up; a multiple of the section's "
        "period",
        default=0.0)
    toward:   tuple | None = param(
        "-", "absolute direction, instead of roll: resolved to the nearest allowed roll",
        input=True, limit="JUNCTION_TOWARD_TOL")
    # duct taps only (absent from a pipe tee's JSON)
    branch:   CircleShape | RectShape | None = param(
        "-", "duct taps: the branch section (a shape with the main's counts)", input=True,
        limit="DUCT_TAP_MAX_RATIO")
    face:     str | None = param(
        "-", "duct taps: the face the branch leaves", input=True, enum=["wide", "narrow"],
        limit="DUCT_TAP_NARROW_ASPECT_WARN")
    margin:   float | None = param(
        "1", "duct taps: layout tunable (DuctTap); resolved when added", input=True)
    dome:     float | None = param(
        "1", "duct taps: layout tunable (DuctTap); resolved when added", input=True)
    sheet:    float | None = param(
        "1", "duct taps: layout tunable (DuctTap); resolved when added", input=True)
    n_wall:   int | None = param(
        "cells", "duct taps: cells from a station to the hole; resolved when added", input=True,
        minimum=1)
    nrad:     int | None = param(
        "cells", "duct taps on an H main: radial cells of the O-H ring; derived when added",
        input=True, minimum=1)
    mprg:     float | None = param(
        "1", "duct taps on an H main: radial growth of the O-H ring; derived when added",
        input=True, exclusiveMinimum=0)

    def __post_init__(self):
        missing = ["branch_length"] if self.branch_length is None else []
        if self.branch_radius is None and self.branch is None:
            missing.append("branch_radius (or branch)")
        if missing:
            raise AssemblyTypeError(f"Tee: missing required argument(s): {', '.join(missing)}",
                                    code="argument_missing", value=list(missing))
        if self.branch_radius is not None and self.branch is not None:
            raise AssemblyTypeError("Tee: give branch_radius or branch, not both",
                                    code="branch_args_conflict", where={"field": "branch"})

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell=None, outlet=None) -> "Tee":
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.resolve(inlet, spec)
        if self.branch is not None and self.branch.is_round:   # the shorthand's long form
            if self.branch.nang != spec.core_shape.nang:
                raise AssemblyError(f"Tee: branch nang {self.branch.nang} must be the main's "
                                    f"{spec.core_shape.nang}",
                                    code="counts_mismatch", where={"field": "branch"},
                                    value=self.branch.nang, limit=spec.core_shape.nang)
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
                raise AssemblyError(msg,
                                    code="predicted_sj_below_minimum", value=float(sj),
                                    limit="PREDICTED_SJ_MIN", hint=hint)
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
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.ports(inlet, spec)
        _check_circle(spec)       # the branch spec needs a radius
        o, ex, ey, ez = self._origin_basis(inlet)
        main = Frame(o + self.run_length * ex, ex, inlet.up)
        branch = Frame(o + self.branch_length * ez, ez, ex)
        return [(main, spec), (branch, branch_spec(spec, self.branch_radius))]

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.check(spec)
        _check_circle(spec)
        duct_only = [n for n in ("branch", "face", "margin", "dome", "sheet", "n_wall",
                                         "nrad", "mprg")
                     if getattr(self, n) is not None]
        if duct_only:
            raise AssemblyError(f"Tee: {', '.join(duct_only)} are for a duct tap (a "
                                f"rectangular main); on a pipe give branch_radius",
                                code="duct_tap_args_on_pipe", where={"field": duct_only[0]},
                                hint="on a pipe give branch_radius")
        if self.run_length is None:
            raise AssemblyError("Tee: run_length=None is resolved by Assembly.add(); "
                                "add the fitting to an assembly",
                                code="fitting_not_resolved", where={"field": "run_length"},
                                hint="add the fitting to an assembly")
        R, r = spec.core_shape.radius, self.branch_radius
        T = thicknesses(spec)[-1]
        if spec.rot != 0 or spec.n_outer != 4:
            raise AssemblyError("Tee prototype requires rot = 0 and n_outer = 4",
                                code="junction_needs_rot_0_n_outer_4", where={"field": "rot"})
        if self.toward is not None:
            raise AssemblyError("Tee: toward is resolved by Assembly.add(); add the "
                                "fitting to an assembly",
                                code="fitting_not_resolved", where={"field": "toward"},
                                hint="add the fitting to an assembly")
        junction_roll(self, spec)
        if not 0 < r < R:
            raise AssemblyError(f"branch radius {r} must be in (0, main radius {R})",
                                code="branch_radius_out_of_range",
                                where={"field": "branch_radius"}, value=r,
                                limit={"min_exclusive": 0, "max_exclusive": R})
        if self.run_length <= r + T:
            raise AssemblyError(f"run_length must exceed the branch's outer radius "
                                f"{r + T:.4g} (branch radius + shells)",
                                code="run_length_too_short", where={"field": "run_length"},
                                value=self.run_length, limit={"min_exclusive": r + T})
        if self.branch_length <= turning_height(R, r, T):
            raise AssemblyError(
                f"branch_length must exceed the turning station's height "
                f"{turning_height(R, r, T):.4g} (outer main radius + outer branch "
                f"radius / 2)",
                code="branch_length_too_short", where={"field": "branch_length"},
                value=self.branch_length, limit={"min_exclusive": turning_height(R, r, T)}
            )
        for n in (self.n_run, self.n_branch, self.n_turn):
            if n < 1:
                raise AssemblyError("layer counts must be >= 1",
                                    code="count_below_minimum",
                                    where={"field": "n_run, n_branch, n_turn"}, value=n,
                                    limit={"min": 1})

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.layout(frames, spec)
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
        # branch inner-square corner offset: the saddle offset scaled to the
        # inner square (oh.inner_half_side(r), in this order bit-identical)
        ci = oh.inner_radius(t)
        si = oh.inner_half_side(R)           # main inner-square corner offset
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
                raise AssemblyError("port interface does not match Tee geometry",
                                    code="outlet_frame_mismatch")
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.validate(frames, spec)
        found = self._quality(frames[0], spec)      # before the layout's own
        try:                                        # inversion check: names a run
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise AssemblyError.wrap(e, f"block layout invalid: {e}",
                                     code="block_layout_invalid") from None
        return found

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count of the block layout (pure; DESIGN P4)."""
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.cell_count(frames, spec)
        return self.layout(frames, spec).cell_count()

    def fill(self, faces, frames, spec, lc):
        tpl = self._template(spec)
        if tpl is not None:          # declared in the ports' own frames
            return tpl.fill(faces, frames, spec, lc)
        lay = self.layout(frames, spec)
        for prefix, face, frame in zip("AB", faces, frames):
            bind_face(lay, prefix, face,
                      corner_shift(rolled(frame, self.roll), frame, spec))
        bind_face(lay, "E", faces[2])
        return lay.realise(spec.layer_names)

    # -- duct taps (decision 0033, task 0070) ---------------------------

    def _template(self, spec: PipeSpec) -> TapTemplate | None:
        """The duct-tap front end on a rectangular main, else None."""
        return None if spec.core_shape.is_round else TapTemplate(self)

    def meshed_sj_check(self, spec: PipeSpec) -> bool:
        """Whether ``Assembly.mesh()`` checks this tee's meshed corner SJ
        on the predicted-SJ tiers: round duct taps, whose prediction (from
        straight block edges) overestimates by up to 0.11 (task 0069), and
        taps on a graded H main, whose switch legs' is an empirical bound
        (task 0086)."""
        tpl = self._template(spec)
        return tpl is not None and (tpl.meshed_sj_check() or tpl.graded_legs(spec))

    def meshed_nonorth_check(self, spec: PipeSpec) -> bool:
        """Taps on a graded H main: their switch legs (task 0086)."""
        tpl = self._template(spec)
        return tpl is not None and tpl.graded_legs(spec)
