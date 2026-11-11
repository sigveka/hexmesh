# 0131 — A tee branch with its own radial grading (and the Reducer pattern documented)

- **Status:** done
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md) (amendment 2026-11-10); [0016](../decisions/0016-class-1-granularity-and-grading-changes.md) (grading-only changes in sweeps)
- **Depends on:** none (task 0027, done, gives the per-station grading).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A tee's branch copies the main's `nrad` and `mprg`
(`hexmesh/assembly/tee.py`, `branch_spec`), so its wall cell scales with
r/R.  A `first_cell` (y+) target set on the main is missed on every
branch: at r/R 0.5 the branch's wall cell is about half the main's.
Decision 0028's amendment: the branch port may carry its own core grading.

**Where.**  `hexmesh/assembly/tee.py`, the sweep machinery task 0027
used (`fittings._with_radii`, `_mprgs`), `API.md`, `docs/GUIDE.md`,
`CHANGELOG.md`, the agent schema (a new field), `tests/`.

**Do.**
1. **Document today's pattern (any time, first).**
   - GUIDE: "a branch with its own wall cell": a grading-only `Reducer`
     straight after the branch (same radius, the branch spec with its own
     `first_cell`), with a short example.  Check it builds; if a
     same-radius `Reducer` is rejected, say so under *Agent notes* and
     document the smallest working form instead.
   - GUIDE's fittings table says `Reducer`: "Only radii may change".
     Task 0027 made grading-only changes legal: correct the line.
2. **The field.**  `Tee(…, branch_first_cell=None, branch_mprg=None)`
   (names may be refined; at most one of the two): the branch port's core
   grading.  Interpolated per station along the branch run, from the
   main's grading at the turning station to the given one at the port,
   as `Reducer` interpolates (task 0027).  Counts and shells unchanged.
   - Circular branches on O-H mains first.  Duct taps and H mains: reject
     with a coded error unless it falls out for free; say which under
     *Agent notes*.
   - `refined(k)`: as for a spec's `first_cell` (API.md): the resolved
     `mprg` nests.
   - The branch port's spec (`asm[...]`, `ports`) carries the new grading,
     so the next fitting matches it.
3. **Measure:** min SJ and non-orthogonality of the tee, against today's,
   for r/R 0.3, 0.5, 0.8 and a branch `first_cell` of 0.5×, 1× and 2× the
   main's wall cell, at `n_branch` 3 and 6.  If the branch run's
   interpolation worsens the tee beyond decision 0016's 10 % target,
   report the case and the `n_branch` that recovers it; propose a hint
   (e.g. a minimum `n_branch`) under *Questions for design*, don't set a
   limit.
4. **Tests:** the branch port's wall cell equals `branch_first_cell` (to
   1e-9 relative); omitting the field gives today's mesh byte-identically;
   a following `Straight` with the branch spec connects; the field
   round-trips through `to_dict`/`from_dict` and the JSON schema.

**Accept.**
- Steps 1–4; meshes without the field byte-identical; full suite: no new
  failures.

**Out of scope.**  Different `nrad`/`nang` in a branch (decision 0003);
the wye; shell grading.

## Agent notes

- **Step 1:** a same-radius `Reducer` after the branch builds and meshes
  (main R 0.05, `first_cell` 5e-4, nrad 10; branch r 0.025 with its own
  `first_cell` 5e-4: 15 104 cells).  Documented as is.
- **Names:** `branch_first_cell` (an input, `input=True`) resolves in
  `add()` to `branch_mprg`, stored; the field is then cleared, so
  `to_dict()` holds `branch_mprg` only, as a spec stores its resolved
  `mprg`.  Both given: `grading_args_conflict` (the spec's code).
- **Interpolation:** the branch run is one block Z → E.  Z keeps the
  main's grading and E is declared with the port spec's,
  `own_grading=True` (the switch's precedent, task 0085).  The run's
  inner stations are then gmsh's transfinite blend: the wall cell changes
  linearly in position from Z to E, not `mprg` geometrically per station
  as `Reducer`.  Measured: at r/R 0.5 with 1e-3 it is 1.0e-3, 6.11e-4,
  4.07e-4, then the main's at Z (n_branch 3).  Per-station faces would
  add blocks to every graded tee; the blend is monotone and the quality
  is unchanged (step 3), so I kept it.
- **Strategies:** a grading change at the branch port is class 2 to
  `check_port_pairs`.  `Tee.strategies` became per port pair,
  `({0, 1}, {0, 1, 2})`: grading-only class 2 on the branch pair, as
  `Reducer` declares (`check_port_pairs` already rejects class 2 beyond
  grading).  DESIGN A4's "declare the classes" holds.
- **Rejected, not free:** duct taps (their branch is built by the tap
  template) and equal tees (the cube; branch spec is the main's):
  `branch_grading_unsupported`, hinting at the grading-only `Reducer`.
  An H main is a duct tap here.
- **Step 4 tolerance:** the task asks for the port's wall cell to equal
  `branch_first_cell` to 1e-9 relative.  The meshed node positions don't
  reach that anywhere: a plain pipe's own `first_cell` 5e-4 meshes to
  4.99999974e-4 (5e-8), and the tee's port, built in a rotated frame,
  differs from that pipe's by 1.8e-7.  The test checks the grading to
  1e-9 (bit-identical to `PipeSpec.core(first_cell=…)`'s `mprg`) and
  the meshed cell to 1e-6.
- **Agent:** `support.json` regenerated (the Tee repr has the new
  fields).  `advise`'s density table sets every spec's grading, so
  `apply` drops `branch_mprg` with the tap's derived fields.
- **Measuring:** in the main's O-H face the mid-arc (largest wall cell)
  is along the frame's `right` (corners at 45°); the measurement takes
  the largest wall cell over the radial spokes of a station plane.

## Questions for design

## Design review (2026-11-11, the design session)

- **Blend:** the branch run is one block, with the wall cell blended linearly in position by gmsh's transfinite interpolation. It replaces the per-station geometric interpolation that decision 0028's amendment implied. Gmsh still meshes (decision 0046), the blend is monotone, and quality is unchanged in all 18 cases. User docs should say the branch's grading is reached at the branch port, blended along the branch run, and that a grading-only Reducer after it gives a geometric change instead.
- **Strategies:** per port pair, ({0,1}, {0,1,2}), accepted, as Reducer declares class 2 (DESIGN A4).
- **Tolerance:** the grading is bit-identical to `PipeSpec.core(first_cell=…)`, and the meshed wall cell is checked to 1e-6, accepted. Meshed node positions carry about 5e-8 relative error even on a plain pipe, so 1e-9 can't hold there.
- **advise (a candidate follow-up, not a block):** `apply` drops `branch_mprg`, consistent with the table setting every grading. But after advise the branch carries the main's wall grading, so its wall cell is no longer sized for the branch radius. A later step could have advise derive `branch_first_cell` from the branch radius and the same y+ target. Please name this under Proposed follow-ups.

## Outcome

**Done 2026-11-11.**

- **Field:** `Tee(branch_first_cell=…)` / `branch_mprg=`; stored as
  `branch_mprg`; `refined(k)` k-th root; JSON schema picks it up from the
  param.  Equal tees and duct taps: `branch_grading_unsupported`.
- **Step 3** (main R 0.05, nrad 10, `first_cell` 5e-4; branch wall cell
  0.5×, 1×, 2× today's; n_branch 3 and 6): the port's wall cell hits the
  target in all 18; the tee's min SJ and max non-orthogonality equal
  today's in all 18: r/R 0.3: 0.1500 / 74.86°; 0.5: 0.2577 / 64.24°;
  0.8: 0.4415 / 49.86° (the junction core sets them).  No `n_branch`
  hint needed.
- **Meshes without the field:** 31 of 31 examples byte-identical (without
  `$Comments`).
- **Files:** `hexmesh/assembly/tee.py`, `intent.py` (refine),
  `hexmesh/errors.py` (code), `hexmesh/agent/advise.py`, `support.json`
  (regenerated), API.md, GUIDE (step 1 pattern, the `Reducer` row, the
  field), CHANGELOG, `tests/test_tee_branch_grading.py` (11 cases),
  `tests/test_signature.py` (strategies).
- **Tests:** full suite 4097 passed, 15 skipped, 1 xfailed (4086 + 11).
- **Proposed follow-ups:** `advise` derives `branch_first_cell` from the
  branch radius and the same y+ target, so a branch's wall cell stays
  sized for it after `apply` (today `apply` drops `branch_mprg` and the
  branch takes the main's grading; design review above).
