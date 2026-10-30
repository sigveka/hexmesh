# 0073 — Validation metadata (`case.json`), categories and a coverage matrix in the gallery

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (amendment 2026-10-30: categories)
- **Depends on:** the gallery's validation section (`docs/gallery/build.py`).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Validation cases are listed flat today.  The user asked how
they're categorised; decision 0012 now defines a primary category (V1
exact, V2 high-fidelity simulation, V3 experiment, V4 correlation) and
tags (regime, physics, hexmesh features, toolchain).  A coverage matrix
shows what is validated and what isn't.

**Where.**  `validation/<case>/case.json` (new, every case),
`docs/gallery/build.py` (validation section), a schema
(`validation/case.schema.json`), `docs/tasks/README.md` (ground rule).

**Do.**
1. **Schema** (`validation/case.schema.json`), with `schemaVersion`:
   - `category`: V1–V4;
   - `references`: a list of {citation key, data source, role:
     primary or secondary};
   - `tags`: regime, physics, features from the fixed list in decision
     0012, toolchain;
   - `status`;
   - `gates`: a short list of quantity and limit;
   - `task`.
2. **Backfill** `case.json` for every existing case (poiseuille,
   heated_rod, layered_conduction, heated_pipe, stenosis), from their
   READMEs and RESULTS.  `status` comes from RESULTS' status line.
3. **Gallery:** the validation section groups cases by category (V1 →
   V4), each with its status, tags and links.  Add a **coverage matrix**:
   the hexmesh features down, the cases across, a mark where a case
   exercises a feature, coloured or annotated by status.  Planned cases
   (from `docs/tasks/*validation*`) appear as planned columns if they
   carry a category in their task file (add one line to each validation
   task: `- **Category:** Vn`).
4. **Ground rule** (tasks README): every new validation case ships a
   `case.json`; the gallery fails loudly on a missing or invalid one.

**Accept.**
- Every existing case has a valid `case.json`.
- The gallery page shows the four categories and the matrix.  The
  matrix's empty rows (e.g. `wye`, `duct-tap`) are visible, which is
  the point.
- Full suite unchanged (the gallery isn't part of it); the schema
  validation has a small test.

**Out of scope.**  Running any case; changing gates.

## Agent notes

- **Step 3 refined:** planned columns need features as well as a
  category to carry marks.  Every validation task now has a
  `- **Features:**` line beside design's `Category` line; the gallery
  checks the names against the schema.
- **`physics: conduction` added** to the schema.  Decision 0012 lists
  `flow` and `cht`, but heated rod and layered conduction are solid
  conduction only: no fluid, so not conjugate.  Their `regime` is empty
  (no flow).  See *Questions for design*: not blocking.
- **heated_rod's RESULTS has no `**Status:**` line.**  Its `case.json`
  says `accepted`: task 0033 is done and its one gate is "met"
  (RESULTS).  I didn't edit RESULTS.
- `heated_pipe` (task 0035, in progress) has only `run.py`.  Its
  `case.json` is `in progress`, on v2406 in Docker, per 0035's Q2.  The
  gallery lists it with a `case.json` link only.
- The loader and the matrix live in `docs/gallery/build.py`:
  `case_meta`, `case_dirs`, `planned_cases`, `coverage_md`.  A case is a
  `validation/<dir>` with `run.py`, so `validation/tools/` isn't one.
  `jsonschema` (4.10, installed but not a declared dependency) validates
  the files; the test skips without it.

## Questions for design

**Q1 (not blocking).** Decision 0012's physics tags are `flow` and
`cht`.  I added `conduction` for the solid-only cases (heated rod,
layered conduction).  Keep it in the list, or fold those into `cht`?

## Outcome

Done 2026-10-30.

**Files.**
- `validation/case.schema.json` (new, `schemaVersion` 1).
- `case.json` for all five cases:

  | case | category | status | features |
  |---|---|---|---|
  | poiseuille | V1 | accepted | circle, straight |
  | heated_rod | V1 | accepted | circle, straight |
  | layered_conduction | V1 | accepted | circle, layers, straight |
  | heated_pipe | V1 | in progress | circle, layers, straight |
  | stenosis | V2 | accepted | circle, straight, profiled-reducer |

- `docs/gallery/build.py`: `case_meta` (which fails loudly), `case_dirs`,
  `planned_cases`, `coverage_md`; the validation section is grouped
  V1 → V4.
- `docs/GALLERY.md` rebuilt with `--markdown-only`; only the validation
  section changed.
- A `Features` line in all 11 validation tasks.
- The ground rule in `docs/tasks/README.md`.

**Tests.**
- `tests/test_validation_meta.py`, 5 tests: every case is valid; bad
  fields are rejected; a missing or invalid file stops the gallery;
  planned tasks' features are known; empty rows show.
- Full suite: 2138 passed, 14 skipped, 0 failed (+5).

**What the matrix shows.**
- 8 of the 14 features have no validation case, existing or planned:
  `miter`, `spline`, `transition`, `tee`, `duct-tap`, `wye`,
  `stack-changes`, `projection`.
- `section:rect` and `bend` are only planned (0071, 0072, 0050).
- V3 has only planned cases; V4 has none.

**Follow-ups.**
- Q1 (the `conduction` tag).
- Junction validation: `tee`, `duct-tap` and `wye` are the empty rows
  that matter most for the network use case.  Štigler's tee is listed
  under V3 in decision 0012 but has no task.
- `heated_rod/RESULTS.md` could gain a `**Status:**` line for
  consistency.
