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

# Quality of a shell whose outline changes shape (a circle in a rectangle,
# a rectangle in a circle; decision 0026 item 4, task 0047), predicted
# before GMSH by ``section_quality``.  Two tiers: past the soft limit,
# ``validate()`` warns; past the hard one, it rejects.
#: Max non-orthogonality, degrees: OpenFOAM ``checkMesh``'s "severely
#: non-orthogonal" count starts here (it fails a mesh only above 90°).
OUTLINE_NONORTH_WARN = 70.0
#: Beyond this, non-orthogonal correction struggles (practitioners' rule).
OUTLINE_NONORTH_MAX = 80.0
#: Min corner scaled Jacobian (``quality_hex``): warn below.
OUTLINE_SJ_WARN = 0.3
#: Reject below: the wye prototype's floor (decision 0017).
OUTLINE_SJ_MIN = 0.1

#: Wall projection (decision 0029): the largest move of a mesh node onto
#: its fitting's analytic wall, in local cell heights (the node's shortest
#: hex edge to a node on no wall).  Beyond it, ``Assembly.mesh()`` stops:
#: the projector or the surface it corrects is wrong.  Task 0051 measured
#: at most 0.86 at ``nrad`` 3 (60° wye), growing as about 0.29 ``nrad``,
#: so 4 admits uniform ``nrad`` up to about 13; a projector that crosses
#: into another branch moves nodes by R or more.  Task 0056 revisits the
#: unit (decision 0029's amendment).
WALL_PROJECTION_MAX_MOVE = 4.0
