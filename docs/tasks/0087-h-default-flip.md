# 0087 — Make H the default rectangular core (version 0.4.0)

- **Status:** ready (after 0086)
- **Decision:** [0036 — Cartesian (H) rectangular section](../decisions/0036-cartesian-rectangular-section.md) (items 1, 3, 4; rollout step 4); DESIGN §6.1 "Sections" (H the default)
- **Depends on:** 0084, 0085, 0086.

Ground rules for all tasks: [README](README.md#ground-rules).  This task
touches `core/`, the examples, the docs and the package version.

**Why.**  The user chose the H face as the default for rectangular
cores.  It flips last, once every rectangular fitting accepts H ports
(0084–0086).

**Where.**
- `core/spec.py`.
- `hexmesh/examples/` (rectangular examples), `validation/rect_duct/`.
- `API.md`, `README.md`, `docs/GUIDE.md`, the gallery (`docs/gallery/`,
  `docs/GALLERY.md`).
- `pyproject.toml`, and the package's version attribute if separate.
- Tests that are about the O-H rectangle.

**Do.**
1. **The default:**
   - `PipeSpec.core(..., layout=None)` resolves to `"h"` for
     rectangular cores and `"oh"` for circles.
   - `from_dict()` of a description without `layout` still gives
     `"oh"` (decision 0036 item 3).  Test it with a fixture saved before
     the flip.
   - The study file format (decision 0025) follows the same rule.
2. **Breaking change** (decision 0036 item 4): `nrad` on a rectangular
   core without `layout="oh"` is now an error naming both fixes.
   - Bump the version to **0.4.0**.
   - Write release notes in the place the project keeps them (README
     "Changes", or a new `CHANGELOG.md` if there's none).  Include the
     change, the reason (RESEARCH §7.11, one sentence) and the two-line
     migration.
3. **Tests:**
   - Tests about the O-H rectangle (oh_rect faces, the 0047 limit,
     O-H duct-tap internals) pass `layout="oh"` explicitly.
   - Tests about rectangular ducts in general use the default, and
     their expected cell counts change.  List the changed expectations
     in *Agent notes*.
4. **Examples:** the rectangular examples use the default (H); drop
   their `nrad` on the core and grade the walls instead.
   - Regenerate the gallery images and `docs/GALLERY.md`.
   - `validation/rect_duct/`'s default run uses H; the O-H series stays
     available by flag for the comparison.
5. **Docs:**
   - API.md: `layout=` on `PipeSpec.core`, and the H face in the
     Sections page.
   - README / GUIDE: a short "rectangular ducts" note on the H default,
     why (one sentence, link to RESEARCH §7.11), and the O-H opt-in.
   - Keep CLAUDE.md's "8× the cells" note as it is.

**Accept.**
- `PipeSpec().core("air", RectShape(...))` builds an H core.  A saved
  pre-0.4 description reproduces its O-H mesh exactly.
- `nrad` on a default rectangular core raises the two-fix error.
- Every example builds and meshes; the gallery is rebuilt.  *Outcome*
  has a table of the rectangular examples' cell counts and min SJ,
  before and after.
- The version is 0.4.0; the release notes are written; the install test
  (task 0080) passes.
- Full suite and `-m openfoam` for the rect duct: no new failures.
- DESIGN §9's row "Rectangular cores have only the O-H layout" can be
  removed.  Propose that under *Outcome*; the design session removes
  it.

**Out of scope.**  Native-H junction layouts; changes to circular
sections.

## Agent notes

## Questions for design

## Outcome
