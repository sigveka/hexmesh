# 0087 — Make H the default rectangular core (version 0.4.0)

- **Status:** done
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

*2026-11-05 (agent).*

- **The default.**  `PipeSpec.core(layout=None)` resolves on the shape:
  a rectangle gives `"h"`, a circle or a station shape (`BlendShape`)
  gives `"oh"`.  The library's own O-H rectangles now say
  `layout="oh"`:
  - `from_dict`'s O-H branch;
  - `sections.h.pillowed`;
  - the duct tap's `_branch_oh`;
  - `fittings._with_layers` and `Transition`'s blend spec.
  The two-fix error says "a rectangular core is H by default since
  0.4.0" when no layout was passed, and "an H core" when `layout="h"`
  was.
- **Saved descriptions.**  `from_dict` and the study files
  (`Assembly.from_dict` via `substitute`, decision 0025) already treat a
  missing `layout` as O-H, so step 1's last item needed no code.
  - Fixture: `tests/data/saved_before_0087.json`, written at d5e503f: a
    duct, a rectangular tap, a bend and a reducer, 2240 cells.
  - Its 2583 nodes mesh identically at d5e503f and after the flip,
    checked with a worktree at d5e503f.
  - The test compares it with the same assembly built today with
    `layout="oh"`.
- **Tests (step 3).**  Every test spec of an O-H rectangle passes
  `layout="oh"`: 29 calls in 11 files, added by an AST pass over
  `core()` calls with `nrad` and no `layout`.
  - They include the conformance kit's rectangular cases.  Those are
    its O-H fitting coverage; the H cases are already separate kit
    entries (0084–0086).
  - `test_rect_duct.py`, the rectangular duct in general, uses the
    default.  Changed expectations:
    - `test_cell_count_closed_form`: now parametrised.  H gives
      5 · 4·2 = 40 cells; O-H (nrad 3) keeps 5 · (8 + 36) = 220.
    - `test_duct_contents`: the layer is `("air", "h_core", 0)`.  The
      O-H `("air", "oh_core", 2)` is asserted with `nrad=2`.
    - `test_square_duct_matches_circle`: the O-H square has the
      circle's signature.  The default H square is a class-1 switch
      from it.
    - `test_first_cell`: `first_cell=` now grades an H duct.  The O-H
      `TypeError` is asserted with `layout="oh"`.
  - `test_h_layout.py`: `test_default_layout_is_oh` is renamed to
    `test_oh_layout_has_no_wall_grading`.  New tests: the default per
    shape, the two-fix message, and the saved-before-0087 fixture.
  - `test_validation.py`'s rect-duct fixture passes `--meshes oh
    cartesian h`, which the default no longer runs.
- **Examples (step 4).**
  - `nrad=` on every rectangular core became `mprg=1.2`, the wall ratio.
  - `hvac_supply`'s rectangle-to-rectangle `Transition` became a
    `Reducer`: with H at both ends a `Transition` is rejected (task
    0086).
  - `rect_duct`'s docstring names the H face and the O-H opt-in.
- **validation/rect_duct.**
  - `assembly()` defaults to `"h"`, and the default `--meshes` is
    `h hg`.  `--meshes oh cartesian` runs the comparison.
  - `control_cells` still sizes the control from the O-H level, so the
    stored control and H levels keep their counts (2000 / 3240 / 6480).
  - `meshes()` shows the H levels, plus the O-H square for comparison.
    Five old O-H images are deleted; `ar1_k1_section.png` is
    re-rendered.
- **Elsewhere.**  `benchmarks/outline_quality.py` (the 0047 O-H outline
  sweep) pins `layout="oh"`.  `PipeSpec`'s docstring example is an H
  duct with `first_cell=`.

## Questions for design

None.

## Outcome

*Done 2026-11-05.*

**Files.**
- Library: `core/spec.py` (the default, the message, the docstring
  example); `sections/h.py`, `sections/__init__.py`;
  `assembly/duct_tap.py`, `assembly/fittings.py` (internal O-H pins);
  `io/writers/msh_comments.py` (version in a docstring).
- Version: `pyproject.toml` and `CITATION.cff` 0.4.0, the README badge;
  new `CHANGELOG.md` (in `MANIFEST.in`).
- Examples: `cooling_channels`, `hvac_branched`, `hvac_supply`,
  `duct_transition`, `insulated_transition`, `lagged_duct`, `rect_duct`.
- Validation: `validation/rect_duct/run.py` and its README, the images.
- Docs: API.md, README.md, `docs/GUIDE.md`; the gallery (seven
  examples, `docs/GALLERY.md`, `metrics.json`).
- Tests: 11 files pinned to O-H, `test_rect_duct.py` on the default,
  `test_h_layout.py` (+3 tests), `test_validation.py`; fixture
  `tests/data/saved_before_0087.json`.
- Benchmark: `benchmarks/outline_quality.py`.

**Tests.**
- Full suite: 3163 passed, 15 skipped, 0 failed (3159 / 15 / 0
  before).
- `-m slow` (install test, task 0080): 5 passed.
- `-m openfoam -k rect_duct`: 3 passed.

**The rectangular examples, before (O-H, d5e503f) and after (H, walls
`mprg=1.2`).**  Min SJ and max non-orthogonality are measured on every
meshed cell, OpenFOAM's definition for the angle.  No example warns.

| example | cells before | cells after | min SJ before | min SJ after | max non-orth before | after |
|---|---|---|---|---|---|---|
| rect_duct | 4 576 | 1 408 | 0.705 | 0.997 | 41.3° | 1.6° |
| rect_duct, 16 × 8 (below) | | 5 632 | | 0.997 | | 1.8° |
| duct_transition | 5 616 | 4 392 | 0.689 | 0.546 | 39.9° | 50.5° |
| insulated_transition | 9 036 | 6 972 | 0.689 | 0.577 | 39.9° | 50.5° |
| lagged_duct | 10 488 | 7 176 | 0.690 | 0.690 | 41.1° | 41.9° |
| hvac_supply | 15 360 | 6 912 | 0.627 | 0.577 | 43.4° | 51.9° |
| hvac_branched | 33 472 | 24 704 | 0.421 | 0.421 | 61.5° | 61.5° |
| cooling_channels | 10 152 | 8 280 | 0.204 | 0.204 | 73.7° | 73.7° |

- The straight H duct is near-orthogonal.  The lowest SJ and the highest
  non-orthogonality move into the embedded switches of the round-to-H
  `Transition`s: about the cube-corner 1/√3, as the switch predicts
  (0.546 in `duct_transition`, sheared by its wall grading).
- The tees (`hvac_branched`) and the wye (`cooling_channels`) keep their
  O-H junction blocks, so their minima don't move.
- `lagged_duct`'s gallery min SICN, 0.024, is unchanged (0.025 before):
  it comes from the thin steel shell, not the core.
- The cell counts fall because an H face has no ring.  The rectangular
  examples keep their `nang_w`/`nang_h`, as the task asks (drop `nrad`,
  grade the walls), so `rect_duct` is now a coarse 8 × 4 face.  Whether
  to raise its counts for the gallery is a judgement for design.

**Surprises.**
- `validation/rect_duct`'s `control_cells` sized the control from
  `assembly()`'s default.  After the flip that recursed (H sizes itself
  from the control), so it now pins `layout="oh"`.
- Two places needed nothing: the study runner and the saved-file path
  already read a missing `layout` as O-H (0084).

**Proposed.**
- **DESIGN §9:** the row "Rectangular cores have only the O-H layout"
  can be removed (for the design session).
- ~~Follow-up: raise `rect_duct`'s counts~~: done on design's answer
  (2026-11-05).
  - The example is now 16 × 8 with `first_cell=0.004`: 4 mm at every
    wall against a uniform cell of 12.5 mm (`wall_bump` 0.154 / 0.111).
  - 5 632 cells, min SJ 0.997, max non-orthogonality 1.8°.
  - Gallery min SICN 0.168 (the graded wall cells' aspect ratio; 0.737
    at 8 × 4 uniform-ish).
