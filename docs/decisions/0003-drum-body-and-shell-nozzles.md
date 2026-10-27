# 0003 — Drum bodies, shell nozzles and density changes

- **Status:** proposed
- **Date:** 2026-10-24
- **Tasks:** none (proposed decisions get no tasks)
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
