# 0012 — Miter bends and standard elbows

- **Status:** done
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0011

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The legacy `MiterBend` (single cut and multi-cut) and `Elbow`
(ASME long/short radius, R = 1.5D / 1D) have no assembly equivalent.

**Where.**  Legacy: `connectors/bend.py` (`MiterBend`; `Elbow` at `:625`);
`fittings._build_miter_outlet`.  New: `assembly/fittings.py`, on top of
`assembly/sweep.py`.

**Do.**
1. `Elbow(schedule="long" | "short", angle=90, n_layers)`: a constructor
   that returns a `Bend` with the radius taken from the inlet spec's outer
   diameter.  This needs the spec, so resolve it in `validate`/`ports`,
   not in `__init__`.
2. `MiterBend(angle, n_cuts=1, n_layers)` as a `Sweep` of straight
   segments.  Each cut is an internal station whose plane bisects the turn.
   The station face is an **ellipse** (the pipe cut obliquely), not the
   circle `build_face` makes from the spec.  Its outer wall nodes must lie
   on both adjacent cylinders.
   - First check whether `Path` can carry an oblique station: a frame whose
     normal is the bisector, with the face scaled by 1/cos(θ/2) along the
     in-plane direction.
   - If this needs a new face kind or a change to `Interface`, record it
     under **Questions for design** and stop.
3. Reject cuts that turn more than the station-face skew allows (decide
   the limit by measuring min SICN).  Do it in `validate`.

**Accept.**
- Both fittings are in the conformance kit `CASES`: single cut, 3 cuts,
  and rolled.
- Test: wall nodes on a miter station lie on both cylinders (tolerance
  1e-9 R).
- Test: `Elbow` radii for both schedules, and a multi-layer spec.

## Agent notes

- **Legacy `MiterBend` is not a miter.**  It revolves about an axis offset
  by 0.15 R, in ≤ 30° sub-steps: in effect a tiny-radius bend.  The new
  `MiterBend(radius, angle, n_cuts, n_layers, roll)` is a true segmented
  bend.
  - Its centreline is the tangent polygon of `Bend(radius, angle, roll)`:
    half-length end legs, `radius · tan(cut / 2)` long.
  - So its ports are identical to `Bend`'s, and the two can replace each
    other.
- **Cut face = stretched station face (step 2 answered, no design change).**
  - Take the station in the bisecting plane and scale it by
    `1 / cos(cut / 2)` along the in-plane bend direction.  The result is
    exactly the parallel projection of either neighbour's circular section
    along that pipe's axis.  Its corners have the same index on both
    sides, so `frame_offset` needs no change.
  - `Interface` is unchanged: only internal stations are stretched.
  - New: `Path.stretch` (per station) and `build_face(..., stretch=)`, plus
    `stretch=` on `faces.build_oh_circle` and `faces.build_annulus`.  The
    face builders are shared code; I edited them because they survive
    task 0017.
- **How the ellipse arcs are built.**  Measured problems with the obvious
  routes:
  - OCC `affineTransform` with a non-uniform scale keeps surface tags but
    renumbers every point and curve.  The face's corner records would have
    to be recovered by matching, which DESIGN §6.1 forbids.
  - OCC `addEllipseArc` rejects arcs whose end points are symmetric about
    the major axis ("Cannot create ellipse arc with start and end point
    symmetric…").  That is the default case, roll = rot = 0.

  `faces._gmsh_helpers.add_conic_arc` therefore builds the circle arc's
  exact rational quadratic B-spline with stretched control points.  NURBS
  are affine invariant, so the curve is the exact ellipse arc.  Measured:
  nodes on the ellipse to 3e-17.
- **Bounding-box trap.**  `occ.getBoundingBox` pads point boxes by the OCC
  tolerance, giving a 3e-8 m error.  The centre of the box is exact.
- **One station per axial layer.**  Plate-filled miter walls put interior
  wall nodes 1.9% of R off the cylinders.  Instead, station planes tilt
  linearly from cut to cut about the bend axis.  Each tilted station is
  again an exact projection of the circle (stretch `1 / cos(tilt)`), so
  every wall node is on a station curve and there are no interior wall
  nodes (tested).  The cell count is unchanged.
- **New `Path.prism` flag** marks slabs whose faces are parallel
  projections of each other:
  - radial side faces are planar;
  - the chord-turn limit does not apply;
  - each slab must have one layer (checked in `Path`);
  - side faces use B-spline "Stretch" filling (`sweep._ruled`).

  The filling choice is measured: OCC plate filling left holes between
  stations less than about 0.2° apart ("Surface … is transfinite but has
  1 hole", "Could not build surface filling").  "Coons" failed on every
  case; "Stretch" passes all of them.  With no interior wall nodes the
  surface type cannot move any node.  `corners.connect_aligned` gained a
  `side_surface` builder argument for this.
- **Step 3, limit.**  Measured min SICN for a single cut (spec `_spec()`;
  0.258 is the straight-pipe baseline):

  | cut (°) | 5 | 30–60 | 75 | 90 | 105 | 120 | 150 |
  |---|---|---|---|---|---|---|---|
  | min SICN | 0.158 | 0.258 | 0.244 | 0.180 | 0.152 | 0.100 | 0.055 |

  - Set `MAX_MITER_CUT = 90°`: a single 90° miter is a common fitting.
  - Set `MIN_MITER_CUT = 1°`: below it the legs are sliver cells, and
    with plate filling 0.05° failed in GMSH.
- **`Elbow(angle, schedule, n_layers, roll)`** is a `Sweep` that delegates
  to `Bend(radius(spec), …)`.  The radius is 1.5 D or 1 D, with D the
  spec's outer diameter, resolved from the spec in `ports`/`validate`.

## Questions for design

## Outcome

- **Files:**
  - `assembly/fittings.py` (`MiterBend`, `Elbow`, `MAX_MITER_CUT`,
    `MIN_MITER_CUT`);
  - `assembly/sweep.py` (`Path.stretch`, `Path.prism`, `_ruled`);
  - `assembly/interface.py` (`build_face(stretch=)`);
  - `assembly/corners.py` (`connect_aligned(side_surface=)`);
  - `faces/_gmsh_helpers.py` (`add_conic_arc`, `stretched`);
  - `faces/oh_circle.py`, `faces/annulus.py` (`stretch=`);
  - `assembly/__init__.py`;
  - `tests/test_miter.py` (new, 13 tests);
  - kit cases `miter-1cut`, `miter-3cut-2layer`, `miter-rolled`,
    `elbow-short`.
- **Tests:** 482 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
- **Measured:**
  - Every miter wall node is on a pipe cylinder (tolerance 1e-9 R).
  - Cut arcs lie on both adjacent cylinders.
  - Predicted cells equal meshed cells for every angle tried.
  - 180° with 4 cuts and 90° with 3 cuts: min SICN 0.258 (baseline).
- **Proposed follow-up (needs a design decision): `Straight` wall
  exactness.**
  - A multi-layer `Straight` fills one slab with plate-filled walls.  Its
    interior wall nodes lie up to **0.69 % of R** off the cylinder
    (measured: `n_layers = 4`, two-layer spec).
  - DESIGN §6 says nodes are placed on exact curves, but asks for one
    layer per slab only "where the axis is curved".  This gap is not in
    the §9 table.
  - Options:
    - one station per layer, as the miter does now (more OCC entities);
    - exact cylinder side surfaces;
    - record a §9 row.
  - The tee's 2–5 % row is the same class.
