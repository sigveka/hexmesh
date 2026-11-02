# 0082 — `hexmesh.sections`: the O-H layout described once

- **Status:** ready (after 0081)
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

## Questions for design

## Outcome
