# 0151 — The pipe tee's circle reads through one helper: the shape-site cap to 0

- **Status:** ready
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

## Questions for design

## Outcome
