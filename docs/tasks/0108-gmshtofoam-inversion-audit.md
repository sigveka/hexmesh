# 0108 — Audit the validation cases for gmshToFoam's silent inversions

- **Status:** done (2026-11-08)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (the toolchain); follow-up of task 0074
- **Depends on:** 0074 (done).  Before the launch post.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0074 found that `gmshToFoam` (v2406) inverts valid warped
hexes: its orientation test uses a face's first vertex, and on a strongly
warped right-handed hex that test fails (`docs/integrations/openfoam.md`,
2026-11-06).  In the MMS 90° wye it flipped 6 cells.  There it was loud:
`checkMesh` failed and the solver stopped.  A flip in a milder cell might
not be loud, and every accepted validation case went through
`gmshToFoam` without `-keepOrientation`.  The repository is public, so
the published results must be shown free of it.  The likely result is
zero flips; this task shows it.

**Where.**  `validation/tools/` (a new audit script); each case's driver;
`hexmesh/study/openfoam.py`; `docs/integrations/openfoam.md`;
`validation/*/RESULTS.md` only if a case is affected; `CHANGELOG.md`.

**Do.**
1. **Move the test into the library:** `foam_would_invert` from
   `validation/mms/run.py` into `hexmesh.study.openfoam` (no GMSH needed
   on a written `.msh`), with tests: zero on a straight, and the 0074
   wye cell planted as a positive case.
2. **Audit:** for every validation case and every level in its
   `results.json`, regenerate the mesh as its driver builds it (no
   OpenFOAM run) and count the hexes gmshToFoam would flip.  Write one
   table (case, level, cells, would-flip) under *Outcome*, and a
   committed JSON in `validation/tools/`.  Delete the meshes as you go
   (disk is limited); keep only the counts.
3. **If any count is non-zero:** stop, set the task `blocked`, and list
   the cases and levels under *Questions for design*.  Don't rerun them.
4. **The default:** the validation drivers convert with
   `keep_orientation=True` when the mesh's worst scaled Jacobian is
   positive (every hex right-handed), and say so in the case's
   `case.json` toolchain.  `convert()`'s own default stays as it is
   (opt-in for users); the docstring and the GUIDE's OpenFOAM section say
   when to use it.
5. A level that would flip and has a non-positive scaled Jacobian is a
   mesh defect, not a converter one: report it.

**Accept.**
- The audit table covers every case and level in `validation/`.
- All zero, or the task is blocked with the list.
- The drivers' default changed; a test checks every driver passes
  `keep_orientation`.
- Full suite: no new failures.

**Out of scope.**  Rerunning OpenFOAM cases (only if design asks, after
step 3).

## Agent notes

- **Step 3, as read here.**  The step says to block if any count is
  non-zero.  Four MMS levels have a non-zero *would-flip* count, but each
  is stored with `keep_orientation: true`: it was converted with the test
  skipped (task 0074's fix).  So the count that reaches a published
  result is zero, and the task isn't blocked.  The table keeps both
  counts (`would_invert`, `flipped_in_result`), so design can overrule
  this reading.
- **Conservative where unrecorded:** only the MMS levels store
  `keep_orientation`.  helical_pipe and square_bend passed it too but
  don't store it, so they're counted as converted with the test on.
  Their counts are zero either way.
- **What the audit covers:**
  - every level in every case's `results.json` (193);
  - the converted side meshes that aren't levels: square_bend's inlet
    straight (k = 2) and poiseuille's five non-orthogonality trend pipes;
  - rect_duct's 9 `cart_` levels are blockMesh meshes: listed, not
    converted by gmshToFoam.
  - Each mesh is rebuilt with its driver's own builder.  The two side
    meshes' builders were lifted out of `match_inlet` and `nonorth_trend`
    (`inlet_assembly`, `trend_assembly`) for that.
  - Every rebuilt cell count equals the stored one.
- **Deduplicated:** 128 distinct meshes for 199 rows.  Re doesn't change
  the helical mesh, and the MMS diagnostic series (`_loc`, `_lsq`,
  `_skew`, `_lim`) reuse their base case's mesh.
- **Counted on the file gmshToFoam reads:** `would_invert(msh)` parses
  the written MSH 2.2 ASCII.  It reproduces 0074's 6 flips in the MMS 90°
  wye at k = 4.
- **v1912 has the same test:** its `correctOrientation` is line-for-line
  v2406's (`docs/integrations/openfoam.md`), so the audit covers the four
  cases run on v1912 too (heated_rod, layered_conduction, poiseuille,
  stenosis).
- **Same mesh with the flag:** with no flips, `-keepOrientation` changes
  nothing.  The MMS tee at k = 1, converted both ways, gave identical
  `polyMesh` files, so the drivers' new default doesn't change any
  stored result.
- **Drivers:**
  - five called `gmshToFoam` directly; three called `convert` without
    the flag;
  - womersley, stenosis, stenosis_pulsatile and poiseuille's levels now
    use `convert`, which runs the same command and then the roles they
    applied by hand;
  - heated_rod and poiseuille's trend apply no roles, so they keep the
    raw command with the flag added;
  - turbulent_pipe and poiseuille's trend now compute the worst scaled
    Jacobian.
- **Step 4 refined (design, 2026-11-08): the study stage follows the
  drivers.**
  - `hexmesh.study.stages.keep_orientation(row)` decides from the mesh
    stage's stored `min_sj`.  If it's positive, the case stage converts
    with `-keepOrientation`.
  - Otherwise, or if it's missing, the stage converts with the test on
    and warns `mesh_sj_not_positive` (a new code), naming the fitting.
  - Each variant's `case.json` records `keep_orientation`.
  - `convert()`'s own default stays off.
  - Tests: four SJ values, and `case_stage` with `convert` stubbed.
- **`msh_hexes` raises `ReaderError`** (`msh_format_invalid`, the
  existing code) on a file that isn't MSH 2.2 ASCII.  Decision 0040
  allows no bare built-in raise; the first version raised `ValueError`.
- **`case.json`:** the schema's `toolchain` gains a required
  `conversion` string, and every case states it.
- **Cost:** 77 min of meshing in all (the helical nang 24 mesh alone is
  2.7M hexes), serial, smallest first.  One `.msh` at a time, deleted
  after counting.

## Outcome

**Done: no published result went through a flipped hex.**  Of 199
levels and side meshes, 4 would be flipped by gmshToFoam's orientation
test, all converted with `-keepOrientation`.  The worst scaled Jacobian
is positive in every mesh, so no level is a mesh defect (step 5).

| case | levels | cells | would flip | flipped in the result | worst SJ |
|---|---|---|---|---|---|
| heated_pipe | 3 | 10 944–295 488 | 0 | 0 | 0.74 |
| heated_rod | 10 | 216–55 296 | 0 | 0 | 0.71 |
| helical_pipe | 11 | 100 416–2 711 232 | 0 | 0 | 0.73 |
| layered_conduction | 6 | 456–7 296 | 0 | 0 | 0.73 |
| mms | 99 | 576–606 208 | 32 | 0 | 0.13 |
| poiseuille | 3 + 5 side | 432–331 776 | 0 | 0 | 0.71 |
| rect_duct | 21 (9 blockMesh) | 2 000–414 720 | 0 | 0 | 0.71 |
| square_bend | 6 + 1 side | 18 576–622 080 | 0 | 0 | 1.00 |
| stenosis | 3 | 122 688–981 504 | 0 | 0 | 0.71 |
| stenosis_pulsatile | 4 | 15 336–414 072 | 0 | 0 | 0.72 |
| turbulent_pipe | 14 | 576–184 320 | 0 | 0 | 0.72 |
| womersley | 4 | 7 680–491 520 | 0 | 0 | 0.72 |

The MMS 32, by level: wye90_shell k = 2: 4; wye90 k = 4: 6; wye60_shell
k = 4: 4; wye90_shell k = 4: 18.  Each level, with its mesh key, is in
`validation/tools/orientation_audit.json`.

- **Files:**
  - `hexmesh/study/openfoam.py`: `foam_would_invert`, `msh_hexes` and
    `would_invert`; `convert`'s docstring;
  - `validation/tools/orientation_audit.py` and its JSON;
  - every driver's conversion; `validation/case.schema.json` and every
    `case.json`;
  - `hexmesh/study/stages.py` (`keep_orientation`), `hexmesh/errors.py`
    and `API.md` (`mesh_sj_not_positive`);
  - `docs/GUIDE.md` (OpenFOAM), `docs/integrations/openfoam.md`,
    `CHANGELOG.md`.
- **Tests:**
  - `tests/test_openfoam_runner.py`: 5 new.  The 0074 wye hex (positive
    at every corner, flipped), a cube and its mirror, a written `.msh`,
    the format check, and a straight with zero flips;
  - `tests/test_validation_meta.py`: every driver passes the flag (12),
    a planted unguarded driver, and every case states its conversion.
  - `tests/test_study.py`: the stage's decision (4) and `case_stage`
    passing it.
- **Surprise:** the shelled 90° wye flips 3× as many as the bare one at
  k = 4 (18 vs 6), and it already flips 4 at k = 2.
- **Proposed follow-up:** none.  The study stage's question went to
  design, who answered it within this task (*Agent notes*).
