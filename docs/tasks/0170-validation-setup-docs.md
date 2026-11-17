# 0170 — Validation needs a checkout: say so, on every platform, with a test

- **Status:** ready
- **Decision:** [0054](../decisions/0054-validation-needs-a-checkout.md)
- **Depends on:** none.  Docs and tests only: not part of the 0.8.0
  API work, and not blocking the tag.
- **Blocks:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A user on Windows installed the wheel, ran
`python -m validation.volunteer list` and got `ModuleNotFoundError`.
Validation is repository tooling (decision 0054).  The docs must say so
before they show a validation command, and they must work on Windows.

**Do.**
1. **Find every validation command shown to people:** README, GUIDE,
   API.md, CONTRIBUTING, `validation/README.md`, the case READMEs,
   `VOLUNTEERS.md` (generated: edit its generator in
   `validation/volunteer.py` and the cards), the gallery's Validation
   page and its generator, and the printed hints in `volunteer.py`
   (`PROG`, "next: …" lines).  Record the count in *Agent notes*.
2. **README *Install*:** the three setups of decision 0054, rule 1, as
   short subsections or one table: *use*, *run validation or volunteer*
   (clone a tag, venv, `pip install -e .`, run from the clone's root),
   *develop* (link to CONTRIBUTING).  The platform table's validation
   rows say "from a source checkout".
3. **validation/README.md and VOLUNTEERS.md:** the checkout requirement
   in the first lines, before any command, saying that a `pip install`
   of the wheel is not enough and why (drivers and data live in the
   repository; the mesh check needs the tag's code).
4. **Windows forms** (rule 3).  Give each page one short note, not
   duplicated command blocks: `python`/`py` for `python3`, the venv's
   `.\.venv\Scripts\Activate.ps1`, and `python -m validation.volunteer
   run run/` in place of `bash run/job.sh`.  Check `job.sh`'s hint lines
   in `volunteer.py` too: on Windows, `prepare` should print the
   `run` form.  Check whether `export HEXMESH_OPENFOAM=…` needs a
   PowerShell form (`$env:HEXMESH_OPENFOAM = "…"`).  Anything else
   found that doesn't work on Windows: a note under *Agent notes*,
   and in `docs/integrations/platforms.md` if it is tool behaviour.
5. **Tests** (rule 5), in `tests/test_install.py` (slow, opt-in):
   - **the boundary:** from the installed wheel, with the working
     directory outside the repository, `python -c "import validation"`
     fails, and the wheel holds no `validation/` (the wheel content test
     may already cover the second; extend it if not);
   - **the documented checkout workflow:** from a copy of the checkout
     (or a `git worktree` at HEAD) in `tmp_path`, `pip install -e .`
     into a fresh venv with the system's site packages, then
     `python -m validation.volunteer list` from the copy's root succeeds
     and names the cards' cases.  Run it with the venv's interpreter,
     never `sys.executable`, so the repository's own path can't leak in.
   - A fast test that the README's validation rows and every page from
     step 1 mention the checkout before their first `validation.`
     command (a text check, like the existing README tests).
6. CHANGELOG: an *Unreleased* (or 0.8.0, if not yet tagged) *Docs* line.

**Accept.**
- Every page from step 1 states the checkout requirement before its
  first validation command; the text test passes.
- The Windows note on each validation and volunteer page; `prepare`'s
  hint correct on Windows.
- The two slow tests pass locally, and on the Windows CI job if the slow
  tests run there (say if they don't).
- `validation/` stays out of the wheel; no new public name in `hexmesh`.

**Out of scope.**  Moving any of `validation/` into the package (decision
0054); a console command for volunteers.

## Agent notes

- **Step 2 done by the design session (2026-11-17, the user's request):**
  README *Install* has three subsections (*Use hexmesh*, *Validate or
  volunteer*, *Develop*), each with what you get, what you don't, and a
  check command, plus *Platforms*.  Both checks were run on Linux:
  `python3 -m hexmesh.examples.fittings.equal_tee` (about 7 s) and the
  coarse Poiseuille level in Docker with `--json check.json` (15 s,
  e(Δp) circle +0.451 %).  It also names the Windows `prepare` crash as a
  known issue, with WSL 2 as the way round.  Update that paragraph when
  the crash is fixed.  Steps 3–6 remain.  Step 5's text test can use
  the README's validation subsection as its first case.

## Questions for design

## Outcome
