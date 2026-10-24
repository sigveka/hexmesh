# 0003 — Meshing drum bodies and shell nozzles

- **Status:** proposed
- **Date:** 2026-10-24
- **Tasks:** none (proposed decisions get no tasks)

## Context

After decision 0002, drums are boundaries.  Some studies need the drum
interior meshed together with the piping, e.g. mixing, residence time,
thermal stratification, or VOF level studies.  There are three cases.

1. **Drum body:** a cylindrical shell with heads.  The shell is a
   large-radius `Straight`.  Heads need a new single-port fitting that
   caps an O-grid cylinder (core square → cube, ring → spherical or
   ellipsoidal shell).
2. **Nozzles on the head axis** (e.g. the bottom outlet of a vertical
   drum): axisymmetric, so they act like a high-ratio reducer through
   the head.  The topology is unchanged.
3. **Off-axis nozzles on the shell or head:** geometrically a tee with
   small r/R, typically 0.02–0.1.

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

### A. Conformal, all hex: heads and axial nozzles only
Cases 1–2 as ordinary fittings (`Head`, `HeadNozzle`).  No rule changes.
Accept the coarser drum, or add 2:1 hex refinement blocks: a new
transition fitting type, still all-hex and conformal, but not simple
transfinite blocks.  Shell nozzles stay unsupported.

### B. A dedicated small-r/R nozzle template
Local refinement blocks around the opening, keeping full conformity.  This
is research work, and §7.1's rejected layouts show the obvious approaches
fail.

### C. Declared non-conformal equipment boundaries
hexmesh meshes piping up to the nozzle.  The drum is meshed separately:
by option A, or by snappyHexMesh/cfMesh when it has internals.  The two
are coupled with OpenFOAM AMI.  hexmesh's rules hold inside its own
domain, because the joint is an open interface (A7).  DESIGN §1/§2 must
state that equipment boundaries may be non-conformal.

## Decision

Not decided.  **Recommendation:** C as the general path, plus A for
heads and axial nozzles when a fully structured drum is wanted.  Defer B
until there is a concrete need and a measured failure of C.

To settle first:
1. Is non-conformal coupling at equipment acceptable for the target
   users?  It is a scope change to DESIGN §1.
2. Which OpenFOAM coupling (AMI, or merge-and-stitch) to support, and is
   it verified on a hexmesh pipe + snappyHexMesh drum pair?
3. Is a ~20× circumferential size jump acceptable in option A drums, or
   are refinement transitions required?

## Consequences (if the recommendation is accepted)

- DESIGN §1: add "non-conformal coupling at declared equipment
  boundaries" to scope; keep "conformal by construction" for everything
  hexmesh meshes itself.
- This record is the open item; it doesn't need a separate DESIGN §10
  entry while it is `proposed`.
- New fittings `Head` and `HeadNozzle` (option A): tasks to be written.
- Internals (baffles, weirs, demisters) stay out of scope (DESIGN §1).

## Verified vs. assumed

- Verified: the tee was measured only for r/R = 0.3–0.95 (DESIGN §7.1).
  The head intersection formula follows directly from the ellipsoid
  equation.
- Assumed: typical shell-nozzle r/R = 0.02–0.1; AMI suitability for this
  coupling; structured drum bodies suit VOF.  None is measured.
