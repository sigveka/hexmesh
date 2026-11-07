# 0103 — The network builder takes angled tees

- **Status:** ready (after 0060)
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
