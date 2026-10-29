# 0052 — Multi-layer tee: shells as offset levels of the junction

- **Status:** ready (after 0051)
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md)
- **Depends on:** 0051 (exact walls).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A pipe wall and insulation must run through a tee (CHT,
insulated plant lines, PCF files).

**Where.**  `hexmesh/assembly/tee.py` (`branch_spec`, `check`, `layout`,
`ports`), `blocks.py` (`face_vertices`, `face_patches` are already
multi-layer), kit, `API.md`, `README.md` limitations.

**Do.**
1. **Branch spec:** the main spec with the core radius replaced by
   `branch_radius` and the same shells (names, `dR`, `nrad`, `mprg`).
2. **Levels.**  The layout has levels 0 (inner square) and 1 (wall).
   Add a level per shell, l = 2 … L, at cumulative thickness T_l:
   - station corners on the main cylinder R + T_l; the top corners on
     the saddle of cylinders R + T_l and r + T_l, at the branch
     diagonals (the level-1 rule, with R → R + T_l, r → r + T_l);
   - the turning station Z at `R + T + 0.5 (r + T)` (T total), with its
     corners at branch radius r + T_l;
   - edges: arcs about the station centres, saddle splines of the offset
     cylinders, cylinder splines on R + T_l (as `on_cylinder`), branch
     arcs;
   - blocks: every level-1 ring block (S+, S−, Bb, the four turn blocks,
     and the slab and branch-run patches via `face_patches`) gets one
     block per shell between level l−1 and l, with that shell's material.
3. **Exact surfaces** for every shell boundary, as 0051 does for the
   wall.
4. **Limits:** check before GMSH that the outer shell fits (run length
   and turning station clear it), naming the limit.  Measure quality over
   r/R ∈ {0.3, 0.6, 0.9} × total thickness T/R ∈ {0.05, 0.2, 0.5} × one
   and two shells, `nang` 4 and 8.  Report min corner SJ and max
   non-orthogonality (task 0047's metrics).  Propose a limit under
   *Questions for design* (the two-tier policy of 0047), with numbers.
5. Remove the single-layer rejection; keep `rot = 0`, `n_outer = 4`,
   circular shells only (rectangular shells rejected, naming decision
   0026).

**Accept.**
- Kit cases (fluid + steel; fluid + steel + insulation), r/R 0.5 and
  0.9: all-hex, meshed = predicted, `interface_*` groups continuous
  through the junction (one group per material pair, covering main and
  branch), every wall and interface node on its analytic surface (0051's
  tolerance).
- Port signatures class 0 against the neighbouring straights.
- Single-layer tee meshes unchanged (node coordinates to 1e-12).
- The quality table and a proposed limit.
- Full suite: no new failures.

**Out of scope.**  Branch shells with their own thicknesses; laterals;
`stack_changes` inside the tee.

## Agent notes

_None yet._

**Note from design (2026-10-29, decision 0029):** junction walls may now
be made exact by **node projection** in `Assembly.mesh()` (task 0051
steps 5–8), not only by OCC surfaces.  For the tee's shell boundaries
(cylinders `R + T_l`, `r + T_l` and their saddle), either works.  Pinned
plates as in 0051's tee are fine for now; if 0051's step 8 drops the
plates in favour of projection, follow it.  Shell nodes must end on
their offset surfaces either way (the accept criteria are unchanged).

## Questions for design

_None._

## Outcome

_Not done._
