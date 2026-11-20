# 0181 — Export check: `.unv` in code_saturne (experimental until it passes); does the pip gmsh write CGNS?

- **Status:** done (2026-11-20; the local check's part handed to 0178)
- **Decision:** [0056](../decisions/0056-other-solvers-mesh-formats.md);
  [0057](../decisions/0057-two-kinds-validation-and-export-checks.md)
  (export checks, widened 2026-11-18)
- **Depends on:** 0182 (the framework and the format test helper).
  0178's local check, if it has landed: step 4 joins it.
- **Blocks:** 1.0 (decision 0057 rule 5).  No new API.

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
   - **Widened by decision 0057:** this is now a full export check in
     `validation/exports/code_saturne/` (`kind: export`):
     - the import as above;
     - Poiseuille at 2–3 levels against the exact Δp, with its order
       (not optional any more);
     - MMS conduction on the fittings, coarse to medium, with the MMS
       case's manufactured solution and its order.  Use code_saturne's
       user source term, and show the OpenFOAM MMS order beside it.  At
       least straight, bend, tee and one wye; all 16 if cheap.
     - The status is `passes` or `fails` (decision 0057 rule 2).  Its
       coarsest level joins the local check.
   - If code_saturne rejects the file, or loses the groups or cells,
     write it under *Questions for design*.  The status is then
     `fails`.
5. CHANGELOG: one line under *Unreleased*.

**Accept.**
- The docs say experimental.
- The format test passes on all CI jobs.
- The CGNS result recorded either way.
- code_saturne's import recorded, with the cell count matching and the
  groups by name, or the failure under *Questions for design*.
- Poiseuille and the MMS fittings reported with their orders.  The
  export check's status is set.
- The local check runs the import if 0178 has landed.

**Out of scope.**  A Fluent-format writer (decision 0056 rule 5);
`.neu` and `.inp` labels (they can follow the same pattern if
asked; `.su2` is task 0183); validating in Fluent or STAR-CCM+.

## Agent notes

- **Step 2:** gmsh writes the groups as dataset **2477**, not 2467; the
  test parses 2477 (`docs/integrations/gmsh.md`).
- **Step 3, CGNS:** the system gmsh 4.12.1 has no CGNS; the pip wheel
  4.15.2 writes it, with a `Family_t` per entity named after its group,
  and `gmsh.merge` reads the groups back.  `tests/test_export_formats.py`
  checks it where gmsh has CGNS and skips elsewhere.  Not tried in a CGNS
  consumer, so no label beyond "written".
- **Step 4, the image:** `simvia/code_saturne:9.2.0`, pinned by digest
  (`docs/integrations/code_saturne.md`).  User sources need C++ linkage,
  and boundary types set face by face; the steady algorithm cycled on
  the pipe, so Poiseuille is time-marched.
- **Step 4, MMS:** all 16 non-diagnostic MMS cases (cheap: 24 min for
  the 48 runs on one core), as a frozen-flow user scalar
  (`src/cs_user_mms.cpp`), `validation/mms`'s field, wave numbers and
  meshes at k = 1, 2, 4.  The import is gated per level, every group by
  name and size; orders are reported, as in `validation/mms`.
- **One driver, one card:** the MMS levels live in the same
  `results.json` as Poiseuille (`mms_<case>_k<k>`, with a `case` key);
  the volunteer hooks cover the Poiseuille levels only.
- **Step 4, "joins the local check":** 0178 hasn't landed; noted in its
  *Agent notes*.

## Questions for design

## Outcome

- **Passes.**  code_saturne 9.2.0 reads every cell and group of the
  `.unv`: the equal tee (8000 cells, every group by name and size), the
  Poiseuille pipe at k = 1, 2, 3 and the 16 MMS fittings at k = 1, 2, 4.
- **Poiseuille:** Δp +1.65 %, +0.40 %, +0.18 % (gate 2 %); order 2.05,
  GCI 0.22 %.
- **MMS (for RESEARCH §7.14):** code_saturne's L2 order in the fitting
  under test, k 2→4, is 1.85–1.99 on 12 of the 16 fittings, including
  the miter (1.97), reducer (1.85), transition (1.94), tee (1.97) and
  tee with shells (1.95), where OpenFOAM's is 1.14, 0.95, 0.97, 1.03,
  1.04 on the same meshes.  It confirms task 0109's cause from the other
  side: the meshes support second order there; OpenFOAM's `fixedValue`
  wall gradient loses it.  The wyes stay low in both (code_saturne
  0.27–0.49, OpenFOAM 0.34–0.51): `n_split` isn't refined.  The duct taps
  converge at k = 4 here (1.87), where OpenFOAM's didn't.
- **Files:** `validation/exports/code_saturne/` (`run.py`,
  `src/cs_user_poiseuille.cpp`, `src/cs_user_mms.cpp`, `case.json`,
  `README.md`, `RESULTS.md`, `results.json`, `figure.png`,
  `img/mms.png`); `tests/test_unv.py` (new);
  `tests/test_export_formats.py` (CGNS); `docs/integrations/code_saturne.md`
  (new), `gmsh.md` (`.unv` datasets, CGNS); README, API.md, GUIDE (*Other
  solvers*), CHANGELOG; `validation/tools/plots.py`, `recheck.py`;
  `case.schema.json`.
- **Follow-ups:** the local check (0178); CGNS in a consumer (SU2 or
  code_saturne) after 1.0 (decision 0057); a refined-split wye family, if
  design wants the split region verified (RESEARCH §7.14: "the split
  region isn't verified").

