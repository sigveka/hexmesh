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
Tee — centred side-branch junction, perpendicular or a lateral, as a block
layout (DESIGN.md §6.1 "Blocks", §7; geometry in docs/RESEARCH.md §3).

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

Laterals (decision 0031 stage 1, task 0060)
-------------------------------------------
``angle`` α leans the branch axis d = cos α ex + sin α ez from the run's
downstream direction ex toward the branch plane's up ez; the axis passes
through the T-point.  The block topology is the tee's.  The saddle arcs are
the exact intersection (RESEARCH §3.1, h = 0) at the same branch diagonals,
so each station's top corners move downstream by an amount that differs
upstream and down; the station cross-sections stay normal to the run, and
the turning station and branch run are normal to d.  The junction core's
top face slides along x to stay centred on d (tilting it with the lean
lowers the SJ: measured, task 0060).  The worst cell is the turn block at
the acute (downstream) crotch.  At 90° every coordinate is computed as
before, bit for bit.

Scope: circular layers, ``rot = 0``, ``n_outer = 4``, branch ratio
``r/R ≤ TEE_MAX_RATIO``, ``0 < angle ≤ 90``.

Equal tees (decision 0043 amendment 2026-11-10, task 0122)
---------------------------------------------------------
A branch as wide as the main (r = R within ``EQUAL_TEE_RTOL``) is an
equal tee or an equal lateral, with the oriented junction cube of
``cube.CubeTee``: ``Tee`` delegates to it, as to the duct-tap template.
The branch must be centred (``offset`` 0) and square
(``EQUAL_LATERAL_ANGLE_MIN``, 90°: equal laterals fold as ``nang``
rises).  Its crease, where the branch meets the main, lies on cube edges
only on the main's two sides, so its chord error is first order in
``nang`` (3.7 % R at nang 8, 1.1 % at 32).  First order only:
``mesh(order=2)`` rejects it, as it does the wye.

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
from ..sections import circle_radius, oh
from .blocks import (
    ArcAbout, BlockLayout, LayoutError, Spline, bind_face, corner_shift,
    face_patches, face_vertices,
)
from .cube import CubeTee
from .duct_tap import TapTemplate
from .interface import (Frame, check_port_frames, junction_roll, junction_toward, lean,
                        outer_radius, rolled)
from .junction_quality import (CUBE_HINT, TAP_HINT, TEE_BLOCKS, TEE_HINT, nonorth_tiers,
                               predicted_angle)
from .limits import (EQUAL_TEE_RTOL, PREDICTED_SJ_MIN, PREDICTED_SJ_WARN, TEE_MAX_OFFSET_RATIO,
                     TEE_MAX_RATIO)
from .projection import Tube, TubeUnion
from .signature import check_port_pairs

_SAMPLES = 9   # interior points per spline edge
# An offset tap's junction core (task 0061): its top follows the branch axis
# (the branch core above it stays straight); its bottom follows by this
# fraction, the best measured (0 folds the wide side's ring at r/R 0.3, h/R
# 0.4–0.6; 0.5 and more fold the bottom ring).  0 at offset 0.
_BOTTOM_SHIFT = 0.25


def thicknesses(spec: PipeSpec) -> list[float]:
    """Cumulative shell thickness at each level ≥ 1 (0 at the wall)."""
    R = circle_radius(spec.core_shape)
    return [o.radius - R for o in spec.outlines]


def main_radii(spec: PipeSpec) -> tuple[float, float]:
    """``(R, T)``: the main's core radius and total shell thickness."""
    return circle_radius(spec.core_shape), thicknesses(spec)[-1]


def branch_spec(spec: PipeSpec, radius: float, mprg: float | None = None,
                first_cell: float | None = None) -> PipeSpec:
    """Branch spec: *spec* with core radius *radius* and the same shells
    (names, thicknesses, ``nrad``, ``mprg``).  The core's grading is the
    main's unless *mprg* or *first_cell* gives the branch its own (task
    0131)."""
    name, shape = spec._core
    if mprg is None and first_cell is None:
        mprg = spec._core_mprg
    out = (PipeSpec(nang=spec.nang, n_outer=spec.n_outer, rot=spec.rot, mbmp=spec.mbmp)
           .core(name, CircleShape(radius=radius, nang=shape.nang),
                 nrad=spec._core_nrad, mprg=mprg, first_cell=first_cell))
    T = thicknesses(spec)
    for sh, t0, t1 in zip(spec.shells, T, T[1:]):
        # the given dR, exactly: t1 - t0 differs in the last bits, and a
        # stack change on the branch compares outlines exactly (task 0155)
        out.shell(sh.name, dR=t1 - t0 if sh.dR is None else sh.dR, nrad=sh.nrad, mprg=sh.mprg)
    return out


def tee_wall(o, ex, ez, R: float, r: float, ob=None) -> TubeUnion:
    """The tee wall: the main cylinder (axis ``o + x ex``, radius *R*)
    united with the branch cylinder (axis ``ob + z ez``, z ≥ 0, radius *r*;
    *ez* the branch axis, leaning for a lateral; *ob* its foot on the main
    axis's plane, offset for an offset tap, default *o*), as a wall
    projector (decision 0029)."""
    return TubeUnion([Tube(tuple(o), tuple(ex), R, ray=False),
                      Tube(tuple(o if ob is None else ob), tuple(ez), r)])


def saddle_point(R: float, r: float, ca: float, sa: float, phi: float, hy: float = 0.0):
    """The main–branch intersection (RESEARCH §3.1) at branch angle *phi*,
    as ``(x, y, z)`` along (main axis, across, the branch plane's up).  The
    branch axis is ``(ca, 0, sa)`` through ``(0, hy, 0)`` (*hy* the offset,
    task 0061), and *phi* is measured from its in-plane normal
    ``(sa, 0, −ca)`` (downstream at 90°) toward ``+y``."""
    c, s = math.cos(phi), math.sin(phi)
    y = hy + r * s
    z = math.sqrt(R * R - y ** 2)
    if ca == 0.0:
        return r * c, y, z
    along = (z + r * c * ca) / sa              # s(φ) of RESEARCH §3.1
    return along * ca + r * c * sa, y, z


def tip_reach(R: float, r: float, angle: float, offset: float = 0.0) -> tuple[float, float]:
    """How far the branch's hole reaches up- and downstream of the T-point,
    for radii *R*, *r*: at the tips (φ = π and 0) when centred, both r at
    90°.  Off the axis (*offset*, task 0061) a lateral's extremes move off
    the tips: sampled every 0.1°."""
    ca, sa = lean(angle)
    if offset == 0 or ca == 0.0:
        return -saddle_point(R, r, ca, sa, math.pi)[0], saddle_point(R, r, ca, sa, 0.0)[0]
    x = [saddle_point(R, r, ca, sa, f, offset)[0] for f in np.linspace(0, 2 * math.pi, 3601)]
    return -min(x), max(x)


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
                                code="junction_shells_not_circular", where={"label": sh.name},
                                hint=f"give shell `{sh.name}` dR= (a circle) instead of outer=")
    _check_rot_n_outer(spec)


def _check_rot_n_outer(spec: PipeSpec) -> None:
    """The template's corners are the 4-corner face's at rot = 0: before
    resolve() measures it (n_outer = 8 passes check_supported, task 0088)."""
    if spec.rot != 0 or spec.n_outer != 4:
        raise AssemblyError("Tee prototype requires rot = 0 and n_outer = 4",
                            code="junction_needs_rot_0_n_outer_4", where={"field": "rot"},
                            hint="use PipeSpec(rot=0, n_outer=4)")


def turning_height(R: float, r: float, T: float, angle: float = 90.0) -> float:
    """Distance of the branch turning station from the T-point along the
    branch axis: its lowest point (on the acute side, for a lateral) clear
    of the outer main shell by half the outer branch radius."""
    ca, sa = lean(angle)
    if ca == 0.0:
        return R + T + 0.5 * (r + T)
    return (R + T + 0.5 * (r + T) + (r + T) * ca) / sa


@dataclass(frozen=True)
class Tee:
    """Perpendicular side-branch tee.

    Parameters
    ----------
    run_length : float, optional
        Distance from the T-point to each main port (inlet and outlet).
        ``None`` (the default) is resolved when the tee is added:
        ``r + T + 0.5 R`` (T the total shell thickness; for a lateral the
        hole's downstream reach + 0.5 R), or the shortest run whose
        predicted corner scaled Jacobian reaches ``PREDICTED_SJ_WARN`` (if
        none does, ``PREDICTED_SJ_MIN``), whichever is longer (task 0052).
    branch_length : float
        Distance from the main axis to the branch port.
    branch_radius : float
        Branch radius: at most ``TEE_MAX_RATIO`` × the main radius, or
        equal to it (an equal tee or lateral: the oriented junction cube,
        task 0122).
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
        Its component across the run sets the roll; *angle* sets the lean.
    angle : float
        Pipe tees: the angle in degrees between the run's downstream
        direction and the branch axis, in (0, 90] (task 0060): 90 is a
        tee, 45 a 45° lateral leaning downstream.  The branch axis passes
        through the T-point on the main axis; ``branch_length`` is
        measured along it.
    offset : float
        Pipe tees: the distance h of the branch axis from the main axis,
        along the main's ``right`` after the roll (task 0061): 0 is a
        centred tee, |h| + r → R a tangential tap.  The axis passes
        through the point h off the T-point; ``branch_length`` is measured
        along it from there.  |h| + r < R.
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
    branch_first_cell, branch_mprg : float, optional
        Pipe tees: the branch port's own core grading (task 0131; decision
        0028), as ``PipeSpec.core``'s ``first_cell`` (resolved to
        ``branch_mprg`` when the tee is added) or ``mprg``; at most one.
        The turning station keeps the main's grading, and the branch run's
        cells blend to the port's over its ``n_branch`` layers.  Without
        them the branch copies the main's ``mprg``, so its wall cell
        scales with r/R.  Not on an equal tee or a duct tap.

    Ports are ``main`` (the run outlet, keeping the inlet's ``up``) and
    ``branch``: ``add(…, names={"main": …, "branch": …})``.
    """

    # per port pair, main in → main out and → branch: class 1 (a pillow) for
    # a round branch on an H main, whose port is O-H (task 0086); the branch
    # also class 2, grading only: its own core grading (task 0131)
    strategies = (frozenset({0, 1}), frozenset({0, 1, 2}))
    pillows = True
    port_names = ("main", "branch")
    toward_offset = 0.0     # the roll of toward's direction from the junction's up

    run_length:    float | None = param(
        "length", "T-point to each main port; None resolves when added", default=None,
        exclusiveMinimum=0, limit="PREDICTED_SJ_WARN")
    branch_length: float | None = param(
        "length", "main axis to the branch port (required)", default=None, exclusiveMinimum=0)
    branch_radius: float | None = param(
        "length", "branch radius: at most TEE_MAX_RATIO times the main radius, or equal to it "
        "(an equal tee); or branch", input=True, exclusiveMinimum=0)
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
        "direction", "absolute direction, instead of roll: resolved to the nearest allowed roll",
        input=True, limit="JUNCTION_TOWARD_TOL")
    angle:    float = param(
        "deg", "pipe tees: angle from the run's downstream direction to the branch axis "
        "(90: a tee; 45: a lateral)", default=90.0, exclusiveMinimum=0, maximum=90)
    offset:   float = param(
        "length", "pipe tees: branch axis from the main axis, along the main's right after "
        "the roll (an offset or tangential tap)", default=0.0)
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
    branch_first_cell: float | None = param(
        "length", "pipe tees: the branch port's core wall cell; resolves to branch_mprg when "
        "added", input=True, exclusiveMinimum=0)
    branch_mprg: float | None = param(
        "1", "pipe tees: the branch port's core radial growth (None: the main's)",
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
        if self.branch_first_cell is not None and self.branch_mprg is not None:
            raise AssemblyTypeError("Tee: give branch_first_cell or branch_mprg, not both",
                                    code="grading_args_conflict",
                                    where={"field": "branch_first_cell"},
                                    hint="give branch_first_cell or branch_mprg")

    def _branch_graded(self) -> bool:
        return self.branch_first_cell is not None or self.branch_mprg is not None

    def _check_branch_grading(self, spec: PipeSpec) -> None:
        """The branch's own grading: a pipe tee with a smaller round
        branch only (task 0131)."""
        if not self._branch_graded():
            return
        field = "branch_first_cell" if self.branch_first_cell is not None else "branch_mprg"
        what = ("a duct tap (a rectangular main)" if not spec.core_shape.is_round
                else "an equal tee" if self._is_equal(spec) else None)
        if what is not None:
            raise AssemblyError(f"Tee: {field} is for a pipe tee with a smaller branch, not "
                                f"{what}",
                                code="branch_grading_unsupported", where={"field": field},
                                hint="leave it out and add a grading-only Reducer after the "
                                     "branch (GUIDE, \"A branch with its own wall cell\")")

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell=None, outlet=None) -> "Tee":
        tpl = self._template(spec)
        if tpl is not None:
            self._check_branch_grading(spec)
            return tpl.resolve(inlet, spec)
        if self.branch is not None and self.branch.is_round:   # the shorthand's long form
            if self.branch.nang != spec.core_shape.nang:
                raise AssemblyError(f"Tee: branch nang {self.branch.nang} must be the main's "
                                    f"{spec.core_shape.nang}",
                                    code="counts_mismatch", where={"field": "branch"},
                                    value=self.branch.nang, limit=spec.core_shape.nang,
                                    hint=f"give the branch nang={spec.core_shape.nang}")
            self = replace(self, branch_radius=circle_radius(self.branch), branch=None)
        tee = junction_toward(self, inlet, spec, self.toward_offset)  # counts keep defaults
        tee._check_branch_grading(spec)
        if tee.branch_first_cell is not None:     # stored as its mprg, which nests (task 0131)
            _check_circle(spec)
            tee = replace(tee, branch_first_cell=None, branch_mprg=branch_spec(
                spec, tee.branch_radius, first_cell=tee.branch_first_cell)._core_mprg)
        if tee._is_equal(spec):
            tee = replace(tee, branch_radius=spec.core_shape.max_extent)   # exactly the main's
            if tee.run_length is None:
                tee = replace(tee, run_length=CubeTee(tee).resolve(inlet, spec))
            return tee
        if tee.run_length is None:
            _check_circle(spec)
            R, r, T = circle_radius(spec.core_shape), tee.branch_radius, thicknesses(spec)[-1]
            run = (max(tip_reach(R + T, r + T, tee.angle, tee._hy())) if r < R
                   else r + T) + 0.5 * R
            if r < R:              # else check() rejects it, naming the radius
                need = tee.shortest_run(inlet, spec, PREDICTED_SJ_WARN)
                if need is None:   # laterals below ~57°: at least pass the floor
                    need = tee.shortest_run(inlet, spec, PREDICTED_SJ_MIN)
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
        (R, T), r = main_radii(spec), self.branch_radius
        lo = max(tip_reach(R + T, r + T, self.angle, self._hy()))
        hi = lo + 2 * R
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

    def smallest_ratio(self, inlet: Frame, spec: PipeSpec, tier: float) -> float | None:
        """Smallest branch ratio r/R (to 1e-3, rounded up) whose predicted
        corner SJ reaches *tier* at this angle and a long run; ``None`` if
        none up to ``TEE_MAX_RATIO`` does.  The SJ rises with r/R."""
        R, T = main_radii(spec)

        def sj(q):
            r = q * R
            if abs(self.offset) > TEE_MAX_OFFSET_RATIO * r:
                return -1.0                     # out of the offset margin: below every tier
            tee = replace(self, branch_radius=r,
                          run_length=max(tip_reach(R + T, r + T, self.angle, self._hy())) + 2 * R,
                          branch_length=turning_height(R, r, T, self.angle) + R)
            return tee.predicted_sj(inlet, spec)
        # an offset leaves no hole from r = R - |h| (check): stop below it
        lo, hi = 0.0, min(TEE_MAX_RATIO, 1.0 - abs(self.offset) / R - 1e-3)
        if sj(hi) < tier:
            return None
        while hi - lo > 1e-3:
            mid = 0.5 * (lo + hi)
            if mid > 0 and sj(mid) >= tier:
                hi = mid
            else:
                lo = mid
        return round(math.ceil(hi / 1e-3 - 1e-9) * 1e-3, 12)

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
                hint = (f"no run length reaches it: the branch ratio r/R "
                        f"{self.branch_radius / circle_radius(spec.core_shape):.3g} limits the "
                        f"junction core")
                if self.angle != 90:
                    q = self.smallest_ratio(inlet, spec, tier)
                    hint += (f" at angle {self.angle:g}°; " + (
                        f"r/R {q:.3g} or more reaches it there, or a larger angle"
                        if q is not None else
                        f"no ratio up to TEE_MAX_RATIO {TEE_MAX_RATIO:g} reaches it "
                        f"there: a larger angle"))
            else:
                hint = (f"a run of {need:.4g} m or more each side of the centre reaches it "
                        f"(now {self.run_length:.4g})")
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

    def _hy(self) -> float:
        """The offset as the layout's y (along ``ey`` = −right)."""
        return -self.offset

    def _branch_axes(self, inlet: Frame):
        """``(ob, d, u)``: the branch axis's foot (the T-point, moved by
        ``offset`` along the main's right), the branch axis (leaning by
        ``angle`` from the run toward the branch plane's up) and its frame's
        up, the axis's in-plane normal (the main axis at 90°)."""
        o, ex, ey, ez = self._origin_basis(inlet)
        ca, sa = lean(self.angle)
        ob = o if self.offset == 0 else o + self._hy() * ey
        return ob, ca * ex + sa * ez, sa * ex - ca * ez

    def ports(self, inlet: Frame, spec: PipeSpec):
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.ports(inlet, spec)
        _check_circle(spec)       # the branch spec needs a radius
        o, ex, ey, ez = self._origin_basis(inlet)
        ob, d, u = self._branch_axes(inlet)
        main = Frame(o + self.run_length * ex, ex, inlet.up)
        branch = Frame(ob + self.branch_length * d, d, u)
        if self._is_equal(spec):            # the inlet's own spec, not rebuilt
            return [(main, spec), (branch, spec)]
        return [(main, spec), (branch, self._branch_port_spec(spec))]

    def _branch_port_spec(self, spec: PipeSpec) -> PipeSpec:
        return branch_spec(spec, self.branch_radius, mprg=self.branch_mprg,
                           first_cell=self.branch_first_cell)

    # -- topology -----------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        self._check_branch_grading(spec)
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
        R, r = circle_radius(spec.core_shape), self.branch_radius
        T = thicknesses(spec)[-1]
        _check_rot_n_outer(spec)
        if self.toward is not None:
            raise AssemblyError("Tee: toward is resolved by Assembly.add(); add the "
                                "fitting to an assembly",
                                code="fitting_not_resolved", where={"field": "toward"},
                                hint="add the fitting to an assembly")
        junction_roll(self, spec)
        if not 0 < self.angle <= 90:
            raise AssemblyError(f"Tee: angle {self.angle:g}° must be in (0, 90]: the angle "
                                f"from the run's downstream direction to the branch",
                                code="tee_angle_out_of_range", where={"field": "angle"},
                                value=self.angle, limit={"min_exclusive": 0, "max": 90},
                                hint="a branch leaning upstream is the same lateral with the "
                                     "run reversed")
        if self._is_equal(spec):
            if self.offset != 0:
                raise AssemblyError(f"Tee: an equal tee's branch can't be offset (offset "
                                    f"{self.offset:g}): |offset| + r must be below R",
                                    code="tee_offset_out_of_range", where={"field": "offset"},
                                    value=self.offset, limit={"max_exclusive": 0.0},
                                    hint=f"offset 0, or a branch radius <= TEE_MAX_RATIO R "
                                         f"({TEE_MAX_RATIO * R:.4g})")
            self._check_counts()
            return CubeTee(self).check(spec)
        if not 0 < r < R:
            raise AssemblyError(f"branch radius {r} must be in (0, main radius {R})",
                                code="branch_radius_out_of_range",
                                where={"field": "branch_radius"}, value=r,
                                limit={"min_exclusive": 0, "max_exclusive": R},
                                hint=f"a branch radius in (0, {TEE_MAX_RATIO * R:.4g}): r/R at most TEE_MAX_RATIO")
        if r > TEE_MAX_RATIO * R:
            raise AssemblyError(f"Tee: branch ratio r/R {r / R:.4g} is above TEE_MAX_RATIO "
                                f"{TEE_MAX_RATIO:g}: the saddle's sides fold the cells",
                                code="tee_ratio_above_max", where={"field": "branch_radius"},
                                value=r / R, limit="TEE_MAX_RATIO",
                                hint=f"an equal tee, or a branch radius <= {TEE_MAX_RATIO:g} R "
                                     f"({TEE_MAX_RATIO * R:.4g})")
        if not abs(self.offset) + r < R:
            raise AssemblyError(f"Tee: offset {self.offset:g} with branch radius {r:g} reaches "
                                f"past the main's radius {R:g}: |offset| + r must be below R",
                                code="tee_offset_out_of_range", where={"field": "offset"},
                                value=self.offset, limit={"max_exclusive": R - r},
                                hint=f"|offset| < {R - r:.4g}, or a smaller branch")
        if abs(self.offset) > TEE_MAX_OFFSET_RATIO * r:
            raise AssemblyError(f"Tee: offset {self.offset:g} is past TEE_MAX_OFFSET_RATIO "
                                f"{TEE_MAX_OFFSET_RATIO:g} × the branch radius {r:g}: the "
                                f"branch no longer covers the main's top line",
                                code="tee_offset_out_of_range", where={"field": "offset"},
                                value=self.offset, limit="TEE_MAX_OFFSET_RATIO",
                                hint=f"|offset| <= {TEE_MAX_OFFSET_RATIO * r:.4g}, or a "
                                     f"branch radius >= {abs(self.offset) / TEE_MAX_OFFSET_RATIO:.4g}")
        reach = max(tip_reach(R + T, r + T, self.angle, self._hy()))
        if self.run_length <= reach:
            what = ("the branch's outer radius" if self.angle == 90 else
                    "the branch hole's reach along the run (its acute-side tip)")
            raise AssemblyError(f"run_length must exceed {what} {reach:.4g} (branch radius "
                                f"+ shells)",
                                code="run_length_too_short", where={"field": "run_length"},
                                value=self.run_length, limit={"min_exclusive": reach},
                                hint=f"run_length > {reach:.4g}, or run_length=None to resolve it")
        z1 = turning_height(R, r, T, self.angle)
        if self.branch_length <= z1:
            where = ("height" if self.angle == 90 else "distance along the branch axis")
            raise AssemblyError(
                f"branch_length must exceed the turning station's {where} {z1:.4g} "
                f"(outer main radius + outer branch radius / 2"
                f"{', at its acute side' if self.angle != 90 else ''})",
                code="branch_length_too_short", where={"field": "branch_length"},
                value=self.branch_length, limit={"min_exclusive": z1},
                hint=f"branch_length > {z1:.4g}",
            )
        self._check_counts()

    def _check_counts(self) -> None:
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
        if self._is_equal(spec):
            return CubeTee(self).layout(frames, spec)
        # Declared in the rolled frame; fill() binds the main ports' faces
        # (built in the unrolled one) with the corner shift between them.
        A, B, E = rolled(frames[0], self.roll), rolled(frames[1], self.roll), frames[2]
        R, r = circle_radius(spec.core_shape), self.branch_radius
        bspec = branch_spec(spec, r)
        o, ex, ey, ez = self._origin_basis(frames[0])
        ob, d, u = self._branch_axes(frames[0])
        ca, sa = lean(self.angle)
        hy = self._hy()                              # the offset, along ey
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
        xc = 0.0 if ca == 0.0 else zq * ca / sa   # the branch axis at that height
        z1 = turning_height(R, r, Ts[-1], self.angle)   # turning station, along d

        def station_y(sy, l):
            """y and height of station level l's top corner on side *sy*:
            the saddle at a branch diagonal, about the offset axis."""
            tl, Rk = rl[l] / math.sqrt(2), Rl[l]
            y = hy + sy * tl
            return y, math.sqrt(Rk * Rk - y * y)

        def station_x(sx, sy, l):
            """x of station level l's top corner on side *sy*: the saddle at
            its branch diagonal (φ = ±π/4 downstream, ±3π/4 upstream).  The
            two sides differ for an offset lateral (task 0061)."""
            tl = rl[l] / math.sqrt(2)
            if ca == 0.0:
                return sx * tl
            zs = station_y(sy, l)[1]
            return (zs + sx * tl * ca) / sa * ca + sx * tl * sa

        # Main wall edges between two points at one radius: on the cylinder.
        def on_cylinder(p0, p1, Rk):
            (x0, y0, z0), (x1, y1, z1_) = (np.linalg.solve(
                np.column_stack([ex, ey, ez]), p - o) for p in (p0, p1))
            a0, a1 = math.atan2(z0, y0), math.atan2(z1_, y1)
            s = np.linspace(0, 1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(x0 + (x1 - x0) * u,
                                        Rk * math.cos(a0 + (a1 - a0) * u),
                                        Rk * math.sin(a0 + (a1 - a0) * u))) for u in s))

        lay = BlockLayout()
        face_vertices(lay, "A", A, spec)
        face_vertices(lay, "B", B, spec)
        if self._branch_graded():     # the port's own grading; Z keeps the main's (task 0131)
            face_vertices(lay, "E", E, self._branch_port_spec(spec), own_grading=True)
        else:
            face_vertices(lay, "E", E, bspec)

        # Stations Sa (approach end) and Sd (departure end); level l at the x
        # of its top corners, which sit on the offset saddle at the branch
        # diagonals (±(r + T_l)/√2 for a tee; asymmetric for a lateral).  An
        # offset (task 0061) moves the top corners and the core's top with
        # the branch axis, the core's bottom by _BOTTOM_SHIFT of it; the
        # wall's bottom corners stay, so the main's side rings take the
        # asymmetry (one wider, one narrower).  Each side keeps its
        # own x: an offset lateral's two diagonals meet the main at different
        # x, and the station's bottom arc then runs on the cylinder between.
        # Corner order follows the main frame: 0 (−y,+z) 1 (+y,+z) 2 (+y,−z) 3 (−y,−z).
        for name, sx in (("Sa", -1.0), ("Sd", 1.0)):
            x0 = xc + sx * ci
            lay.vertex((name, 0, 0), P(x0, hy - ci, zq))
            lay.vertex((name, 0, 1), P(x0, hy + ci, zq))
            lay.vertex((name, 0, 2), P(x0, _BOTTOM_SHIFT * hy + si, -si))
            lay.vertex((name, 0, 3), P(x0, _BOTTOM_SHIFT * hy - si, -si))
            for l in levels:
                Rk = Rl[l]
                (ym, zm), (yp, zp) = station_y(-1.0, l), station_y(1.0, l)
                xm, xp = station_x(sx, -1.0, l), station_x(sx, 1.0, l)
                lay.vertex((name, l, 0), P(xm, ym, zm))
                lay.vertex((name, l, 1), P(xp, yp, zp))
                lay.vertex((name, l, 2), P(xp, +Rk / math.sqrt(2), -Rk / math.sqrt(2)))
                lay.vertex((name, l, 3), P(xm, -Rk / math.sqrt(2), -Rk / math.sqrt(2)))
                lay.edge((name, l, 1), (name, l, 2), ArcAbout(tuple(P(xp, 0, 0))))
                lay.edge((name, l, 2), (name, l, 3), ArcAbout(tuple(P(xp, 0, 0))) if xm == xp
                         else on_cylinder(lay.coords[(name, l, 2)], lay.coords[(name, l, 3)], Rk))
                lay.edge((name, l, 3), (name, l, 0), ArcAbout(tuple(P(xm, 0, 0))))

        # Saddle arcs: exact cylinder–cylinder intersection, branch angle φ.
        def saddle(l, phi0, phi1):
            Rk, rk = Rl[l], rl[l]
            phis = np.linspace(phi0, phi1, _SAMPLES + 2)[1:-1]
            return Spline(tuple(tuple(P(*saddle_point(Rk, rk, ca, sa, f, hy))) for f in phis))
        q = math.pi / 4
        for l in levels:
            lay.edge(("Sa", l, 0), ("Sa", l, 1), saddle(l, 5 * q, 3 * q))   # through −x tip
            lay.edge(("Sd", l, 0), ("Sd", l, 1), saddle(l, -q, q))          # through +x tip
            lay.edge(("Sa", l, 1), ("Sd", l, 1), saddle(l, 3 * q, q))       # through +y side
            lay.edge(("Sa", l, 0), ("Sd", l, 0), saddle(l, 5 * q, 7 * q))   # through −y side

        # Main wall edges from the ports to the stations: on the cylinder.
        for port, st in (("A", "Sa"), ("B", "Sd")):
            for k in range(4):
                lay.edge((port, 0, k), (st, 0, k), divisions=self.n_run)
                for l in levels:
                    pa, ps = lay.coords[(port, l, k)], lay.coords[(st, l, k)]
                    geom = on_cylinder(pa, ps, Rl[l]) if k in (0, 1) else None
                    lay.edge((port, l, k), (st, l, k), geom, divisions=self.n_run)

        # Branch turning station Z (internal) at z1 along the branch axis;
        # frame as port E.
        Z = Frame(ob + z1 * d, d, u)
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
        lay.walls = {l: tee_wall(o, ex, d, Rl[l], rl[l], ob) for l in levels}
        # interior faces: Stretch B-spline fillings, as the wye's.  A free
        # plate is a different surface in each OCC version (7.6.3 / 7.8.1:
        # up to 1.5 % of the size), and the junction's quality moved with
        # it (task 0145, docs/integrations/gmsh.md)
        lay.filling = "Stretch"
        return lay

    # -- contract -----------------------------------------------------

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """Raise ValueError if invalid; return warnings (predicted quality
        below ``PREDICTED_SJ_WARN``)."""
        self.check(spec)
        check_port_pairs(self, [spec] + [s for _, s in self.ports(frames[0], spec)])
        check_port_frames(self, [f for f, _ in self.ports(frames[0], spec)], frames[1:],
                          self.run_length)
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.validate(frames, spec)
        if self._is_equal(spec):
            return CubeTee(self).validate(frames, spec)
        found = self._quality(frames[0], spec)      # before the layout's own
        try:                                        # inversion check: names a run
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise AssemblyError.wrap(e, f"block layout invalid: {e}",
                                     code="block_layout_invalid") from None
        return found + nonorth_tiers(
            self, frames, spec, lambda: self.layout(frames, spec), TEE_BLOCKS, TEE_HINT)

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

    def _is_equal(self, spec: PipeSpec) -> bool:
        """An equal tee (``cube.CubeTee``): a round branch within
        ``EQUAL_TEE_RTOL`` of the main's radius."""
        if not spec.core_shape.is_round or self.branch_radius is None:
            return False
        R = spec.core_shape.max_extent
        return abs(self.branch_radius - R) <= EQUAL_TEE_RTOL * R

    def meshed_sj_check(self, spec: PipeSpec) -> bool:
        """Whether ``Assembly.mesh()`` checks this tee's meshed corner SJ
        on the predicted-SJ tiers: round duct taps, whose prediction (from
        straight block edges) overestimates by up to 0.11 (task 0069),
        taps on a graded H main, whose switch legs' is an empirical bound
        (task 0086), and equal tees, whose projected walls lower it by up
        to 0.12 (task 0122)."""
        if self._is_equal(spec):         # projected walls: the prediction is optimistic
            return True
        tpl = self._template(spec)
        return tpl is not None and (tpl.meshed_sj_check() or tpl.graded_legs(spec))

    def meshed_sj_hint(self, spec: PipeSpec) -> str:
        """The hint of ``Assembly.mesh()``'s meshed-SJ error."""
        if self._is_equal(spec):
            return "a branch radius <= TEE_MAX_RATIO R may do better"
        return "a smaller tap, or the wide face, may do better"

    def second_order_limitation(self, spec: PipeSpec) -> str | None:
        """Why ``mesh(order=2)`` rejects this tee before meshing, or None
        (the wye's rule, for the other projected junction)."""
        if self._is_equal(spec):
            return ("its second-order hexes near the projected wall invert (72 of 4160 in "
                    "the equal tee example at nang 8; task 0122)")
        return None

    def meshed_nonorth_check(self, spec: PipeSpec) -> bool:
        """Every tee: the prediction is up to 3.7° optimistic at r/R ≥ 0.6
        (tasks 0104, 0145), and a graded H main's switch legs are an empirical
        bound (task 0086)."""
        return True

    def meshed_nonorth_hint(self, spec: PipeSpec) -> str:
        tpl = self._template(spec)
        if tpl is None:
            return CUBE_HINT if self._is_equal(spec) else TEE_HINT
        if tpl.graded_legs(spec):
            return TAP_HINT + "; at a switch leg, a gentler wall grading of the H main"
        return TAP_HINT

    def predicted_nonorth(self, frames: list[Frame], spec: PipeSpec) -> float:
        """``validate()``'s predicted worst non-orthogonality (cached)."""
        tpl = self._template(spec)
        if tpl is not None:
            return tpl.predicted_nonorth(frames, spec)
        return predicted_angle(self, frames, spec, lambda: self.layout(frames, spec))
