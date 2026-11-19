# 0182 — Export checks: the framework, and FEniCSx moved into it

- **Status:** done
- **Decision:** [0057](../decisions/0057-two-kinds-validation-and-export-checks.md)
  rules 2 and 4
- **Depends on:** none.  Coordinate with 0179 (cards) and 0178 (local
  check): this task adds `kind`, and they read it.
- **Blocks:** 0181, 0183 (they add their checks here); 1.0 (decision
  0057 rule 5).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-18) split validation into two kinds:
OpenFOAM validation of fittings and cases, and export checks that a mesh
arrives intact in another code.  Today the one export check
(`fenicsx_second_order`) sits among the physics cases.

**Do.**
1. **Schema:** `validation/case.schema.json` gets `kind`, either
   `validation` (the default, so the existing files are unchanged) or
   `export`.  An export check has:
   - `format` (e.g. `.unv`) and `consumer` (name, image, version);
   - status `passes` or `fails`, with no V-category (decision 0057
     rule 2);
   - `checks`: the import (cell count, cell types, groups), the exact
     answer, and the order.
   Validate both kinds in the existing meta test.
2. **Move FEniCSx** to `validation/exports/fenicsx/`, with `git mv` so
   the history follows.
   - Its `case.json` becomes `kind: export`, with format `.msh` 4.1
     (Hex8 and Hex27) and consumer dolfinx v0.11.0.  Its results and
     figures are unchanged.
   - Update every link to its old path: README, gallery, RESEARCH §7.15,
     decision 0034 via a note (the design session writes that), and
     task 0077 (leave historical task text, but fix links).  `python3 -m
     validation.tools.recheck` must still find it.
3. **Tables:** the README's validation table, the gallery's VALIDATION
   page and FEATURES lists, and `hexmesh/agent/validation.json` show the
   two kinds apart:
   - *Validation*: the existing columns;
   - *Export checks*: format, consumer, checks, status.
   The generators (`docs/gallery/build.py`, `validation.tools.summary`)
   do it.  Their stale-file tests pass.
4. **Local check** (if 0178 has landed): a step that runs every export
   check's coarsest level.  Otherwise leave a note for 0178.
5. **A CI format test helper**, shared by 0181 and 0183: write an
   example to a format, then assert group names, cell types and the
   cell count by parsing the file.  No solver.  The `.unv` parser can
   come with 0181.  Here, the helper and a `.msh` 4.1 test.
6. CHANGELOG *Unreleased* (Docs): one line.

**Accept.**
- `fenicsx_second_order` is in `validation/exports/fenicsx/` with its
  history.
- The tables show two kinds, and the summary tests pass.
- No validation case changed category or status.
- The full suite passes.

**Out of scope.**  New consumers (0181, 0183); the tee in a second code
(decision 0057 rule 1, after 1.0).

## Agent notes

- **The name stays `fenicsx_second_order`** (2026-11-19); the directory
  is `validation/exports/fenicsx/`.  `figure.png` embeds the SHA of
  `results.json` and the case names it was drawn from.  Renaming the
  case would change `results.json` (its `case`) and make the figure
  stale, against "results and figures unchanged".  So an export check's
  `case.json` carries `name`, and `validation/tools/cases.py` maps a
  name to its directory: a validation case is named by its directory,
  an export check by `name`.  recheck, plots, the summary and the
  gallery all find cases through it, and take the repository root as an
  argument, since tests patch it.  `python3 -m validation.tools.recheck
  fenicsx_second_order` works as before.
- **Step 1:** `kind` (`validation` when absent), and for `export`:
  - `name`, `format` (`extension`, `version`, `elements`), `consumer`
    (`name`, `image` pinned by digest, `version`), and `checks`
    (`import`, `exact`, `order`, each a sentence with its limit);
  - status `passes` or `fails`, and `reason` required with `fails`;
  - no `category` or `gates`.

  A validation case may not carry the export fields.  `if`/`then`/`else`
  in the schema; every existing `case.json` validates unchanged.  The
  meta test checks both kinds, and seven bad export files are rejected.
- **The import check is now asserted.**  FEniCSx's recheck gained a gate:
  dolfinx's stored cell count equals `cell_count()` at every level,
  18/18.  `cell_count()` needs no gmsh.  Before, the count was stored
  but not compared.  Cell types and group names are checked on the
  written file by step 5's test.
- **`exact`, honestly:** FEniCSx has no absolute-tolerance gate.  Its
  errors are reported per level, and the order gate is on them.
  `checks.exact` says so (a follow-up below).
- **Step 2:** `git mv` (the history follows: `git log --follow`).
  - `run.py`: ROOT is now `parents[2]`; paths and docstring updated.
  - `README.md` and `RESULTS.md`: paths; status *passes* (accepted in
    0077); no V1.
  - `.gitignore`: `validation/exports/*/work/`.
  - Links updated in `validation/README.md` (FEniCSx's row is now its
    own export-check table), RESEARCH §7.15's path,
    `docs/integrations/fenicsx.md` and task 0077 (a "now" note beside
    the old path; the history is left as written).
  - Decision 0034's note: for the design session.
- **Step 3:**
  - The gallery (`docs/gallery/build.py`): `export_dirs()` beside
    `case_dirs()`; the VALIDATION page's *Export checks* section (a
    table: format, consumer, checks, status; then each check's images
    and files); FEATURES' *Validated by* lists export checks under their
    own heading; the landing page counts them apart.
  - The README's generated block: a second table (check, format,
    consumer, result, status).
  - `hexmesh/agent/validation.json`: `cases` and `features` are
    validation only; `exports` holds each check (title, status, task,
    format, consumer, checks, features, levels, cells).  API.md's
    manifest row says so.
  - `planned_cases` counts an export check's task as done, so 0077
    doesn't reappear as planned.
  - Regenerated with `--markdown-only` and `validation.tools.summary`.
- **Step 4:** 0178 hasn't landed; a note in its *Agent notes*: the
  command and the lookup.
- **Step 5:** `tests/test_export_formats.py`.
  - `check_written(asm, path, read, order=)` meshes the assembly, writes
    the file, and parses it with the format's reader.  It asserts the
    group names, each group's cell types and counts, and the volume
    count against `cell_count()`.
  - `read_msh41` reads ASCII 4.1 (`$PhysicalNames`, `$Entities`,
    `$Elements`).
  - Tested on FEniCSx's straight, bend and tee at Hex8 and Hex27, plus a
    reader that drops a group (the check fails).
  - 0181 and 0183 add a reader and a test each.

## Questions for design

## Outcome

- **Files:**
  - New: `validation/tools/cases.py`, `tests/test_export_formats.py`.
  - Moved: `validation/fenicsx_second_order/` →
    `validation/exports/fenicsx/` (case.json as an export check; recheck
    with the import gate; README and RESULTS paths and status).
    `results.json`, `figure.png` and `img/` are byte-identical.
  - Changed: `validation/case.schema.json`; recheck, plots and summary
    in `validation/tools/`; `docs/gallery/build.py` and its pages;
    README; `hexmesh/agent/validation.json`; API.md; `validation/README.md`;
    `.gitignore`; RESEARCH (one path); `docs/integrations/fenicsx.md`;
    task 0077 (one note); task 0178 (step 4's note); CHANGELOG
    *Unreleased* (Docs).
  - Tests changed: `tests/test_validation_meta.py`,
    `tests/test_agent_manifest.py`, `tests/test_convergence.py` (scans
    `exports/` too).
- **Tests:** 9 new: 7 format tests and 2 meta tests.  Locally, `-n 1`,
  the affected modules pass: 361 passed (`test_validation_meta`,
  `test_agent_manifest`, `test_convergence`, `test_readme`,
  `test_export_formats`, `test_architecture`, `test_api_inventory`,
  `test_volunteer`, `test_agent_schema`).  The full suite is left to CI.
- **Accept:** FEniCSx is in `validation/exports/fenicsx/` with its
  history.  The tables show two kinds, and the summary tests pass.  No
  validation case changed category or status: 12 accepted and 1 missed,
  as before less FEniCSx, which goes from accepted to passes.
- **Follow-ups for design:**
  - Decision 0034's note.
  - Whether an export check needs an absolute-tolerance gate on the
    exact answer, beyond the order (decision 0057 says "within a
    tolerance"; FEniCSx has none).
  - `tags.toolchain` is still required with `openfoam` or `fenicsx`, so
    0181 and 0183 must widen it for code_saturne and SU2, or the schema
    could let `consumer` replace it for an export check.
- **CI:** green on all 8 jobs at e64ff49 (run 44595951544); promoted,
  `main` is e64ff49.
