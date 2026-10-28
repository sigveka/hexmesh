# 0053 — Multi-layer wye: shells as offset level sets

- **Status:** ready (after 0051; can run alongside 0052)
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md)
- **Depends on:** 0051.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The same as 0052, for the wye.  It is also the vessel wall
through a bifurcation (decision 0018).

**Where.**  `hexmesh/assembly/wye.py` (`Skeleton`, `check`, `layout`),
`blocks.py`, kit, `API.md`, `README.md`.

**Do.**
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

## Questions for design

_None._

## Outcome

_Not done._
