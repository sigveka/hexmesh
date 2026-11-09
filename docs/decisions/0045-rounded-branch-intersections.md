# 0045 — Rounded branch intersections: forged tees with a radiused crotch

- **Status:** proposed (recorded at the user's request, 2026-11-10: keep
  the idea; no tasks until accepted)
- **Date:** 2026-11-10
- **Tasks:** none

## Context

hexmesh's junction walls are the **sharp** union of cylinders: the
branch meets the run along an intersection curve with a crease
(decision 0029; RESEARCH §4.3b).  That is the geometry of fabricated
tees (a stub welded into a hole) and of drilled test rigs: the
Vattenfall T-junction is drilled from a Plexiglas block
([`oecdnea_2009`]), and the 2024 dead-leg rig has "machine milled sharp
corners" ([`angele_and_howard_etal_2024`]).

Most plant tees are **forged butt-weld fittings** (ASME B16.9), whose
branch blends into the run with a radiused crotch: no crease.  So for
plant models, the sharp wall is the less faithful one.

The crease is also hexmesh's hardest meshing problem.  Its chord error
is first order in `nang`, and no layout measured so far meets decision
0029's 1 % R at `nang` 8: today's wye hub 2.9 %, the junction cube's
equal tee 3.7 % (task 0118; RESEARCH §4.3).  A smooth wall has no
crease: its chord error falls at second order, like any curved wall.
Bošnjak et al. 2024 ([`bosnjak_and_pepe_etal_2024`]) mesh smooth
blended junctions this way (convolution surfaces).

## Options

### A. Sharp only (today)
Exact for fabricated and drilled tees; the crease stays the limiting
error for every junction.

### B. A fillet radius on junctions (proposed)
`Tee(…, crotch_radius=…)` (and the wye family's equivalent): the wall
is the run and branch cylinders blended by a rolling-ball fillet of
that radius along the intersection.  `crotch_radius=0` is today's sharp
wall and stays the default, so existing models don't change.
- The wall projector (decision 0029) takes the blended surface: a
  closed-form or implicit distance (a rolling-ball fillet between two
  cylinders, or a smooth-union implicit surface), with its normal for
  the projection direction.
- PCF: forged tees could default to a radius from the fitting's
  dimensions (B16.9 gives the centre-to-end, not the crotch radius; a
  source is needed).
- The quality and chord gates apply as for any smooth wall.

### C. Smooth blends everywhere (Bošnjak's convolution surfaces)
Faithful to vessels (decision 0018) but not to plant fittings' exact
radii; changes every junction's geometry.  Possible later for vascular
networks only.

## Recommendation (not decided)

**B, after decision 0043's route is chosen**, so the blend is built on
the layout that will stay.  Settle first:
1. **The fillet's geometry:** a rolling-ball fillet between two
   cylinders (exact, but its distance function is piecewise) or a
   smooth-union implicit surface (simpler, but not a constant radius).
   Which can the projector evaluate robustly, with a normal?
2. **Measured, not assumed:** that the chord error on the blended wall
   falls at second order and meets 1 % R at `nang` 8 on the cube's
   equal tee, and how small a radius still does (below some radius the
   blend behaves like a crease).
3. **A source for forged tees' crotch radii** (B16.9 or manufacturers'
   data), before any default is set.
4. **Validation:** the Štigler and dead-leg benchmarks are sharp; a
   rounded-tee reference (loss coefficients for radiused tees) would be
   needed to validate the option itself.

## Consequences (if accepted)

- **API:** one additive field per junction (`crotch_radius`, default 0);
  a 1.x addition under decision 0042's promises, or in 1.0 if accepted
  before the 0.8 review.
- **DESIGN §6/§7:** the wall of a junction may be a blended surface,
  reached by projection as today.
- **Future expansions:** 0018 (vascular) helped (smooth bifurcations,
  option C later); 0021, 0030, 0035 none; 0040 (agents): the field goes
  through the schema and the manifest.

## Verified vs. assumed

- **Verified:** the measured crease errors (tasks 0056, 0116, 0118); the
  two benchmarks' sharp corners (their documents).
- **Assumed:** that forged tees' crotches are radiused enough to matter
  (common knowledge of B16.9 fittings; no dimension source yet); that a
  blended wall's chord error is second order on hexmesh's layouts.
