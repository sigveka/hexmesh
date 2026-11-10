# 0122 — Equal tees and equal laterals: the oriented junction cube behind `Tee`

- **Status:** ready
- **Decision:** [0043 — The wye-layout redesign](../decisions/0043-wye-layout-redesign.md), amendment 2026-11-10; [0031](../decisions/0031-general-branch-junctions.md) (one public `Tee`; amendment 2026-11-10); [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (gmsh meshes)
- **Depends on:** 0118 (done): `hexmesh/assembly/_cube_probe.py`, the
  orientation search and the harness.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Equal tees are a 1.0 criterion (decision 0042), and today
`Tee(branch_radius = R)` raises `equal_tee_unsupported`.  Task 0118
measured the oriented cube (Bošnjak et al. 2024) on gmsh's transfinite
path: the equal tee builds with min SJ 0.577 and no warning, the equal
lateral at 45° builds with a warning (0.134).  The crease chord misses
0043's 1 % R gate (3.7 % at `nang` 8); that miss is accepted and stated,
not hidden.

**Where.**  A layout module beside `tee.py` and `wye.py` (e.g.
`hexmesh/assembly/cube.py`, private names), `tee.py` (the routing),
`limits.py`, `junction_quality.py` (its tiers), `errors.py` (codes),
`docs/GUIDE.md`, `API.md`, the gallery, `tests/`.  `_cube_probe.py`
is folded in and removed; `_wye_probe.py` stays.

**Do.**
1. **Route** `Tee` with r = R (the existing relative tolerance, or one
   added to `limits.py` and named) to the cube layout.  `offset` must be
   0 at r = R (|h| + r < R can't hold); keep the existing error for it.
   Roll (task 0062) works as for any tee.  Remove
   `equal_tee_unsupported`; the τ < r/R < 1 error's hint keeps "an equal
   tee, or a branch radius ≤ τ·R".
2. **The layout** as 0118 built it: centre hex, a ported side block per
   pipe sweeping to its station, unported sides on the wall; cube
   corners on the wall along the diagonals; shells as offset levels;
   wall projection onto the tube union (decision 0029) with the
   existing `projection_report`; second order as other projected
   junctions.  Orientation by the paper's heuristic; `hub` and `station`
   fixed per angle from 0118's tuning, or tuned before meshing by
   predicted SJ, deterministically (same description, same mesh).
3. **The angle range, measured:** equal laterals at 90°, 75°, 60°, 45°,
   40°, 35°, 30° (`nang` 8, single and shelled).  Set the warn and
   error tiers from the predicted SJ (0.3 warn, 0.1 build: unchanged
   limits) and the folds, and state the smallest angle that builds.  An
   angle that doesn't build is an error before gmsh with a coded hint.
4. **Report per angle,** in the GUIDE and the docstring: min SJ,
   non-orthogonality and the crease chord (% R) at `nang` 8 and 16, so a
   user sees the crease error before meshing.
5. **Gallery:** an equal tee and an equal 45° lateral, with their
   numbers.
6. **Propose DESIGN §7.2 wording** ("Equal tee: the oriented cube")
   under *Questions for design*; design writes it into DESIGN.

**Accept.**
- `Tee(branch_radius = R)` builds at 90° with min SJ ≥ 0.3 and no
  inverted cells, single and shelled; ports class-0; `checkMesh` v2406
  passes on the equal tee (Docker).
- The lateral range and tiers set from step 3's numbers, in
  `limits.py` with their source.
- Every new error and warning coded, with a hint (task 0106's rules).
- No hexmesh-written elements (decision 0046): every element from gmsh.
- Full suite: no new failures; the gallery's other meshes byte-identical.
- Meshes and scratch output deleted; numbers in the task and the JSON.

**Out of scope.**  The crease fix (decision 0045, proposed); wyes
(unchanged); unequal daughters; crosses (noted in 0118: they would fit,
not built); B3 (task 0124).

## Agent notes

## Questions for design

## Outcome
