# 0053 — Multi-layer wye: shells as offset level sets

- **Status:** ready (after 0056; start with the thin-shell probe, step 0)
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md)
- **Depends on:** 0051.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The same as 0052, for the wye.  It is also the vessel wall
through a bifurcation (decision 0018).

**Where.**  `hexmesh/assembly/wye.py` (`Skeleton`, `check`, `layout`),
`blocks.py`, kit, `API.md`, `README.md`.

**Do.**
0. **Thin-shell probe first** (design, 2026-10-29, after 0056's Q3).
   Projection moves wall nodes about 0.14 R through the knee, which folds
   thin cells.  A realistic pipe wall is about 0.04 R thick.  Before
   anything else, a 90° and a 120° wye with one shell of T/R = 0.04,
   with the wall and shell boundary projected.  Does it fold, and what
   is the min corner SJ?  If it folds (or SJ < 0.1), stop and report
   under *Questions for design*: the wye-layout redesign then comes
   before this task.
1. **Level sets:** generalise `Skeleton` to a wall at any distance
   (`to_wall(p, radius)`, `curve(points, radius)`); shell l's outer
   boundary is `dist = R + T_l`.
2. **Levels:** as 0052, one block level per shell around every ring
   block, vertices projected onto `dist = R + T_l` along the same rays as
   the level-1 vertices, with exact surfaces (0051).
3. **Crotch limit:** the daughters' offset surfaces merge in the crotch;
   check before GMSH that every shell level keeps the crotch blocks
   valid (`BlockLayout.corner_jacobians` > 0 at least), naming the angle
   and thickness.  Measure angle ∈ {30, 60, 90, 120}° × T/R ∈ {0.05,
   0.2, 0.5} × one and two shells, `nang` 4 and 8.  Report min corner SJ
   and max non-orthogonality, and propose a limit under *Questions for
   design*.
4. Remove the single-layer rejection (circular shells only).

**Accept.**
- Kit cases (fluid + wall; fluid + wall + insulation) at 60° and 90°:
  all-hex, meshed = predicted, continuous `interface_*` groups, wall
  and interface nodes on their level sets (0051's tolerance), port
  signatures class 0.
- Single-layer wye meshes unchanged (node coordinates to 1e-12).
- The quality table and a proposed limit.
- Full suite: no new failures.

**Out of scope.**  Unequal daughters; non-coplanar wyes.

## Agent notes

_None yet._

**Note from design (2026-10-29, decision 0029):** the wye's wall is
exact by **node projection**, not by OCC surfaces (task 0051 steps
5–8).  Build the shells the same way: each shell boundary gets the
projector at `dist = R + T_l`, applied in `Assembly.mesh()`.  The
crease-aware rule applies to every level, since offset surfaces crease
too.

## Questions for design

_None._

## Outcome

_Not done._
