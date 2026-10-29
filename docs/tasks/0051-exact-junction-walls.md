# 0051 — Exact junction walls (tee and wye)

- **Status:** ready (design answered Q1 2026-10-29: steps 5–8)
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

**Partial: tee done, wye blocked on Q1.**

- **Tee walls within 1e-3 R.**  Every tee wall node is within 3.0e-4 R
  (r/R 0.5) or 1.3e-4 R (r/R 0.9) of the cylinders, at `nang` 4 and 8
  and in the oblique kit case.  Before: 2.2–3.2 %.
  - Method: a plate filling of each curved wall face, pinned to a 7 × 7
    grid projected onto the cylinder union (`BlockLayout.wall`,
    `_wall_surface`, `tee.tee_wall`).
  - The accuracy limit is OCC's plate fit.  Node projection on top would
    give 7e-7 (Q1).
- **Unchanged:** cell counts (1296 per kit tee case), all-hex, the 5
  physical groups, min SICN (0.149 / 0.263) and the tee's min corner SJ
  (0.258 / 0.509).  The worst cells aren't on the wall faces.
- **Build time** of the kit tee cases, median of 3, idle machine:
  1.44 → 1.85 s (r/R 0.5) and 1.33 → 1.66 s (0.9, oblique), about
  +0.35 s per tee for 12 plate solves.
  - Each tee also leaves 588 construction points for the batch removal.
    At about 3.9 ms per point in a 2000-volume model (`gmsh.md`), that
    is about 2.3 s per tee in a large network.
- **Kit:** `wall_deviations` measures `Tee` against the cylinder union,
  and `test_walls_exact` runs the tee cases at 1e-3 R (the wye cases
  are still skipped, Q1).  `tests/test_tee.py` adds a `nang` 8 check and
  a negative control: without the projection the check sees 3.2 %.
- **Files:** `hexmesh/assembly/blocks.py`, `hexmesh/assembly/tee.py`,
  `tests/test_fitting_conformance.py`, `tests/test_tee.py`,
  `docs/integrations/gmsh.md`.
- **Suite:** 1809 passed, 3 skipped (before: 1805 passed, 5 skipped; +2
  tests, +2 kit cases no longer skipped).
- **For design:** the DESIGN deviation row on tee wall faces can be
  reworded to "within 3e-4 R (plate fit)" or closed, as design sees fit.
  The wye has no row of its own yet, though its faces are 11–16 % off.
