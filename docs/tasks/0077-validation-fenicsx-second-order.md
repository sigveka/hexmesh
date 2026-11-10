# 0077 — Verification (V1): FEniCSx toolchain, and second-order export checked end to end

- **Status:** done
- **Decision:** [0034 — Secondary solvers and second-order export](../decisions/0034-secondary-solvers.md) (accepted in part); [0012](../decisions/0012-openfoam-validation-cases.md) (categories); [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
- **Category:** V1 (exact: manufactured solutions)
- **Features:** `section:circle`, `straight`, `bend`, `tee`, `projection`
- **Depends on:** 0076 (`Assembly.mesh(order=2)`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The second-order export needs a consumer that uses curved
elements, to show it is read and used correctly.  FEniCSx is decision
0034's first secondary solver.  The test is classic: the L2 error of a
Q2 finite-element solution converges at order **3** only when the
geometry is second order.  On straight-sided cells it stalls at about
**2**, the geometry error.

**Where.**  `validation/fenicsx_second_order/` (`run.py`, `README.md`,
`RESULTS.md`, `case.json`, `meshes()`); `docs/integrations/fenicsx.md`
(new).  FEniCSx stays out of hexmesh's dependencies (decision 0034).

**Do.**
1. **Toolchain (any time).**
   - Run dolfinx in a container: the official `dolfinx/dolfinx` image,
     a pinned stable tag at least two weeks old (record tag and digest).
   - Mount the case directory as the OpenFOAM v2406 runner does (user
     id, no root-owned output).
   - Record in `fenicsx.md`:
     - how hexmesh's `.msh` is read (`dolfinx.io.gmshio`, physical
       groups → cell and facet tags), and which MSH versions and
       element types it accepts (Hex8, Hex27; Hex20?);
     - any quirks: node ordering, the MPI partitioner, a mesh with
       several volume groups.
   - **First check:** a linear straight from hexmesh read and solved,
     against Poiseuille's exact profile as a Stokes or Poisson problem
     (u = 1 − r²/R² solves −∇²u = 4/R²).
2. **Manufactured solution.**
   - Choose u_m(x, y, z), smooth and with a few wavelengths across the
     geometry (state it).
   - Solve −∇²u = f with f = −∇²u_m (UFL does this symbolically) and
     u = u_m on every boundary.
   - Compute the L2 and H1 errors with a higher-degree quadrature.
3. **Matrix**, at three refinements (`nang` doubling, as 0076):

   | mesh | element | expected L2 order |
   |---|---|---|
   | linear (Hex8) | Q1 | 2 |
   | linear (Hex8 geometry) | Q2 | ≈ 2 (geometry-limited) |
   | second order (Hex27) | Q2 | 3 |

   - Geometries: straight, bend, tee.  Add the wye if 0076's step 2
     succeeded; otherwise record that it was skipped and why.
   - For the "Q2 on linear geometry" row, feed the Hex8 mesh with a Q2
     function space.  Don't build a Hex27 with straight edges by hand.
4. **Wall-only check:**
   - **Neumann variant:** prescribe the exact flux on the curved wall
     instead of the value (the normal comes from the curved geometry).
   - With straight cells the wall normals are wrong, so the error
     stalls harder there.  This is the most sensitive test of the wall
     nodes' placement.

**Accept.**
- Hex27/Q2 observed L2 order ≥ **2.7** on straight, bend and tee.  The
  geometry-limited row is visibly lower (report both).
- Neumann variant: the same pattern, reported.
- `case.json` (V1, toolchain `fenicsx:<tag>`, features as above);
  `fenicsx.md`; RESULTS.md; *Outcome* table for RESEARCH.

**Out of scope.**  Flow (Stokes/Navier–Stokes MMS) and the cross-check
of task 0074's OpenFOAM results.  These are natural follow-ups once the
toolchain exists; propose them in *Outcome*.

## Agent notes

- **Task 0130 (step 4):** this task's *Outcome* lifts the "experimental"
  label on `order=2` in the docs, if the Hex27 rows pass.
- **Toolchain:** `dolfinx/dolfinx:v0.11.0`, pinned by digest, run as the
  host user (`docs/integrations/fenicsx.md`).  Hex8 and Hex27 read with
  their physical groups; Hex20 (`incomplete=True`) is rejected by
  dolfinx's reader.  First check: −∇²u = 4/R² with u = 1 − r²/R² on a
  linear straight (R 0.5, `nang` 8): Q1 relative L2 1.4e-2; Q2 exact to
  1e-15 (the solution is in the space, the data exact on the polygon);
  Q2 on Hex27 4.2e-6 (the isoparametric map).
- **Step 2/4 refined: where the geometry enters.**  With task 0074's
  u_m (defined everywhere) and the data taken on the mesh's boundary,
  the discrete problem is consistent on the polygonal domain, so Q2 on
  Hex8 converged at order 3 like Hex27 (straight, k 1 → 2: L2 9.0e-3 →
  1.2e-3 on both): the matrix's "geometry-limited" row can't appear.
  The Neumann variant therefore uses the **exact** wall's normal (step 4:
  "the normal comes from the curved geometry"): capped cylinders and a
  torus from the assembly's ports and the bend's arc, in UFL, nearest
  surface per point.  The Dirichlet rows stay as a control: there the
  geometry isn't seen, by construction.
- **Wye and equal tee skipped:** `mesh(order=2)` rejects them
  (`second_order_unsupported`, task 0076).
- **Gate applied to both variants:** the recheck gates Hex27/Q2 at
  ≥ 2.7 on Dirichlet and Neumann, both pairs of levels (stricter than
  "Neumann: reported").
- **Memory:** the first full matrix ran every solve on a mesh in one
  process and was stopped by Claude Code's memory guard during the tee
  at k = 4.  `run.py` now runs one container per solve, capped with
  `--memory`; BoomerAMG's default setup still exceeded 6 GB on Q2 at
  1.1 M dofs, so the solver uses low-complexity settings (results
  unchanged at k = 2; `fenicsx.md`).

## Questions for design

_None._

## Outcome

**Done 2026-11-11.**  Hex27/Q2 passes the gate everywhere.

| case | variant | Q2 on Hex27 | Q2 on Hex8 | Q1 on Hex8 |
|---|---|---|---|---|
| straight | Dirichlet | 2.91, 2.98 | 2.90, 2.98 | 1.96, 1.99 |
| straight | Neumann | 2.87, 2.98 | 2.50, 2.28 | 2.08, 2.02 |
| bend | Dirichlet | 2.81, 2.96 | 2.81, 2.96 | 2.06, 2.01 |
| bend | Neumann | 2.80, 2.96 | **2.00, 2.03** | 2.13, 2.04 |
| tee | Dirichlet | 2.80, 2.95 | 2.79, 2.95 | 2.02, 2.01 |
| tee | Neumann | 2.78, 2.95 | 2.64, 2.50 | 2.09, 2.03 |

L2 orders, k = 1 → 2 and 2 → 4 (`nang` 6, 12, 24; 864 to 138 240
cells).  At k = 4 the Neumann error of Q2 on Hex8 is 10× Hex27's on the
bend, 2.5× on the straight and 1.7× on the tee.

- **Files:** `validation/fenicsx_second_order/` (`run.py`, `solve.py`,
  `README.md`, `RESULTS.md`, `case.json`, `results.json`, `figure.png`,
  `img/`); `docs/integrations/fenicsx.md` (new);
  `validation/case.schema.json` (`toolchain` takes `openfoam` or
  `fenicsx`); `validation/tools/recheck.py` and `plots.py` (the case);
  `docs/gallery/build.py` (the tag line names FEniCSx);
  `tests/test_validation_meta.py` (the `-keepOrientation` check applies
  to OpenFOAM cases); generated `README.md`, `docs/GALLERY.md`,
  `hexmesh/agent/validation.json`.
- **Tests:** 269 passed (validation meta, drivers, agent manifest,
  validation, study, architecture, convergence, readme, volunteer,
  validation counts).
- **Cost:** 22 min of solving, serial; peak 4.4 GB per solve (Q2,
  tee, k = 4, 1.13 M dofs).
- **Surprises:**
  - Data taken on the mesh's own boundary (Dirichlet, or the
    mesh's `FacetNormal`) hide the geometry error entirely: Q2 on Hex8
    then converges at order 3 like Hex27.  The exact wall's normal is
    what tests the wall (`fenicsx.md`).
  - On the straight and the tee, Q2 on Hex8 hasn't reached order 2 by
    k = 4; the bend, curved in two directions, has.
  - dolfinx rejects Hex20 (gmsh type 17).
- **The "experimental" label (task 0130, step 4):** second order is now
  verified, so it doesn't need the label.  0130 hasn't run yet, so the
  label was never added; 0130's step 4 drops out (noted there when it
  is worked).
- **Proposed follow-ups:** Stokes MMS on the same meshes (flow,
  decision 0034's next step); a cross-check of task 0074's OpenFOAM
  errors on the straight and bend; second order for the wye and equal
  tee would let this case cover them.

