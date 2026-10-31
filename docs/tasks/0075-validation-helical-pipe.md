# 0075 — Validation (V3): laminar flow in a helical pipe (spline pipe)

- **Status:** ready (on the v2406 runner)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (V3, with V4 secondary); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: De Amicis et al. 2014; V4 correlation, Manlapaz & Churchill 1980, secondary)
- **Features:** `section:circle`, `straight`, `spline`
- **Depends on:** the shared OpenFOAM helpers and the Docker runner.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `SplinePipe` has no validation (task 0073's matrix).  A helical
coil is the classic curved-and-twisted pipe: laminar, with measured
friction factors.

**References** (RESEARCH §7.9).
- **De Amicis et al. (2014, Politecnico di Milano):** experimental and
  numerical laminar flow in helically coiled pipes; measured Darcy
  friction factors agree with laminar correlations to a few per cent.
  Open copy:
  `https://re.public.polimi.it/handle/11311/861372`.  **Read it first**
  and record in RESEARCH §7.9: coil diameter, pitch, tube diameter, the
  Reynolds and Dean ranges, and whether the data are tabulated.
- **Manlapaz & Churchill (1980):** the laminar friction-factor
  correlation for finite pitch.  Germano's torsion analysis (1982, 1989)
  says torsion matters little for the friction factor at moderate Dean
  numbers.

**Where.**  `validation/helical_pipe/` (`run.py`, `README.md`,
`RESULTS.md`, `case.json`, `meshes()`), v2406.

**Do.**
1. **Geometry:** one of the paper's coils.  A `SplinePipe` through points
   on the helix (dense enough; say how many per turn).  Then:
   - **record the geometric deviation** of the meshed centreline from the
     true helix (max distance, in tube diameters);
   - a straight inlet run long enough for a developed inlet, and several
     turns, so the friction factor is measured on fully developed turns
     (check that consecutive turns agree).
2. **Flow:** laminar, `simpleFoam` (or `pimpleFoam` to steady if SIMPLE
   stalls); three Reynolds numbers inside the paper's laminar range.
3. **Compare:** the Darcy friction factor per turn against the measured
   values and the correlation; the ratio to the straight-pipe value
   (fc/fs).
4. **Convergence:** three levels; GCI on the friction factor at the
   middle Re.

**Accept** (V3 gates, provisional; report and don't tune if missed):
- friction factor within **5 %** of the measured value at each Re (the
  correlations agree with the data to a few per cent), at the finest
  level, with GCI reported;
- the geometric deviation of the spline from the helix stated, and small
  against the tube diameter (≤ 0.1 %, or say why not);
- `case.json`; RESULTS.md; *Outcome* table.

**Out of scope.**  Turbulent coils (Hüttl & Friedrich's DNS, later);
heat transfer in coils.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
