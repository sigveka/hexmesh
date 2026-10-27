# 0031 — Profiled `Reducer`: constrictions, venturis and nozzles

- **Status:** done
- **Decision:** [0008 — Profiled sweep: a varying-radius fitting](../decisions/0008-profiled-sweep.md)
- **Depends on:** —  (0027 also changes `Reducer.path`; coordinate if
  both are in progress: grading interpolation and profiles use the same
  per-station specs)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Venturis, flow nozzles, smooth constrictions and simplified
valve seats are axisymmetric with a radius that varies along the axis.
`Reducer` already places one exact station per axial layer with linear
radii; a profile generalises it (decision 0008).  The smooth cosine
constriction is also the next OpenFOAM validation case (task 0032).

**Where.**
- `hexmesh/assembly/fittings.py`: `Reducer` (`path`, `fractions`,
  `validate`, `cell_count`), `_with_radii`.
- `hexmesh/assembly/intent.py`: the new fields must save and load.
- `tests/test_reducer.py`, `tests/test_fitting_conformance.py`;
  `API.md`.
- Reference: RESEARCH §7.3 (cosine profile), `../geometry_valve/`
  (constant-core variant).

**Do.**
1. **`Reducer(outlet, length, n_layers, axial_grading=1.0, profile=None, core="scale")`.**
   - `profile=None`: today's linear cone, unchanged.
   - Named shapes, serialisable:
     - `("cosine", s0)`: R(s) = R_in · [1 − s0 · (1 + cos(2π(s − ½)))] on
       s ∈ [0, 1], so the ends have R_in and the throat is at the middle.
       This requires `outlet` radii equal to the inlet's; check it.
     - `("venturi", …)`: standard convergent–throat–divergent proportions.
       Cite the source under *Agent notes* (e.g. ISO 5167-4 classical
       venturi: convergent 21°, throat length 1 d, divergent 7–15°).  If
       no source is at hand, leave venturi out and say so.
   - Table: `[(s, r), …]` with r = R / R_in, s from 0 to 1, interpolated
     by a monotone cubic (no overshoot); the end values must match the
     inlet and outlet specs.
   - No callables (they can't be saved).
   - The profile scales every radius of the stack proportionally, as the
     linear reducer does (D1).
2. **Stations.**  One station per axial layer, as now, at fractions from
   `axial_grading`.  Every wall node of a station lies on R(s) exactly.
3. **Chord error bound in `validate()`.**  Between stations the wall is a
   straight chord.  Estimate the largest gap between the chord and the
   profile per slab (sample the profile; don't rely on h²|R″|/8 alone),
   and reject if it exceeds a tolerance (propose a default, e.g.
   1e-3 · R_in), naming the slab and the `n_layers` needed.
4. **D2 experiment: `core="fixed"`.**  The core square keeps the size it
   has at the smallest radius along the profile; only the outer ring
   follows R(s) (`../geometry_valve/`).  Measure it against D1 (below).
   If it isn't clearly better at the throat, remove it and record the
   numbers.
5. **Docs.**  `API.md` `Reducer` entry: profiles, the chord tolerance,
   the 8× cells note if relevant.

**Accept.**
- Kit cases: cosine constriction (s0 = 0.25, length 2 D), venturi (if
  included), table profile.  All-hex, meshed = predicted, every kit check
  passing; with task 0025's wall-exactness check if it is done (wall
  nodes on R(s) at stations).
- A test that every station's wall nodes lie on R(s) to 1e-9 · R.
- `validate()` rejects a too-coarse cosine constriction, naming the
  layers needed.
- Save/load round-trip with each profile kind.
- **D1 vs D2 table** for the cosine constriction (s0 = 0.25) at `nang` 6
  and 12, 24 layers: min SICN overall and at the throat slab, max aspect
  ratio, cell count.
- Full suite: no new failures.

**Out of scope.**  Profiles along a curved centreline (a profiled
`SplinePipe`), non-circular sections, and the OpenFOAM run (task 0032).
But keep the profile and per-station radius logic reusable by other
sweeps rather than private to `Reducer`: a profiled `SplinePipe` is a
planned expansion ([decision 0018](../decisions/0018-future-vascular-networks.md), constraint 2).

## Agent notes

- **Profile logic lives in `hexmesh/assembly/profile.py`** (`Profile`,
  `CHORD_TOL`), not in `Reducer`, so a profiled `SplinePipe` can reuse it
  (decision 0018, constraint 2).  `Reducer` only asks it for r(s), the
  station fractions and the chord gaps.
- **Extra field `chord_tol`** (default 1e-3 · R_in) on `Reducer`, so a
  user can trade wall accuracy for layers explicitly; it serialises like
  the other fields.
- **Venturi source:** ISO 5167-4:2003 (classical Venturi tube):
  convergent 21° ± 1° included angle, cylindrical throat of length d,
  divergent 7°–15° included angle.  Cited from the standard's published
  summary, not from a copy in `docs/papers/` (none there).  Left out: the
  inlet cylinder (length D, part of the upstream pipe here), the
  convergent/throat fillets (corners are sharp), and the standard's
  β range 0.3–0.75 (any 0 < β < 1 is accepted; geometry, not metering).
  Corners are moved onto the nearest interior station, so they are exact.
- **Table interpolation:** Fritsch–Carlson PCHIP written in numpy
  (scipy is only an optional `io` dependency).
- **Chord check:** sampled (64 points per slab), so kinks and inflections
  count; the suggested `n_layers` is found by doubling then bisection, so
  it is the same from any starting count (36 for cosine s0 = 0.25).
- **Step 4 (D2) was measured, not added as an option**: a patched face
  builder fixed the core square at the throat size.  Not clearly better,
  so no `core=` field (numbers in *Outcome*).

## Questions for design

_None._

## Outcome

**Done.**  `Reducer(..., profile=None, chord_tol=1e-3)` with cosine,
venturi and table profiles (D1: the whole stack scales with r(s)).

Files:
- `hexmesh/assembly/profile.py` (new): `Profile`, PCHIP slopes, station
  fractions with kinks pinned, sampled chord gaps.
- `hexmesh/assembly/fittings.py`: `Reducer.profile`, `chord_tol`,
  `_check_profile` (end radii vs specs, chord bound naming the layers
  needed), profiled `path`.
- `tests/test_reducer.py`: +18 tests (station wall nodes on R(s) to
  1e-9 · R for each kind; too-coarse cosine names 36 layers; venturi
  corners on stations; PCHIP monotone; 8 rejection messages; shell
  thickness scales; save/load per kind).
- `tests/test_fitting_conformance.py`: kit cases `profile-cosine`
  (s0 0.25, L = 2D, 40 layers), `profile-venturi` (β 0.5, 15°, 12
  layers), `profile-table-2layer` (two layers, graded 1.1, 16 layers).
  All kit checks and `refined(2)` pass, including wall exactness.
- `API.md`: `Reducer` profiles section.

**D1 (scale) vs D2 (fixed core)**, cosine s0 = 0.25, L = 2D, 24 layers
(with `chord_tol` 3e-3: 24 layers is below the 36 the default needs),
`nrad = nang/2`:

| nang | core | cells | min SICN | at throat | min SJ | at throat | max AR | at throat |
|---|---|---|---|---|---|---|---|---|
| 6  | scale (D1) | 2592  | 0.605 | 0.605 | 0.773 | 0.793 | 2.5 | 2.5 |
| 6  | fixed (D2) | 2592  | 0.590 | 0.606 | 0.793 | 0.793 | 3.4 | 2.5 |
| 12 | scale (D1) | 10368 | 0.329 | 0.329 | 0.732 | 0.751 | 5.0 | 5.0 |
| 12 | fixed (D2) | 10368 | 0.330 | 0.330 | 0.752 | 0.752 | 5.0 | 5.0 |

At the throat the two are equal to within 0.001 SICN; D2 only improves
min SJ away from the throat (0.773 → 0.793 at nang 6) and worsens the
max aspect ratio (2.5 → 3.4: thick ring cells at the inlet).  Not
clearly better, so D2 was not added (decision 0008 point 3).

Suite: 1204 passed, 5 skipped (was 1142 after task 0029; includes other sessions' additions).

Surprises:
- At 24 layers the default tolerance already fails for s0 = 0.25
  (gap 2.1e-3 · R_in); 36 layers are needed.  The benchmark run (task
  0032) should budget ≥ 36 layers over the constriction.
- The error names slab 0: |R″| of the cosine peaks equally at both ends
  and at the throat, and with equal spacing the first of those slabs is
  reported.  Axial grading toward the throat would not help, since the
  ends need the same resolution.

Follow-ups:
- A profiled `SplinePipe` (decision 0018) can reuse `Profile` directly.
- Venturi fillets, if a metering case needs them: a table profile can
  already approximate one.

