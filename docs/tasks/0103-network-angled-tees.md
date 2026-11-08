# 0103 — The network builder takes angled tees

- **Status:** done (3 questions for design)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md), amendment 2026-11-07, item 4
- **Depends on:** 0060 (`Tee(angle=…)`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The network builder (`hexmesh/interchange/build.py:513–520`)
rejects a tee whose branch isn't perpendicular, with
`tee_branch_angled`.  Since 0060 the assembly has `Tee(angle=…)`, so
plant networks with laterals (PCF `TEE` with an angled branch, Y-type
laterals) can be built.

**Where.**  `hexmesh/interchange/build.py`; the PCF fixtures and tests;
`hexmesh/errors.py`; `API.md`, `docs/GUIDE.md`, `CHANGELOG.md`.

**Do.**
1. **Build angled tees.**  Pass the measured branch angle to
   `Tee(angle=…)`, with the branch direction from the model's branch
   point.
   - The angle comes from geometry: `90° − tilt`, as computed today.
   - Below a tolerance (today's 1°), keep `angle=90`, so existing
     networks build exactly as before.
   - The run's other checks (symmetry, sizes, run along the pipe) are
     unchanged.
2. **Rejections come from the Tee.**  An angle and ratio the Tee can't
   mesh is rejected by the Tee's own quality tiers, with its hint (the
   0031 amendment, item 1), and with the PCF file and line (task 0096).
   `tee_branch_angled` stays in `CODES` only if something still raises
   it; otherwise remove it, and say so in CHANGELOG.
3. **Fixtures:** a PCF line with a 45° lateral at r/R 0.5 or more (which
   builds), and one with a 35° lateral at a small ratio (which is
   rejected, naming the angle and the smallest ratio that would pass).
4. **Docs:** the GUIDE's network section and API.md say angled tees are
   read, with the range from DESIGN §7.1.

**Accept.**
- Every existing PCF fixture builds the same assembly (`to_dict()`
  identical).
- The 45° fixture builds and meshes; the 35° small-ratio one is rejected
  with the Tee's code and hint and the file:line.
- `hexmesh manifest`'s support data is regenerated if it changes.
- Full suite: no new failures.

**Out of scope.**  Offset taps (0061) and the 30° layout (held).

## Agent notes

- **The angle:** `_tee_angle(branch, downstream)` in
  `hexmesh/interchange/build.py`, the degrees between the branch and the
  run's downstream direction.
  - It's 90 within `_TEE_SQUARE_TOL` = 1°, today's tolerance (the old
    `tilt = asin(|b·axis|)` ≤ 1° is the same test).
  - The `Tee` gets `angle=` beside the `toward=` it already had.
    `branch_length` is the PCF distance along the branch, as the `Tee`
    measures it.
  - Both names are private, per decision 0042's "no public surface to
    rename later".
- **Set-ons lean too.**  `_split_hosts` turns `TEE-SET-ON`/`OLET` into
  tees through `seton_run`, which sized the split with a 90° `Tee`.
  - It now uses the acute lean, `min(a, 180 − a)`: the host's flow
    direction isn't known at the split, and the acute lean's downstream
    reach is the longer.
  - A 45° set-on's run is longer than a square one's (tested).
- **What still raises `tee_branch_angled`:** a branch leaning upstream
  of the build (angle > 90°), which no `Tee` builds (`angle` ∈ (0, 90]).
  - The hint: build from the other end, `to_assembly(inlet=…)`.
  - Checked: an upstream-leaning set-on builds from the other end, by
    name (`A_100_end2`) or by point.
  - So the code is still raised, and stays (see *Questions*).
  - Its description in `CODES` and API.md now reads "leans upstream of
    the build direction".
- **Rejections come from the `Tee`, at `validate()`**, not at
  `to_assembly`.  That's where the quality tiers run; build, mesh and the
  commands call it.
  - The message is `fitting #1 Tee(…), f0.pcf:8: predicted corner scaled
    Jacobian 0.060 …`.  Its hint: "at angle 35°; r/R 0.876 or more
    reaches it there, or a larger angle".
  - `where.source` has the file, line 8 and record `TEE`.
- **Fixtures** (`tests/test_pcf_junctions.py`, `_lateral`):
  - **45° at r/R 0.6 builds and meshes:** 4 176 of 4 176 predicted, worst
    SJ 0.118, with the PREDICTED_SJ_WARN warning naming `f0.pcf:8`.
  - **r/R 0.5 isn't enough at 45°:** exactly 0.5 predicts SJ 0.100, just
    under the floor (0.501 needed).  DESIGN §7.1's "0.50" is rounded, so
    the building fixture uses 0.6.
  - **35° at r/R 0.5 is rejected** as above.
  - The old "60° rejected" case is now the 120° upstream lean.
- **Every existing PCF fixture builds the same `to_dict()`.**  All 23
  PCF strings defined at module level in the tests were built by HEAD (a
  worktree) and by this change, with nang 4 and the bore as the
  diameter.  All 23 are identical, 3 of them as the same rejection.  The
  inline `parametrize` records are covered by their tests, which pass.
- **The 1° snap is narrower than it looks** (not new: the old code did
  the same).
  - A tee drawn 0.2° off square is built square.  So its branch port
    lands off the file's point (1.4 mm at 400 mm; 3.5 mm at 0.5°,
    beyond the model tolerance).
  - A branch pipe drawn along the tilted branch then "changes direction
    without a fitting".
  - So the snap only helps a nearly square tee whose branch pipe is
    square.  See *Questions*.
- **Support matrix:** `hexmesh/agent/support.json` is unchanged;
  `test_the_stored_support_matrix_is_the_library_s` passes on a fresh
  probe.

## Questions for design

1. **`tee_branch_angled` stays, against step 2's "remove it".**
   - It's still raised, for the upstream lean.  But even if it weren't,
     0.5.0's *Stability* section (task 0115, released) says removing a
     code is breaking.
   - I kept it and narrowed its description.  Is the new meaning (an
     upstream lean, with an `inlet=` hint) right, or should that case
     have its own code?
2. **The 1° snap:** keep it, or build every leaning branch at its
   measured angle?
   - Without the snap, a tee drawn 0.2° off square would build as
     `Tee(angle=89.8)` and its tilted branch pipe would join.  Today it
     is rejected (port miss or kink), as it was before 0103.
   - The snap only changes something for a nearly square tee whose
     branch pipe is square.  Dropping it would change those assemblies
     (89.x instead of 90), against this task's "build exactly as
     before".
   - I kept it, as the task says.
3. **Upstream leans could be built automatically,** by choosing the root
   so the run flows the way each branch leans.  It isn't done: the root
   is chosen once for the network, and two laterals leaning opposite ways
   have no such root.  A follow-up if plant files show it.

## Outcome

- **Files:**
  - `hexmesh/interchange/build.py` (`_tee_angle`, the junction and
    `seton_run`);
  - `hexmesh/errors.py` (the description);
  - `tests/test_pcf_junctions.py`: one case changed, 6 tests added;
  - `API.md`, `docs/GUIDE.md` (the plant section, and the stale "Tee:
    perpendicular" limitation), `README.md` ("not read yet"),
    `CHANGELOG.md`.
- **Measured:**
  - 45° lateral, r/R 0.6: 4 176 cells, worst SJ 0.118;
  - 35° at r/R 0.5: predicted SJ 0.060, rejected;
  - 45° at r/R 0.5: predicted 0.100, rejected.
- **Tests:** `test_pcf_junctions.py` 33 passed; the full suite 3759 passed,
  15 skipped (2026-11-09).
