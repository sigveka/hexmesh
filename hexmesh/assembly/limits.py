"""
Input limits and tolerances, as data (decision 0019, constraint 6;
decision 0024).

Plain module constants, so a schema or an agent can read them without
building anything.  Angles are in degrees.
"""

from __future__ import annotations
import math

# A bend angle below this is probably in radians: ``Bend(angle=1.57)``
# builds a 1.57° bend.  A warning, not an error: small field bends exist.
RADIANS_WARNING_BELOW = 2 * math.pi     # 6.28°: a full turn, read as radians

# ``toward=`` must be at least this far from the inlet normal (either
# sense): closer, its component across the pipe is too small to set a roll.
TOWARD_MIN_ANGLE = 1.0

# A junction's ``toward=`` may miss the nearest allowed roll (a multiple of
# the section's period) by at most this much.
JUNCTION_TOWARD_TOL = 1.0

#: Smallest gap between consecutive layer outlines, as a fraction of the
#: outer one's largest extent (decision 0026, item 5): each outline must lie
#: strictly inside the next all round, or the ring has cells of no height.
OUTLINE_MIN_GAP = 1e-3

# Quality predicted before GMSH: a shell whose outline changes shape (a
# circle in a rectangle, a rectangle in a circle; decision 0026 item 4, task
# 0047, ``section_quality``), and a tee's block layout (task 0052).  Two
# tiers: past the soft limit, ``validate()`` warns; past the hard one, it
# rejects.
#: Max non-orthogonality, degrees: OpenFOAM ``checkMesh``'s "severely
#: non-orthogonal" count starts here (it fails a mesh only above 90°).
OUTLINE_NONORTH_WARN = 70.0
#: Beyond this, non-orthogonal correction struggles (practitioners' rule).
OUTLINE_NONORTH_MAX = 80.0
#: Min corner scaled Jacobian (``quality_hex``): warn below.
PREDICTED_SJ_WARN = 0.3
#: Reject below: the wye prototype's floor (decision 0017).
PREDICTED_SJ_MIN = 0.1

#: ``("cosine", s0)`` profile severity (decision 0008, amended 2026-10-28;
#: task 0055): s0 > 0 a constriction with throat ``(1 − 2·s0)·R``, s0 = 0 a
#: plain pipe, s0 < 0 a bulge of largest radius ``(1 − 2·s0)·R``.  The
#: minimum is inclusive (a bulge to 3 R); the maximum is exclusive (a
#: throat of zero radius).
COSINE_S0_MIN = -1.0
COSINE_S0_MAX = 0.5

#: Largest resolved ``Wye.n_split`` (task 0056): the turning blocks' min
#: corner SJ falls as n_split grows (0.21 → 0.10 at 60° from 3 to 20
#: layers) and a 120° wye folds under projection from about 20.  At 6
#: every angle measured keeps SJ ≥ 0.11.
WYE_N_SPLIT_MAX = 6

#: Total shell thickness through a wye (task 0053): T ≤ R ·
#: min(WYE_SHELL_TAN_FACTOR · tan(angle/2), WYE_SHELL_MAX), R the core
#: radius.  Measured limits (any nang): 0.19 / 0.28 / 0.40 / 0.59 / 0.84 R
#: at 30° / 45° / 60° / 90° / 120°, i.e. 0.69 tan(angle/2) below 90°.
#: Past them the daughters' shells fold where they meet, OCC fails
#: building the crotch (90°), or a hub shell block inverts (120°).  The
#: rule allows 0.17 / 0.27 / 0.38 / 0.55 / 0.55 R.
WYE_SHELL_TAN_FACTOR = 0.65
WYE_SHELL_MAX = 0.55
#: Narrowest wye with shells (task 0053): the shell cells' min corner SJ is
#: 0.11–0.13 at 40° (thin and at the limit) but 0.04–0.05 at 30°.
#: Single-layer wyes keep 30°–120° (decision 0017).
WYE_SHELL_MIN_ANGLE = 40.0

#: Wall projection (decision 0029, task 0056): a node moved further than
#: this many local wall radii onto its fitting's analytic wall gets a
#: warning naming the fitting.  Legitimate moves reach 0.77 R (30° wye,
#: task 0051); a projector sending nodes across a branch moves them about
#: R or more.  Folds are rejected by ``Assembly.mesh()``'s inversion check,
#: not by distance.
WALL_PROJECTION_WARN_MOVE = 1.0
