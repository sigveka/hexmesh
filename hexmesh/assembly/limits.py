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
Input limits and tolerances, as data (decision 0019, constraint 6;
decision 0024).

Plain module constants, so a schema or an agent can read them without
building anything.  Angles are in degrees.

Each constant is also an entry of :data:`LIMITS` (task 0095): its value,
unit, kind and a one-line doc.  Units: ``deg``; ``1`` (a ratio or a
quality metric); ``R`` (radii: the core's, or the local wall's);
``t`` (ring thicknesses); ``layers``.  Kinds: ``error`` (past it,
input is rejected), ``warn`` (past it, ``validate()`` warns) and
``info`` (a cap or a table hexmesh applies itself, rejecting nothing).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

KINDS = ("error", "warn", "info")


@dataclass(frozen=True)
class Limit:
    """A registered limit: *value*, *unit*, *kind* (one of :data:`KINDS`)
    and a one-line *doc*."""

    value: object
    unit: str
    kind: str
    doc: str


#: name → :class:`Limit`, one per constant of this module (task 0095).
#: Errors name these in ``limit`` (``hexmesh.errors``).
LIMITS: dict[str, Limit] = {}


def _limit(name: str, value, unit: str, kind: str, doc: str):
    """Register *name* and return *value* (the module constant)."""
    if kind not in KINDS or name in LIMITS:
        raise AssertionError(f"limit {name}: kind {kind!r} or a duplicate name")
    LIMITS[name] = Limit(value, unit, kind, doc)
    return value


# A bend angle below this is probably in radians: ``Bend(angle=1.57)``
# builds a 1.57° bend.  A warning, not an error: small field bends exist.
RADIANS_WARNING_BELOW = _limit(          # 6.28°: a full turn, read as radians
    "RADIANS_WARNING_BELOW", 2 * math.pi, "deg", "warn",
    "a bend, elbow or wye angle below this is probably in radians")

# ``toward=`` must be at least this far from the inlet normal (either
# sense): closer, its component across the pipe is too small to set a roll.
TOWARD_MIN_ANGLE = _limit(
    "TOWARD_MIN_ANGLE", 1.0, "deg", "error",
    "smallest angle between toward= and the inlet axis")

# A junction's ``toward=`` may miss the nearest allowed roll (a multiple of
# the section's period) by at most this much.
JUNCTION_TOWARD_TOL = _limit(
    "JUNCTION_TOWARD_TOL", 1.0, "deg", "error",
    "largest miss of a junction's toward= from its nearest allowed direction")

#: Smallest gap between consecutive layer outlines, as a fraction of the
#: outer one's largest extent (decision 0026, item 5): each outline must lie
#: strictly inside the next all round, or the ring has cells of no height.
OUTLINE_MIN_GAP = _limit(
    "OUTLINE_MIN_GAP", 1e-3, "1", "error",
    "smallest gap between consecutive layer outlines, over the outer one's extent")

# Quality predicted before GMSH: a shell whose outline changes shape (a
# circle in a rectangle, a rectangle in a circle; decision 0026 item 4, task
# 0047, ``section_quality``), and a tee's block layout (task 0052).  Two
# tiers: past the soft limit, ``validate()`` warns; past the hard one, it
# rejects.
#: Max non-orthogonality, degrees: OpenFOAM ``checkMesh``'s "severely
#: non-orthogonal" count starts here (it fails a mesh only above 90°).
OUTLINE_NONORTH_WARN = _limit(
    "OUTLINE_NONORTH_WARN", 70.0, "deg", "warn",
    "predicted or meshed non-orthogonality above this warns")
#: Beyond this, non-orthogonal correction struggles (practitioners' rule).
OUTLINE_NONORTH_MAX = _limit(
    "OUTLINE_NONORTH_MAX", 80.0, "deg", "error",
    "predicted or meshed non-orthogonality above this is rejected")
#: Min corner scaled Jacobian (``quality_hex``): warn below.
PREDICTED_SJ_WARN = _limit(
    "PREDICTED_SJ_WARN", 0.3, "1", "warn",
    "predicted or meshed min corner scaled Jacobian below this warns")
#: Reject below: the wye prototype's floor (decision 0017).
PREDICTED_SJ_MIN = _limit(
    "PREDICTED_SJ_MIN", 0.1, "1", "error",
    "predicted or meshed min corner scaled Jacobian below this is rejected")

#: Pipe tees (decision 0031 amendment, task 0060): the largest branch ratio
#: r/R.  Above it the saddle's curved sides pull the meshed corner SJ below
#: the straight-edge prediction: at r/R 0.95 by at most 0.025, at 0.97 by
#: 0.07 and at 0.99 by 0.27 (nang 8, 90°: 0.30 against 0.57 predicted).
TEE_MAX_RATIO = _limit(
    "TEE_MAX_RATIO", 0.95, "1", "error",
    "largest branch radius of a pipe tee, over the main radius")

#: Offset tees (task 0061, proposed to design): the largest offset over the
#: branch radius, |h|/r.  Past h = r the branch's footprint leaves the main's
#: top line and OCC's face fills turn erratic: at nang 8, 90°, cases fail
#: from h/r 1.38 (folded wall projection, failed fills, a plane face whose
#: edge OCC rebuilds without end points), with meshed cases between them.
#: Every one of 90 cases with h ≤ r (r/R 0.25–0.85 at 90°, 0.55–0.8 at
#: 45°) meshes or is rejected by its predicted SJ.
TEE_MAX_OFFSET_RATIO = _limit(
    "TEE_MAX_OFFSET_RATIO", 1.0, "1", "error",
    "largest offset of a pipe tee's branch axis, over the branch radius")

#: Equal tees (decision 0043 amendment 2026-11-10, task 0122): a branch
#: radius within this of the main's, relatively, is an equal tee (the
#: oriented junction cube), and is taken as exactly the main's.
EQUAL_TEE_RTOL = _limit(
    "EQUAL_TEE_RTOL", 1e-9, "1", "info",
    "relative tolerance within which a branch radius equals the main's (an equal tee)")

#: Equal tees (task 0122; design's answer, 2026-11-10): square only.  The
#: junction cube builds equal laterals at nang 8 down to 40°, but their
#: meshed SJ falls as nang rises (60°: 0.304, 0.108, then 0.031 at nang
#: 24) and from 60° down they fail checkMesh's skewness at nang 8 (60°:
#: 4.6; 45°: 6.2).  The square tee holds: 0.511 at nang 8, 0.305 at 48.
EQUAL_LATERAL_ANGLE_MIN = _limit(
    "EQUAL_LATERAL_ANGLE_MIN", 90.0, "deg", "error",
    "smallest angle of an equal tee (branch as wide as the main): square only")

#: Equal tees, measured (task 0127; validation/tools/equal_tee.json,
#: rows "refinement", "short_stations_and_nang48" and "fine_nang"): the
#: square tee's meshed min SJ falls with nang, single and shelled alike
#: (0.511, 0.399, 0.353, 0.330, 0.305, 0.293 at nang 8, 16, 24, 32, 48,
#: 64).  The largest measured nang with SJ >= 0.3; above it validate()
#: warns.  None measured falls below 0.1, so there is no maximum; nang 96
#: needs ~16 GB to mesh and wasn't measured.
EQUAL_TEE_NANG_CLEAN = _limit(
    "EQUAL_TEE_NANG_CLEAN", 48, "1", "warn",
    "largest nang at which an equal tee measured meshed SJ >= 0.3")

#: Duct taps (decision 0033, task 0070): the largest across ratio q/a of a
#: tap inside the face (q its reach across, a the face's half-width).  The
#: ±y tube blocks thin as q → a: at 0.95 a 1:1 duct's rectangular tap
#: meshes at corner SJ 0.095, below ``PREDICTED_SJ_MIN``; at 0.93 every
#: measured case (1:1–3:1, both faces, rectangular and round) is ≥ 0.12.
DUCT_TAP_MAX_RATIO = _limit(
    "DUCT_TAP_MAX_RATIO", 0.93, "1", "error",
    "largest reach across of a duct tap, over the face's half-width")
#: A tap on the narrow face of a duct at least this deep (depth/width)
#: warns: the dome reaches into a deep, thin core (task 0069, 3:1).
DUCT_TAP_NARROW_ASPECT_WARN = _limit(
    "DUCT_TAP_NARROW_ASPECT_WARN", 3.0, "1", "warn",
    "a tap on the narrow face of a duct this deep (depth / width) or deeper warns")

#: Shortest ``Switch`` (task 0085), in ring thicknesses t: the cap is one
#: t deep, and the core block between the O-H port and the cap must have a
#: length.  Measured from 1.25 t to 6 t (a/b 1–4, nrad 1–6): min corner SJ
#: 1/√3 throughout, max non-orthogonality ≤ 54° (task 0085's table).
SWITCH_MIN_LENGTH = _limit(
    "SWITCH_MIN_LENGTH", 1.25, "t", "error",
    "shortest Switch, in ring thicknesses")
#: On a graded H face (task 0086, design answer to Q2), also
#: ``L ≥ Δ_max / SWITCH_MAX_SHEAR``: Δ_max the largest shift of a side node
#: between the O-H and the H face (``switch.wall_shift``).  The side
#: blocks' cells shear by about Δ_max / L.
SWITCH_MAX_SHEAR = _limit(
    "SWITCH_MAX_SHEAR", 0.4, "1", "error",
    "largest side-block shear of a switch to a graded H face (wall shift / length)")
#: And ``L ≥ t + Δ_max / SWITCH_MAX_CORE_SHEAR``: the core block (L − t
#: long) carries the same change of grading (task 0086, Q4).  With both,
#: every measured case meshes at min SJ ≥ 0.501 (450 runs: a/b 1–4,
#: n 8–24, first cell to h/200, nrad derived to 9, L/t 1.25–16).
SWITCH_MAX_CORE_SHEAR = _limit(
    "SWITCH_MAX_CORE_SHEAR", 1.0, "1", "error",
    "largest core-block shear of a switch to a graded H face (wall shift / core length)")
#: The empirical min corner SJ of a switch against its wall shear
#: Δ_max / L, with the core term kept: (shear, the smallest meshed SJ up to
#: that shear in task 0086's table, rounded down), ascending.
#: ``validate()`` reports the row at the smallest tabulated shear not
#: below the switch's.
SWITCH_SHEAR_SJ = _limit(
    "SWITCH_SHEAR_SJ",
    ((0.1, 0.577), (0.2, 0.550), (0.3, 0.548), (0.35, 0.546), (0.4, 0.501)), "1", "info",
    "(wall shear, smallest meshed min corner SJ) of measured switches, for reports")

#: ``("cosine", s0)`` profile severity (decision 0008, amended 2026-10-28;
#: task 0055): s0 > 0 a constriction with throat ``(1 − 2·s0)·R``, s0 = 0 a
#: plain pipe, s0 < 0 a bulge of largest radius ``(1 − 2·s0)·R``.  The
#: minimum is inclusive (a bulge to 3 R); the maximum is exclusive (a
#: throat of zero radius).
COSINE_S0_MIN = _limit(
    "COSINE_S0_MIN", -1.0, "1", "error",
    "smallest cosine-profile s0 (inclusive): a bulge to 3 R")
COSINE_S0_MAX = _limit(
    "COSINE_S0_MAX", 0.5, "1", "error",
    "largest cosine-profile s0 (exclusive): a throat of zero radius")

#: Largest resolved ``Wye.n_split`` (task 0056): the turning blocks' min
#: corner SJ falls as n_split grows (0.21 → 0.10 at 60° from 3 to 20
#: layers) and a 120° wye folds under projection from about 20.  At 6
#: every angle measured keeps SJ ≥ 0.11.
WYE_N_SPLIT_MAX = _limit(
    "WYE_N_SPLIT_MAX", 6, "layers", "info",
    "largest Wye.n_split that resolution or refined(k) chooses")

#: Total shell thickness through a wye (task 0053): T ≤ R ·
#: min(WYE_SHELL_TAN_FACTOR · tan(angle/2), WYE_SHELL_MAX), R the core
#: radius.  Measured limits (any nang): 0.19 / 0.28 / 0.40 / 0.59 / 0.84 R
#: at 30° / 45° / 60° / 90° / 120°, i.e. 0.69 tan(angle/2) below 90°.
#: Past them the daughters' shells fold where they meet, OCC fails
#: building the crotch (90°), or a hub shell block inverts (120°).  The
#: rule allows 0.17 / 0.27 / 0.38 / 0.55 / 0.55 R.
WYE_SHELL_TAN_FACTOR = _limit(
    "WYE_SHELL_TAN_FACTOR", 0.65, "1", "error",
    "a wye's total shell thickness is at most this × R × tan(angle / 2)")
WYE_SHELL_MAX = _limit(
    "WYE_SHELL_MAX", 0.55, "R", "error",
    "a wye's total shell thickness is at most this many core radii")
#: Narrowest wye with shells (task 0053): the shell cells' min corner SJ is
#: 0.11–0.13 at 40° (thin and at the limit) but 0.04–0.05 at 30°.
#: Single-layer wyes keep 30°–120° (decision 0017).
WYE_SHELL_MIN_ANGLE = _limit(
    "WYE_SHELL_MIN_ANGLE", 40.0, "deg", "error",
    "narrowest wye with shells")

#: Wall projection (decision 0029, task 0056): a node moved further than
#: this many local wall radii onto its fitting's analytic wall gets a
#: warning naming the fitting.  Legitimate moves reach 0.77 R (30° wye,
#: task 0051); a projector sending nodes across a branch moves them about
#: R or more.  Folds are rejected by ``Assembly.mesh()``'s inversion check,
#: not by distance.
WALL_PROJECTION_WARN_MOVE = _limit(
    "WALL_PROJECTION_WARN_MOVE", 1.0, "R", "warn",
    "a wall projection moving a node further than this many local wall radii warns")

#: Decision 0046 rule 5 (task 0123): a wall node counts as moved by a
#: correction when it moves more than this many local wall radii; below
#: it, the move is the projector's rounding of a node gmsh already placed
#: on the wall.
CORRECTION_MIN_MOVE = _limit(
    "CORRECTION_MIN_MOVE", 1e-9, "R", "info",
    "smallest move, in local wall radii, a correction record counts")

#: Miter cuts (task 0094 named them; moved here from ``fittings``, task
#: 0095): each cut of a ``MiterBend`` turns at least ``MIN_MITER_CUT`` (a
#: smaller cut is a Straight) and at most ``MAX_MITER_CUT``.
MIN_MITER_CUT = _limit(
    "MIN_MITER_CUT", 1.0, "deg", "error", "smallest turn of each MiterBend cut")
MAX_MITER_CUT = _limit(
    "MAX_MITER_CUT", 90.0, "deg", "error", "largest turn of each MiterBend cut")

#: Sweeps (moved from ``sweep``, task 0095): a slab with straight axial
#: edges turns at most ``MAX_CHORD_TURN`` (splines, closures); a bend's
#: layer turns less than ``MAX_SLAB_TURN`` (at 180° its faces are
#: antiparallel, ``corners.frame_offset``; inline in ``Bend.layers_ok``
#: before); resolution tries counts up to ``MAX_RESOLVED_LAYERS``.
MAX_CHORD_TURN = _limit(
    "MAX_CHORD_TURN", 30.0, "deg", "error",
    "largest turn of one axial layer with straight axial edges (splines, closures)")
#: Twisted straights (task 0062, proposed to design): the largest roll of
#: one axial layer.  A layer's side faces warp by about its roll (5° → 5°,
#: 10° → 10.7° at Δz = R), and at half the section's period (45° for a
#: circle) its corners are ambiguous.  More layers lower it; the wall
#: shear (twist per length) goes through the predicted-quality tiers.
STRAIGHT_TWIST_WARN = _limit(
    "STRAIGHT_TWIST_WARN", 15.0, "deg", "warn",
    "a twisted straight's roll per axial layer above this warns")
STRAIGHT_TWIST_MAX = _limit(
    "STRAIGHT_TWIST_MAX", 30.0, "deg", "error",
    "largest roll of one axial layer of a twisted straight")
MAX_SLAB_TURN = _limit(
    "MAX_SLAB_TURN", 180.0, "deg", "error",
    "a bend's axial layer turns less than this (exclusive)")
MAX_RESOLVED_LAYERS = _limit(
    "MAX_RESOLVED_LAYERS", 100_000, "layers", "error",
    "largest axial layer count n_layers=None resolution tries")

#: Wye angle (moved from ``wye.ANGLE_RANGE``, task 0095; decision 0017).
WYE_ANGLE_MIN = _limit("WYE_ANGLE_MIN", 30.0, "deg", "error", "narrowest Wye")
WYE_ANGLE_MAX = _limit("WYE_ANGLE_MAX", 120.0, "deg", "error", "widest Wye")

#: Venturi divergent included angle, ISO 5167-4 (moved from
#: ``profile.VENTURI_DIVERGENT``, task 0095).
VENTURI_DIVERGENT_MIN = _limit(
    "VENTURI_DIVERGENT_MIN", 7.0, "deg", "error", "narrowest venturi divergent (ISO 5167-4)")
VENTURI_DIVERGENT_MAX = _limit(
    "VENTURI_DIVERGENT_MAX", 15.0, "deg", "error", "widest venturi divergent (ISO 5167-4)")

# --- the resolution advisor (hexmesh.agent.advise, task 0098) ----------------------
# Guidance, not checks: the advisor's rules read them, nothing rejects a
# mesh that passes them.

MAX_WALL_GROWTH = _limit(
    "MAX_WALL_GROWTH", 1.2, "1", "info",
    "largest growth ratio between neighbouring cells from the wall cell inward that "
    "the advisor plans [casey_and_wintergerste_2000]")
MAX_AXIAL_ASPECT_STRAIGHT = _limit(
    "MAX_AXIAL_ASPECT_STRAIGHT", 6.0, "1", "info",
    "the advisor's axial cell over core cell in straights: the calibrated runs had "
    "5–7.5 (validation/poiseuille, rect_duct)")
MAX_AXIAL_ASPECT_FITTING = _limit(
    "MAX_AXIAL_ASPECT_FITTING", 2.0, "1", "info",
    "the advisor's axial cell over core cell in bends, junctions and other fittings, "
    "where the flow develops (judgement; no validated case)")
MAX_AXIAL_ASPECT_BUDGET = _limit(
    "MAX_AXIAL_ASPECT_BUDGET", 12.0, "1", "info",
    "the straights' axial aspect the advisor relaxes to first when over the budget")
