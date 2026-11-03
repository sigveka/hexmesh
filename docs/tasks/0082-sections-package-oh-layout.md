# 0082 — `hexmesh.sections`: the O-H layout described once

- **Status:** done
- **Decision:** [0037 — Capability boundaries](../decisions/0037-capability-boundaries.md) (item 1, with the refinement at acceptance); DESIGN §3.1, §6.1 "Sections"
- **Depends on:** 0081 (the architecture test guards the move).

Ground rules for all tasks: [README](README.md#ground-rules).  This task
creates `hexmesh/sections/` and moves `hexmesh/faces/` into it; it
touches `core/` and `assembly/` as listed.

**Why.**  The 5-patch O-H face is described in nine modules, and twice
over (RESEARCH §12.2, item 1; DESIGN §9):
- the GMSH builders `faces/oh_circle.py`, `oh_rect.py`, `oh_blend.py`
  and `annulus.py`;
- an independent pure declaration for block layouts in
  `assembly/blocks.py`: `face_levels`, `face_vertices`,
  `_rect_face_vertices`, `face_patches`, `corner_shift`.

The rectangle's ring inset `(1 − OH_RATIO) · min(half_w, half_h)` is
written in both `faces/oh_rect.py` and `blocks._rect_face_vertices`.
Nothing checks that the two agree.  A second layout (decision 0036's H
face) or multi-core sections (0035) would need all nine places changed.

**Not in this task (DESIGN §6.1, "not built on speculation"):** a
generic section interface.  Gather the one layout into one place.  The
interface shared by all layouts is derived when the H face exists.

**Where.**
- New `hexmesh/sections/`:
  - `__init__.py`;
  - `oh.py`: the layout's pure part;
  - the GMSH builders moved from `faces/`, e.g. `sections/oh_gmsh.py`
    or `sections/_build/…` (your choice; one layout, one place).
- Changed: `core/shape.py` (`OH_RATIO`, `oh_core_wall_span`,
  `ring_corners` move if they're layout, not shape),
  `core/cross_section.py`, `assembly/blocks.py`,
  `assembly/interface.py` (`build_face`), `assembly/corners.py`,
  `assembly/signature.py`.
- Tests that import `hexmesh.faces` (`tests/test_faces.py`,
  `tests/test_transition.py`).

**Do.**
1. **Pure layout, `sections/oh.py`.**  Given a `PipeSpec` (and a frame
   where needed), return plain data: corner positions per level, edges
   with division counts and grading, and patches with their materials.
   `blocks.face_vertices` / `face_patches` / `face_levels` /
   `corner_shift` become thin adapters that declare that data into a
   `BlockLayout`.
   - `sections` must not import `assembly` (DESIGN §3.1), so the data
     goes in plain form: tuples, arrays, small dataclasses.
   - Keep the vertex key scheme `(prefix, level, k)`: the tee, wye and
     duct tap bind to it.
2. **GMSH faces.**  Move the builders from `faces/` into `sections/`.
   Make them take their corner and inset geometry from step 1, so the
   inset formula, `OH_RATIO` and the corner angles are written once.
   `interface.build_face` calls one entry point in `sections` instead
   of dispatching on shape type.  The shape dispatch moves into
   `sections`.
3. **Signature and corners.**  The `"oh_core"` signature kind and the
   corner-0 angle (`corners.corner0_angle`) come from the layout.
   `signature.py` and `corners.py` ask it rather than re-deriving them.
4. **`CrossSection`.**  Leave its fields as they are (inner points,
   radials, corner angles).  Move its O-H-specific docstring to the
   layout, and note in *Agent notes* which fields are layout-specific.
   The generic shape of `CrossSection` is decided with the second
   layout.
5. **`hexmesh.faces`:** remove it.  It isn't in API.md, and the tests
   update their imports.  If anything outside `tests/` imports it,
   leave a re-export module with a `DeprecationWarning` and say so.
6. **Agreement test** (new, the point of the task): for a set of specs
   (circle; rectangle at a/b 1, 2, 4; multi-layer circle and
   rectangle; rectangular shells on a circle; `rot` ≠ 0), build the
   GMSH face and the pure declaration at the same frame.  Check:
   - every declared corner coincides (1e-12 relative) with the
     corresponding GMSH point;
   - the edge division counts match the transfinite settings.
7. Update the architecture test (0081): `faces` no longer exists;
   `sections` sits between `core` and `assembly`.  Lower the
   shape-site cap by what moved into `sections`.

**Accept.**
- **Every O-H constant and formula in exactly one place:** grep for
  `OH_RATIO`, `1 - ratio`, `(1 - OH_RATIO)` and `inner_points =` and
  list the hits in *Agent notes*.
- The agreement test passes.
- **No behaviour change:** task 0065's method over every
  `hexmesh/examples` script, the conformance kit's fixtures and the
  tee, wye and duct-tap tests' builds.  `to_dict()`, cell counts,
  predicted quality and meshed node coordinates (1e-12) all identical.
- `tests/test_architecture.py` passes with the lowered cap.
- Full suite: no new failures.  OpenFOAM tests not needed (meshes are
  identical).
- *Outcome*: modules and line counts before and after, and the list of
  places a new layout must now touch (it should be `sections/` plus
  any fitting that builds junction blocks).

**Out of scope.**  A generic section interface; the H face (task
0084); `n_outer = 8`; the shape protocol (0083).

## Agent notes

- **Where the formulas live (refines "Where").**  `core` needs three O-H
  formulas itself: `first_cell`'s wall span, `spec.corners()` and the
  inner outline of `BlendShape`.  `core` must not import `sections`
  (decision 0037), so the 2-D formulas are written once in
  `core/shape.py`, in the section "O-H face geometry: each formula
  once": `OH_RATIO`, `oh_ring_thickness`, `oh_inner_corner`,
  `oh_inner_arc_centre` and `oh_core_wall_span`.  `sections/oh.py`
  builds the layout from them: corner directions, corners per level,
  edges, patches, corner 0, signature kinds and side counts.
  `sections/oh_gmsh.py` builds the GMSH faces from `oh`, and
  `sections.build_face` holds the shape dispatch.  See *Questions*.
- **Two disagreements in the old block declaration** (fixed by
  declaring from `oh.levels`, which mirrors `build_ring`):
  - the circle branch put every shell corner at `r + dR` along the
    core's angle, which is wrong for an outline shell (`dR` is `None`)
    and for rectangular shells;
  - `_rect_face_vertices` took every level's direction from the inner
    corners, but the face chains from the previous ring's corners.  On
    a 2:1 duct in a circular casing the casing corners were 0.0168 apart
    (probe).  No existing fitting or test builds junction blocks on such
    a spec, so the meshes don't change; the agreement test now covers
    it (`rect-in-circle`, `circle-in-rect`, `circle-square-circle`).
- **Acceptance grep**: `OH_RATIO`, `1 - ratio`, `(1 - OH_RATIO)`,
  `inner_points =` in `hexmesh/`:
  - `core/shape.py:281` (definition), `:290` (`oh_ring_thickness`),
    `:300` (`oh_inner_corner`), `:308` (`oh_inner_arc_centre`), `:312`
    and `:341` (`oh_core_wall_span`);
  - `sections/oh.py:90`: the circle core's inner corners, placed by
    angle;
  - junction blocks, which are fitting geometry and not the face:
    `tee.py:340–341`, `wye.py:374`, `duct_tap.py:229`.  The tee and the
    duct tap call `oh_ring_thickness` instead of repeating the inset.
  - No `1 - ratio` or `inner_points =` left: the builders lost their
    `ratio` parameter.
- **Layout-specific `CrossSection` fields**: `inner_points`,
  `inner_curves`, `radial_curves`, `corner_angles`, and the order of
  `surfaces` (centre, then the four quadrants).  `center` is generic
  for a one-core section.  The docstring now says so and points to
  `sections.oh`; the corner diagram moved to the `sections/oh.py`
  docstring.
- **`hexmesh.faces`**: removed.  Nothing outside `tests/` imported it.
- The blend builder now records `corner_angles` (the circle's
  directions), so a ring on a blend station reads them like any other.
  It used to recompute the same values.
- **Rotation**: the layout returns corners with `rot` applied.  A
  circle's corners are placed at their angle (`rot` added to it), the
  others turned as points.  This is how the old builders did it, and it
  keeps the builders' points bit-identical.

## Questions for design

Neither blocks.

1. **The O-H formulas in `core/shape.py`.**  They're there because
   `core` uses them (`first_cell`, `spec.corners()`, `BlendShape`).
   Should they move to `sections` once the shape protocol (task 0083)
   gives `core` another way to ask?  Or does DESIGN §3.1 make
   "layout geometry the shapes need" part of `core`?
2. **Junction blocks still repeat `OH_RATIO · R`** (tee, wye, duct
   tap).  The H face (task 0084) changes what a junction meets.
   Should the fittings ask `sections.oh` for their inner-square corners
   then, or keep their own block geometry?

## Outcome

- **Files.**
  - New: `hexmesh/sections/__init__.py` (`build_face`, exports),
    `sections/oh.py` (the pure layout), `sections/oh_gmsh.py`
    (builders), `sections/_gmsh_helpers.py` (moved),
    `tests/test_sections.py`.
  - Removed: `hexmesh/faces/`.
  - Changed: `core/shape.py`, `core/cross_section.py`,
    `assembly/{blocks,interface,corners,signature,tee,wye,duct_tap,assembler}.py`,
    `tests/test_{architecture,faces,transition,corners,orientation}.py`,
    `docs/integrations/gmsh.md` (paths).
- **Line counts**, before → after.  After excludes the 13-line logo
  header these files gained.
  - O-H faces: `faces/` 1045 → `sections/` 807.
  - `assembly/blocks.py` 696 → 633; `interface.py` 309 → 281;
    `corners.py` 381 → 369; `signature.py` 193 → 193.
  - `core/shape.py` 425 → 458 (the formulas section);
    `core/cross_section.py` 210 → 201.
  - Total over these modules: 3259 → 2942.
- **Tests.**
  - The agreement test, `tests/test_sections.py`: 27 tests over 13
    specs (circle; rect at a/b 1, 2, 4 and with unequal counts; 3-layer
    circle and rect; circle in rect; circle, square, circle; rect in
    circle; `rot` 30° and −17° with `mbmp`; `n_outer = 8`).  Each checks
    every declared corner against the GMSH point (1e-12 relative, in an
    oblique frame), the divisions and grading of every declared edge
    against the transfinite settings, and that every face curve is
    declared once.  It also checks each declared patch's corners and
    material against the built surface.
  - The architecture test: 39 pass.  `SHAPE_SITES_CAP` 69 → 59.
  - Full suite: 2320 passed, 15 skipped, 0 failed.
- **No behaviour change** (task 0065's method).  473 meshes, 124
  warnings.  `to_dict`, cell counts, warnings and node tags are
  identical everywhere.  Node coordinates are identical to 1e-12 except
  in two builds:
  - `tee-0.5-3layer-oblique` (kit, five records): 1.29e-10;
  - `networks.skewed_network`: 1.23e-11.

  Cause, checked: the old `face_vertices` computed a circle's vertex as
  `p + r·(cos a·right + sin a·up)`; the new adapter computes
  `p + u·right + v·up`.  The two differ by up to 9e-16 (floating-point
  association only).  Restoring the old expression in `blocks.py` gave
  0.0 difference in both builds.  Placing ring corners by angle did not
  change it.  The oblique tee amplifies vertex round-off by about 10⁵;
  I didn't trace where.  I kept the single form rather than a
  circle-only special case in the adapter.
- **Where a new layout must touch now**:
  - `sections/`: a module like `oh.py` (levels, patches, corner 0,
    kinds, side counts), its builders, and the dispatch in
    `sections.build_face`;
  - `blocks.face_vertices` / `face_patches` / `corner_shift` and
    `corners.side_counts`: today they call `sections.oh` directly.
    With a second layout they choose it by spec, one line each, or call
    a `sections` entry point once one exists;
  - `signature.py`: takes its kinds from the layout;
  - fittings that build junction blocks: tee, wye, duct tap.

  That is `sections/` plus four adapter lines plus the junction
  fittings, down from nine modules.
- **Surprises.**
  - The block declaration disagreed with the face for mixed stacks
    (see *Agent notes*), and nothing had caught it.
  - The oblique tee is sensitive to 1e-16 vertex changes.  That may be
    worth a look if bit-reproducibility across platforms matters (task
    0092).
- **Follow-ups (proposed).**  The two Questions above.
- **Disk:** the baseline and after records, 73 MB in the
  scratchpad, were deleted when done.  Nothing in the repo.

