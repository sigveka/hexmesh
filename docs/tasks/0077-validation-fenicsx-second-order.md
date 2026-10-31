# 0077 — Verification (V1): FEniCSx toolchain, and second-order export checked end to end

- **Status:** ready (step 1 any time; steps 2–4 after 0076)
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
