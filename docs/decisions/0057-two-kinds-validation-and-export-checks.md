# 0057 — Two kinds of checks: validation (OpenFOAM) and export checks (other codes, one per format); export checks before 1.0

- **Status:** accepted (2026-11-18, the user)
- **Date:** 2026-11-18
- **Tasks:** 0182, 0181 (widened), 0183

## Context

The user (2026-11-18): "Then I think we have two validation types 1)
rigorous high fidelity fittings and case studies (can stay OpenFOAM) 2)
Mesh export sanity check (coarse to medium meshes for fenics, saturne,
??)", then: "record it as a decision and I believe this should be in
place before 1.0."

Today:
- Validation has 14 cases (`validation/*/case.json`), 13 of them in
  OpenFOAM.
- One case checks an export rather than a fitting:
  `fenicsx_second_order` (decision 0034, task 0077).  It is the
  second-order `.msh` read by dolfinx, with an MMS of the order a correct
  geometry gives.  It sits in the same tables as the physics cases.
- Decision 0056 makes `.unv` experimental, with code_saturne as its one
  real consumer.  Decision 0055's *Not decided* lists other solvers.
- What gmsh writes with the group names (`docs/integrations/gmsh.md`,
  2026-11-18): `.unv`, `.neu`, `.inp` and `.su2` keep them; `.bdf` loses
  them; there is no `.cgns` or `.med` in the build here.

## Options

- **A. One list of cases, as now.**  Export checks would be cases with a
  V1 category beside the physics.
- **B. Two kinds, kept apart (chosen).**  Each has its own purpose,
  rules, tables and cost.
- **C. B, with every export format checked before 1.0.**  That's seven
  consumers.  Most have no request behind them.

## Decision

**B.**  Before 1.0: the framework and three consumers.

1. **Validation** (what `validation/` has meant until now):
   - Is the mesh good enough for engineering answers?  Fittings and case
     studies against experiments, DNS and exact solutions, with
     convergence studies and gates fixed in advance (decisions 0012,
     0015).
   - **OpenFOAM** is the solver.  High fidelity is welcome (volunteer
     cards, decisions 0044 and 0055).
   - A second code may be used *inside* a validation case to separate
     the mesh's share of a miss from the model's.  The tee (0162) in
     code_saturne with SST is the candidate.  That is validation, not an
     export check (after 1.0, proposed).
2. **Export checks:**
   - Does a mesh arrive intact and usable in another code?  **One
     consumer per export format.**
   - Coarse to medium meshes, and exact-answer problems only: laminar
     Poiseuille, or MMS conduction on the fittings.  No experiments, no
     turbulence.
   - **Each check asserts:**
     - the import keeps the cell count, the cell types and the group
       names (as boundaries and cell zones);
     - the solve reaches the exact answer within a tolerance;
     - the order of convergence over two or three levels is the one the
       consumer's discretisation should give.  Where the same problem
       runs in OpenFOAM, its order is shown beside it.
   - **Where they run:** locally (decision 0055: no solver in CI), in a
     pinned container per consumer.  The fast format tests (parsing
     the written file: groups, cell types, counts) run in CI, with no
     solver.
   - **Pass or fail:** export checks have no V1–V4 category.  Their
     status is `passes` or `fails`, with the reason.  A format whose
     check passes loses its "experimental" label for that consumer only.
3. **Consumers before 1.0:**

   | Format | Consumer | Problem | Task |
   |---|---|---|---|
   | `.msh` 4.1, Hex27 | FEniCSx (dolfinx) | MMS conduction, second order (exists) | 0182 moves it |
   | `.unv` | code_saturne | Poiseuille; MMS conduction on the fittings | 0181 |
   | `.su2` | SU2 | Poiseuille (laminar, incompressible) | 0183 |

   **After 1.0, if asked:** CalculiX (`.inp`, conduction), Nek5000
   (`gmsh2nek`, all-hex, decision 0034's proposal), and CGNS (if the pip
   gmsh writes it, checked in 0181) in SU2 or code_saturne.  code_aster
   (`.med`) needs a gmsh built with MED.  `.msh` 2.2 into OpenFOAM is
   checked by every validation case already, so it needs no separate
   check.
4. **Where they live:** `validation/exports/<consumer>/`, each with a
   `case.json` of `"kind": "export"`.  It holds the format, the
   consumer, its image and version, and the checks above.  The gallery,
   the README and `hexmesh/agent/validation.json` show the two kinds in
   separate tables.  The `python3 -m validation run` command (0179) and
   the cards (0055) cover both.  An export check is cheap, so its card
   has no volunteer levels.
5. **1.0:** the export checks join decision 0042's exit criteria.  All
   three consumers above must `pass`, or each failure is reported with
   its cause and the format stays experimental in the docs.  Note on 0042.

## Consequences

- **Task 0182:** the framework:
  - `kind` in the case schema;
  - `validation/exports/`;
  - FEniCSx moved there, keeping its history and results;
  - the separate tables and summaries;
  - the local check runs every export check's coarsest level.
- **Task 0181** widens to a full export check in code_saturne: the import,
  Poiseuille, and MMS conduction on the fittings.  It is now before 1.0.
- **Task 0183:** SU2.
- **Decision 0034:** its FEniCSx case is now an export check (a note).
  **Decision 0055:** *Not decided* is settled for export checks, and the
  second code inside validation stays proposed.  **Decision 0056:** rule
  3's "once" becomes the export check of rule 2 here.  **Decision 0042:**
  a 1.0 criterion added (a note).
- **DESIGN.md:** no change.  The public API: none (`write` already takes
  any extension).
- **Harder:** three more containers to keep pinned, and a slower path
  to 1.0.  Each check stays coarse, so its cost is minutes, not hours.
- **Future expansions:** 0030 (the simulation suite) could later run
  the same consumers.  Not planned.  0018, 0019, 0021, 0035: not
  affected.

## Verified vs. assumed

- **Verified (2026-11-18):** the 14 cases and their categories; the
  FEniCSx case's set-up; which formats gmsh 4.12.1 writes with the
  names.
- **Assumed:**
  - that code_saturne reads gmsh's `.unv` (0181 checks first);
  - that SU2 runs incompressible laminar Poiseuille on gmsh's `.su2`
    with its markers (0183 checks);
  - that both have a container image that can be pinned, or can be
    built and pinned.  Each task records it.

## Note (2026-11-21): a second code inside validation, before 1.0

Rule 1's second code inside a validation case becomes step 3 of
decision 0058's ladder.  It runs before 1.0 on the tee (task 0187).
Rule 3's list gains Nek5000/NekRS (Hex27) before 1.0, as the ladder's
step 5 tool (task 0189).
