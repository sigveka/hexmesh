# 0028 — Multi-layer junctions: insulation and pipe walls through tees and wyes

- **Status:** accepted
- **Date:** 2026-10-28 (the user: "First I want junctions to support
  insulation, then promote 0019")
- **Tasks:** 0051 (exact junction walls), 0052 (multi-layer tee), 0053
  (multi-layer wye), 0054 (insulated junctions end to end)

## Context

`Tee` and `Wye` accept single-layer specs only (`tee.py` `check`,
`wye.py` `check`; DESIGN deviations table).  So a pipe wall or insulation
cannot run through a junction:
- conjugate heat transfer through a tee is impossible;
- an insulated line with a tee is rejected by the PCF reader (task 0038);
- an agent building insulated networks (decision 0019) would hit this
  first.

What exists:
- **Port faces and run slabs are already multi-layer.**
  `face_vertices` / `face_patches` (`blocks.py`) declare every layer level
  of an O-H face, so the slabs from the ports to the junction stations
  follow.  Only the junction's own blocks are single-layer.
- **Tee (DESIGN §7.1):** the O-grid ring is continuous around the
  junction, an offset of the whole tee wall.  Its levels are 0 (inner
  square) and 1 (wall).
- **Wye (decision 0017):** the wall is the level set `dist = R` of the
  skeleton (inlet axis and daughter rays); `Skeleton.to_wall` projects
  onto it.

**Geometry of the offset wall.**  The outward offset of a union is the
union of the offsets.  So the outer surface of a shell of total thickness
T around the tee is exactly the two cylinders R + T and r + T, meeting
at their own saddle curve.  Around the wye it is the level set
`dist = R + T`.  Each shell boundary is therefore known exactly, by the
same construction as the wall.

**A prerequisite: the junction's wall faces are not exact.**  DESIGN's
deviations table: "Tee wall faces (junction and run slabs) are
OCC-filled surfaces, so interior wall nodes lie 2–5 % of R off the true
cylinders".  A steel wall is typically 5–10 % of R thick.  Shells built
on such faces would have cells squeezed by about half their thickness,
or folded.  The same issue held for straight slabs until task 0025 made
them exact.

## Options

### A. Shells as further offset levels of the junction layout
Each shell adds one level (2, 3, …) to every ring block of the junction.
Its vertices sit on the offset surfaces (tee: cylinders R + T_l and
r + T_l and their saddle; wye: `dist = R + T_l`), and its blocks mirror
the ring blocks.  The topology is unchanged, and so are the port faces.
Branch shells have the same names, `nrad` and thicknesses as the main's.

### B. Bare junctions: layers stop before the junction
Shells end inside the neighbouring straights (`stack_changes`), and the
junction stays single-layer.  It is possible today (the PCF reader
already does this for a bare tee), but the pipe wall has a gap, so it is
no use for CHT.

### C. A separate shell mesh around the junction
Non-conformal: violates P1/P2.

## Decision

**A**, with exact junction walls first.

1. **Exact junction walls (prerequisite).**  Every wall and shell
   boundary face of a junction carries its interior nodes on the exact
   surface.  The tee's main faces lie on cylinders, the branch faces on
   cylinders, and the saddle region on the analytic intersection; the
   wye's on its level sets.  The task chooses the method (exact OCC
   surfaces, interpolating B-spline surfaces through analytic points, or
   one-layer-per-face where §6 allows) and measures it.  This closes the
   tee deviation row.  The kit's wall-exactness check (task 0025) is
   extended to junctions.
2. **Shells as offset levels** (option A) in `Tee` and `Wye`; circular
   shells only.
   - **Branch shells** copy the main's (same names, `nrad`, `mprg`,
     `dR`).  A branch with its own wall thickness (a different schedule)
     is geometry only (class 0), so it can come later as a `Tee` field;
     out of scope now.
   - **Shells beyond the first** stack in the same way.
3. **Limits:** total thickness T against the junction's room.
   - **Tee:** the branch's outer shell must stay inside the main's run
     length, and the turning station must clear the outer main shell.
     The station height becomes `R + T + 0.5 (r + T)`.
   - **Wye:** the offset level sets of neighbouring daughters merge in
     the crotch, so T is bounded by the crotch gap.
   - Quality is measured on a prototype first, then a limit is set
     (decision 0017's approach), using the two-tier policy of task 0047
     (warn / reject, on corner SJ and non-orthogonality).
     `BlockLayout.corner_jacobians` gives a pre-GMSH estimate.
4. **Insulation ending at a junction** stays the job of `stack_changes`
   on a neighbouring straight: a junction's ports carry one spec.

## Consequences

- DESIGN: the tee deviation rows (inexact walls; single-layer) close
  when tasks 0051/0052 land; §7.1 gains a paragraph on offset levels.
  Applied by the design session when the tasks are done.
- PCF (decision 0023, task 0038): insulated junctions stop being an
  error once 0054 lands.
- **Effect on future expansions:**
  - **0018 (vascular):** a vessel wall through bifurcations is this
    feature on the wye.  The level-set construction carries over to
    unequal or asymmetric daughters when the wye grows.
  - **0019 (agent SDK):** removes the first wall an agent building
    insulated networks would hit.  New limits go in `limits.py`;
    errors name the junction, the layer and the limit.
  - **0021 (flow restrictions):** none.
  - **0026 (layer outlines):** junction shells are circular only.
    Rectangular shells at junctions, and insulated duct tees (decision
    0027), combine both later.

## Verified vs. assumed

- **Verified (code, 2026-10-28):** the single-layer checks; the
  multi-layer `face_vertices` / `face_patches`; the tee's two levels; the
  wye's level-set wall; the deviation row on inexact tee wall faces.
- **Assumed:**
  - that offset levels keep every block a proper hex for useful
    thicknesses (0052/0053 measure);
  - that exact junction faces can be built at an acceptable build cost
    (0051 measures).
