# 0050 — Documentation as units: features, applications and validation cases

- **Status:** proposed
- **Date:** 2026-11-11
- **Tasks:** none yet (stage 1 is written once this is accepted)

## Context

The user (2026-11-11) wants the gallery organised for its readers, in
three tiers:

1. **Basic features** (the fittings, sections and layers): what each
   looks like, a link to an explanation of how its parameters affect the
   mesh, and the verification behind it (tests, validation cases).
2. **Applications** (the aorta, the HVAC runs, the rocket manifold of
   task 0140): what a reader wants is which fitting is used where, and
   how the network hangs together.
3. **Validation cases.**

And beyond the gallery: "towards the future where we are using Essens
and may want to produce a 'paper' (pdf) for a validation case for
instance or a booklet of basic fittings.  Three page + landing page may
be the first step to overhaul this better."  Also: "the text is very
dense in the documentation and not necessarily suited for human
consumption yet (I will also help at some point)."

Today:
- `docs/GALLERY.md` is one generated page of about 1 240 lines: four
  example groups (fittings 10, sections 10, networks 5, applications 6)
  then the validation cases.  Its prose comes from the examples'
  docstrings; numbers and images from meshing them
  (`docs/gallery/build.py`).
- **Validation cases are already units:** one folder each, with a
  `README.md` (the case), `RESULTS.md` (generated tables and graphs),
  `case.json` with feature tags (`straight`, `bend`, `tee`,
  `profiled-reducer` …, decision 0012), from which the gallery builds a
  coverage matrix.
- **No per-feature explanation exists to link to.**  The GUIDE's
  *Fittings* section is a table of signatures; the parameters' details
  are in `API.md`, written as reference.
- **Application examples don't label their fittings** (no `label=`), so
  a "which fitting is where" map can't be generated.
- Essens renders `html`, `latex`, `pdf`, `revealjs` and `beamer`
  (`docs/integrations/essens.md`); decision 0049 renders the site from
  the Markdown.  PDF output of hexmesh's own documents is untested.
- `build.py` already writes generated blocks between markers into a
  hand-written file (the README's `<!-- readme:NAME:start -->` blocks).

## Options

### A. Reorder the one page
Three parts on one page.  Least work; stays a long generated page, and
nothing in it can become a booklet or a paper.

### B. Three generated pages and a landing page
`GALLERY.md` becomes a short index; Features, Applications and
Validation each get a generated page.  Readable on the site.  The text
still lives in docstrings and in the generator, so a PDF of "the
fittings" would be a print of a web page.

### C. Documents as units, assembled into pages, booklets and papers
One Markdown document per **feature**, per **application** and per
**validation case** (the last exists).  Each is written for reading:
prose by people, with **generated blocks** (images, numbers, the fitting
map, the validation and test links) filled between markers, as the
README's are today.  Then:
- the gallery's pages are indexes of the units (option B's three pages
  and landing page, generated);
- the site renders every unit as a page (decision 0049);
- a **booklet** is Essens rendering a list of units to one PDF (e.g.
  every feature unit, in order);
- a **paper** is one validation case's units (`README.md`, `RESULTS.md`)
  rendered to PDF with its bibliography.

A feature unit *is* the explanation of its parameters: the GUIDE links
to it rather than repeating it, and `API.md` stays the reference.  The
examples' docstrings shrink to a line and a link.

## Decision

**Recommended: C, in stages; B is stage 1.**

1. **Stage 1, the three pages (B),** built so that each entry is
   already one self-contained block (a heading, images, the generated
   numbers, a "Parameters" link, a "Checked by" list), so that stage 2
   moves blocks into files instead of rewriting them.  Networks
   examples go under features, as "Building networks" (composition:
   `add`, `close`, `roll`/`toward`, branching), unless the user decides
   otherwise.
2. **Stage 2, feature and application units:** the files, the
   generated blocks, the fitting labels in the application examples and
   their fitting maps; the GUIDE's per-fitting text moved into them.
   Writing for reading is the point: short paragraphs, the picture
   first, one idea at a time, the reference left to `API.md`.  The user
   will help with the prose.
3. **Stage 3, PDFs:** a fittings booklet and one validation paper,
   once Essens's PDF output has been tried on these documents.

**To settle before accepting:**
- Where the units live (e.g. `docs/features/<name>.md`,
  `docs/applications/<name>.md`), and whether a feature unit covers one
  fitting or a family (bends; junctions; sections and layers).
- What "Checked by" lists for a feature: the validation cases (from
  their tags: generated) and which tests (the fitting conformance
  matrix, cell-count prediction, quality tiers).  Tests have no feature
  tags today; a hand-kept map, or tags on the tests.
- The fitting map's form: a table only (label, fitting, key
  parameters, link to the feature), or also an image coloured by fitting.
- The feature tags' list (decision 0012) lacks `reducer`, `elbow`,
  `closure`, `switch`: extend it, so every feature unit can name its
  validation coverage, including "none".

## Consequences

- **DESIGN.md:** none.
- **Decision 0049:** the site gains the unit folders; `site.py`'s
  navigation groups them.  No change to its principles (Markdown stays
  the source, GitHub-renderable).
- **Repository:** stage 1 changes `docs/gallery/build.py` and splits
  `docs/GALLERY.md`; two links point at anchors in it today (about 30
  files link to the page).
- **Future expansions:** 0030 (simulation suite): validation papers are
  its natural output; 0019/0040 (agents): units are good retrieval
  documents; 0018, 0021, 0035: none.

## Verified vs. assumed

- **Verified** (2026-11-11): the gallery's size and groups, the
  validation feature tags and coverage matrix, the missing labels and
  per-fitting guide text, the README marker mechanism, Essens's listed
  output formats.
- **Assumed:** that Essens can render several units into one PDF with
  figures, tables, math and a bibliography (untested on hexmesh's
  documents); that generated blocks between markers are acceptable in
  documents people write in.
