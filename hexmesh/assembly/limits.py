"""
Input limits and tolerances, as data (decision 0019, constraint 6;
decision 0024).

Plain module constants, so a schema or an agent can read them without
building anything.  Each is in degrees.
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
