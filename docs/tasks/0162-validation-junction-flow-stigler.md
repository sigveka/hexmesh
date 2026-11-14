# 0162 — Validation: loss coefficients of equal-diameter tees and laterals (Štigler et al. 2014)

- **Status:** ready
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) criterion 4
  ("a junction-flow benchmark (Štigler's T-junction, on equal tees)"),
  milestone 0.7; [0012](../decisions/0012-openfoam-validation-cases.md);
  judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md)
  as amended.  The user, 2026-11-14: "add junction-flow benchmark".
- **Category:** V3 (experiment: Štigler et al. 2014)
- **Features:** `section:circle`, `straight`, `tee`
- **Depends on:** 0049 (the turbulent model setup and post-processing).
  Equal tees and laterals are done (0122, 0126, 0127).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  It is the 1.0 validation of the junction family, and the
only fitting family without a flow case.  A loss coefficient is what a
user of a tee mesh wants right, and it tests the junction's cells where
the flow turns and separates.

**Reference** (`stigler_and_klas_etal_2014`, in `docs/papers/`, open
access CC-BY; RESEARCH §7.2):
- **Rig:** water; three branches of equal diameter, **50 mm**, drilled
  in a plastic block (so the walls meet **sharp**, as hexmesh's do;
  decision 0045).  Adjacent-branch angle γ = 30°, 45°, 60°, 75°, 90°.
- **Six configurations** per angle (three dividing, three combining,
  their figure 3), **11 flow-rate ratios** each.  Flow rates by magnetic
  flow meters, pressure differences by differential and U-tube
  manometers.
- **Their CFD:** GAMBIT, all hex, about 2.3 M cells, worst skewness
  0.51; realizable k–ε with non-equilibrium wall functions; branches
  25 D long from the junction; velocity inlets, outflow outlets; solved
  unsteady; 21 flow ratios per configuration.
- **Results are figures only** (their figures 5–16): their "geometry"
  coefficients against the flow-rate ratio q, points measured, lines
  computed.
- **Not given in the paper** (read 2026-11-14): the Reynolds number or
  the flow rates' magnitude, and any uncertainty.  Step 1 deals with
  both.

**Where.**  `validation/junction_loss/` (a new case), on
`hexmesh.study.openfoam`; RESEARCH §7.2.

**Do.**
1. **The reference, before any run.**
   - Read the paper fully; record in RESEARCH §7.2 the coefficient
     definitions you compare (their model's coefficients, and Miller's
     loss coefficient, their eq. for $K_{31}$), and the configurations'
     branch labels (a, b, c) against hexmesh's `Tee` ports.
   - Digitise the measured points for the chosen subset (step 2) from
     the figures, with the digitising uncertainty stated, into
     `validation/junction_loss/reference/` (CC-BY: credit in the
     README and the data file).
   - **The Reynolds number:** ask the authors' later papers (search
     Štigler, Klas, Brno, T-junction) for the rig's flow rates.  If
     none gives it, choose Re = 10⁵ on the combined branch (fully
     turbulent, where loss coefficients depend weakly on Re), say so in
     the README, and add a check of that dependence: one point at Re
     5 × 10⁴ and 2 × 10⁵.
   - **Fix the gates before running** (decision 0015): the tolerance on
     each coefficient, set from the digitised scatter and the paper's
     CFD-to-experiment spread at the same points.  Write them in
     `case.json`.
2. **The subset** (the full matrix is 30 configurations × 11 ratios):
   γ = **90°** and **45°** (a tee and a lateral); configurations **Div
   a** and **Com a** (one dividing, one combining); **five** flow-rate
   ratios each, spanning the measured range.  20 points.  Add others
   only if the subset passes and the cost is reported.
3. **Network:** an equal `Tee` (90°) and an equal lateral (45°), each
   branch 25 D from the junction as in their CFD (or longer, if the
   outlet's recirculation reaches the boundary: check).  `walls_by_
   fitting` for the wall patches.  Sharp intersections (the default).
4. **Model:** the 0049 setup that passed (k–ω SST); also realizable
   k–ε with wall functions at one level, for comparison with their CFD.
   Steady `simpleFoam`; if a point won't converge steadily, say so and
   run it transient, as they did.
5. **Pressure:** area-averaged static pressure at stations in each
   branch, extrapolated back to the junction centre along the fully
   developed friction gradient, as the paper's definition requires
   (their section 3; the friction from 0049's validated straight pipe).
6. **Convergence:** three levels with `refined(k)` at one point per
   angle (q ≈ 0.5); Richardson / GCI on the loss coefficient.  The
   other points at the finest level that the budget allows.
7. **Report:** `results.json`, the README's verdict table and graphs
   (coefficient against q, measured points, their CFD line, ours),
   `case.json`'s status.  The gallery's validation page picks it up.
   Cell counts, wall time and peak memory per level.
8. **Resources** (CLAUDE.md): check `pgrep -af pytest` and free memory
   before runs; delete each level's OpenFOAM case once its numbers are
   stored; say in the task if a run needs more than ~1 GB of disk.

**Accept.**
- The gates fixed in `case.json` before the first run (its git history
  shows it).
- 20 points run, each pass or fail reported, whether it passes or not.
- GCI reported at both angles.
- `tests/test_validation_meta.py` passes; a quick check (`-m
  openfoam`), if a coarse point runs in under a few minutes.

**Out of scope.**  Unequal branches (Miller's and the BHRA data: a later
V4 comparison); the Vattenfall thermal-mixing case (0120, LES); rounded
intersections (decision 0045).

## Agent notes

## Questions for design

## Outcome
