# 0003 — Drum bodies, shell nozzles and density changes

- **Status:** proposed
- **Date:** 2026-10-24
- **Tasks:** none for its options (proposed); 0132 and 0133 from the
  note of 2026-11-10 (documentation, and a probe)
- **Revised:** 2026-10-24, widened to cover density changes along a network
  (RESEARCH §9)

## Context

After decision 0002, drums are boundaries.  Some studies need the drum
interior meshed together with the piping, e.g. mixing, residence time,
thermal stratification, or VOF level studies.  There are four cases.

1. **Drum body:** a cylindrical shell with heads.  The shell is a
   large-radius `Straight`.  Heads need a new single-port fitting that
   caps an O-grid cylinder (core square → cube, ring → spherical or
   ellipsoidal shell).
2. **Nozzles on the head axis** (e.g. the bottom outlet of a vertical
   drum): axisymmetric, so they act like a high-ratio reducer through
   the head.  The topology is unchanged.
3. **Off-axis nozzles on the shell or head:** geometrically a tee with
   small r/R, typically 0.02–0.1.
4. **Density changes along a network** (`nang`/`nrad` differ between two
   parts of a network).  Added because cases 1–3 and this one share one
   question: may hexmesh declare non-conformal joints, or must every
   change be a conformal transition?

**The core difficulty is size scaling.**  A structured ring keeps the
same `nang` divisions all the way round, so circumferential cell size
scales with radius.  A 2 m drum on a 100 mm nozzle has roughly 20× larger
circumferential cells in the drum.  Grading cannot fix this.  The
block-layout tee (DESIGN §7.1) was measured only for r/R = 0.3–0.95.  At
small r/R the nozzle covers a fraction of one drum cell.  DESIGN §7.1
already rejected hole-on-wall layouts.

Intersection geometry is available in closed form:
- shell nozzles: RESEARCH §3.1, with R = drum radius;
- nozzles parallel to the axis on an ellipsoidal head (semi-axes a, b)
  at offset c: $z(\varphi) = b\sqrt{1 - |c + r\,e(\varphi)|^2/a^2}$;
- normal nozzles on an ellipsoid need a numerical solve.

## Options

### A. Conformal, all hex: heads, axial nozzles, refinement transitions
Cases 1–2 as ordinary fittings (`Head`, `HeadNozzle`).  Case 4 (and the
drum size jump) as a **refinement-transition fitting**: one slab that
multiplies `nang` or `nrad` by ×2 (parallel-sheet templates) or ×3
(single-sheet templates), after `harris_and_benzley_etal_2004`; see
RESEARCH §9.3–9.4.
- The paper's restrictions (convex target, parallel sheets) are met in a
  structured O-grid pipe.  The rings are a 2-D template repeated through
  each layer's thickness; the core square needs 3-D templates.
- Transition cells lose quality.  The paper's best unsmoothed minimum was
  0.417 (unstructured base), and hexmesh may not smooth.
- Realisation: many one-cell blocks, or a discrete GMSH volume.  Either
  way, a new fitting kind.
- DESIGN A5 changes from "density solved globally" to "solved per zone",
  zones being separated by transition fittings with fixed ratios.
- For the drum size jump in cases 1–2 *without* changing any port,
  single-sheet (pillow) insertion inside the `Head`/`HeadNozzle` sweep
  is a lighter alternative.  Sheets start inside the large end and end on
  the outer wall (`borden_and_benzley_etal_2000`, RESEARCH §9.5).  It
  carries the same unsmoothed-quality risk.
Shell nozzles (case 3) stay unsupported.

### B. A dedicated small-r/R nozzle template
Local refinement blocks around the opening, keeping full conformity.  This
is research work, and §7.1's rejected layouts show the obvious approaches
fail.

### C. Declared non-conformal joints (equipment and density breaks)
hexmesh meshes piping up to the nozzle.  The drum is meshed separately:
by option A, or by snappyHexMesh/cfMesh when it has internals.  The two
are coupled with OpenFOAM AMI.  The same mechanism serves case 4: a
declared **density break** between two hexmesh zones with different
`nang`/`nrad`.  hexmesh's rules hold inside each zone, because the joint
is a pair of open interfaces (A7).  DESIGN §1/§2 must state that declared
joints may be non-conformal.

## Decision

Not decided.  **Recommendation:** C as the general path for equipment
and density breaks.  Add A's `Head`/`HeadNozzle` when a fully structured
drum is wanted.  Treat A's refinement-transition fitting as research: build
it only if C proves inadequate (e.g. AMI interpolation error at the break
matters for the study), and only after a prototype slab measures
unsmoothed transition quality.  Defer B until there is a concrete need and
a measured failure of C.

To settle first:
1. Is non-conformal coupling at equipment acceptable for the target
   users?  It is a scope change to DESIGN §1.
2. Which OpenFOAM coupling (AMI, or merge-and-stitch) to support, and is
   it verified on a hexmesh pipe + snappyHexMesh drum pair?
3. Is a ~20× circumferential size jump acceptable in option A drums, or
   are refinement transitions required?
4. For density breaks: what quality do unsmoothed ×2 transition templates
   reach on a structured O-grid slab?  This decides whether A is viable
   at all.

## Consequences (if the recommendation is accepted)

- DESIGN §1: add "non-conformal coupling at declared equipment
  boundaries and density breaks" to scope; keep "conformal by
  construction" for everything hexmesh meshes itself.
- DESIGN A5: needs only a clarification under C: density is solved
  globally within each zone, and a declared joint separates zones.
- This record is the open item; it doesn't need a separate DESIGN §10
  entry while it is `proposed`.
- New fittings `Head` and `HeadNozzle` (option A): tasks to be written.
- Internals (baffles, weirs, demisters) stay out of scope (DESIGN §1).

## Verified vs. assumed

- Verified: the tee was measured only for r/R = 0.3–0.95 (DESIGN §7.1).
  The head intersection formula follows directly from the ellipsoid
  equation.
- Verified from the paper: template ratios (×2, ×3), restrictions, and
  the quality figures quoted in RESEARCH §9.3.
- Assumed: typical shell-nozzle r/R = 0.02–0.1; AMI suitability for this
  coupling; structured drum bodies suit VOF; that the paper's
  restrictions are met in a structured pipe.  None is measured.

## Note (2026-11-10): one density per network in 1.x; stated up front; a probe after 1.0

The user (2026-11-10): "This limitation is OK for me and we need to be
clear and up-front with users about it."  Settled, without deciding this
record's options:

- **1.0 ships with one density per network:** `nang` and `nrad` are the
  same everywhere a network connects (DESIGN A5); radial *grading* may
  differ (decisions 0016, 0028 amendment).  A density change is not a
  1.0 item (decision 0042: future expansions are additive and not
  needed).
- **Stated up front** (task 0132): the README, GUIDE, API.md and the
  error a count mismatch raises say so plainly, with what it costs
  (circumferential cells scale with the pipe's radius) and what to do
  instead (grading, a separate mesh coupled in the solver).  Today's
  error points to "a density switch (decision 0003)", which doesn't
  exist.
- **The probe** (task 0133, after 1.0) measures a +1-ring radial step by
  pillowing and a ×2 `nang` slab of one-cell blocks, both meshed by gmsh
  (decision 0046), to choose between this record's options A and C.
- **The 1.x constraint:** whatever comes of it must arrive additively
  (decision 0042's promise): a new fitting or a declared joint, never a
  change of meaning for an existing description.

## Note (2026-11-14): a second use for `Head`, the reentry capsule; after 1.0

The user (2026-11-14) asked whether a reentry capsule's body could be an
application mesh: the solid only (cabin structure, insulation and heat
shield), for conduction through the thermal protection.  Asked to
research it and keep it for after 1.0.  RESEARCH §13 has the survey.

- **It is option A's `Head`**, with a second use beside drum heads.
  Both of the Apollo command module's ends are torispherical (a
  spherical crown and a toroidal knuckle), as dished drum heads are.
  The aft head joins a 33° cone, so a `Head` needs the half-angle of
  the shell it closes, not only a cylinder.
- **Its sections are today's:** an O-H core (the cabin) with four
  shells (aluminium honeycomb, insulation, steel honeycomb, ablator),
  the same materials everywhere, thicker at the aft end.  A `Reducer`
  carries the thickness change along the cone.  Constant-thickness
  shells make the example axisymmetric; the real ablator is thicker on
  the windward side.
- **A limit for the `Head`'s design:** the aft stack is 0.178 m thick
  on a 0.196 m shoulder radius, so the innermost layer turns at 0.018 m.
  `Head` must reject a non-positive offset knuckle radius with a coded
  error.
- **5 patches, not 12, for the shield** (RESEARCH §13.3): `n_outer = 8`
  is a sub-partition of the same cells, so it doesn't change the mesh.
  The shield's resolution is through the thickness.
- **Not affected:** this record's density question (cases 3–4) and
  1.0.  A `Head` is a new fitting, additive after the freeze (decision
  0042).  No task until the design session takes 0003 up after 1.0.
