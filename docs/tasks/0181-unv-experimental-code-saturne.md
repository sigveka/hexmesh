# 0181 — `.unv` as an experimental export, checked in code_saturne; does the pip gmsh write CGNS?

- **Status:** ready
- **Decision:** [0056](../decisions/0056-other-solvers-mesh-formats.md)
- **Depends on:** none.  0178's local check, if it has landed: step 4
  joins it.
- **Blocks:** none.  Docs and tests only (no new API), so it can land
  before or after 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user wants an experimental `.unv` export for ANSYS-type
tools, but has no access to Fluent or STAR-CCM+.  gmsh already writes
`.unv` with the group names (`docs/integrations/gmsh.md`, "Formats for
ANSYS").  code_saturne, which is open source, reads `.unv`, so one real
consumer can check it.

**Do.**
1. **Docs:**
   - README *Use hexmesh* gets one line on other formats;
   - API.md's `write` row lists `.unv` as experimental;
   - the GUIDE gets a short "Other solvers" paragraph.
   Each says what is checked (the groups and hex cells; code_saturne
   after step 4) and what isn't (Fluent, STAR-CCM+).  Warn about Fluent's
   own `.msh` files: same extension, a different format.  No runtime
   warning.
2. **The format test** (`tests/test_unv.py`, CI, no solver):
   - write `equal_tee` (and one layered example, so a second cell zone
     shows) to `.unv`;
   - parse the file directly: dataset 2411 (nodes), 2412 (elements) and
     2467 (groups);
   - check every physical group appears by name, the volume elements are
     I-DEAS type 115 (8-node hexahedra), and their count equals
     `cell_count()`;
   - a read-back with `gmsh.merge` gives the same node and element
     counts.
   Record the I-DEAS dataset numbers and the element type in
   `docs/integrations/gmsh.md`.
3. **CGNS:**
   - in a fresh venv with the pip gmsh (the version `pip install
     hexmesh` gives today), try `write("….cgns")` on the same example;
   - if it writes, check the group names (`h5dump`, or a reader if one is
     at hand) and give it the same label and test;
   - if not, record the build's message in `docs/integrations/gmsh.md`,
     with the version.
4. **code_saturne, locally** (decision 0055: never in CI):
   - pick a pinned container image (record it in a new
     `docs/integrations/code_saturne.md`, with the version);
   - run the preprocessor on the tee's `.unv`;
   - record the cell count against `cell_count()`, the cell types, the
     group names it lists as boundary zones, and its quality summary;
   - **if cheap** (say under half a day): the Poiseuille pipe in
     code_saturne, laminar, Δp against the exact value at two meshes.
     Report it, not gated.  If it works, propose under *Questions for
     design* whether it becomes a validation case.
   - If code_saturne rejects the file, or loses the groups or cells,
     stop and write it under *Questions for design*.
5. CHANGELOG: one line under *Unreleased*.

**Accept.**
- The docs say experimental.
- The format test passes on all CI jobs.
- The CGNS result recorded either way.
- code_saturne's import recorded, with the cell count matching and the
  groups by name, or the failure under *Questions for design*.
- The local check runs the import if 0178 has landed.

**Out of scope.**  A Fluent-format writer (decision 0056 rule 5);
`.neu`, `.inp`, `.su2` labels (they can follow the same pattern if
asked); validating in Fluent or STAR-CCM+.

## Agent notes

## Questions for design

## Outcome
