# 0034 — Secondary solvers for code-to-code comparison, and second-order mesh export

- **Status:** accepted in part (2026-10-31, the user): **FEniCSx** as
  the first secondary solver, and **second-order mesh export**, verified
  by FEniCSx.  Nek5000/NekRS stays proposed.
- **Date:** 2026-10-31
- **Tasks:** 0076 (second-order export), 0077 (FEniCSx toolchain and
  second-order verification).  Task 0074 carries a FEniCSx option as a
  note.

## Context

Every validation case runs on OpenFOAM (decision 0012; v2406 in Docker,
v1912 native).  A difference from a reference can come from the mesh,
the solver and its setup, or the reference itself.  With one solver the
first two can't be separated.  Task 0068 shows the problem: the DNS's
upstream flow doesn't match its stated inlet, and nothing in our runs
says whether the rest of the mismatch is ours.

A second, independent solver on **the same hexmesh mesh** separates
them:
- both solvers agree with each other but not the reference → the mesh
  or the reference;
- they disagree → a solver or setup issue.

It also widens hexmesh's audience.  Some solvers *need* conforming
all-hex meshes (spectral element, high-order finite element), and that
is exactly what hexmesh makes.

## Options

Candidates (none installed on this machine, 2026-10-31; gmsh 4.12.1
is):

| Tool | Method | Licence | Mesh route | Fits |
|---|---|---|---|---|
| **FEniCSx (dolfinx)** | finite element | LGPL | gmsh `.msh` via `gmshio`; hexes supported | manufactured solutions (0074): the source is a Python expression, with no coded-source problem; conduction, Stokes, laminar flow |
| **Nek5000 / NekRS** | spectral element | BSD | `gmsh2nek`; hexes only; second-order elements for curved walls | V2 cases (stenosis, later junctions): the DNS method family; the all-hex showcase |
| **SU2** | finite volume | LGPL | gmsh's SU2 export | second FV code for the RANS cases (0049, 0050) |
| **code_saturne** | finite volume | GPL | gmsh `.msh`, MED, CGNS | RANS and CHT; industrial validation |
| **Elmer** | finite element | GPL / LGPL | `ElmerGrid` from gmsh | conduction and CHT |

Commercial codes (Fluent, STAR-CCM+) read the meshes too.  They are not
candidates: licence-bound and not reproducible by others.

## Proposed direction

1. **OpenFOAM stays the primary target.**  Its gates decide acceptance.
   Secondary solvers are **comparisons**: they never gate on their own.
2. **Two secondary solvers, for different jobs:**
   - **FEniCSx for verification.**  It's cheap, scripted in Python and
     independent of OpenFOAM's discretisation.  A finite-volume and a
     finite-element result agreeing on a fitting's manufactured solution
     is strong evidence.  First use: task 0074.
   - **Nek5000/NekRS for the high-fidelity cases.**  First use: the
     steady and pulsatile stenosis (0032, 0068).
3. **Run in containers, as OpenFOAM v2406.**  Pin the image versions
   and record them in `docs/integrations/<tool>.md`.
4. **Same `case.json`.**  A secondary run is recorded in the case's
   `case.json` as an extra toolchain with its own results.  The coverage
   matrix (task 0073) can mark cases with two solvers.
5. **Mesh exchange through gmsh's own writers** (`.msh`, SU2, CGNS,
   MED) wherever one fits.  A hexmesh writer only where none does,
   which keeps hexmesh solver-neutral (decision 0030's solver
   adapters).

## Open questions

- **Second-order mesh export.**  hexmesh's walls are exact at the nodes
  (decision 0029), but linear hexes are flat between nodes.  Nek and
  high-order FEniCSx gain most from second-order elements (Hex27):
  nodes on the true wall.
  - gmsh can raise the order (`gmsh.model.mesh.setOrder(2)`).  Whether
    the new nodes land on the true surface depends on the geometry
    entities, and on how it interacts with decision 0029's node
    projection on junction walls.  It needs a probe.
  - It may deserve its own decision (option: `Assembly.mesh(order=2)`
    with the projection applied to the mid-edge and mid-face nodes).
  - **Probed 2026-10-31** (`docs/integrations/gmsh.md`, "Second-order
    hexes"):
    - **Possible:** `setOrder(2)` works on hexmesh's transfinite meshes,
      and is exact and valid on straights, bends and the stenosis.
    - **Projected junction walls need hexmesh's own pass:** re-project
      the high-order wall nodes, and never use gmsh's high-order
      optimiser, which undoes the projection.  That works for the tee.
      The wye inverts, worse with refinement; probably the projector at
      the creases.  It needs a crease-aware projection before second
      order can be offered for wyes.
    - **OpenFOAM can't use it:** `gmshToFoam` (v1912, v2406) rejects
      second-order elements (`docs/integrations/openfoam.md`).  Second
      order is only for secondary solvers; the OpenFOAM writer stays
      first order.
- **Which comes first:** FEniCSx (small, Python, immediately useful for
  0074) or Nek (bigger payoff for V2, more setup).  Design's view:
  FEniCSx first.
- **Native install vs container** for FEniCSx (pip/conda wheels exist),
  and whether it becomes an optional dependency (`hexmesh[fenics]`) or
  stays out of the package (validation scripts only).  Design's view:
  validation scripts only.

## Decision (2026-10-31, the user)

On the probe's findings, the user: "seems like a good idea, now we need
another tool as part of validation though to verify the second order
export".

1. **Second-order export, `Assembly.mesh(order=2)`:**
   - Hex27 by default;
   - high-order wall nodes on projected fittings are projected too;
   - gmsh's high-order optimisers are never run;
   - invalid elements are rejected as for linear meshes.
   - **Wyes:** a crease-aware projection for chord midpoints.  Until it
     works, `order=2` on a `Wye` (and equal tees) is rejected with a
     clear error.
   - **OpenFOAM writer:** refuses order 2.
2. **Verification in two layers:**
   - **Solver-free, in the test suite:** volume and wall area
     integrated with Gauss quadrature over the curved elements converge
     at about h⁴ for second order, against h² for linear;
   - **FEniCSx (dolfinx):** a manufactured-solution Poisson problem,
     Q2 on Hex27 meshes against Q2 on the same mesh straightened.  The
     L2 error converges at order 3 only if the curved geometry is right;
     with straight cells it stalls at about 2.  This is the end-to-end
     check that a real consumer reads the export correctly.
3. **FEniCSx runs in a pinned container,** like OpenFOAM v2406.
   `docs/integrations/fenicsx.md` records the image and version.  It
   stays out of hexmesh's dependencies: validation scripts only.
4. **Nek5000/NekRS:** still proposed.  Revisit when all three
   conditions hold (2026-10-31, the user):
   - **Second order works on every fitting, wyes included** (0076,
     with its crease-aware projection), and FEniCSx confirms it (0077).
     Nek meshes are coarse macro meshes of high-order elements, so
     curved faces are mandatory.  Also check corner quality: what
     OpenFOAM tolerates (SJ ≈ 0.2) may hurt spectral accuracy.
   - **A case needs resolved transition or turbulence**, which OpenFOAM
     laminar/RANS can't credibly give.  First candidate: the eccentric
     stenosis, steady (Part 1) then pulsatile (Part 2), whose Purdue
     DNS data exist.  Then vascular work (0018), and junction LES
     (the Vattenfall T-junction).
   - **Compute is available** (a cluster or GPUs for NekRS).
     Varghese: about a day on 32 processors per pulsatile period; six
     days for the transitional eccentric case.  The 4-core shared
     machine can't.

   **Before then, a cheap converter probe** (once 0076 is done, no
   solve):
   - run `gmsh2nek` on hexmesh Hex27 exports (straight, bend, tee);
   - check the curved sides are carried and boundary conditions map
     from the physical groups;
   - record it in `docs/integrations/nek5000.md`.

**DESIGN.md §6** gains one sentence: with `order=2`, high-order nodes on
projected walls are projected too.

## Consequences

If accepted:
- **New integrations files** per solver; the decision 0012 toolchain
  amendment gains "secondary solvers".
- **No change to DESIGN.md.**  Meshes are solver-neutral already; the
  OpenFOAM writer stays the only built-in writer unless a later
  decision adds one.

**Future expansions:**
- **0018 (vascular):** Nek is the standard tool for haemodynamics DNS;
  hexmesh vascular meshes would run there directly.
- **0019 (agent SDK):** solver choice stays outside hexmesh's tool
  interface (the suite's solver adapters, 0030).
- **0021 (flow restrictions):** the FDA nozzle (RESEARCH §7.9) has a
  28-simulation round-robin; a second solver puts hexmesh in its
  comparison set.
- **0030 (suite):** this is the first instance of the suite's solver
  adapters; keep the adapter interface solver-neutral (mesh path, case
  directory, results), not OpenFOAM-shaped.
