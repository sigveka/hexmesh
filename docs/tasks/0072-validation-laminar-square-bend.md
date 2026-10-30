# 0072 — Validation (V3): laminar flow in a 90° square-duct bend (Taylor, Whitelaw & Yianneskis, Re 790)

- **Status:** ready (after 0071)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (category V3); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: Taylor, Whitelaw & Yianneskis 1982)
- **Depends on:** 0071 (the rectangular-duct setup); duct bends (task
  0028).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Measured data through a duct fitting, laminar, so no
turbulence model: the duct counterpart of the stenosis case (0032).

**Reference** (RESEARCH §7.8).  Taylor, Whitelaw & Yianneskis, "Curved
ducts with strong secondary motion: velocity measurements of developing
laminar and turbulent flow", *J. Fluids Eng.* 104 (1982); NASA
contractor report, NTRS 19820016574 (free).
- Imperial College water tunnel: square duct, hydraulic diameter 40 mm,
  mean bend radius 92 mm, 90° bend after a straight section.
- Laser-Doppler velocity at **Re 790 (laminar)**, at stations upstream,
  through (e.g. 30°, 60°, 77.5°, 90°) and after the bend.
- **Read the report first** and record in RESEARCH §7.8: the exact
  stations, the inlet conditions (measured profile upstream, or the
  development length), Re's definition (bulk velocity and hydraulic
  diameter?), and whether the tables are tabulated or must be digitised.
  Check the report's copyright before committing any tables (NASA
  contractor reports can differ from NASA's own); otherwise download at
  run time.

**Where.**  `validation/square_bend/` (`run.py`, `README.md`,
`RESULTS.md`, `case.json`, `meshes()`), on `hexmesh.study.openfoam`,
v2406.

**Do.**
1. Network: the measured upstream length (or a developed inlet matched
   to the measured upstream profile), the bend (`Bend` on a square
   section, radius 92 / 40 D_h), and a downstream run past the last
   station.
2. Laminar `simpleFoam`, or `pimpleFoam` to steady if SIMPLE stalls (as
   for the stenosis; say which).
3. **Compare** the streamwise velocity profiles at every measured
   station, both along the plane of symmetry and across it where
   measured; the secondary-flow strength where given.
4. **Convergence:** three levels; GCI on the peak streamwise velocity at
   two stations.

**Accept** (V3 gates, provisional; report and don't tune if missed):
- profile RMS difference within **5 % of the bulk velocity** at every
  station at the finest level (measurement uncertainty and digitising
  error recorded);
- the outward shift of the velocity peak through the bend on the
  measured side;
- `case.json` (category V3; tags `laminar`, `flow`, `section:rect`,
  `bend`); RESULTS.md; *Outcome* table.

**Out of scope.**  The turbulent Re 40 000 case (after 0049/0050's RANS
setup); the S-duct.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
