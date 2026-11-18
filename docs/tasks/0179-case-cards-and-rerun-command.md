# 0179 — A card for every validation case, and `python3 -m validation run <case>`

- **Status:** ready (after 0176, which settles the hooks and the try-out
  level)
- **Decision:** [0055](../decisions/0055-cards-for-every-case-ci-without-openfoam.md)
  rules 1 and 2; [0044](../decisions/0044-volunteer-runs.md) (the card
  and the tool it generalises); [0054](../decisions/0054-validation-needs-a-checkout.md)
- **Depends on:** 0176.  Coordinate with 0168 and 0169, which write cards
  in the same format.
- **Blocks:** none.  Not a 1.0 criterion: it's repository tooling.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-18): "I do want a very easy way to re-run
validation cases."  Today each of the 14 cases has its own `run.py`
flags.

**Do.**
1. **The card format:** generalise `volunteer.json` into `card.json`
   (schema `validation/card.schema.json`).
   - Each level has its requirements (*measured* or *estimated*, as
     0044 says), the OpenFOAM version and image (or other runner) its
     stored result used, and `reproduce` tolerances.  A `volunteer`
     flag says whether it is offered to volunteers; the try-out flag
     comes from 0176.
   - **The volunteer tags:** the `volunteer-helical-*` tags hold
     `volunteer.json`, and `check` must still read contributions made
     from them.  Say how: keep reading the old name, or convert on load.
   - VOLUNTEERS.md lists only the volunteer levels, as now.
2. **The commands**, in `validation/__main__.py` (it may delegate to
   `volunteer.py`):
   - `python3 -m validation list`: every case, its levels, each level's
     cost and runner; the cheapest level of each case first;
   - `python3 -m validation run <case> [--level L | --all] [--np N]
     [--keep]`:
     - prepare, run, collect and compare, in a temporary directory;
     - the result is a table of quantity, stored, re-run, difference
       and tolerance, then **reproduced** or **not reproduced**, with
       exit status 0 or 1;
     - it never writes `results.json`;
     - the run directory is deleted unless `--keep`;
     - it checks the OpenFOAM version against the card, refusing
       another unless `--allow-version`;
     - it prints the case's gates' verdict from the re-run values,
       beside the reproduce result;
   - `python3 -m validation.volunteer` keeps working as now.
3. **Cards for all 14 cases**, cheapest first.  For each one:
   - give the driver `prepare`/`run`/`collect` (the helical and
     Poiseuille drivers are the pattern), leaving `main()` and the stored
     levels unchanged;
   - write the card from the stored levels.  Requirements come from the
     recorded wall times where they exist; otherwise *estimated*, with
     the method;
   - re-run the cheapest level with `validation run` and record its
     time and the reproduce result under *Agent notes*;
   - in one table: case, levels, cheapest level's time, reproduced
     (yes/no), runner.
   - **The v1912 cases** (poiseuille, heated_rod, layered_conduction,
     stenosis): the card pins v1912, as their results were made.  If
     the image is no longer pullable, say so, and put the question
     (re-run on v2406 and re-store?) under *Questions for design*.  Don't
     re-store anything here.
   - **fenicsx_second_order:** its runner is FEniCSx in Docker.  The
     card names that runner, and `run` must handle it, or the card says
     why it can't.
   - **MMS:** its card marks the 16 `<fitting>_k1` levels as the
     local check's fitting levels (decision 0055's note).  `python3 -m
     validation run mms --fitting tee` (or `--level tee_k1`) runs one.
   - **Not reproduced:** a cheapest level that doesn't reproduce goes
     under *Questions for design* with the numbers.  Don't widen a
     tolerance to make it pass.
4. **Docs:**
   - README *Validate or volunteer*: the check command becomes
     `python3 -m validation run poiseuille`;
   - `validation/README.md`: re-running is the first section;
   - each case's README gets one line, its re-run command;
   - keep `test_readme` and 0170's text test green.
5. **Tests (CI, no OpenFOAM):**
   - every `card.json` validates;
   - every card level exists in its driver's `meshes()` or levels;
   - `list` orders by cost;
   - the comparison table and verdict, from fake collected values;
   - `run` refuses another OpenFOAM version without `--allow-version`
     (faked).
6. The local check's step c (task 0178) uses these cards.

**Accept.**
- Every case has a card, and `python3 -m validation run <case>` works on
  each case's cheapest level here.  Step 3's table is complete, with each
  case reproduced or listed under *Questions for design*.
- `results.json` files are unchanged by any re-run.
- Contributions from the volunteer tags still pass `check`.
- The full suite passes.

**Out of scope.**  Other solvers (decision 0055, *Not decided*).
Re-running the expensive levels here.  Changing any case's gates or
stored results.

## Agent notes

## Questions for design

## Outcome
