# 0198 — The validation stage pipeline: mesh → setup → run → extract → evaluate → plot, proved on Poiseuille

- **Status:** ready
- **Decision:** [0060](../decisions/0060-validation-readable-and-solver-neutral.md)
  point 3
- **Depends on:** none.  Coordinate with 0179 (its `validation run` is
  this task's command).
- **Blocks:** 0200, 0201.  Before 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-28) wants the validation code readable, and
runnable by users of other solvers: "a multi-stage sequence for instance:
mesh, preprocess (setup case), run case, postprocess, visualize".

**Do.**
1. **The framework** (`validation/tools/stages.py` or a package):
   - six stages: `mesh`, `setup`, `run`, `extract`, `evaluate`, `plot`
     (decision 0060's table).  Each is a function that reads its inputs
     from a level's directory and writes its outputs there;
   - **stamps:** each output records the hash of its inputs (files, code
     version, arguments).  A stage is skipped when the stamp matches and
     rerun when it doesn't.  Test that changing an input reruns
     exactly the stages after it;
   - **the command:** `python3 -m validation run <case> [--level L]
     [--stage S | --from S --to S] [--np N] [--keep]`, and `list`.  Take
     over 0179's spec for `run` (reproduce table, exit status, never
     writing the committed `results.json` unless `--store`).
2. **The formats**, each with a JSON schema and a `format` version:
   - `problem.json`:
     - properties;
     - the boundary condition per named group, in physical terms (velocity
       profile, pressure, no-slip, temperature, heat flux);
     - the initial state;
     - steady or transient, with the averaging rule;
     - the sampling (points, lines, planes, slabs, wall faces);
     - each quantity as a formula over the samples;
   - `samples.csv` (or one CSV per sample set), with the layout the
     problem names;
   - `mesh.json`: cells, groups, quality.
   Write them small, and only what Poiseuille needs plus what the bend's
   and tee's quantities will need (lines, slabs).  Say what is left for
   0200.
3. **Shared code** moved into `validation/tools`: `of.num` (already
   shared); the convergence statistics; the time-mean statistics (0186's
   batch means, when it lands); chunked resumable runs (0190's), as a
   helper the `run` stage uses.  Move only what Poiseuille and the next
   two cases use.
4. **Poiseuille converted** end to end:
   - `mesh.py`, `problem.json`, `openfoam.py` (setup, run, extract) and
     `quantities.py`;
   - its stored levels reproduce within the card's tolerances;
   - its volunteer hooks (`prepare`, `run`, `collect`) become wrappers
     over the stages, and the try-out card (0176) still works from both
     the current code and the `volunteer-*` tags;
   - its README shows the six stages and which files each writes.
5. **The line between `extract` and `evaluate`:** test it.  Hand
   `evaluate` a `samples.csv` written by hand from the stored values, and
   get the stored verdict.
6. Docs: `validation/README.md` gets a short "How a case runs" section
   with the stage table.  CHANGELOG (Development).

**Accept.**
- Poiseuille runs stage by stage and whole, reproducing its levels.
- Stamps rerun exactly the downstream stages.
- `evaluate` works from a hand-written samples file.
- The volunteer hooks and the try-out card still work.
- The full suite passes; the local check runs Poiseuille through the
  command.

**Out of scope.**  Converting other cases (0200, 0201); the plots
(0199); bundles (0200).

## Agent notes

## Questions for design

## Outcome
