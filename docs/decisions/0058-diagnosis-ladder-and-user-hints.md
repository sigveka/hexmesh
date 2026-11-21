# 0058 — When a validation case misses: a diagnosis ladder, and what it finds becomes hints for users; before 1.0

- **Status:** accepted (2026-11-21, the user)
- **Date:** 2026-11-21
- **Tasks:** 0187, 0188, 0189

## Context

The user (2026-11-21): "If OpenFoam fails to meet a criteria, can we
try a higher order solver to check whether it is the mesh, problem setup
or solver accuracy causing failure?", then: "I want it before 1.0 to
show that we are striving for quality and improve the hints provided by
hexmesh for potential users".

Today:
- **The tee misses** (`junction_loss`, 0162): ξ_PG about 0.1 above the
  measurement with SST and with k–ε.  Its grid convergence isn't shown,
  because `refined(k)` shrank the wall cell (RESEARCH §7.2 correction,
  task 0186).
- **The bend** (0050) passes its gates at `refined(k)`'s k = 3.  But its
  levels changed the wall model, and the fixed-wall family doesn't
  settle at level 2 (Q3).
- **One cause is already separated with a second code:** code_saturne
  on the MMS meshes (0181) showed that OpenFOAM's `fixedValue` wall
  gradient, not the mesh, holds five fittings near first order
  (RESEARCH §7.14).
- **Lessons found so far live only in task files and RESEARCH:**
  - `refined(k)` with `first_cell` moves y⁺;
  - steady RANS plateaus in the bend;
  - `potentialFoam` blows up in thin wall cells;
  - a decomposed precursor floors its residuals;
  - `fixedValue` is first order on sloped walls.
  A user meets none of them before they make the same mistake.
- **The advisor** (`hexmesh.agent` `advise`, decision 0040) refuses
  wall functions until they're validated (`advice_wall_function_unsupported`).
- **A higher-order solver separates only discretisation error.**  For
  RANS, the model usually dominates.  High-order codes ship different
  turbulence models (NekRS: k–τ, not SST).  Higher order pays off for
  laminar, MMS and scale-resolving cases, and for checking curved
  geometry.  NekRS/Nek5000 is spectral-element, all-hex and curved: it
  takes hexmesh's Hex27 export (decision 0034 proposed it).

## Options

- **A. Report misses as they are** (today's rule, decisions 0012/0015).
- **B. A fixed ladder of checks for every miss, before 1.0, and its
  findings written as user hints (chosen).**  Each step changes one
  thing, so what moves names the cause.
- **C. B with LES or DNS at step 4 for every miss.**  Not on this
  machine; it becomes a volunteer card where the case has one.

## Decision

**B.**
1. **The ladder.**  A case that misses a gate, or doesn't converge,
   climbs it in order.  It stops at the step that explains the miss.
   1. **Converged?**  Iterations (residuals, not plateau means), and
      the grid with the model held fixed: with wall functions, the wall
      cell fixed (0050's lesson).
   2. **Setup?**  Sensitivity to the inlet (profile, length), the
      outlet and the domain length, at a mid level.  Each change is one
      run beside the base.
   3. **Solver?**  The same model on the same mesh in a second code:
      code_saturne (k–ω SST, through `.unv`, the 0181 set-up).  Where
      the two codes' wall functions differ, say how.
   4. **Model?**  A second RANS model in OpenFOAM, as 0162 did with k–ε.
      LES only as a volunteer card.
   5. **Discretisation, finally?**  A higher-order code on the curved
      Hex27 mesh: NekRS or Nek5000.  For RANS cases it applies only if
      steps 1–4 leave the mesh suspected.  For laminar and scale-
      resolving cases it is the direct check.
   Each step's result goes into the case's RESULTS.md, in a section
   *Why it misses*, with a one-line verdict per step: explains it, part
   of it, or rules it out.  The gates, the verdict and the
   rules-fixed-before-the-run principle (decision 0015) don't change.
   The ladder explains a miss; it never turns a miss into a pass.
2. **Before 1.0, on the cases that need it:**
   - **the tee** (`junction_loss`): steps 1–4 (0186 is step 1;
     task 0187 is the rest);
   - **the bend** (0050): step 1 as Q3's answer says.  Steps 2–4 only if
     its gates miss on the family that settles.
   - **Step 5's tool:** NekRS or Nek5000 as an export check for Hex27
     (decision 0057 rule 2: import, laminar Poiseuille, the order),
     task 0189.  That makes step 5 usable.  Its first use is the laminar
     cases, to show that the curved mesh carries a high-order solve.
3. **Hints from the findings (task 0188).**  Every lesson that a user
   could repeat becomes a hint, where users look:
   - a **GUIDE section** "From our validation: what to watch", one
     paragraph per lesson, each linking the case that found it;
   - **docstrings** where the trap is: `refined()` says it splits
     the wall cell.  For wall functions, fix the wall cell and refine
     the rest; show how.
   - **per case, in `hexmesh/agent/validation.json`**: a `lessons` list,
     so agents get the same advice;
   - **the advisor:** once 0050 and 0186 show a fixed-wall family that
     converges, decide whether `advise` accepts wall functions (with
     the wall cell fixed).  That is a question for design then, not
     now.
   - **No behaviour change to frozen API** (decision 0053).  A new
     runtime warning, if one is proposed, comes as a question for
     design.
4. **1.0:** decision 0042's exit row gains the ladder:
   - the tee's steps 1–4 reported;
   - the bend reported per Q3;
   - the Hex27 export check in NekRS or Nek5000 passing or reported;
   - the hints in place.
   Note on 0042.

## Consequences

- **Tasks:** 0187 (the tee's ladder: steps 2–4; 0186 stays step 1),
  0188 (hints), 0189 (the Nek export check, step 5's tool).
- **Decision 0057:** rule 1's "second code inside validation" moves
  before 1.0, as the ladder's step 3 (a note).  Its export-check list
  gains Nek5000/NekRS before 1.0, through 0189.  **Decision 0034:** the
  Nek proposal is taken up (a note).  **Decision 0042:** a note.
- **DESIGN.md:** no change.
- **Harder:**
  - 1.0 moves later: the tee's steps 2–3 cost about a day of runs;
  - another container to pin (Nek);
  - code_saturne's SST set-up is new.
- **Future expansions:**
  - 0018 (vascular): its laminar and pulsatile cases are where step 5
    pays off most.
  - 0030 (simulation suite): it may reuse the ladder for users'
    studies.  Not planned.
  - 0019, 0021, 0035: not affected.

## Verified vs. assumed

- **Verified (2026-11-21):**
  - the misses and their state (0162, 0050 Q2–Q3, 0186);
  - code_saturne reads our `.unv` and solved MMS on all 16 fittings
    (0181);
  - the advisor refuses wall functions.
- **Assumed:**
  - that code_saturne's SST with its wall functions runs the tee at k = 2
    on this machine;
  - that Nek5000 or NekRS builds and runs on CPU here, and reads
    gmsh's Hex27 through `gmsh2nek` (0189 checks first, with a stop
    rule).
