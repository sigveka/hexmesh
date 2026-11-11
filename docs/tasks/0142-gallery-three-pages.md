# 0142 — The gallery as three pages and a landing page, by family

- **Status:** ready
- **Decision:** [0050 — Documentation as units](../decisions/0050-documents-as-units.md) (stage 1)
- **Depends on:** none.  Not alongside another task that regenerates the
  gallery (0139, 0140): suggested after 0139 and before 0140, so the
  rocket manifold lands in the new layout.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The gallery is one generated page of about 1 240 lines, grouped
by kind of thing (fittings, sections, networks, applications) and then
the validation cases.  Decision 0050 makes the documentation a set of
units (one per feature family, application and validation case) that
can later be assembled into site pages, a fittings booklet or a
validation paper.  This stage is the step that fits today's generator:
three pages, with every entry already a self-contained block, so stage 2
moves blocks into `docs/features/<family>.md` and
`docs/applications/<name>.md` instead of rewriting them.

**Where.**  `docs/gallery/build.py`; `docs/GALLERY.md` (becomes the
landing page); new generated pages `docs/gallery/FEATURES.md`,
`docs/gallery/APPLICATIONS.md`, `docs/gallery/VALIDATION.md`;
`hexmesh/examples/__init__.py` (the family grouping);
`validation/case.schema.json` and the cases' `case.json`; `docs/site.py`
(the sidebar); the two anchor links `docs/GALLERY.md#validation`
(`README.md:261`, `docs/WHY.md:54`); the GUIDE's *Examples* section;
`tests/` (the examples' and validation-meta tests).

**Do.**
1. **The families.**  Group the feature examples by family, replacing
   `CATEGORIES`' `fittings`/`sections`/`networks` (applications stay).
   A starting proposal, to refine (record changes under *Agent notes*):
   - **Bends:** `smooth_bend`, `miter_bend`, `spline_pipe`;
   - **Reducers and profiles:** `reducer_network`, `stenosis`;
   - **Junctions:** `tee`, `equal_tee`, `wye`, `junction_walls`;
   - **Sections and transitions:** `rect_duct`, `duct_transition`;
   - **Layers:** `insulated_pipe`, `insulated_route`, `layer_outlines`,
     `lagged_duct`, `insulated_transition`, `insulated_tee`,
     `insulated_network`;
   - **Grading and resolution:** `graded_bend`;
   - **Building networks:** `loop`, `pipe_network`, `pipe_rack`,
     `distribution_tree`, `bifurcation_tree`, `skewed_network`.

   Each family: a name (its future file `docs/features/<family>.md`), a
   one-paragraph introduction, its fittings, and the validation tags it
   collects (step 3).  One place holds this (e.g. `FAMILIES` beside
   `CATEGORIES`); module paths (`hexmesh.examples.fittings.…`) don't
   move: users run them.
2. **The pages.**
   - **`docs/GALLERY.md`, the landing page:** what the three pages
     are, one line and a thumbnail per family and per application, the
     validation summary line, "Reading the numbers".  Short.
   - **`FEATURES.md`:** by family.  Each family opens with its
     introduction, then its examples.
   - **`APPLICATIONS.md`:** the application examples, each with the
     fittings it uses (today's count line, each fitting type linked to
     its family on `FEATURES.md`).  The fitting map (labels, coloured
     image, cut-away and face) is stage 2.
   - **`VALIDATION.md`:** today's validation section and coverage
     matrix, unchanged in content.
3. **Validation tags.**  Add `reducer`, `elbow`, `closure` and `switch`
   to the schema's `features` list; check each case's `run.py` and add
   the tags it truly exercises (a plain cone in a case is `reducer`;
   none is fine).  The coverage matrix then has these rows, `(none)`
   where nothing covers them.
4. **Every feature entry is one block** in this order: heading; images
   (network, section; cut-away where the example has one); what it
   shows (the docstring); the run command; the numbers table; the
   names (open ends, walls, interfaces); **Parameters:** a link per
   fitting to its `API.md` section (stage 2 replaces it by the family
   document); **Validated by:** the validation cases whose tags the
   family collects, with their status mark and the date and hexmesh
   commit of their last run (each level's `environment` in
   `results.json`; the latest), or "none".  Generate the block from one
   function, so stage 2 can write it to another file.
5. **Stamp each page** with its generation date and hexmesh commit, as
   `GALLERY.md`'s footer does today.
6. **Links.**  Update the two anchor links (to `docs/gallery/VALIDATION.md`),
   the GUIDE's *Examples* table (families, not the old categories), and
   `docs/site.py` (`TOP`'s "Examples" stays the landing page; a sidebar
   group for `docs/gallery`).  `python3 docs/site.py` builds with no
   broken links (locally; the docs site isn't live yet).

**Accept.**
- `python3 docs/gallery/build.py --markdown-only` writes the four pages;
  with meshing, the images and numbers are unchanged from today's
  (same examples, same meshes).
- Every example and every validation case appears exactly once; every
  fitting type in an application links to a family.
- The coverage matrix has the four new tags; every case's tags checked
  against its `run.py` (say which changed).
- Full suite: no new failures; no broken links in the site build.

**Out of scope.**  The `docs/features/` and `docs/applications/` files
(stage 2); fitting labels and maps in the applications (stage 2); test
results stamped per family (stage 2: a marker per family); rewriting the
prose for readability (stage 2, with the user); PDFs (stage 3).

## Agent notes

## Questions for design

## Outcome
