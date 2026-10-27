# 0027 — Grading-only changes across a sweep (wall-resolved reducers)

- **Status:** done
- **Decision:** [0016 — Class-1 granularity, and grading changes across a sweep](../decisions/0016-class-1-granularity-and-grading-changes.md)
- **Depends on:** —  (touches `Reducer.path`, like 0025 touches straight
  slabs; coordinate if both are in progress)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  With an absolute `first_cell` (a fixed y⁺ target), the solved
radial `mprg` differs on the two sides of a reducer, so a wall-resolved
mesh through a reducer is rejected today.  Task 0019 showed the join
works mechanically but costs quality, because the whole grading change
lands in the last slab: min SICN 0.193 → 0.094 for `mprg` 1.0 → 1.3, and
0.019 for 1.0 → 2.0.

**Where.**
- `hexmesh/assembly/signature.py`: `classify`, `SwitchClass`.
- `hexmesh/assembly/fittings.py`: `Reducer.path`, `_with_radii` (also
  used by `io/readers/pcf.py`), `Reducer.strategies`.
- `hexmesh/assembly/sweep.py`: per-station specs (`path.spec_at`) and
  `face_grading`.
- `tests/test_signature.py`, `tests/test_reducer.py`; `API.md` (switch
  classes, `Reducer`).

**Do.**
1. **Classifier.**  Mark a class-2 pair as grading-only when its only
   differences are per-layer radial `mprg`, with all counts equal (like
   `ends="wall"` on class 1; record the attribute name).  `mbmp`
   differences stay ordinary class 2.
2. **Reducer.**
   - Intermediate stations interpolate grading as well as radii.
     Suggested: geometric in `mprg`, `mprg_k = mprg_in^(1−u) ·
     mprg_out^u`, at the same fractions `u` as the radii.  If another
     rule measures better (for example interpolating the first-cell
     height), use it and record why.
   - `Reducer` declares class 2, and `validate()` accepts only
     grading-only class-2 pairs.  A count difference keeps today's error
     naming the field and the class.
3. **Other sweeps.**  Check which other fittings can see different specs
   at their two ends (`Closure` joins two existing interfaces).  If one
   can, give it the same per-station grading and declaration, or record
   why not under *Agent notes*.
4. `API.md`: the class table note and the `Reducer` entry ("may change
   radii and radial grading").

**Accept.**
- **The use case:** a reducer between `pipe(0.1)` and `pipe(0.06)`, both
  with the same absolute `first_cell` (e.g. 1 mm) and `nrad`, validates,
  meshes all-hex with the predicted count, and passes the quality check.
- **Quality**, measured with task 0019's setup (core + shell, `nrad`
  6 / 4) at `n_layers` 6 and 12:

  | `mprg` in → out | min SICN, 0019 (last-slab) | min SICN, interpolated |
  |---|---|---|
  | 1.0 → 1.0 | 0.193 | (baseline) |
  | 1.0 → 1.3 | 0.094 | measure |
  | 1.3 → 0.77 | 0.097 | measure |
  | 1.0 → 2.0 | 0.019 | measure |

  ~~Target: within 10 % of the baseline for 1.0 → 1.3 at 6 layers.~~
  **Target (revised 2026-10-27):** min SICN within 10 % of the worse end
  section's own min SICN (each end as a plain `Straight` with that end's
  spec), for the use case and the table cases.
- A count difference across a reducer is still rejected, with the class
  named.
- Classifier unit tests: grading-only marked; `mbmp` and count
  differences not.
- Full suite: no new failures.  Record the measurements in *Outcome*.

Put the per-station grading in the shared sweep machinery where it is
natural, so curved sweeps can use it later
([decision 0018](../decisions/0018-future-vascular-networks.md), constraint 2).

**Out of scope.**  Angular grading (`mbmp`) changes; count changes
(density switches, decision 0003); grading changes in fittings whose
ports always share one spec.

## Agent notes

- **Classifier.**  The attribute is `SwitchClass.grading_only: bool`.
  It is set on class 2 when every difference is a per-layer
  `… mprg`.  `mbmp`, `nang` and `nrad` differences leave it False,
  also when combined with an `mprg` change.
  - `check_port_pairs`: a fitting declaring class 2 bridges
    grading-only pairs only.  Other class-2 pairs get "switch class 2
    beyond radial grading (counts or mbmp), which needs a density switch
    (decision 0003)".
  - Fittings that don't declare class 2 keep the old message.
- **Reducer.**
  - `strategies = {0, 2}`;
  - `path` interpolates each layer's `mprg` geometrically at the radii's
    fractions (the suggested rule);
  - `_with_radii` gained an optional `mprgs`.  The PCF reader still
    calls it without, so it is unaffected.
- **Other sweeps (step 3).**  Only `Closure` can see two independent end
  specs, because `close()` joins two existing interfaces.  It is left
  at `{0}`:
  - `Closure.path(a, b, spec)` receives the source spec only, and builds
    every station from it.  Per-station grading would need the target
    spec passed through `Sweep.path` and `sweep_fill`, an interface
    change for a case no one has asked for;
  - a differently graded loop end is rejected with the class named, as
    before.
  - Every other sweep places its outlet from its own spec
    (`Straight`/`Bend` through `stack_changes`, which keep grading).
- **Quality setup.**  The 0019 table's exact parameters were not
  recorded, so I used core + shell, `nrad` 6 / 4, `nang` 8,
  R 0.1 → 0.06, `dR` 0.02, length 0.2.  My 1.0 → 1.0 baseline is 0.266
  at 6 layers (0019: 0.193).
  - **Last-slab** means a `Reducer` subclass declaring `{0, 2}` on the
    code before this task; **interpolated** is this task's `Reducer`.
  - Script: `grading_measure.py` (session scratchpad).

## Questions for design

1. **The quality target (within 10 % of the 1.0 → 1.0 baseline for
   1.0 → 1.3 at 6 layers) is missed, and per-station interpolation
   barely helps.**  Not tuned.

   | `mprg` in → out | layers | last-slab | interpolated | Reducer, same `mprg` both ends | Straight at R 0.06 with the outlet `mprg` |
   |---|---|---|---|---|---|
   | 1.0 → 1.0 | 6 | 0.266 | 0.266 | 0.266 | 0.269 |
   | 1.0 → 1.3 | 6 | 0.142 | 0.142 | 0.142 (1.3 → 1.3) | 0.144 |
   | 1.3 → 0.77 | 6 | 0.151 | 0.151 | 0.151 (0.77 → 0.77) | 0.157 |
   | 1.0 → 2.0 | 6 | 0.029 | 0.030 | 0.030 (2.0 → 2.0) | 0.030 |
   | 1.0 → 1.0 | 12 | 0.468 | 0.468 | 0.468 | 0.496 |
   | 1.0 → 1.3 | 12 | 0.261 | 0.268 | 0.268 (1.3 → 1.3) | 0.271 |
   | 1.3 → 0.77 | 12 | 0.261 | 0.261 | 0.261 (0.77 → 0.77) | 0.270 |
   | 1.0 → 2.0 | 12 | 0.052 | 0.057 | 0.057 (2.0 → 2.0) | 0.058 |

   - **The worst cell belongs to the graded end section, not to the
     transition.**  A reducer that doesn't change grading at all scores
     the same as the interpolated one.  A plain `Straight` with the
     outlet's spec is at most a few percent better.
   - So, in this setup, no transition can come within 10 % of the
     ungraded baseline: the pipes on either side are already below it.
   - Interpolating per station still helps slightly at 12 layers
     (0.261 → 0.268, 0.052 → 0.057).
   - **The use case** (pipe(0.1) → pipe(0.06), `first_cell` 1 mm,
     `nrad` 8 + 3, `nang` 8; `mprg` 0.667 → 0.737) gives min SICN 0.061
     at 6 layers and 0.092 at 12.  The ends as plain `Straight`s give
     0.063 / 0.069 and 0.094 / 0.119, so the transition costs about 3 %
     against its worse end.  The quality check passes.
   - 0019's 0.193 → 0.094 drop may have measured the same end-section
     effect.  Its setup was not recorded, so I can't tell.
   - **Question:** should the acceptance be "within 10 % of the worse
     end section's own min SICN" (met: 3 %), rather than of the
     ungraded baseline?  If yes, this task is done as implemented.

   **Design answer (2026-10-27, accepted by the user): yes.**  The
   reducer can only be judged against what it connects: the ends'
   grading sets the floor, and the transition costs ~3 % against the
   worse end, well inside 10 %.  Acceptance revised above.  The task is
   done as implemented: write *Outcome* (files, the table above, the use
   case numbers, suite counts), set it `done`.  0019's 0.193 → 0.094 drop
   needs no follow-up.

## Outcome

- **Done** (code in commit 4b27a72; Outcome written 2026-10-27 after
  the design answer).  The revised quality target is met.
- **Files:**
  - `hexmesh/assembly/signature.py`: `SwitchClass.grading_only`, the
    `check_port_pairs` rule and the module doc;
  - `hexmesh/assembly/fittings.py`: `Reducer.strategies = {0, 2}`, its
    docstring and `path` (geometric `mprg` interpolation at the radii's
    fractions); `_with_radii(…, mprgs)`, `_mprgs`;
  - tests: `tests/test_signature.py` (+9) and `tests/test_reducer.py`
    (+4);
  - `API.md`: the class table and note, the example message, and the
    `Reducer` entry.
- **Accept:**
  - **use case** (pipe(0.1) → pipe(0.06), `first_cell` 1 mm, `nrad`
    8 + 3, `nang` 8; `mprg` 0.667 → 0.737): validates, all-hex, meshed
    = predicted, quality check passes.  Min SICN 0.061 at 6 layers and
    0.092 at 12; the ends as plain `Straight`s give 0.063 / 0.069 and
    0.094 / 0.119.  The transition costs about 3 % against its worse
    end, inside the revised 10 % target;
  - **table cases:** every row's interpolated min SICN is within 6 % of
    the outlet-end `Straight` (the table under *Questions for design*;
    worst 0.468 vs. 0.496 at 1.0 → 1.0, 12 layers).  The worse end is at
    or below that column, so the 10 % target holds in every row;
  - **count difference:** still rejected with the class named (nang,
    nrad, nrad + mprg);
  - **`mbmp`:** rejected;
  - **classifier units:** pass.
- **Tests:** full suite 863 passed, 2 skipped (tee exactness), 0 failed
  at the implementing commit.  Re-checked 2026-10-27 on 8dac5b8:
  `test_signature.py` + `test_reducer.py`, 59 passed.
- **Measurements:** setup core + shell, `nrad` 6 / 4, `nang` 8,
  R 0.1 → 0.06, `dR` 0.02, length 0.2 (0019's exact setup was not
  recorded; baseline 0.266 here vs. 0.193 there).
- **Surprises:** the worst cell sits in the graded end section, not the
  transition, so interpolating per station barely changes min SICN
  (it helps slightly at 12 layers: 0.261 → 0.268, 0.052 → 0.057).
- **Follow-ups:** none proposed.  `Closure` stays at `{0}` (see *Agent
  notes*); per-station grading for it would need the target spec passed
  through `Sweep.path`, to do only if a case asks for it.
