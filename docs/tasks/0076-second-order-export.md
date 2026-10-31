# 0076 — Second-order mesh export: `Assembly.mesh(order=2)`

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
