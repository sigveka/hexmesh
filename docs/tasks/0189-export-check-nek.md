# 0189 — Export check: Hex27 in Nek5000 or NekRS (the ladder's step 5)

- **Status:** ready
- **Decision:** [0058](../decisions/0058-diagnosis-ladder-and-user-hints.md)
  rule 2; [0057](../decisions/0057-two-kinds-validation-and-export-checks.md)
  rule 2 (export checks); [0034](../decisions/0034-secondary-solvers.md)
  (the Nek proposal)
- **Depends on:** 0182 (the export-check framework).
- **Blocks:** 1.0 (decision 0058 rule 4), unless the stop rule fires.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A higher-order code is the ladder's last step: it separates
discretisation error.  Nek5000 and NekRS are spectral-element codes on
curved all-hex meshes.  They take hexmesh's second-order export.  This
task makes that path work and checks it, as an export check.

**Do.**
1. **The consumer:** Nek5000 (CPU, Fortran/MPI) or NekRS (OCCA; its
   CPU/serial backend), whichever builds and runs here more simply.
   Pin it in a container or a scripted build.  Record the version, the
   build and how to reproduce in a new `docs/integrations/nek.md`.
2. **The conversion:** `write(..., order=2)` to `.msh`, then `gmsh2nek`
   (Nek's tool) to `.re2`.
   - Record what `gmsh2nek` needs: the msh version, Hex20 or Hex27,
     boundary groups to sideset IDs, and periodic pairs.
   - Say whether the curved edges survive (the `.re2`'s curvature
     section).
3. **The format test (CI, no solver):** if `.re2` can be produced
   without Nek installed, parse its header: element count against
   `cell_count()`, and boundary IDs per group.  Otherwise test what
   reaches `gmsh2nek` (Hex27 and groups), through the 0182 helper.
4. **The solve:** laminar Poiseuille in a straight pipe and in the
   bend (the Dean case's laminar point, if `validation/square_bend` or
   the helical driver gives a reference; otherwise the straight only).
   - Polynomial order N = 5–7, at two or three meshes or orders.
   - Compare against the exact Δp and u_max, and report the
     convergence in N (spectral) and in h.
   - This checks the curved geometry: with straight-sided elements, the
     error would plateau at the geometry error.  Show both if cheap
     (Hex8 against Hex27).
5. **`validation/exports/nek/`**: `case.json` (`kind: export`), run.py,
   README and RESULTS.md.  Status `passes` or `fails`.
6. **Stop rule:** if a pinned build of either code that runs Poiseuille
   costs more than about a day, stop.  Write what failed under
   *Questions for design*: the user decides whether it stays before 1.0.
7. Docs: list the Nek path with its status where 0181 lists `.unv`.
   CHANGELOG.

**Accept.**
- A pinned Nek that imports a hexmesh mesh with its boundaries.
- Poiseuille at the exact answer, with spectral convergence shown, and
  the curved geometry's effect shown.
- The status is set, or the stop rule's report.

**Out of scope.**  RANS or LES in Nek (that's the ladder's step 5 for a
case, after this tool exists); GPU runs.

## Agent notes

## Questions for design

## Outcome
