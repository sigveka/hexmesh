# 0029 — `Transition`: circle ↔ rectangle and rectangle ↔ rectangle sweeps

- **Status:** done
- **Decision:** [0009 — Rectangular sections and circle ↔ rectangle transitions](../decisions/0009-rectangular-sections-and-transitions.md) (option B)
- **Depends on:** 0028

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Ducts meet pipes: fans, dampers, HVAC and process plant all
have circle ↔ rectangle transitions and duct size changes.  Circular
and rectangular O-H cores have the same 5-patch layout, so with equal
counts a transition is a **class-0 sweep** (decision 0009, "shape is
geometry"), like `Reducer`, with stations that blend the shape.

**Where.**
- `hexmesh/assembly/fittings.py`: a new `Transition`, next to
  `Reducer` (its `path`, `fractions`, `_with_radii`).
- `hexmesh/assembly/intent.py`: register the fitting type.
- `hexmesh/__init__.py`, `API.md`, `README.md`; tests.

**Do.**
1. **`Transition(outlet, length, n_layers, axial_grading=1.0)`.**
   - The inlet and `outlet` are single-layer circle or rectangle specs:
     circle → rectangle, rectangle → circle, or rectangle → rectangle
     (size or aspect change).  Circle → circle stays `Reducer`'s job;
     reject it with a pointer to `Reducer`.
   - Counts must match: a circle's `nang` equals the rectangle's
     `nang_w` and `nang_h`.  Also `nrad`, grading, the layer name.
     `validate()` names the first field that differs.
   - The two specs have equal signatures (class 0): check it through the
     classifier, so the strategy declaration is `{0}`.
2. **Station shapes: settle decision 0009's open question by
   measurement.**  Prototype both:
   - **superellipse**: |x/a|^p + |y/b|^p = 1, with a, b and p
     interpolated from the inlet to the outlet (p = 2 for the circle; a
     large p, e.g. 20–50, standing in for the rectangle's straight
     sides, with the rectangle's own straight-edge face at the end
     station itself);
   - **node blend**: each station's boundary nodes are a linear blend of
     the inlet and outlet nodes with the same index, joined by splines.
   Measure min SICN for circle → square (1:1) and circle → 2:1, at
   `n_layers` 4 and 8, `nang` 6.  Pick the better, keep only it, and
   record the table under *Outcome* (it goes to RESEARCH).
3. **Corner identity across the fitting.**  Corners are matched by
   index (decision 0010).  The outlet's roll is fixed by its frame; a
   circle inlet's corners sit at 45° + k·90°, which is where a
   rectangle's corners point for a square and close to it otherwise.
   Make sure no twist is introduced inside the fitting.
4. **Exactness.**  Inlet and outlet faces are exact (circle arcs,
   rectangle lines).  Intermediate stations are exact to the chosen
   station shape: their curves are built from it, one axial layer per
   slab (DESIGN §6), so no surface carries interior nodes.
5. **Docs and example.**  `API.md` entry; `README.md` table; an example
   `duct_transition`: a circular pipe, a transition to a 2:1 duct, a
   duct bend, and a transition back (register it).

**Accept.**
- Conformance-kit cases: circle → square, circle → 2:1, 2:1 → circle,
  2:1 → 1:1 rectangle.  All-hex, meshed = predicted, every kit check
  passing, in either fill order.
- Rejections: count mismatch (naming the field), circle → circle
  (pointing to `Reducer`), multi-layer specs.
- The station-shape measurement table in *Outcome*.
- Saved and loaded through `Assembly.save` / `load`.
- Full suite: no new failures.

**Out of scope.**  Multi-layer transitions; transitions with unequal
counts (class 2); square-shell layers (decision 0009, option C).

## Agent notes

- **Station shapes as a shape.**  The two end shapes got pure 2-D
  outlines (`core.shape.outline(shape, k, s, inner)`: curve k at
  arc-length fraction s, outer or inner, as the face builders make them).
  A station's shape is `BlendShape(inlet, outlet, u)`, and a new builder,
  `faces/oh_blend.py`, makes its 5-patch face from any shape's outline:
  splines through 24 samples per curve.  `build_face` dispatches on the
  shape, so `Transition.path` only supplies station specs, as `Reducer`
  does.  `PipeSpec.side_counts`, `period` and `corners.side_counts` now
  treat any non-circle as having `nang_w` / `nang_h`.
  `test_outlines_match_face_builders` checks the outlines against the
  real circle and rectangle faces (corners exact, curve midpoints to
  1e-6).
- **`Path.blend`**: the stations change shape, so the radial side faces
  are not planar: they are filled, not `addPlaneSurface`.  It also
  requires one axial layer per slab.  The kit's `wall_deviations` treats
  blend paths like splines: no closed form, one layer per slab asserted,
  not measured.
- **Prototype bug, fixed:** the circle's left inner arc (k = 1) straddles
  ±180°.  `atan2` sent it the long way round, OCC then split the station's
  centre face, and transfinite meshing failed (17 vs 6 nodes).  Angles are
  now unwrapped the short way.
- **Count rule** (step 1): `Transition.check` compares
  `side_counts` first, so a count mismatch names both ends' counts
  (`inlet nang 6 vs outlet nang_w 6, nang_h 4`).  The classifier would
  report it as a period difference instead.  Then `Sweep.validate`'s
  signature check (strategies `{0}`) names any other field that differs:
  `nrad`, `mprg`, layer name, `mbmp`.  `rot` is checked in `check`, as in
  `Reducer`.

## Questions for design

_None._

## Outcome

Done 2026-10-27.  `Transition(outlet, length, n_layers, axial_grading=1.0)`
for circle → rectangle, rectangle → circle and rectangle → rectangle,
single-layer, equal counts per side.  Class 0, all-hex, meshed =
predicted.  Station shape: **node blend** (measured below).

**Files.**
- `hexmesh/core/shape.py`: `outline()`, `BlendShape`.
- New `hexmesh/faces/oh_blend.py`: `build_oh_blend`.
- `hexmesh/assembly/fittings.py`: `Transition`; the `Reducer` message
  points to it.
- `hexmesh/assembly/sweep.py`: `Path.blend`.
- `hexmesh/assembly/interface.py`: `build_face` dispatch.
- `hexmesh/core/spec.py`, `hexmesh/assembly/corners.py`: counts and
  period for any non-circle shape.
- Exports and registry: `hexmesh/assembly/__init__.py`,
  `hexmesh/__init__.py`, `hexmesh/assembly/intent.py`.
- Tests:
  - kit cases `transition-circle-square`, `transition-circle-2to1`,
    `transition-2to1-circle`, `transition-2to1-1to1` (graded): every kit
    check, both fill orders, plus `refined(2)`;
  - new `tests/test_transition.py` (15 tests): class 0 for all three
    kinds, cell count, no twist, rejections (counts, circle → circle,
    nrad, layer name, rot, multi-layer), save/load, outlines against the
    real faces, exact end walls;
  - `tests/test_intent.py` registry.
- Example `hexmesh/examples/duct_transition.py`: pipe → 2:1 duct → duct
  bend → pipe.  Registered in `tests/test_examples.py` and
  `hexmesh/examples/__init__.py`.
- Docs: `API.md` (`Transition`; duct fitting list; grading note) and
  `README.md` (intro, fitting table, ducts section, example row,
  limitations).

**Tests.**  Full suite: 1142 passed, 5 skipped (1074 + 5 before).

**Station-shape measurement** (step 2; for RESEARCH).
- Setup:
  - a transition alone, `length` 0.3, nang 6, nrad 3, circle R = 0.1;
  - square 0.18 × 0.18; 2:1 is 0.28 × 0.14; 1:1 is 0.2 × 0.2;
  - min SICN from GMSH; SJ is the 8-corner scaled Jacobian
    (`hexmesh.quality_hex`).
- **Superellipse:** a, b interpolated; p from 2 (circle) to 20
  (rectangle), linearly.  Corners at the 45° parameter; inner curves
  node-blended in both prototypes.

| Case | n_layers | min SICN, blend | min SICN, superellipse | min SJ, blend | min SJ, superellipse | mean SJ, blend | mean SJ, superellipse |
|---|---|---|---|---|---|---|---|
| circle → square | 4 | 0.311 | 0.311 | 0.704 | 0.706 | 0.918 | 0.902 |
| circle → square | 8 | 0.557 | 0.557 | 0.704 | 0.705 | 0.926 | 0.908 |
| circle → 2:1 | 4 | 0.251 | 0.251 | 0.689 | 0.689 | 0.904 | 0.890 |
| circle → 2:1 | 8 | 0.423 | 0.421 | 0.689 | 0.682 | 0.911 | 0.896 |
| 2:1 → circle | 4 | 0.251 | 0.251 | 0.689 | 0.689 | 0.904 | 0.890 |
| 2:1 → circle | 8 | 0.423 | 0.421 | 0.689 | 0.682 | 0.911 | 0.896 |
| 2:1 → 1:1 | 4 | 0.254 | 0.254 | 0.696 | 0.673 | 0.877 | 0.883 |
| 2:1 → 1:1 | 8 | 0.423 | 0.421 | 0.696 | 0.667 | 0.877 | 0.886 |

- **Min SICN** is the same for both shapes (to 0.002).  It is set by the
  axial cell length, not the station shape: 0.075 axial against
  about 0.02 in-plane at 4 layers.  It rises from about 0.25–0.31 to
  0.42–0.56 when the layer count doubles.
- **Scaled Jacobian**: the blend is as good or better at the minimum
  (2:1 → 1:1: 0.696 against 0.673) and better in mean for circle ends
  (+0.015).  The superellipse's mean is 0.006–0.009 higher for
  2:1 → 1:1.
- **Chosen: node blend.**  Equal min SICN, better minimum SJ.  It keeps
  nodes at matching arc-length fractions at every station, needs no
  exponent parameter, and its rectangle → rectangle stations are exact
  rectangles (the superellipse rounds their corners).  The superellipse
  code was removed.

**Example `duct_transition`.**  5616 cells = predicted, min SICN 0.377.
OpenFOAM v1912 `checkMesh`: Mesh OK, max non-orthogonality 39.9° (average
12.5°), max skewness 1.56.

**Surprises.**
- With identical station faces in both prototypes, SICN measured only
  the axial aspect.  Scaled Jacobian was needed to tell the shapes apart.

**Proposed follow-ups.**
- Multi-layer transitions need the rectangular annulus builder from
  task 0028's assessment.  The blend would apply per layer.
- Transitions with unequal counts (class 2) stay out of scope.
