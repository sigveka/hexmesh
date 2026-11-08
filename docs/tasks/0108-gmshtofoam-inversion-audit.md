# 0108 — Audit the validation cases for gmshToFoam's silent inversions

- **Status:** ready
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
