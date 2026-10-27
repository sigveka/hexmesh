# 0028 — Rectangular cores in the assembly (single-layer ducts)

- **Status:** done
- **Decision:** [0009 — Rectangular sections and circle ↔ rectangle transitions](../decisions/0009-rectangular-sections-and-transitions.md) (option A); corner identity and P: [0010](../decisions/0010-section-symmetry-period.md)
- **Depends on:** —  (0025 changes straight slabs; if both are in
  progress, make sure rectangular straights get the same treatment: a
  ruled surface between two parallel straight edges is the exact plane)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  DESIGN §1 puts rectangular ducts in scope, and `PipeSpec`
can already describe them (`.core(name, half_w=…, half_h=…)`, with
`nang_w`/`nang_h`), but `interface.check_supported` rejects every
non-circular core.  The legacy face builder `faces/oh_rect.py` has the
same 5-patch O-H layout as `oh_circle` (same point and curve order,
lines instead of arcs), so the sweeps should work once corner identity
and roll use the section's own period.

**Where.**
- `hexmesh/assembly/interface.py:171`: `check_supported`; the face
  builder chosen per core shape.
- `hexmesh/faces/oh_rect.py`: `build_oh_rect` (legacy signature with
  `cx, cy, cz, h_axis, v_axis`; adapt as `oh_circle` was).
- `hexmesh/assembly/corners.py:131`: `frame_offset`, and roll handling
  (`roll_mismatch`, `Closure`): P from the spec.
- `hexmesh/core/spec.py`: a `PipeSpec` property for the geometric P
  (DESIGN §6.1 table), and for the counts per side.
- `hexmesh/assembly/signature.py:79`: `signature()` rejects non-circle
  cores today.
- Every use of the core radius in `hexmesh/assembly/` (about 17; e.g.
  `outer_radius`, `Elbow`, bend-radius checks, `extend_open_ends`).
- `hexmesh/assembly/intent.py` (save/load), `tests/test_fitting_conformance.py`.

**Do.**
1. **Faces.**  Build rectangular O-H faces from the interface frame:
   width along `frame.right`, height along `frame.up`.  Keep corner
   order NE, NW, SW, SE and the same curve order as `oh_circle`.
2. **Period and corner identity (decision 0010).**
   - Geometric P: π/2 for a square (`half_w == half_h` and
     `nang_w == nang_h`), π for any other rectangle.
   - `frame_offset` and roll absorption (`roll_mismatch`, `Closure`) take
     P from the spec, not from `n_outer`.  A roll within 10⁻⁹ of P/2 is
     ambiguous and an error, as now.
3. **Signature (decision 0009, "shape is geometry").**
   - Layout `oh_core` for both shapes.  Record counts per side; a
     circle has `nang_w = nang_h = nang`.
   - Section period in the signature: **combinatorial**, 90° when
     `nang_w = nang_h`, else 180°.
   - Check: a circle and a rectangle with equal counts give equal
     signatures apart from what the classifier treats as geometry.  Add
     a unit test.
4. **Sizes that used the radius.**  Go through every use and decide per
   use; record the list under *Agent notes*:
   - **`extend_open_ends`:** diameters → the hydraulic diameter 4A/P_w
     (P_w the wetted perimeter).  A circle's is D, so circles are
     unchanged;
   - **bend-radius checks** (`Bend`, `SplinePipe`, `Closure`): the
     centreline radius must exceed the half-extent **in the bend plane**
     (from `roll`), so a "hard way" bend of a flat duct is checked on
     its larger side.  If the plane isn't known in a check, use the
     half-diagonal and record it;
   - **`Elbow`:** reject rectangular specs with a message pointing to
     `Bend` (its schedules are ASME pipe fittings);
   - **`first_cell`:** reject for rectangular cores unless it is simple.
     Record which;
   - **`Tee`, `Reducer`:** reject rectangular specs, naming the fitting
     (task 0029's `Transition` covers rectangle size changes);
   - **`MiterBend`:** its cut faces are stretched sections (`stretch=`).
     If `build_oh_rect` can take the same stretch cheaply, support it;
     otherwise reject and propose a follow-up.
5. **Save/load.**  Rectangular specs round-trip through `to_dict` /
   `from_dict` and `Assembly.save` / `load`.
6. **Multi-layer assessment, no implementation.**  Read
   `faces/annulus.py` (`build_annulus`) and report under *Outcome*
   whether a rectangular annulus (a shell around a rectangular core)
   needs a new builder, and roughly what.  Decision 0009 writes the
   multi-layer task from that.
7. **Docs.**  `API.md` (`PipeSpec.core` with `half_w`/`half_h`;
   supported fittings), `README.md` limitations, and a note on "hard
   way" vs "easy way" bends: `up` sets which side is the height, and
   `roll` sets the bend plane.

**Accept.**
- Conformance-kit cases, each meshing all-hex with meshed = predicted
  and passing every kit check (including 0025's wall-exactness check if
  it is done: the walls are the four planes, and on bends the
  corresponding torus-section planes and cylinders):
  - straight, 2:1 duct;
  - bend, 2:1, easy way (`roll` 0) and hard way (`roll` 90);
  - square duct with a rolled bend (P = π/2);
  - closure loop of a 2:1 duct: roll absorbed modulo π;
  - spline pipe, 2:1.
- A roll of 90° on a 2:1 duct at a closure is rejected as a mismatch
  (not absorbable modulo π); on a square it is absorbed.
- Rejections with clear messages for `Elbow`, `Tee`, `Reducer` (and
  `MiterBend`, `first_cell` if rejected).
- Signature unit tests from step 3.
- A new example, `rect_duct`: a 2:1 duct with an easy-way and a hard-way
  bend (register it in `tests/test_examples.py`).
- Full suite: no new failures.

**Out of scope.**  Multi-layer rectangular sections (step 6 only
assesses), circle ↔ rectangle transitions (task 0029), square-shell
layers (decision 0009, option C), rectangular tees.  Keep section shape
behind one abstraction, so a future contour shape can join
([decision 0018](../decisions/0018-future-vascular-networks.md), constraint 1).

## Agent notes

- **One abstraction for section shape** (decision 0018, constraint 1):
  `PipeSpec.side_counts` (divisions per outer curve, corner k → k+1) and
  `PipeSpec.period` (geometric P).  The sweeps, the cell count, the
  signature and the corner code read only these two; the shape type is
  read only where geometry is built (`build_face`) or measured
  (`outer_radius`, `half_extent`, `hydraulic_diameter`).  A future contour
  shape implements the same two properties plus a face builder.
- **`frame_offset`** now carries `a.right` onto plane b, takes the roll,
  rounds it to a multiple of P and converts to corner steps
  (`m · P·n/2π`), as decision 0010 asks.  Same results for circles
  (all kit cases unchanged).
- **`build_oh_rect` changed in one way beyond the exports** (refined
  step 1): the inner rectangle is inset by a uniform ring thickness
  `(1 − ratio)·min(hw, hh)` instead of scaled by `ratio`.  Scaling puts the
  corner radial along the diagonal, at atan(h/w) to the long wall, so the
  corner cells have SJ sin(atan(h/w)): 0.447 at 2:1, 0.316 at 3:1.  A
  uniform ring puts it at 45°: SJ 0.707 at any aspect (measured, Outcome).
  A square is unchanged.  It also gained `rot`, `stretch` and the corner
  exports (`inner_points`, `inner_curves`, `radial_curves`, `nrad`,
  `corner_angles`).  The legacy face tests still pass.
- **Uses of the radius in `hexmesh/assembly/`, decided per use:**

  | Where | Use | Decision |
  |---|---|---|
  | `interface.outer_radius` | clearance, default `lc` | rectangle: half-diagonal (smallest enclosing circle) |
  | `Sweep.validate` bend check | min centreline radius | new `Sweep.clearance(spec)`: half-diagonal by default; `Bend`/`MiterBend`: half-extent toward the centre of curvature (`interface.half_extent`, from `roll`) |
  | `SplinePipe`, `Closure` | same | half-diagonal (bend plane varies); in the error message |
  | `Elbow.radius` | 1.5 D / 1 D | rejected for ducts, message points to `Bend` |
  | `Reducer`, `_with_radii`, `_radii`, `_check_termination` | radii per layer | `Reducer` rejects ducts (names `Transition`, task 0029); termination needs shells, which ducts don't have |
  | `extend_open_ends` | run length in D | hydraulic diameter 4A/P_w (`interface.hydraulic_diameter`); circles unchanged |
  | `Tee`, `branch_spec` | radii | rejected, in `ports` too (the branch spec needs a radius) |
  | `Wye` | radius | already rejected non-circles |
  | `blocks.face_vertices` | ring radii | tee/wye only; unreachable for ducts |
  | `equipment` nozzles | clearance | drum nozzles must be circular (new check) |
  | `PipeSpec.core(first_cell=…)` | wall span | already `TypeError` for rectangles; kept (the ring is uniform now, so it would be simple, but it was not asked for) |
  | `io/readers/pcf.py` | bore radii | PCF is circular pipe; unchanged |
- **Signature fields** `nang` → `nang_w`, `nang_h`.  When both sides of a
  pair have equal counts per side, a count change is still reported as
  one `nang` difference, so circle messages read as before.
  `tests/test_signature.py` and `tests/test_refined.py` updated for the
  field names.
- **Closure at exactly P/2.**  `roll_mismatch` used to return +P/2 and
  absorb it.  DESIGN §6.1/§8 say a roll within 1e-9 of P/2 is ambiguous and
  an error, so `Closure.path` now raises.  This applies to circles too
  (45°); no existing test hit it.
- **`Closure.stations(a, b, period)`** takes P in radians instead of
  `n_outer` (`tests/test_assembly.py` updated).

## Questions for design

_None._

## Outcome

Done 2026-10-27.  Single-layer rectangular ducts run through `Straight`,
`Bend`, `MiterBend`, `SplinePipe` and `Closure`, all-hex, with
meshed = predicted, exact walls, and P = π (2:1) or π/2 (square).

**Files.**
- `hexmesh/core/spec.py`: `PipeSpec.side_counts`, `PipeSpec.period`.
- `hexmesh/faces/oh_rect.py`: uniform ring, `rot`, `stretch`, corner
  exports.
- `hexmesh/assembly/interface.py`:
  - `build_face` picks `build_oh_rect`;
  - `check_supported` accepts single-layer rectangles;
  - `roll_mismatch(…, period)`;
  - `outer_radius` (half-diagonal), `half_extent`, `hydraulic_diameter`.
- `hexmesh/assembly/corners.py`: `frame_offset` by P; `side_counts`;
  per-side transfinite counts in `connect_aligned` (it used to fall back
  to 5 for any non-circle).
- `hexmesh/assembly/sweep.py`: `section_cells` from `side_counts`;
  `Sweep.clearance`; outlet roll check by P.
- `hexmesh/assembly/fittings.py`: `Bend`/`MiterBend` clearance in the bend
  plane; `Elbow` and `Reducer` rejections; `Closure` and spline stations by
  P; the P/2 ambiguity error.
- `hexmesh/assembly/signature.py`: per-side counts, combinatorial period.
- `hexmesh/assembly/tee.py`, `equipment.py`: circular-only guards.
- `hexmesh/assembly/assembler.py`: `extend_open_ends` in hydraulic
  diameters.
- Tests:
  - kit cases `duct-straight`, `duct-bend-easy`, `duct-bend-hard`,
    `duct-rolled-180`, `duct-miter`, `duct-closure` (absorbs 49.9° of
    twist modulo π; a circle would take −40.1°), `duct-spline`,
    `square-bend-rolled`, `square-rolled-90`;
  - the kit's `wall_deviations` measures duct walls against the
    rectangle in the section frame (straight, prism and torus cases);
  - new `tests/test_rect_duct.py` (36 tests): period and offsets (90° on a
    2:1 duct ambiguous, on a square one step), closure at 90° (rejected on
    2:1, nothing to absorb on a square), signatures (square duct = circle
    with equal counts; circle → 2:1 is class 3 on the period), cell count,
    bend clearance by roll, hydraulic diameter, rejections, `rot`,
    save/load, `refined(2)`;
  - `tests/test_signature.py`, `tests/test_refined.py`,
    `tests/test_assembly.py`: field and argument renames.
- Example `hexmesh/examples/rect_duct.py`, registered in
  `tests/test_examples.py` and `hexmesh/examples/__init__.py`.
- Docs: `API.md` (`PipeSpec` counts, the duct `.core`, P, easy/hard way,
  supported fittings, cells; `Bend`, `Closure`, `extend_open_ends`),
  `README.md` (a *Rectangular ducts* section, example row, limitations).

**Tests.** Full suite: 1074 passed, 5 skipped (921 + 5 before).  Kit duct cases: 54 checks, all pass,
including `test_walls_exact` (deviations ≤ 7e-16 of the half-diagonal).

**Measurements** (`hexmesh.quality_hex`; straight runs of 4 layers, nrad 3):

| Duct | Counts | min SJ, scaled inner rectangle (before) | min SJ, uniform ring (after) | mean SJ (after) | max NES (after) |
|---|---|---|---|---|---|
| 2:1 (0.2 × 0.1) | 8 × 4 | 0.447 | 0.707 | 0.882 | 0.500 |
| square (0.14) | 6 × 6 | 0.707 | 0.707 | 0.886 | 0.500 |
| 3:1 (0.3 × 0.1) | 12 × 4 | 0.316 | 0.707 | 0.895 | 0.500 |

- The minimum is the duct's corner cell (45° between wall and radial).
  The bends in `rect_duct` (easy way R/h = 3, hard way R/w = 2.5) keep
  0.705 / 0.706.
- `rect_duct` example: 4576 cells = predicted, min SICN 0.317.
- OpenFOAM v1912 `checkMesh`: Mesh OK, max non-orthogonality 41.3°
  (average 15.8°), max skewness 1.77.  Total volume 0.034525 against
  0.034560 for area × centreline length: −0.1 %, from the chordal bend
  walls between stations (wall nodes are exact).

**Multi-layer assessment (step 6).**
- `build_annulus` cannot take a rectangle.  It requires
  `BoundaryType.CIRCULAR` and a `CircleShape` inner layer, its outer
  boundary is `radius + dR` with arcs about the centre, and its counts are
  one `nang`.  So a duct wall needs a new builder,
  `build_rect_annulus(inner, dR, …)`, about 100 lines mirroring
  `build_annulus`:
  - outer corners at (hw + dR, hh + dR), rotated by `rot` and stretched as
    in `build_oh_rect`;
  - straight outer sides; counts per side from the inner layer;
  - the same patch order, and the same exports.
- With the uniform ring, the shell's corner radials continue the core's
  45° radials, so its corner cells are 45° too.  The outer boundary is a
  sharp-cornered rectangle (sheet-metal duct), not the rounded offset
  curve.
- Elsewhere:
  - `build_face` would dispatch shells by inner shape;
  - `check_supported` would drop the single-layer limit;
  - `_radii` and `_check_termination` (layer termination) would compare
    per-layer thicknesses rather than the core radius;
  - `outer_radius`, `half_extent` and `hydraulic_diameter` would use the
    outer rectangle (the core for D_h);
  - shell `first_cell` is exact on the sides; the corner radial is √2
    longer;
  - kit cases with a duct wall, and a straight with a duct-insulation gap.
- `section_cells` and the signature already handle shells around a
  rectangle (`sum(side_counts) · nrad` per shell).

**Surprises.**
- `connect_aligned` assumed 5 divisions for any non-circular face.
- The legacy `build_oh_rect` corner layout caps a flat duct's quality at
  sin(atan(h/w)).
- `roll_mismatch` absorbed an exact P/2 instead of rejecting it.

**Proposed follow-ups.**
- Multi-layer rectangular sections (above), for decision 0009's next task.
- `first_cell` for a duct core: with the uniform ring every wall-normal
  span equals the ring thickness, so it is exact; a small change if
  wanted.
- DESIGN §6.1 could note that the rectangle's ring is uniform (corner
  radials at 45°), if that should be a rule.
