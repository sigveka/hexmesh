# 0014 — Spline pipe

- **Status:** done
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

- **API refined:** `SplinePipe(points, n_layers, end_tangent=None)`, a
  single optional outlet direction instead of `tangents`.  The start
  tangent is always the inlet normal (clamped).  With no `end_tangent`
  the spline ends with zero curvature (natural), as legacy did.
- **No SciPy.**  SciPy is only an optional `io` dependency, so
  `fittings._cubic_spline` is a numpy clamped/natural cubic spline,
  chord-length parametrised.  It interpolates the points to 2e-16 and is
  C2 (tested).  Legacy clamped the start derivative to
  `tangent · dt0`, which is inconsistent with chord-length
  parametrisation; here the clamp is the unit tangent per unit chord.
- **Shared with `Closure`:** station placement (arc length + turning
  angle) and Bishop transport moved from `Closure.stations` into
  `fittings._transported_stations(curve, n, start, end=None)`, with the
  curvature check in `_min_radius(curve)`.
  - `Closure` passes `end` and absorbs the twist.
  - `SplinePipe` places its own outlet: last transported frame, twist 0.
  - `Closure`'s behaviour is unchanged (its tests pass unmodified).
- One station per layer, chord axial edges: wall nodes lie on station
  circles.  The 30° chord-turn limit and the min-radius check run in
  `validate` (tested).
- Points must start at the inlet position, which is checked rather than
  shifting the spline as legacy did.  Legacy silently translated the
  curve.
- `ports()` checks `n_layers >= 1` itself, because `Assembly.add` calls
  `ports` before `validate`.

## Questions for design

## Outcome

- **Files:** `assembly/fittings.py` (`SplinePipe`, `_cubic_spline`,
  `_transported_stations`, `_min_radius`; `Closure` refactored onto
  them), `assembly/__init__.py`, `tests/test_spline.py` (new, 18 tests),
  kit cases `spline-s-bend`, `spline-3d-2layer`.
- **Ported legacy assertions:** spline sampling (straight line, station
  count, end positions, unit tangents), Bishop frames (no rotation on a
  straight pipe, orthonormal, no twist), validation (too few points,
  zero layers), chaining after a `Straight`, two-layer specs, and cells
  scaling with stations.
- **Not ported:** `_rodrigues` tests (replaced by `interface.rotate`) and
  connector bookkeeping (nodes, inlet/outlet lists, region names); the
  conformance kit covers groups, walls and interfaces.
- **Tests:** 523 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
