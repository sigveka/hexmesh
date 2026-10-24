# 0014 — Spline pipe

- **Status:** ready
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0011

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The legacy `SplinePipe` (a pipe along a cubic spline through
given points, with Bishop frames) has no assembly equivalent.

**Where.**  Legacy: `connectors/spline_pipe.py`; `tests/test_spline_pipe.py`
(25 tests); memory note on the `v = cross(h, T)` sign.  New:
`assembly/fittings.py`.  `Closure` already builds a curved `Path` from a
Hermite curve, with stations spread by arc length and turn.  Reuse that
station placement.

**Do.**
1. `SplinePipe(points, n_layers, tangents=None)`: the inlet is the
   cursor frame and the outlet is placed at the last point
   (`places_outlet = True`).  The first point must be the inlet position;
   reject it otherwise.
2. Use Bishop (rotation-minimising) frames along the curve.  The outlet
   roll follows from the frames, and the assembly absorbs it modulo
   2π/n_outer, as `Path` already does.
3. Validation runs before GMSH: the minimum radius of curvature against
   the outer radius, and the chord-turn limit (`MAX_CHORD_TURN`).

**Accept.**
- Kit cases: an S-bend and a 3-D curve.
- Port the legacy `test_spline_pipe.py` assertions that still apply,
  rewritten against the assembly API.

## Agent notes

## Questions for design

## Outcome

_Not done._
