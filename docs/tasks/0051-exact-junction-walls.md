# 0051 — Exact junction walls (tee and wye)

- **Status:** done
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md) (item 1); [0029 — Wall exactness by node projection](../decisions/0029-wall-exactness-by-node-projection.md); DESIGN §6
- **Depends on:** —  (0052 and 0053 build on it)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  DESIGN's deviations table: "Tee wall faces (junction and run
slabs) are OCC-filled surfaces, so interior wall nodes lie 2–5 % of R
off the true cylinders".  The wye's faces are built the same way.  Shells
of 5–10 % of R would be squeezed or folded on such faces (decision 0028),
and the flow sees a wrong wall, as in Poiseuille before task 0025.

**Where.**  `hexmesh/assembly/blocks.py` (`BlockLayout.realise`, how faces
are filled), `tee.py`, `wye.py`, `sweep._ruled` (task 0025's ruled
surfaces), the wall-exactness check of the conformance kit (task 0025),
`docs/integrations/gmsh.md`.

**Do.**
1. **Measure first:** for every wall face of the tee (approach and
   departure slabs, junction blocks, branch) and the wye, the maximum
   distance of interior mesh nodes from the analytic surface (tee:
   cylinder R, cylinder r; wye: `Skeleton.distance = R`), at `nang` 4
   and 8 and two r/R (tee) or angles (wye).  Table in *Agent notes*.
2. **Make them exact.**  Each wall face must carry its interior nodes on
   the analytic surface.  Options, cheapest first; measure each:
   - faces between two exact boundary curves that are rulings of the
     surface (the run slabs' cylinder patches): ruled surfaces, as in
     task 0025;
   - other faces: a B-spline surface interpolating analytic points
     (enough samples that the nodes are within tolerance), or an exact
     OCC primitive face (a cylinder) trimmed by the boundary curves;
   - for the wye's level set, interpolate points projected with
     `Skeleton.to_wall`.

   Record what OCC does with each in `docs/integrations/gmsh.md`.
3. Keep interior (non-wall) faces as they are unless they cause trouble.
4. Extend the kit's wall-exactness check to `Tee` and `Wye` cases.

**Accept.**
- Every tee and wye wall node within **1e-3 R** of its analytic surface
  (or say what limits it, with numbers) in every kit junction case.
- Cell counts, groups and all-hex unchanged; quality reported before and
  after (min SICN, min corner SJ).
- Build time of the tee and wye kit cases before and after (idle
  machine); state the cost.
- DESIGN's tee wall row can be removed (design does it).
- Full suite: no new failures.

**Out of scope.**  Multi-layer junctions (0052, 0053).

## Agent notes

**Step 1: measured before** (2026-10-29; largest distance of any node on a
junction wall face from the analytic wall, × R; kit geometry, R = 0.1,
`nrad` 3).  Tee: the union of the main cylinder and the branch cylinder
(z ≥ 0).  Wye: `Skeleton.distance` − R.  Curve nodes are on the wall;
the maximum is always at interior nodes.  Faces whose sides are two
arcs and two lines (run-slab bottoms, branch run) are ruled and exact.

| case | `nang` 4 | `nang` 8 | worst faces (`nang` 4) |
|---|---|---|---|
| tee r/R 0.5 | 0.032 | 0.032 | junction sides S± 0.032; run-slab sides 0.026; branch turning faces 0.004–0.013; run-slab tops 0.006 |
| tee r/R 0.9 | 0.022 | 0.022 | branch turning faces 0.006–0.022; run-slab sides 0.005; S± 0.004 |
| wye 60° | 0.149 | 0.156 | hub top/bottom 0.149; crotch 0.090; daughter top/bottom 0.049; daughter outer 0.016 |
| wye 90° | 0.113 | 0.126 | hub top/bottom 0.113; daughter top/bottom 0.110; daughter outer 0.063; crotch 0.004 |

The deviation doesn't fall with `nang`: it is the surface's, not the
mesh's.  Every inexact tee face lies on one cylinder; the wye's faces
cross several pieces of the canal surface (inlet cylinder, knee sphere,
daughter cylinders) and the crotch face contains the crease.

**Step 2: methods tried** (details and OCC behaviour in
`docs/integrations/gmsh.md`, "Wall surfaces through analytic points").
Every method starts from a Coons grid between the face's four edges,
sampled from the layout's edge geometry (no synchronize), and projects
it onto the wall.
1. **Interpolating bicubic B-spline surface, trimmed by the loop**
   (`addBSplineSurface(wireTags, wire3D=True)`).  Exact (1e-7 R on an
   isolated cylinder patch), but OCC bounds the face by new projected
   curves, so it is not conformal with its neighbours ("Incompatible
   surface … in transfinite volume").  Rejected.
2. **Exact trimmed cylinder** (`addTrimmedSurface`): the same wire
   projection, so the same new curves; not pursued.
3. **Plate filling of the loop pinned to the projected interior points**
   (7 × 7, `tol3d` 1e-6 × face size).  Keeps the loop's curves.
   - Tee: ≤ 3.0e-4 R at every case.  **Used** (`BlockLayout.wall`,
     `_wall_surface`; `tee.tee_wall` projects onto the cylinder union).
   - Wye: erratic, 1–46 % of R depending on settings (table in
     `gmsh.md`).  **Not used**: the wye keeps its Stretch filling.
4. **Mesh-node projection** (not one of 0028's methods; prototype only,
   in this session's scratchpad, not in the code): after `generate(2)`,
   move every node of the junction's wall curves and faces onto the wall
   with `setNode`, then `generate(3)`.  Results under *Questions for
   design*.

**Steps 5–8 (2026-10-29): node projection.**

- **Interface (step 5).**  A projector is a callable `points (n, 3) →
  points (n, 3)` (`hexmesh/assembly/projection.py`).
  - `BlockLayout.walls` maps a level to its projector.  `realise` puts
    the faces of each listed level in `FillResult.projections`, as
    `(projector, surfaces)`.
  - `Assembly.mesh()` runs `generate(2)`, then `_project_walls`: every
    node on those surfaces, their curves and their points is moved with
    `setNode`.  Then `generate(3)`; `mesh(2)` projects too.
  - The tee lists levels 1…L (walls and shell boundaries, ready for
    0053); the wye lists level 1.  To give the crotch faces a level, the
    wye's `F`/`W` vertex ids gained one (`("W", 1, k)`).
  - **Shared nodes are a no-op:** port-curve nodes move ≤ 1.5e-15 R
    (`test_shared_nodes_do_not_move`).
- **Projector (step 6), refined.**  `TubeUnion`: a union of tubes about
  lines or rays (half-sphere caps at the ray origins).  So it is the
  canal surface, knee sphere included.
  - `nearest()` is the projector step 6 asked for: candidates on each
    tube, on each pair's intersection curve (Gauss–Newton) and the triple
    point; those inside another tube are dropped; the nearest wins.  At a
    tie between two flanks it goes onto the crease.
  - **Nearest-point projection folds the 60° wye** (min corner SJ
    −0.04 at `nang` 8, −0.57 at 16).  The Stretch-filled crotch face is
    a sharper V than the wall.  Just inside the crease, nearest points
    run backwards across the mirror plane
    (`test_crease_keeps_order`).
  - **So the projector maps along a smoothed normal instead.**  The
    direction is the gradient of a soft minimum of the tubes' signed
    distances (width `TubeUnion.SOFT` = 2 R); the result is the wall
    point on that line nearest the node.  Away from creases, that is the nearest point.
    Across one, rows of nodes stay in order on both flanks.  No folded
    cells at any measured case.
  - **The width matters for narrow wyes.**  The full suite found the 30°
    wye folded (`test_wye::test_all_hex_valid_mesh[30]`).  Min corner SJ
    at `nang` 8 / 16:

    | width | 30° | 35° | 40° | 45° | 50° | 55° |
    |---|---|---|---|---|---|---|
    | 0.25 R | −0.39 / … | −0.38 | −0.29 | −0.34 | −0.39 | — |
    | 0.5 R | −0.07 / −0.25 | −0.24 / −0.22 | −0.29 / −0.32 | 0.12 / −0.37 | 0.16 / 0.16 | 0.18 / 0.18 |
    | 1 R | −0.18 / −0.21 | 0.07 / −0.27 | 0.11 / 0.11 | 0.13 / 0.13 | 0.16 / 0.16 | 0.18 / 0.18 |
    | **2 R** | 0.07 / 0.06 | 0.09 / 0.09 | 0.11 / 0.11 | 0.13 / 0.13 | 0.16 / 0.16 | 0.18 / 0.18 |
    | 4 R | 0.07 / 0.07 | 0.09 / 0.09 | 0.11 / 0.11 | 0.13 / 0.13 | 0.16 / 0.16 | 0.18 / 0.18 |
    | no projection | 0.065 | | | 0.133 | | |

    2 R and 4 R match the unprojected mesh's quality from 30° to 120°;
    2 R is used.  The longer the crease, the further the filled crotch
    face strays from the wall and the wider the blend has to be.
    (0.25 R row: `nang` 8 only.)
  - **Moves grow as the angle narrows:** 0.77 R at 30°, 0.60 R at 35°,
    0.47 R at 40°, 0.38 R at 45°, 0.18 R at 60°, 0.13 R at 90° and 120°.
  - The tee uses the same class (main line plus branch ray).
- **Move limit (step 7).**  `limits.WALL_PROJECTION_MAX_MOVE = 4.0`.
  - Measured in local cell heights: a node's shortest hex edge to a node
    on no wall, checked after `generate(3)`.  Moved nodes are matched by
    position, since `generate(3)` renumbers them (`gmsh.md`).
  - My first measure, the shortest wall-mesh edge, grew with `nang` (2.6
    at 16) while nothing folded.
  - By cell height the ratio doesn't depend on `nang`, but does on
    `nrad`.  See the tables below and *Outcome*, "For design".
- **Tee plates kept (step 8).**  Stretch plus projection puts the tee's
  nodes on the wall to rounding, with the same quality.  But the nodes
  sit up to 1.3 % of R (r/R 0.5) and 0.6 % (0.9) from the pinned-plate
  nodes, sliding tangentially; about 13 % of all nodes differ by more
  than 1e-6 R.  That fails "the same nodes to 1e-6 R", so the plates
  stay.  Without them a tee builds about 0.4 s faster (1.7 → 1.3 s at
  r/R 0.5, `nang` 8).

**Measurements** (`Straight` – junction – two `Straight`s, R = 0.1,
`nrad` 3, `n_layers` defaults; scratchpad `proj_measure.py`).  "dev":
largest node distance from the analytic wall.  "move": largest
projection move.  "ratio": move ÷ local cell height.  SJ: the junction's
min corner scaled Jacobian.

| case | `nang` | dev before | dev after | move | ratio | SJ before → after | min SICN |
|---|---|---|---|---|---|---|---|
| wye 60° | 4 | 0.15 R | 1e-15 R | 0.180 R | 0.77 | 0.211 → 0.211 | 0.173 → 0.173 |
| wye 60° | 8 | 0.16 R | 1e-15 R | 0.180 R | 0.87 | 0.211 → 0.211 | 0.110 → 0.110 |
| wye 60° | 16 | 0.16 R | 1e-15 R | 0.180 R | 0.87 | 0.211 → 0.211 | 0.059 → 0.059 |
| wye 90° | 4 | 0.11 R | 1e-15 R | 0.121 R | 0.70 | 0.258 → 0.236 | 0.168 → 0.151 |
| wye 90° | 8 | 0.13 R | 1e-15 R | 0.129 R | 0.70 | 0.258 → 0.233 | 0.122 → 0.122 |
| wye 90° | 16 | 0.13 R | 1e-15 R | 0.138 R | 0.74 | 0.251 → 0.227 | 0.070 → 0.070 |
| wye 120° | 4–16 | — | 1e-15 R | 0.127–0.138 R | 0.78 | 0.155 → 0.149–0.155 | unchanged |
| tee 0.5, plates | 4–32 | ≤ 1.2e-3 R | 6e-16 R | ≤ 0.0012 R | ≤ 0.008 | 0.258 → 0.258 | unchanged |
| tee 0.9, plates | 4–32 | ≤ 4.1e-4 R | 6e-16 R | ≤ 0.0004 R | ≤ 0.003 | 0.509 → 0.509 | unchanged |
| tee 0.5, Stretch | 4–32 | 3.2–3.4 % R | 6e-16 R | 0.034 R | ≤ 0.15 | 0.258 → 0.258 | unchanged |
| tee 0.9, Stretch | 4–32 | 2.2 % R | 6e-16 R | 0.022 R | 0.13 | 0.509 → 0.509 | unchanged |

Wye rows at width 2 R; the cell-height ratios and the `nrad` table below
were measured at 0.25 R (moves differ by under 0.01 R).  The min SICN
falls with `nang` before projection too (the hub's back
corners, task 0030).

**Move ratio against `nrad`** (`nang` 8; no folds, SJ as above):

| `nrad` | wye 60° | wye 90° |
|---|---|---|
| 3 | 0.86 | 0.68 |
| 6 | 1.70 | 1.43 |
| 9 | 2.54 | 2.28 |
| 9, `mprg` 1.3 | 1.12 | 0.90 |

At `nrad` 9 the 90° wye's min SICN drops from 0.067 to 0.023, and its
SJ from 0.258 to 0.226; nothing inverts.  The transfinite volume
re-interpolates the whole block from its projected faces, so a move is
spread across the block, not taken by the first cell.

**Crotch chord error** (step 8): the largest distance from the analytic
wall of the wall quads' centres and edge midpoints near the crease (both
daughter flanks within 0.25 R of each other, past the hub, away from the
inlet tube).

| `nang` | wye 60°, before | wye 60°, after | wye 90°, before | wye 90°, after |
|---|---|---|---|---|
| 4 | 12.6 % R | 2.8 % R | 2.1 % R | 3.2 % R |
| 8 | 14.4 % R | **0.85 % R** | 5.0 % R | **0.88 % R** |
| 16 | 15.7 % R | 0.23 % R | 5.4 % R | 0.24 % R |

Width 2 R (at 0.25 R: 2.9 / 0.95 / 0.26 % for 60°, and 0.07 / 0.06 % at
`nang` 32).  Second order in `nang`, under the 1 % threshold at `nang`
8.  120°: 2.0 / 0.52 / 0.13 %.

**Elsewhere** on the wye wall the chord error stays at **10 % of R (60°)
and 8 % (90°) at every `nang`**.  These are the hub's spherical cap at
the outer knees: axial edges 0.94 R long, set by `n_run`, not `nang`.

## Questions for design

**Q1. The wye's wall can't be made exact by an OCC surface; may it be
done on the mesh nodes instead?**

None of 0028's methods works for the wye:
- plate and B-spline fillings know only the boundary (11–16 % of R);
- a plate pinned to wall points is erratic (best 1–9 %, worst 46 %);
- a trimmed exact surface (B-spline through wall points, or a
  primitive) gets new boundary curves from OCC, so it isn't conformal;
- one layer per face isn't possible: every ring face has `nang` and
  `n_split` divisions.

What does work, measured on a prototype, is **mesh-node projection**:
`generate(2)`, then each node of the junction's wall curves and faces
moved onto the wall (`setNode`), then `generate(3)` (transfinite volumes
interpolate from the moved surface nodes).

| case | before (× R) | after (× R) | largest move | junction min SICN before → after |
|---|---|---|---|---|
| wye 90°, `nang` 4 | 0.113 | 1e-15 | 0.113 | 0.168 → 0.168 |
| wye 90°, `nang` 8 | 0.126 | 1e-15 | 0.126 | 0.122 → 0.122 |
| wye 60°, `nang` 4 | 0.149 | 1e-15 | **3.8** | 0.173 → **−0.815** |
| wye 60°, `nang` 8 | 0.156 | 1e-15 | **4.0** | 0.110 → **−0.643** |
| tee r/R 0.5, on the plates | 3.0e-4 | 7e-7 | 3e-4 | 0.243 → 0.243 |

- **At 60° the projection itself is wrong, not the method.**  A node
  just inside the crotch crease is equidistant from both daughters.
  `Skeleton.to_wall` marches from its nearest axis point along the ray
  through the node; that ray crosses the other daughter, so the node
  lands on the far wall.  A crease-aware projection is needed: the
  nearest point of the canal surface, with the crease as its own case.
- **Consequences, for design to weigh.**
  - Wall exactness would live in the mesh step, not in the geometry.
    Every path that meshes must apply it (`Assembly.mesh`, and anything
    calling `generate` itself).
  - The OCC surface stays inexact, so CAD export and `getValue`
    queries see the old wall.
  - Nodes lose their parametric coordinates (`setNode` with none).
  - It would fit DESIGN §6's "exactness lives in curves and nodes"
    literally, but not its "a filled surface may carry interior mesh
    nodes only where it is the exact surface".
  - It would also make the tee exact to 1e-6 instead of 3e-4, and make
    the wye's shells (0053) follow the offset level sets with the same
    projector at `R + T`.
- **Alternatives:**
  - a wye topology whose faces each lie on one smooth piece (split at
    the crease and at the cylinder/sphere seams), so pinned plates or
    trimmed primitives have a chance;
  - or accept the wye's walls as they are, with a deviation row, and
    build 0053 on node projection only for shells.

**Proposed:** node projection for junction walls (wye; optionally tee
too), with a crease-aware projector, as a new 0051 step or a follow-up
task.  0053 depends on the answer; 0052 (multi-layer tee) does not.

### Design answer (2026-10-29): yes, node projection (decision 0029)

Accepted, as you proposed, with three conditions.  DESIGN §6 is amended
(the projection paragraph after decision 0015's), and the deviation
rows are updated (tee: pinned plates, 3e-4 R; a new wye row).

**Steps 5–8** (replace "wye blocked"):
5. **Projector interface.**  A fitting exposes an analytic projector per
   surface it owns (wall now; shell boundaries at offset `R + T` for
   0052/0053): points → nearest points.  Keep it an interface, not wye
   code: vascular surfaces (decision 0018) will bring their own.
   `Assembly.mesh()` applies it between `generate(2)` and `generate(3)`
   to every node of the fitting's wall curves and faces, and nowhere
   else.  Nodes on curves shared with a swept neighbour are already
   exact; projecting them must be a no-op (check).
6. **Crease-aware wye projector.**  The nearest point on the canal
   surface `dist = R` (union of the inlet and daughter tubes and the
   knee sphere), never crossing into another branch.  For a point near
   the crotch, take the nearest point over the pieces whose projection
   lies on the outer boundary of the union (not inside another tube); on
   the crease itself, the crease curve.  The 60° wye is the test: no
   folded cells, no node moved across the crotch.
7. **Safety:**
   - a move larger than `WALL_PROJECTION_MAX_MOVE` × the local cell
     height (in `limits.py`; propose the value from your measurements)
     is an `AssemblyError` naming the fitting and the move;
   - `check_quality` after projection in the kit.
8. **Tee and measurements.**
   - Apply the projector to the tee as well.  Measure whether its
     pinned plates are still needed: if plain Stretch fillings plus
     projection give the same nodes (to 1e-6 R) and quality, drop the
     plates and their 588 construction points per tee, and report the
     build time before and after.
   - **Crotch chord error:** with projection, every node is on the wall,
     but faces containing the crease cut across it.  Report the largest
     distance from the analytic wall at face centres and edge midpoints
     near the crease, wye 60° and 90°, `nang` 4 / 8 / 16.  Above about
     1 % of R at `nang` 8, design opens a wye-layout follow-up (crease on
     block edges).
   - Document in `API.md` and `docs/integrations/gmsh.md` that the OCC
     surfaces stay approximate (CAD export, `gmsh.model` queries) and
     projected nodes lose their parametric coordinates.

**Accept (added):**
- every tee and wye wall node within 1e-6 R of the analytic wall on the
  final mesh, in every kit case, wye 60° included;
- no folded cells, quality reported before and after projection;
- the crotch chord-error table;
- the kit's exactness check runs the wye cases (no skips).

## Outcome

**Done (2026-10-29).**  Steps 1–4 (tee plates) in `705a35d`; steps 5–8
(node projection, decision 0029) in this commit.

- **Every tee and wye wall node is on the analytic wall to 1e-15 R** on
  the final mesh, in every kit case (wye 60°, 60° oblique and 90°
  included), and at `nang` 4–32 (*Agent notes*).
  - Before: tee 2.2–3.4 % (3e-4 R with the plates), wye 11–16 %.
  - The kit's `test_walls_exact` runs the wye cases (no skips), at 1e-6
    R for junctions.
- **No folded cells**, wyes 30°–120° at `nang` 4–16.  Min corner SJ:
  30° 0.06–0.07 (0.065 before), 60° 0.211 before and after, 90° 0.258 →
  0.227–0.236, 120° 0.155 → 0.149–0.155; tees unchanged.  Min SICN
  unchanged except 90° at `nang` 4 (0.168 → 0.151).  Kit
  `test_realisation` checks quality after projection.
  - This took a wide smoothing (2 R): narrower ones fold 30°–50° wyes
    (*Agent notes*).  The full suite's 30° wye test found it.
- **Crotch chord error** 0.85 % R at `nang` 8 (60°) and 0.88 % (90°);
  2.8–3.2 % at `nang` 4, 0.23–0.24 % at 16.  Table under *Agent notes*.
- **Tee plates kept:** projection after Stretch fillings gives nodes up
  to 1.3 % R away from the plate nodes (same quality), so it fails the
  "same nodes to 1e-6 R" rule.  The plates cost about 0.4 s per tee.
- **Projection cost:** about +0.1 s for a kit wye (1.19 → 1.32 s at
  `nang` 8).
- **Files:**
  - new `hexmesh/assembly/projection.py`: `Tube`, `TubeUnion`;
  - `hexmesh/assembly/assembler.py`: `mesh()` projects between
    `generate(2)` and `(3)`, plus `_project_walls`, `_check_projection`,
    `projection_report`;
  - `hexmesh/assembly/sweep.py`: `FillResult.projections`;
  - `hexmesh/assembly/blocks.py`: `walls` lists every level's faces for
    projection, and `pin_walls`;
  - `hexmesh/assembly/limits.py`: `WALL_PROJECTION_MAX_MOVE`;
  - `hexmesh/assembly/tee.py`: `tee_wall` is a `TubeUnion`;
  - `hexmesh/assembly/wye.py`: `Wye.wall`, crotch vertex levels;
  - `API.md`, `README.md`, `docs/integrations/gmsh.md` ("Moving surface
    nodes before volume meshing": stale parametric coordinates,
    renumbering);
  - tests: new `tests/test_projection.py` (15); `test_fitting_conformance`,
    `test_tee`, `test_wye` updated.
- **Suite:** 1881 passed, 0 skipped, 0 failed (at the 0052 commit: 1859
  passed, 3 skipped).  +19 in `test_projection.py`; the 3 wye kit
  exactness cases no longer skipped; the rest is the other session's
  stenosis example in the working tree.
- **Surprises:**
  - nearest-point projection folds the crotch;
  - `setNode(…, [])` keeps stale (u, v);
  - `generate(3)` renumbers nodes in the assembly;
  - the wye's hub-cap chords don't refine with `nang`.

**For design:**
1. **Projector is not nearest-point.**  Decision 0029 and step 6 say
   nearest point.  At the crotch that folds cells, so `TubeUnion` maps
   along a smoothed normal (nearest away from creases).  If DESIGN §6's
   new paragraph says "nearest", it could say "a nearby point on the
   surface that keeps neighbouring nodes in order (nearest, away from
   creases)".
2. **Move-limit unit.**  In local cell heights, a legitimate move grows
   with `nrad` (0.29 × `nrad` for the 60° wye: 2.5 at 9), so 4.0 rejects
   valid wyes above `nrad` ≈ 13.  A projector that crosses branches moves
   nodes by R or more.  Options:
   - (a) keep cell heights (4.0);
   - (b) a fraction of the wall's local radius, e.g. 0.5 R (measured
     ≤ 0.18 R), independent of density;
   - (c) both: reject above 0.5 R, warn above some cell-height multiple.
   I'd take (b): what the limit guards against is a wrong projector, and
   folds are caught by `check_quality` anyway.
3. **DESIGN rows:** the tee row ("pinned plates, 3e-4 R") and the new wye
   row can close: the nodes are exact.  What remains is OCC geometry
   only (CAD export) and the chord error above.
4. **Task 0056's 0.5 R move limit rejects narrow wyes.**  Measured moves:
   0.77 R at 30°, 0.60 R at 35°, 0.47 R at 40° (`nang` 8), all valid and
   unfolded.  Either the limit depends on the angle, or it's higher
   (about 1 R; a branch-crossing projector moves nodes by R or more, so
   1 R doesn't separate them cleanly), or the inversion check carries
   the safety alone.  Narrow wyes can't use a 0.5 R limit without a
   crotch layout that follows the crease.
5. **Proposed follow-ups:**
   - the wye's hub cap is resolved by `n_run` alone: chords about 10 % R
     there at any `nang`.  Scale its axial layers with `nang`, or tie
     them to the cap's arc.
   - Wye shells (0053) can reuse `Wye.wall(…, radius=R + T)`.

**Design response to *For design* 1–4 (2026-10-29):** see decision
0029's amendment and task 0056.  In short:
1. smoothed-normal projector accepted (DESIGN §6 reworded);
2. move limit becomes 0.5 × local wall radius, plus an inversion check
   in `mesh()` (task 0056);
3. both DESIGN rows closed; the crotch is under the 1 % threshold, so no
   layout follow-up;
4. wye axial counts from arcs (task 0056).

Finish this task as it stands (fill in the suite result); 0056 carries
the changes.

**Design response to item 4 (2026-10-29):** agreed.  No distance
limit: `mesh()` rejects inverted cells in projected fittings (the guard),
and only *warns* above 1.0 × local wall radius.  Decision 0029's
amendment, DESIGN §6 and task 0056 are updated.  Leave
`WALL_PROJECTION_MAX_MOVE` as you have it in this task; 0056 replaces it.
