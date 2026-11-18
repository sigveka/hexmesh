# 0056 — Meshes for other solvers: `.unv` experimental, checked with code_saturne; no Fluent writer for now

- **Status:** accepted (2026-11-18, the user)
- **Date:** 2026-11-18
- **Tasks:** 0181

## Context

The user (2026-11-18) asked whether gmsh can make ANSYS-valid meshes,
then: "We should have an experimental (un-validated) unv writer, how
about star-cc?", and: "I do not have access to fluent or star-ccm+".

What the design session found (`docs/integrations/gmsh.md`, "Formats for
ANSYS", 2026-11-18):
- `write(path)` passes any extension to `gmsh.write`.
- `.unv` (I-DEAS universal), `.neu` (GAMBIT), `.inp` (Abaqus) and `.su2`
  keep the physical group names.  `.bdf` (NASTRAN) loses them.
- The gmsh build here writes no `.cgns` or `.med`, and gmsh has no ANSYS-
  native writer (`.cdb`).
- Fluent imports `.unv`, GAMBIT and CGNS (its documentation, not tested).
- For STAR-CCM+, no source found lists `.unv`.  Forum reports name its own
  formats, CGNS and Fluent's mesh format as the volume-mesh routes.  Its
  documentation page couldn't be reached.
- Neither Fluent nor STAR-CCM+ is available to the project.
- **code_saturne** (EDF, open source, GPL) reads I-DEAS universal
  volume meshes with groups: tetrahedra, prisms and hexahedra (its user
  guide's file formats).  So it can check a `.unv` in a real solver.

## Options

- **A. Document `.unv` as experimental; no check.**
- **B. A, plus a format test and one check in code_saturne (chosen).**
  `.unv` gets a real consumer, as second-order export got FEniCSx
  (decision 0034).
- **C. B, plus a Fluent-format writer** (an ASCII mesh with cells, faces
  and named zones), which reaches both Fluent and STAR-CCM+.  It would be
  new public API, after the 0.8 freeze, and couldn't be tested in either
  solver here.
- **D. CGNS through gmsh**, if the pip gmsh writes it: both commercial
  codes import CGNS.

## Decision

**B, and D's check.**
1. **`.unv` is experimental.**
   - `write("…unv")` keeps working as it does, with no new API.
   - The user docs (README, API.md's `write` row, GUIDE) say it is
     experimental: written by gmsh, keeps the groups, checked in
     code_saturne (once task 0181 has), and not checked in Fluent or
     STAR-CCM+.
   - No runtime warning, as decision 0034's note of 2026-11-10 put it
     for second order: docs only.
2. **A format test in CI** (no solver): an example written to `.unv`
   carries every physical group by name, and its volume cells are
   8-node hexahedra (I-DEAS element 115) in the expected number.  It
   reads the file directly.  A read-back through gmsh is a second check.
3. **code_saturne, once, as a local check** (decision 0055: no solver in
   CI):
   - import the tee example's `.unv` with code_saturne's preprocessor
     in a pinned container;
   - check the cell count, that every cell is a hex, that the groups
     became boundary zones by name, and its mesh quality report;
   - if it is cheap, a laminar Poiseuille pipe solved in code_saturne
     against the exact Δp.  That would make `.unv` a validated path.
   - Record it in `docs/integrations/code_saturne.md`.
   - "Experimental" stays for Fluent and STAR-CCM+, whatever
     code_saturne shows.
4. **CGNS:** check whether the pip gmsh (4.15.x) writes `.cgns` with
   the group names.  If it does, it gets the same experimental label and
   the same format test.  It is then the suggested route for STAR-CCM+
   and Fluent in the docs.
5. **No Fluent-format writer** until someone with Fluent or STAR-CCM+
   asks and can check an import.  If it comes, it is a 1.x addition.

## Consequences

- **Task 0181:** the docs label, the format test, the CGNS check and the
  code_saturne import.
- **DESIGN.md:** no change.
- **The 1.0 freeze:** unaffected.  No new public name.
- **Future expansions:** decision 0055's *Not decided* (other solvers)
  gains code_saturne as a candidate secondary solver.  Its V1 cases
  would be a local check, never CI.  0018, 0019, 0021, 0030, 0035: not
  affected.

## Verified vs. assumed

- **Verified (2026-11-18):** what gmsh 4.12.1 writes and which formats
  keep the names (the tee example); no CGNS or MED in that build; no
  `.cdb` writer.
- **Assumed:**
  - Fluent's `.unv` and GAMBIT import, from its documentation as
    commonly described;
  - that code_saturne reads gmsh's `.unv` (its documentation says it
    reads I-DEAS universal; not tried);
  - whether the pip gmsh has CGNS.
