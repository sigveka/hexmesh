# 0055 — Cosine profile bulges: `("cosine", s0)` with s0 ≤ 0

- **Status:** ready
- **Decision:** [0008 — Profiled sweep](../decisions/0008-profiled-sweep.md), amendment 2026-10-28 (bulges)
- **Depends on:** —  (small; can run between larger tasks)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Outward bulges are real geometries: aneurysms, expansion
chambers, strainer housings.  One parameter spanning constriction →
plain pipe → bulge also gives node-aligned study variants across the
whole range.  Today `("cosine", s0)` rejects s0 ≤ 0 ("cosine
constriction s0 must be in (0, 0.5)"); only a table profile can make a
bulge, and that isn't the exact cosine.

**Where.**  `hexmesh/assembly/profile.py` (`_cosine`, the docstring),
`hexmesh/assembly/limits.py` (the range), `API.md` (profile table),
`hexmesh/examples/fittings/stenosis.py`, tests (`tests/test_reducer.py`).

**Do.**
1. Accept **−1 ≤ s0 < 0.5**; s0 < 0 is a bulge of largest radius
   `(1 − 2·s0)·R`, and s0 = 0 a plain pipe.  Put the bounds in
   `limits.py`.  The error outside the range names both bounds and what
   they mean.
2. Docstring and `API.md`: "constriction (s0 > 0) or bulge (s0 < 0)".
3. Check the existing machinery covers bulges, and adjust if not:
   - the chord-error check (it was written for constrictions);
   - `validate()`'s bend-radius and containment checks downstream (the
     outermost radius now exceeds the inlet's inside the fitting);
   - `half_extent` / `outer_radius` users that assume the inlet is the
     largest section.
4. **`stenosis` example:** `build(s0, length_d)` accepts the new range.
   Check that its fixed counts still give one topology and a valid
   chord error at s0 = −1, length 1 D; raise `N_STENOSIS` if needed and
   say so in its docstring.  Regenerate its gallery entry if the default
   mesh changes.

**Accept.**
- Every wall node at a station is on R(s) for s0 ∈ {−1, −0.5, −0.1, 0},
  as the existing constriction test does.
- A bulge kit case (s0 = −0.5) validates and meshes all-hex, meshed =
  predicted; quality reported.
- `stenosis.build` at s0 ∈ {−1, 0, 0.25} × length_d ∈ {1, 4}: one cell
  count, identical connectivity (node tags and hexes) when meshed.
- Out-of-range s0 rejected with the bounds named.
- Full suite: no new failures.

**Out of scope.**  Asymmetric (saccular) bulges; an aneurysm validation
case (RESEARCH §7.5, later).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
