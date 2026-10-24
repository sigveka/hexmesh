# 0012 — Miter bends and standard elbows

- **Status:** ready
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0011

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The legacy `MiterBend` (single cut and multi-cut) and `Elbow`
(ASME long/short radius, R = 1.5D / 1D) have no assembly equivalent.

**Where.**  Legacy: `connectors/bend.py` (`MiterBend`; `Elbow` at `:625`);
`fittings._build_miter_outlet`.  New: `assembly/fittings.py`, on top of
`assembly/sweep.py`.

**Do.**
1. `Elbow(schedule="long" | "short", angle=90, n_layers)`: a constructor
   that returns a `Bend` with the radius taken from the inlet spec's outer
   diameter.  This needs the spec, so resolve it in `validate`/`ports`,
   not in `__init__`.
2. `MiterBend(angle, n_cuts=1, n_layers)` as a `Sweep` of straight
   segments.  Each cut is an internal station whose plane bisects the turn.
   The station face is an **ellipse** (the pipe cut obliquely), not the
   circle `build_face` makes from the spec.  Its outer wall nodes must lie
   on both adjacent cylinders.
   - First check whether `Path` can carry an oblique station: a frame whose
     normal is the bisector, with the face scaled by 1/cos(θ/2) along the
     in-plane direction.
   - If this needs a new face kind or a change to `Interface`, record it
     under **Questions for design** and stop.
3. Reject cuts that turn more than the station-face skew allows (decide
   the limit by measuring min SICN).  Do it in `validate`.

**Accept.**
- Both fittings are in the conformance kit `CASES`: single cut, 3 cuts,
  and rolled.
- Test: wall nodes on a miter station lie on both cylinders (tolerance
  1e-9 R).
- Test: `Elbow` radii for both schedules, and a multi-layer spec.

## Agent notes

## Questions for design

## Outcome

_Not done._
