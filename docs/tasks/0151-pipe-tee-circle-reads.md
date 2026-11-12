# 0151 — The pipe tee's circle reads through one helper: the shape-site cap to 0

- **Status:** done
- **Decision:** [0051](../decisions/0051-design-9-remaining-rows.md)
  (option A); [0042](../decisions/0042-road-to-1-0.md) exit criterion 1.
- **Depends on:** none.  Not alongside another task that edits
  `assembly/tee.py` (0145 may: coordinate).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  DESIGN §9's shape-switch row has 7 sites left, all in
`hexmesh/assembly/tee.py`, and each reads a circle's radius on the
pipe-tee path (`spec.core_shape.radius`, `self.branch.radius`).
Decision 0051 makes the pipe tee's circular shells a stated 1.0 limit;
the reads should go through `sections`, so the cap reaches 0 and the row
goes.

**Do.**
1. **One helper in `sections`** (name it: `circle_radius(spec)` or
   better).  It returns the core radius of a circular section and raises
   the existing coded error (`pipe_tee_needs_circle`, or a general code
   if one fits better: say which) for anything else.  The branch's
   `self.branch.radius` likewise (a `CircleShape`, on this path).
2. **The 7 sites use it.**  `_check_circle` may become a call to it.
3. **`SHAPE_SITES_CAP` = 0** in `tests/test_architecture.py`, its comment
   updated.  Then remove DESIGN §9's row in the same commit (decision
   0051 authorises it; this is the one DESIGN edit the task makes).
4. **Docs:** GUIDE and API state the limit as DESIGN §7.1 does: a pipe
   tee's shells are circular, and the branch's copy the main's.

**Accept.**
- The cap is 0.
- Every example mesh byte-identical.
- Tee tests unchanged; full suite: no new failures.

**Out of scope.**  Branch shells of their own (decision 0051 B; still
open, asked again in task 0150).

## Agent notes

- **The helper:** `sections.circle_radius(shape)`, taking a shape, not a
  spec, so the branch's `CircleShape` goes through it too.  Its error is
  a new general code, `shape_not_circular` (`SpecError`).  It isn't
  `pipe_tee_needs_circle` because `sections` sits below `assembly`
  (no `AssemblyError` there), and the wye reaches it too (through
  `thicknesses`).  Every caller checks its own rule first, with its own
  code and message (`_check_circle`, the wye's `wye_needs_circle`), so
  the helper is a backstop.  `_check_circle` stays as it is: it also
  checks the shells, and its message is the tee's.
- **Step 3's DESIGN edit is the design session's.**  The coding
  session never edits DESIGN.md (CLAUDE.md), so this task's commit has
  only `SHAPE_SITES_CAP = 0`.  I first wrote here that the row was
  already gone; it wasn't (my search missed its wording, "Type switches
  on shapes").  The design session removed it in 0e4aa24, 2026-11-12.

## Questions for design

## Outcome

Done 2026-11-12.

- `hexmesh/sections/__init__.py`: `circle_radius(shape)`, exported.
  `hexmesh/errors.py`: `shape_not_circular` (`SpecError`).
- `hexmesh/assembly/tee.py`: the 7 sites (`thicknesses`, `main_radii`,
  the branch shorthand, the run-length estimate, the no-run hint,
  `check`'s and `_declare`'s radii) read through it.
- `tests/test_architecture.py`: `SHAPE_SITES_CAP = 0`, comment updated;
  the detector finds no site.  `tests/test_tee.py`: +1 (the helper, and
  its error on a `RectShape`).
- Docs: GUIDE (the tee's limits) and API.md (*Shells*; the code
  catalogue) state DESIGN §7.1's two stated 1.0 limits.  The CHANGELOG
  line goes in with the 0.6.0 release commit (task 0146).
- **Meshes:** all 35 examples byte-identical to HEAD.
- **Tests:** architecture, tee, error and manifest tests 197 passed.
  The junction set (27 files, the user's choice after the full suite
  was stopped for low memory): 1886 passed, 1 skipped, 1 failed: the
  version test, run while task 0146's version bump was half written;
  it passes since.

