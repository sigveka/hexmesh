# 0166 — Rename the mesh-jargon names

- **Status:** done
- **Decision:** [0053](../decisions/0053-api-hardening-before-freeze.md), amendment item 5 (the table of names)
- **Depends on:** 0164.
- **Blocks:** 0165, the 0.8.0 tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Do.**
1. **Rename by the decision's table**, with no aliases: `nang` →
   `n_arc`, `nang_w`/`nang_h` → `n_width`/`n_height`, `nrad` →
   `n_radial`, `mprg` → `radial_grading`, `mbmp` → `arc_bump`; remove
   `lc` (and its uses: it doesn't affect the mesh; check that no mesh
   changes).  Arguments, attributes and properties, the description's
   fields, the schema, limits' names, error-code `where` fields and
   messages, the CLI's JSON, the advisor's output, the manifest.
2. **Error codes containing an old name** are renamed; list each old →
   new in the CHANGELOG.
3. **Saved descriptions:** old field names migrate on load (a version
   bump with a migration test over one saved description per example).
4. **Internal names** may keep the old spelling where renaming isn't
   worth it; nothing public does.  An architecture test: none of the
   old names appears in `docs/api-1.0.json`, the schema, or a public
   docstring.
5. Docs (README, API.md, GUIDE, the gallery's text), examples
   (byte-identical meshes), `validation/` drivers, the inventory,
   CHANGELOG *Breaking*.  Tell the design session when it lands:
   CLAUDE.md and the decisions' future text use the new names.

**Accept.**  The architecture test; the migration test; examples
byte-identical; full suite and CI green.

## Agent notes

- **Rename (step 1):** a script renamed each old name wherever it is a
  part of a name, not glued to a letter on either side (a plural `s`
  aside), in every tracked text file except the history (decisions,
  tasks, integrations, CHANGELOG before 0.8.0), the design session's
  files (DESIGN.md, CLAUDE.md, RESEARCH.md) and `tests/data`.  About
  5300 uses in 213 files.  Compound names follow (`branch_mprg` →
  `branch_radial_grading`, `insulation_nrad` → `insulation_n_radial`,
  internal `_core_mprg`, `NANG` constants), so nothing keeps the old
  spelling outside the migration.  Generated files regenerated:
  `support.json` (probe), `docs/api-1.0.json`, the gallery pages and the
  README's blocks.
- **The gallery rebuild** also picked up content that was stale before this
  task (the junction-loss case, task 0050's new title), and showed `\v{S}}tigler`:
  `build.py`'s `cite` now turns BibTeX accents into letters (Štigler).
- **`lc` (step 1):** removed from the public calls and from the
  plumbing below them: the fitting protocol's `fill(faces, frames,
  spec)`, `build_face`, the section builders, `CrossSection`, and
  `add_point`, which now leaves gmsh's point size at its default.
- **Error codes (step 2):** five renamed, listed in the CHANGELOG.
- **Migration (step 3):** description version 3.  `intent.upgrade`
  takes version 2 to 3 by renaming every key as a name part and
  dropping `lc`; version 1 goes through 2.
  `tests/data/examples_v2.json` holds the 35 examples' descriptions as
  saved before this task (version 2, from a worktree at fcb5d42); a test
  loads each and compares it with what the example builds today.
- **Architecture (step 4):** `test_no_retired_name_in_the_public_api`
  (the inventory, which holds the public docstrings, and the error
  codes; no `lc` parameter), and `test_schema_uses_the_1_0_names`.
- **Found on the way:** three `test_orientation` tests still expected
  the tee's `main` port (0164); fixed in cd14b1c.

## Questions for design

## Outcome

- **Done** (2026-11-17): the decision's table, with no aliases.  `lc` is
  removed from the API and from the plumbing below it.  Five error codes
  renamed (CHANGELOG).  Description version 3, migrating version 2 (and 1
  through it).
- **Files:** about 230: the package, tests, examples, validation drivers
  and their stored results, benchmarks, API.md, GUIDE, README, the gallery
  (regenerated), `support.json` (probed), `docs/api-1.0.json`; new
  `tests/data/examples_v2.json`.  The validation results files are
  re-written as the store writes them (renamed keys sort differently), and
  their figures redrawn, because a figure records its results file's
  hash.
- **Tests:** `test_intent.py` +36 (35 examples load from version 2 as they
  build today; the key renaming), `test_architecture.py` +2 (no retired
  name in the inventory or the error codes; the pattern), and
  `test_agent_schema.py` +1.  Full suite on one worker (beside a CFD run):
  4622 passed, 16 skipped, 36 failed.  The 36 had three causes, all fixed:
  three tests passed `lc` positionally (`build_face`, `build_oh_circle`),
  ten results files needed re-writing, and 25 figure checks followed from
  those.  The four failing files then passed: 172 passed, 1 skipped.
- **Examples:** all 35 byte-identical (meshes, recipe block left out)
  with the worktree at fcb5d42, so removing `lc` (gmsh's point size,
  now its default) changes no mesh.
- **Left with the old names, as history or the design session's:**
  DESIGN.md, CLAUDE.md, docs/RESEARCH.md, decisions, tasks,
  docs/integrations, and the CHANGELOG before 0.8.0.
- **Also:** the gallery's `cite` now renders BibTeX accents (Štigler); the
  rebuild picked up the junction-loss case and task 0050's new title.
