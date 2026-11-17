# 0054 — Validation runs from a source checkout; the docs say so first

- **Status:** accepted (2026-11-17, by the user: "Checkout-only, docs fixed")
- **Date:** 2026-11-17
- **Tasks:** 0170

## Context

A report from use on Windows (the user, 2026-11-17).  A clean venv,
`pip install "hexmesh @ git+…@v0.6.0"`, then
`python -m validation.volunteer list` fails with `ModuleNotFoundError`:
the wheel holds `hexmesh/` only (`pyproject.toml`, `include =
["hexmesh*"]`), and `validation/` is importable only from the repository
root.  The report asks the question to settle first: is volunteer
validation part of the installed product, or repository tooling?

What the docs say today (checked 2026-11-17):
- `validation/VOLUNTEERS.md` and `validation/README.md` both start from
  a clone and `pip install -e .`.  So the requirement is written down,
  but only on the pages a reader reaches after the README.
- README *Install* lists the wheel and git installs first, then a table
  with "studies and validation … yes" on every platform, and never says
  validation needs a checkout.  That is the likely route to the report.
- The commands are written `python3 …` and `bash run/job.sh`.  On
  Windows the interpreter is `python` (or `py`), and `bash` from a
  prompt can be WSL's launcher (`docs/integrations/platforms.md`).
  `python -m validation.volunteer run run/` does the same as `job.sh`
  without bash, but the docs don't offer it.

What validation is: 12 MB of drivers (`validation/<case>/run.py`),
cards, reference data, figures and results, plus tools
(`validation/tools/`) used by CI and the gallery.  A volunteer's mesh
check compares a fingerprint, so it needs exactly the tagged meshing
code, which a clone of the tag gives.

## Options

### A. Repository tooling; the docs fixed
Validation, volunteer runs included, needs a source checkout of the
tag.  The docs separate three setups and say so before any validation
command.

### B. Package the volunteer tooling now
Move the volunteer CLI, drivers, cards and reference data into
`hexmesh` (`hexmesh.validation`, a console command).  Volunteers would
need only a wheel.  It costs a larger wheel, drivers frozen as public
surface at 1.0, and one more task before the 0.8.0 tag, for a trial
with no volunteers yet.

### C. A, plus a recorded plan to package in 1.x
The same work as A now, with B recorded as the expected next step.

## Decision

**A.**  Validation is how the project checks itself.  Volunteers are
contributors, and they work from a clone of the tag the card names.
Nothing under `validation/` moves into the package.

1. **Three setups, named alike everywhere:**
   - *Use hexmesh*: `pip install` of the wheel or the git URL.  Meshing,
     writing, `hexmesh.study`.
   - *Run validation or volunteer*: a clone of a tag, then
     `pip install -e .` in a venv, run from the clone's root.  Plus
     OpenFOAM, as validation/README.md describes.
   - *Develop*: the same clone, `pip install -e ".[dev]"`, as
     CONTRIBUTING.md has it.
2. **README *Install*** shows the first setup.  Its platform table's
   validation rows say "from a source checkout" and link to the second
   setup.  No page shows a `validation.*` command before saying it needs
   the checkout.
3. **Windows.**  Each validation and volunteer page says how its
   commands read on Windows: `python` (or `py`) for `python3`, and
   `python -m validation.volunteer run run/` for `bash run/job.sh`.
   The task checks which other lines need a Windows form.
4. **No placeholder module.**  The installed `hexmesh` doesn't add a
   `validation` stub to explain the error: it would be public surface.
   The README line of rule 2 sits where people look first.
5. **A regression test** of the documented checkout workflow, and of
   its negative: from an installed wheel, run outside the repository,
   `validation` is not importable.  This guards the package boundary,
   so validation can't leak into the wheel by accident, and the docs'
   claim that the wheel isn't enough.

Packaging the volunteer CLI stays possible in 1.x as an addition.  It
isn't planned; a request from a real volunteer would reopen it.

## Consequences

- **Task 0170** does the docs, the Windows forms and the tests.  It is
  docs and tests only, so it can land before or after the 0.8.0 tag.
- **DESIGN.md:** no change.
- **Easier:** the package boundary is a written rule, with a test.
  **Harder:** a volunteer needs git and a clone (they did already).
- **Future expansions:** 0030 (the simulation suite) is `hexmesh.study`,
  installed, and unaffected; validation drivers are not its API.  0018,
  0019, 0021, 0035: not affected.

## Verified vs. assumed

- **Checked (2026-11-17):** `pyproject.toml`'s package list and package
  data; README *Install* and its table; the clone lines in VOLUNTEERS.md
  and validation/README.md; `cmd_run` in `validation/volunteer.py` (it is
  what `job.sh` calls); the `bash` finding in
  `docs/integrations/platforms.md`; `du -sh validation` (12 MB).
- **Assumed:** that the reporter followed README *Install* rather than
  VOLUNTEERS.md.  The report doesn't say which page they used.  The fix
  covers both.
