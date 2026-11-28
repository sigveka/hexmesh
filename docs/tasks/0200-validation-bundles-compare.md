# 0200 — Bundles for other solvers and `validation compare`: Poiseuille, the bend and the tee

- **Status:** ready (after 0198; the tee after 0186 and 0187)
- **Decision:** [0060](../decisions/0060-validation-readable-and-solver-neutral.md)
  point 4
- **Depends on:** 0198 (the stages and formats).  0186/0187 for the tee,
  whose runs are in flight on today's driver.
- **Blocks:** none.  Before 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-28) wants the validation cases "to run for
other exporters": a user of another solver should be able to run a case
and get the same verdict.

**Do.**
1. **Convert the bend and the tee** to stages (0198's form):
   - `mesh.py`, `problem.json`, `openfoam.py`, `quantities.py`;
   - the precursor, chunked runs and time means from `validation/tools`;
   - every stored level reproduces from its stored fields within the
     card's tolerances, by `evaluate` on re-extracted samples where the
     fields exist, or by rerunning the cheapest level;
   - the volunteer cards and tags keep working.
2. **The bundle** per case (`python3 -m validation bundle <case> [--level
   L]`, also on the docs site):
   - the mesh in each checked format (`.msh` 2.2/4.1, `.unv`, `.su2`,
     CGNS where the gmsh build has it), with the group names;
   - `problem.json`;
   - the reference as CSV;
   - the samples layout and an example `samples.csv`;
   - a README: what to run, and what each boundary condition means in
     OpenFOAM, code_saturne, SU2 and Fluent terms (a table; Fluent named
     only from its documentation, as decision 0056 says).
3. **`python3 -m validation compare <case> <samples.csv> [--level L]`:**
   the verdict against the same gates, the same table as `run`, and the
   standard plots (0199) with the user's values beside ours.
4. **Test the vocabulary against a second solver:**
   - Poiseuille's bundle in code_saturne and SU2, from their existing
     export checks (0181, 0183), producing `samples.csv` and passing
     `compare`;
   - say what `problem.json` lacked, and fix it.
   The bend and the tee in a second solver are 0187's step 3 (the tee in
   code_saturne), which should use this bundle if it lands first.
5. Docs: the validation README's "Run a case in your own solver"
   section; the sheet (0199) links each case's bundle.  CHANGELOG.

**Accept.**
- Three bundles.
- `compare` gives the stored verdict from our own samples.
- Poiseuille passes `compare` from code_saturne and SU2.
- The bend's and the tee's levels reproduce on the converted drivers.

## Agent notes

## Questions for design

## Outcome
