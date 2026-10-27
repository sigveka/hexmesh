# 0018 — Future expansion: idealised vascular networks

- **Status:** proposed (future expansion; no tasks)
- **Date:** 2026-10-26 (recorded at the user's request: "plan this as a
  future expansion and keep it in mind with decisions that are done
  going forward")
- **Tasks:** none.  Decisions until then are checked against the
  constraints below (decisions README, template).

## Context

Cardiovascular CFD meshes vessel networks: curved vessels with varying
radius, bifurcations, sometimes loops (the Circle of Willis), sometimes
a vessel-wall layer for fluid–structure or heat studies.  The published
structured bifurcation methods hexmesh's wye follows come from this
field (RESEARCH §4: Decroocq et al., Marcinnó et al.).

**Typical data** (pipeline: DICOM images → lumen segmentation → surface
→ centrelines → mesh):

| Data | Typical format | Contents |
|---|---|---|
| Lumen surface | STL, or VTK `.vtp` | triangulated wall, open at inlets and outlets |
| Centrelines (VMTK) | VTK `.vtp` polydata | polylines per vessel, `MaximumInscribedSphereRadius` per point; branch extraction adds per-point branch/group ids |
| SimVascular project | `.pth` (XML paths), `.ctgr` (XML segmentation contours), `.vtp` model | a path per vessel plus closed cross-section contours along it |
| 1-D network models | solver-specific text | nodes, segments, lengths, areas |

Public sources: the Vascular Model Repository (SimVascular), AneuriskWeb
(cerebral vessels with centrelines).

**How it maps onto hexmesh:**

| Need | hexmesh piece | Status (2026-10-26) |
|---|---|---|
| Curved vessel with varying radius | `SplinePipe` + profile | profile on a straight axis: task 0031; a profiled `SplinePipe` is not planned |
| Bifurcation | `Wye` | symmetric prototype: task 0030; asymmetric, non-planar, unequal radii: not planned |
| Tree from a root vessel | `add(interface, fitting)` | exists |
| Loops | `Closure` | exists |
| Vessel-wall layer | layer stack | exists in sweeps; not through junctions |
| Input | reader → `NetworkSpec` → `to_assembly` | pattern exists (PCF, bathymetry); no vascular reader |

## Scope, when taken up

- **In view:** *idealised* networks, built from centrelines plus radius
  (VMTK-style) or paths plus circular-equivalent sections.
- **Not in view without its own decision:** *patient-specific
  fidelity*, i.e. a mesh that follows the segmented surface (STL)
  exactly.  It needs node projection onto a non-analytic surface, which
  DESIGN §6 (decision 0015) rules out today.

## Prerequisites (in likely order)

1. Wye prototype quality (task 0030) and the quality-limit decision
   (decision 0017).
2. Profiled sweep on a straight axis (task 0031).
3. A profiled `SplinePipe`: per-station radius along a curved
   centreline.
4. Asymmetric, non-planar wyes with unequal radii.
5. **Density changes** within a network (decision 0003): radii in one
   tree differ by 10× or more, and one `nang` per network makes large
   vessels' cells ~10× wider around than small ones'.
6. A VMTK centreline reader (VTK XML polydata; a dependency question).
7. Later, separately decided: non-circular "contour" sections
   (SimVascular `.ctgr`), multi-layer junctions, surface fidelity.

## Constraints for decisions going forward

Decisions that touch these areas should not close off this expansion.
Check each new decision against the list, and say in its *Consequences*
if one is affected (decisions README, template).

1. **Sections.**  Keep section shape as geometry behind one abstraction
   (decision 0009: "shape is geometry").  Don't hard-code circularity
   outside the circle shape itself, so a contour shape can join later.
2. **Per-station specs on every sweep.**  Radius and grading that vary
   along a path (decisions 0008, 0016) should live in the shared sweep
   machinery, not only in `Reducer`, so curved sweeps can use them.
3. **Junction data models.**  Prototypes may restrict (symmetric, equal
   radii, coplanar), but their parameters and port frames should not
   assume symmetry in a way that a general wye would have to undo
   (decision 0017).
4. **Readers.**  Keep `NetworkSpec` format-neutral: centreline samples,
   radii, topology and units.  A new reader should not need new assembly
   concepts.
5. **Density.**  Decision 0003 should consider radius ratios of 10–30 in
   one network, not just drum-to-nozzle jumps.
6. **Exactness (decision 0015).**  Keep the rule; when surface fidelity
   comes up, it is a new decision (e.g. a "reference surface" concept),
   not an exception carved into existing fittings.
7. **Quality limits (decision 0017).**  Vascular references report min
   scaled Jacobian around 0.5 at bifurcations; a limit should leave room
   for that.
8. **Units and scale.**  Vessels are millimetres; nothing should assume
   pipe-sized defaults (e.g. tolerances in absolute metres).

## Verified vs. assumed

- **Verified:** hexmesh capabilities and task status in the tables
  above; the RESEARCH §4 sources.
- **Assumed (from general knowledge, not checked in this repo):** the
  file formats and array names listed above, and the repositories'
  contents.  Check against VMTK and SimVascular documentation when a
  reader is planned.
