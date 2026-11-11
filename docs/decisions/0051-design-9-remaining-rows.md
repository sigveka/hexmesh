# 0051 — DESIGN §9's last rows: the pipe tee's circular shells, for 1.0

- **Status:** accepted (2026-11-11, by the user: "yes" to the recommendation, A)
- **Date:** 2026-11-11
- **Tasks:** 0151; 0150 waits on it

## Context

Decision 0042's first exit criterion: DESIGN §9 is empty at 1.0, or each
remaining row is accepted as permanent by a decision.  Three rows remain:

1. **"Readers sit in `io`".**  Task 0148 deprecates the old path, and
   task 0150 removes it.  Settled; nothing to decide here.
2. **"Tee limited to a perpendicular, centred branch with circular
   shells copied from the main".**  Half of this is stale: offsets
   (0061), any roll (0062), angled branches (laterals, 0122) and the
   branch's own radial grading (0131) are done.  What still holds:
   - a **pipe tee** (a circular main) takes **circular shells only**
     (`junction_shells_not_circular`).  A rectangular main isn't
     limited: `Tee` delegates it to a duct tap (decision 0033), a
     separate layout;
   - the branch's **shells copy the main's** (the same layers and
     thicknesses; `hexmesh/assembly/tee.py:45`, `:135`).
3. **The shape-switch cap: 7 sites.**  Checked 2026-11-11 with
   `tests/test_architecture.py`'s `shape_sites`: all 7 are in
   `assembly/tee.py`, and each reads `spec.core_shape.radius` or
   `self.branch.radius` on the pipe-tee path, after `_check_circle`.
   The sites are row 2's circular pipe tee, seen from the code.

So rows 2 and 3 are one question: is the pipe tee's circular-only shells,
with the branch copying them, a deviation to remove before 1.0, or a limit 1.0 states?

**What matters for 1.0** is only what can't be added later.  Each of
these could be added in 1.x without breaking anything: non-circular
shells on a pipe tee, or a branch with its own shells (an optional argument whose default
is today's copy).  None of them changes an existing description or name.

## Options

### A. Accept both as permanent 1.0 limits, and route the reads
- Row 2 becomes a documented limit: GUIDE and API say "a pipe tee's
  shells are circular, and the branch's copy the main's".  Non-circular
  shells are already rejected with a coded error.
- The 7 reads go through one helper in `sections` (say
  `circle_radius(spec)`, raising the existing coded error for other
  shapes).  The cap goes to **0**, and the row goes.
- Cost: a small task.  The extra features wait for users.

### B. Branch shells before 1.0
- The branch takes its own layer thicknesses (same materials and
  order).  Insulated branches of a different class are common on plant
  isometrics, so PCF would gain from it.
- Cost: a medium task across tee faces, the projection and PCF.  It
  delays 0.7.  It is additive, so it isn't needed for the freeze.

### C. Non-circular shells on pipe tees before 1.0
- A large task: the intersection curves (RESEARCH §3) are analytic for
  circles only.  No user has asked.

## Decision

**Recommendation: A.**  1.0 freezes names and formats, not features.
Both limits can be lifted in 1.x without breaking anything (B as an
optional `branch_shells=` whose default is today's copy, C as more
accepted shapes).  Holding 1.0 for them buys nothing the freeze needs.

**To settle:** whether branch shells (B) should still be planned for
early 1.x, given PCF's insulated branches.  If yes, the API review (task
0150) reserves the argument name, so that it reads naturally when it
arrives.

**Accepted (2026-11-11), A.**  The branch-shell question stays open; the
API review (task 0150) asks it again when it reaches the `Tee`'s
arguments.  Corrected before acceptance: the first draft said "the tee is
circular only", but a rectangular main is a duct tap (decision 0033).
The limit is the pipe tee's shells.

## Consequences

- **DESIGN §9:**
  - the tee row is removed;
  - the cap row is removed when the task brings the cap to 0;
  - DESIGN §7.1 gains one sentence on the circular tee and the copied
    branch shells, as a stated limit.
- **Tasks:**
  - one small task (routing the reads, the cap to 0, the docs);
  - 0150 depends on this decision.
- **Future expansions:**
  - pipe-in-pipe and multi-core sections (0035) need non-circular
    junctions eventually; A neither helps nor blocks them;
  - vascular networks (0018) use circular branches.

## Verified vs. assumed

- **Checked (2026-11-11):**
  - the 7 sites and their file;
  - the "branch shells copy the main's" comment and the spec helper in
    `tee.py`;
  - `_check_circle` and its two coded errors, and the duct-tap
    delegation (`tee.py`, module notes);
  - the done tasks listed under row 2.
- **Assumed:** that B is additive as an optional argument.  The API
  review should confirm that no current name blocks it.
