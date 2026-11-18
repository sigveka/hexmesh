# 0182 — Export checks: the framework, and FEniCSx moved into it

- **Status:** ready
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

## Questions for design

## Outcome
