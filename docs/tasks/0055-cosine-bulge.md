# 0055 — Cosine profile bulges: `("cosine", s0)` with s0 ≤ 0

- **Status:** done
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

**Steps 1–3 (2026-10-29).**
- `limits.COSINE_S0_MIN = -1.0` (inclusive) and `COSINE_S0_MAX = 0.5`
  (exclusive).  Outside, the error names both bounds and their meaning:
  "cosine s0 must be in [-1, 0.5), got 0.6: -1 is a bulge to 3·R
  (COSINE_S0_MIN), 0.5 a throat of zero radius (COSINE_S0_MAX); s0 > 0
  constricts, s0 < 0 bulges".
- **Step 3, existing machinery: nothing needed changing.**
  - The chord check takes absolute gaps between chord and profile, so it
    holds for bulges.  Layers needed at the default `chord_tol` (uniform
    stations): 23 at s0 = −0.1, 36 at 0.25, 50 at −0.5, 71 at −1.  The
    gap depends on s0 and the layer count only, not on the length.
  - `Sweep.validate`'s bend-radius check uses `clearance` (the inlet's
    outer radius) against the path's curvature.  A Reducer is straight,
    so a bulge's larger radius doesn't enter it.
  - No assembly-level clash or containment check uses a fitting's
    largest radius.  `outer_radius` callers (equipment nozzles, `lc`
    default, tee) all read port specs, which a bulge leaves at R.
  - `_scale_layers` scales every radius by r(s), so the layers stay
    nested at every station.
  - Absolute `first_cell` scales with the radius too (as in a
    constriction): at s0 = −1 the first cell is 3× the inlet's at the
    bulge's middle.  Noted, not changed.
- **Quality** (nang 4, nrad 3, 72 layers over 4 R, with straights;
  meshed = predicted, 4864 cells): min SICN 0.29 at s0 = 0.25, 0.19 at
  −0.5, 0.13 at −1.  All valid.

**Step 4, done once the example was committed (2026-10-29).  At first
not done: `hexmesh/examples/fittings/stenosis.py` was not committed** (it is the paused stenosis work, with its gallery entry and
`validation/stenosis/`), so I left it alone.
- `build(s0, length_d)` passes s0 through, so it already takes the new
  range.  But `N_STENOSIS = 40` is rejected at s0 = −1 ("use n_layers >=
  71"), at any length.
- Measured in a scratch copy with `N_STENOSIS = 71`: s0 ∈ {−1, 0, 0.25}
  × length_d ∈ {1, 4} all give 23 220 cells and identical node tags and
  hexes (one SHA-1).  Min SICN 0.098 at 1 D and 0.108 at 4 D at every
  s0: the worst cell is outside the stenosis.  Mesh time 5.3–6.4 s.
  Today's default (40 layers) has 17 640 cells.
- The change needed: `N_STENOSIS = 71`; the docstring's "every
  `build(s0, length_d)` with `s0 ≤ 0.25`" becomes "`−1 ≤ s0 ≤ 0.25`",
  sized for `s0 = −1`; then regenerate its gallery entry.
  `validation/stenosis/run.py` may depend on the count.

## Questions for design

_None._

## Outcome

**Done (2026-10-29).**  Steps 1–3 in `5f12e1e`.  Step 4 came with the
stenosis example's own commit: `N_STENOSIS = 71`, docstring for
−1 ≤ s0 ≤ 0.25, gallery entry regenerated (23 220 cells, min SICN
0.101, min SJ 0.772, 5.5 s), and `test_reducer.py::test_stenosis_variants_aligned`
(six variants validate with one cell count; s0 = −1 at 1 D and 0.25 at
4 D mesh to identical node tags and hexes).
- **Files:** `hexmesh/assembly/limits.py` (`COSINE_S0_MIN`,
  `COSINE_S0_MAX`), `profile.py` (range, docstring), `fittings.py`
  (Reducer docstring), `API.md` (profile table).
- **Tests:** `test_reducer.py`: station nodes on R(s) for s0 ∈ {−1,
  −0.5, −0.1, 0}, bulge shape and layer count, both bounds rejected
  with the message.  Kit case `profile-cosine-bulge` (s0 = −0.5, 50
  layers), so conformance and refinement cover it.
- **Suite:** 1913 passed (+20).
- **Surprise:** none in the machinery; bulges need more layers than
  constrictions (71 at s0 = −1 against 36 at 0.25).
