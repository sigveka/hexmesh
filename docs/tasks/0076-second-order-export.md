# 0076 — Second-order mesh export: `Assembly.mesh(order=2)`

- **Status:** done (2026-11-05)
- **Decision:** [0034 — Secondary solvers and second-order export](../decisions/0034-secondary-solvers.md) (accepted in part); [0029](../decisions/0029-wall-exactness-by-node-projection.md) (wall projection)
- **Depends on:** none.  0077 verifies it with FEniCSx.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  hexmesh's walls are exact at the nodes, but linear hexes are
flat between them.  Second-order elements put the mid-edge, mid-face
and body nodes on the true wall too, for solvers that use them
(FEniCSx, Nek).  OpenFOAM can't (`gmshToFoam` rejects them).

**Evidence** (`docs/integrations/gmsh.md`, "Second-order hexes", design
probe 2026-10-31).
- `setOrder(2)` works on our transfinite meshes: exact and valid on
  straights, bends and the stenosis.
- On projected walls, gmsh puts the new nodes on the inexact OCC
  surface: tee 7.8e-4 R off; wye 0.16 R off with 32 inverted hexes.
- Re-projecting them fixes the tee.  The wye still inverts, worse with
  refinement (36 / 180 / 1044 at `nang` 6 / 12 / 24).  The worst chord
  midpoint is 0.039 R off at every resolution: probably the union
  projector sending midpoints near a crease onto the other tube.
- gmsh's high-order optimisers pull wall nodes back to the OCC surface.
  Don't use them.

**Where.**  `hexmesh/assembly/assembler.py` (`mesh`, `write`,
`write_openfoam`); the junction projectors (tee, wye); `limits.py` if a
new limit is needed; `docs/integrations/gmsh.md`; tests.

**Do.**
1. **`Assembly.mesh(dim=3, *, order=1, …)`.**  `order=2` runs
   `setOrder(2)` after the linear mesh and its checks.  Hex27 by
   default.  Offer Hex20 (`incomplete=True`) only if it costs nothing
   extra; otherwise say so.  Then:
   - **re-project** every high-order node on a projected fitting's wall
     surfaces and their curves, with that fitting's projector;
   - **recompute** the face and body nodes of the hexes touching those
     walls from their edges (the Hex20 serendipity interpolant, as the
     probe did), then re-project the wall face centres.  Keep this only
     if it measurably helps; the probe saw no gain on the wye;
   - **never** call gmsh's high-order optimisers;
   - **validity:** reject any element whose Jacobian determinant is
     ≤ 0 at the Hex27 nodes or Gauss points (state which), naming the
     fitting, as `mesh()` does for linear cells.
2. **Crease-aware midpoint projection (wye, equal tees).**  Project a
   high-order node on an edge or face onto the branch surface its
   end or corner nodes lie on, not by the union's smoothed normal.
   - **Success** = no inverted hexes at `nang` 6, 12 and 24, and the
     worst wall offset falling with refinement.
   - **If it fails:** `order=2` on `Wye` (and on tees dispatched to the
     wye family) raises a clear error naming the limitation.  Record
     the measurements, and say what was tried, under *Questions for
     design*.
3. **Writers.**
   - `write_openfoam` (and the `.msh` it writes) refuses an order-2
     mesh, with the reason (`gmshToFoam` reads first-order only:
     `docs/integrations/openfoam.md`).
   - `write` keeps gmsh's default format.  Check that `.msh` 4.1 and
     2.2 both carry Hex27 and that the physical groups survive (wall,
     inlet, outlet, interfaces).
4. **Cell count:** unchanged (cells, not nodes).  `cell_count()` stays;
   add a node count for order 2 if cheap.
5. **Solver-free verification (tests).**  Integrate with Gauss
   quadrature over the curved elements (gmsh's Jacobians at integration
   points, or numpy with the Hex27 basis):
   - **volume** of a straight (πR²L) and of a bend (the torus section,
     πR²·ρθ), at three refinements, linear vs order 2.  Expect about
     **h²** linear and **h⁴** second order; gate order 2 at observed
     order ≥ 3.5;
   - **wall area** of the same (2πRL; 2πR·ρθ): the same expectations,
     with the gate at ≥ 3.5 (say if area converges slower);
   - **tee** (and the wye, if step 2 succeeds): no closed form, so
     report the observed order from three levels (Richardson), and
     require order 2's to exceed linear's by at least 1.

**Accept.**
- `order=2` meshes all fitting examples except those rejected by step 2,
  with no invalid elements.
- Step 5's orders for straight and bend ≥ 3.5; tee (and wye) reported.
- `write_openfoam` refuses order 2.
- `docs/integrations/gmsh.md` updated with what the implementation
  found; full suite passes; *Outcome* with the convergence table.

**Follow-up (decision 0034, after this task):** a converter-only Nek5000
probe on this task's Hex27 output (`gmsh2nek`; no solve).  Propose it
in *Outcome* with the files to use; design writes the task.

**Out of scope.**  Order 3+; curved first-order elements for OpenFOAM
(not a thing); Nek export (`gmsh2nek`, later with Nek).

## Agent notes

- **A finding outside the task's scope: bends.**
  - At order 2, three examples' plain bends and elbows inverted:
    - `lagged_duct` Bend1, 72 hexes;
    - `insulated_route` Elbow6, 16;
    - `pipe_rack` Elbow1, 24.
  - All are in 6 mm steel shells with 2 radial cells, at Hex27 nodes 14
    and 15 (axial edges) and 24 (an axial face).
  - `setOrder(2)` puts wall nodes on the torus but leaves interior axial
    edges straight.  The arc's sag across one axial cell folds a cell
    that thin.
  - Fix (`Assembly._revolve_high_order`): a bend is a solid of
    revolution.  Every high-order node between two stations becomes its
    counterpart on the hex's first station, rotated about the bend axis
    by half the slab's turn.  The counterpart is the corner, edge node
    or face node with the same in-station parents.  This is exact, and
    all three examples are valid.  A test checks that every wall node
    of a bend lies on the torus to 1e-12.
- **Step 1's recompute (face and body nodes from the edges).** I kept
  only what helps:
  - on tees, re-projecting the wall nodes with the fitting's own
    projector is enough;
  - the transfinite carry changed nothing on tees, and helps only the
    wye, which is rejected anyway.
  So the carry is not in the library; the prototype is described under
  Outcome.
- **"Smallest corner Jacobian 8.7e-8" (the wye, design's question) is
  the raw determinant** of `getJacobians` on the linear hexes, in m³ per
  unit reference volume.  It is not the scaled Jacobian.
  - The cell with that minimum has scaled Jacobian 0.626.  It is only
    small: edges 6.5–23 mm, against a median determinant of 1.2e-6.
  - The wye's linear cells: min corner SJ 0.156, median 0.914, none
    below 0.1, out of 3132 cells.  Edges are 6.5–61 mm.
  - The wye's predicted min corner SJ is 0.211
    (`BlockLayout.validate()`), so the linear mesh has no defect.  The
    order-2 inversions come from the high-order nodes at the creases.
- **Validity** is checked at both the element's own nodes (Hex27 or
  Hex20) and the `Gauss4` points.  On the wye, Gauss3 found 0 inverted
  where the nodes found 32, so the Gauss points alone aren't enough.
- **Hex20** (`incomplete=True`) costs nothing extra.  hexmesh sets
  `Mesh.SecondOrderIncomplete` for the call and restores it.  The
  re-projection reads each element's node count, so it handles Quad8
  and Quad9.
- **The wye rejection** is a class attribute,
  `Wye.second_order_limitation` (the reason, with the measurements).
  `mesh(order=2)` checks every fitting for one before building anything.
  No tee has equal radii (`branch_radius` must be below the main), so no
  tee reaches the wye family; nothing else is rejected.
- **Recipe block.**  `write(order=2)` adds `order=2 incomplete=…` to the
  block's write line.  At order 1 the line is unchanged, so existing
  `.msh` files are byte-identical.
- **Node count** (step 4): not added.  The exact count needs the hex
  mesh's edge and face counts, which `cell_count()`'s pure-Python model
  doesn't have.  After meshing it is `len(gmsh.model.mesh.getNodes()[0])`.
- **Codes** (new, in `CODES` and the API.md table):
  - `mesh_order_invalid`;
  - `mesh_order_needs_volume`;
  - `second_order_unsupported`;
  - `second_order_inverted`;
  - `openfoam_needs_order_1`.

## Questions for design

_None._  Step 2 failed, and its fallback (reject `order=2` on `Wye`) is
in place.  The measurements and what was tried are under Outcome.  A
design question for later, not blocking: should the wye's linear crease
error be addressed at order 1?  See Outcome.

## Outcome

**Files.**
- `hexmesh/assembly/assembler.py`:
  - `mesh`, `write`, `write_openfoam(order=)`;
  - `_second_order`, `_revolve_high_order`, `_check_second_order`;
  - the helpers `_element_parents` and `_rotation`.
- `hexmesh/assembly/wye.py`: `second_order_limitation`.
- `hexmesh/errors.py`: 5 codes.
- `tests/test_second_order.py`: 39 tests.
- `API.md`: the `mesh`, `write` and `write_openfoam` rows, and the codes.
- `docs/integrations/gmsh.md`: "Second-order hexes in hexmesh".
- `CHANGELOG.md`.

**Examples at order 2.**
- 23 of the 28 mesh as valid Hex27: no hex with a determinant ≤ 0 at a
  node or Gauss4 point.  The meshed hex count equals `cell_count()`.
- The 5 with a `Wye` are rejected before meshing:
  - `wye`, `junction_walls`, `insulated_network`, `bifurcation_tree`,
    `cooling_channels`.
- Times: 2.5–14 s each, against 1–8 s linear.

**Convergence table** (step 5).
- Gauss6 quadrature of the volume and the wall area; nang 4k, nrad 2k,
  k = 1, 2, 4.
- Straight: R 0.1, L 0.4.  Bend: ρ 0.3, 90°.  Tee: R 0.1, r 0.05.
- The tee has no closed form, so its errors are successive differences.

| case, quantity | order | error at k = 1, 2, 4 | observed order |
|---|---|---|---|
| straight volume | 1 | 2.55e-2, 6.41e-3, 1.61e-3 | 1.99, 2.00 |
| straight volume | 2 | 4.93e-5, 3.09e-6, 1.94e-7 | 4.00, 4.00 |
| straight area | 1 | 6.41e-3, 1.61e-3, 4.02e-4 | 2.00, 2.00 |
| straight area | 2 | 2.45e-5, 1.54e-6, 9.67e-8 | 3.99, 4.00 |
| bend volume | 1 | 5.04e-2, 1.28e-2, 3.21e-3 | 1.98, 1.99 |
| bend volume | 2 | 9.86e-5, 6.19e-6, 3.87e-7 | 4.00, 4.00 |
| bend area | 1 | 2.23e-2, 5.61e-3, 1.41e-3 | 1.99, 2.00 |
| bend area | 2 | 6.14e-5, 3.86e-6, 2.42e-7 | 3.99, 4.00 |
| tee volume | 1 | differences 2.05e-2, 5.14e-3 | 1.99 |
| tee volume | 2 | differences 5.42e-5, 3.40e-6 | 3.99 |
| tee area | 1 | differences 4.62e-3, 1.16e-3 | 2.00 |
| tee area | 2 | differences 2.55e-5, 1.62e-6 | 3.98 |

- The gates hold: straight and bend ≥ 3.5, and the tee's order 2 is 2.0
  above linear (required ≥ 1).  Area converges as fast as volume.

**Step 2, the wye: failed.**  Example `fittings.wye`, hexes counted at
the Hex27 nodes (Gauss3 points in brackets):

| rule | k = 1 | k = 2 | k = 4 |
|---|---|---|---|
| gmsh placement only | 32 (0) | | |
| union projector | 44 (0) | | |
| crease-aware | 32 (0) | 260 (94) | 1512 (878) |
| crease-aware + transfinite carry | 6 (0) | 94 (4) | 684 (64) |

| wall offset between nodes (/R) | k = 1 | k = 2 | k = 4 |
|---|---|---|---|
| linear | 0.030 | 0.034 | 0.040 |
| crease-aware | 0.016 | 0.017 | 0.015 |

- Crease-aware: each high-order node goes onto the tube all its parent
  corners lie on.
- The transfinite carry moves the touching hexes' interior nodes: Coons
  on faces, Gordon-Hall in the body.
- Neither the inversions nor the offset fall with refinement.  The
  linear offset grows, so the error is where mesh lines cross the
  creases, not curvature.  A wye whose mesh lines followed the creases
  would be a layout change (the wye redesign), not an export one.

**Tees** (union projector, the library's rule):
- valid at k = 1, 2 and 4;
- wall offset between nodes 5.4e-5, 9.8e-6, 4.9e-6 R, against linear's
  1.3e-2, 3.4e-3, 8.6e-4 R.

**Full suite:** 3352 passed, 15 skipped (3313 before, plus 39 new).  Order-1 meshes are unchanged: all 28 examples hash identically to before.

**Proposed follow-up (decision 0034): a Nek5000 converter probe.**
- Run `gmsh2nek` on Hex27 output, with no solve.
- Files to use:
  - `_bend(2)` from `tests/test_second_order.py` (`write("bend.msh",
    order=2)`, msh 2.2, which `gmsh2nek` reads);
  - `hexmesh/examples/fittings/tee.py` at `order=2`;
  - `sections/insulated_pipe.py` (multi-material) at `order=2`.
- Check that `gmsh2nek` accepts Hex27 with the physical groups as
  boundary IDs, and the curved-side data it writes.

