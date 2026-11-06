# 0072 — Validation (V3): laminar flow in a 90° square-duct bend (Taylor, Whitelaw & Yianneskis, Re 790)

- **Status:** ready (design answered Q3, 2026-11-06)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (category V3); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V3 (experiment: Taylor, Whitelaw & Yianneskis 1982)
- **Features:** `section:rect`, `straight`, `bend`
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

**Design note (2026-11-02, decision 0036).**  Run this case on hexmesh's
**H** rectangular section (`layout="h"`, task 0084), not the O-H face.
On a rectangle the O-H face converges at order 0.3–0.9 (RESEARCH
§7.11), and a bend would inherit that.  Wall-grade the H face for the
secondary-flow boundary layers (`first_cell=`).  If a reviewer asks,
the O-H mesh can be added as a reported, ungated comparison.

## Agent notes

- **The report:** the NTRS number in the task, 19820016574, is the
  S-duct report ("Developing flow in S-shaped ducts. 1").  The 90° bend
  data are in NASA CR-3367 (1981), "Measurements of laminar and turbulent
  flow in a curved duct with thin inlet boundary layers", NTRS
  19810007898.  NTRS rates it "GOV_PUBLIC_USE_PERMITTED".  The 1982
  J. Fluids Eng. paper is the journal version: a reprint on NTRS, with no
  download.  Bib: `taylor_and_whitelaw_etal_1981`.
- **What it gives (for RESEARCH §7.8):**
  - Geometry: 40 × 40 mm, r_i 72, r_o 112 (mean 92) mm; 0.3 m of
    straight from the contraction exit to the bend; 2.0 m downstream
    (figs. 1–2).
  - Flow: V_c = 0.0198 m/s, Re = V_c D_h/ν = 790, De 368.
  - **Tabulated**, not digitised: Table I gives U/V_c (and V/V_c, gapwise,
    positive toward the inner wall) at z/z½ = 0–0.9 and
    (r − r_o)/(r_i − r_o) = 0.1–0.9.  Stations: X_H = −0.50 and −0.25,
    θ = 30°, 60° and 77.5°, X_H = +0.25, +0.40 and +2.50.
  - Errors (§2.3): V_c ±0.8 %; U/V_c up to 3 % systematic near
    gradients (<1 % elsewhere).
  - Inlet: boundary layers a quarter of D_h at X_H = −0.25 (95 % of the
    maximum); the bend's influence is small at −0.50 and absent at −0.75.
  - Transcribed by hand from the page images to
    `validation/square_bend/data/taylor_1981_table1.csv`, with a
    README; +2.50 is not transcribed.  Every number the PDF text layer
    reads cleanly matches.
- **Inlet:** a plug at the rig's 7.5 D_h gives profiles too flat at
  X_H = −0.50 (RMS 0.101 V_c at k = 1).  So the inlet is matched instead,
  as the task allows: a straight duct from a plug inlet, and the distance
  whose profile best fits X_H = −0.50.  At k = 1 that is 12.2 D_h, RMS
  0.077 V_c.  The study uses k = 2's match for every level.  No plug
  distance gets within 5 %: the measured profile has both a higher core
  (1.64 V_c) and faster near-wall fluid than any developing laminar
  profile.
- **The measured grid's flux:** by the trapezoid rule on the measured
  points, the measured values give 0.947–0.974.  At first (k = 1) the
  computed field gave only 0.90–0.93 at the same points, which suggested
  the measured values ran about 5 % above V_c.  **That was the coarse
  field:** at k = 3 the computed field gives 0.943–0.955, and the
  measured grid carries 0–3 % more flux than the computation (−0.3 % at
  X_H = −0.50, +2.9 % at +0.25).  That is within the report's error
  budget.  The flux-matched RMS (measured values scaled to the computed
  flux through the same points) is kept as a reported diagnostic.  At
  k = 3 it changes the RMS by at most 0.007 V_c.
- **Peak shift:** the gapwise position of the peak U on the symmetry
  plane matches at every station already at k = 1: 0.5 upstream and at
  30°, 0.3 at 60°, 0.1 from 77.5° on.
- **After the design answers (2026-11-06):**
  - The driver runs two series: `rig` (the plug at L_UP = 7.5 D_h,
    gated) and `matched` (12.6 D_h, reported).  The levels carry
    `inlet`, and `--inlets` picks the series.
  - The stored k = 1–3 levels were the matched series; they were renamed
    `matched_k*` in `results.json`, with values unchanged and no rerun.
  - The rig series ran at k = 1, 2, 3: 18.6k / 149k / 502k cells, about
    12 min on 4 processes, all converged (about 200 SIMPLEC steps each).
  - `recheck` gates the rig inlet's peak U convergence (θ = 60°, 77.5°)
    and the peak position per station.  The RMS rows are reported for
    both inlets.
  - `case.json`'s gates follow the answers.

## Questions for design

The finest level misses the 5 % RMS gate at five of seven stations, so
it is reported and nothing is tuned.

- **Q1. The RMS gate:**
  - At k = 3 the RMS is 0.047 (X_H = −0.50), 0.076 (−0.25), 0.048 (30°),
    0.093 (60°), 0.098 (77.5°), 0.082 (+0.25) and 0.081 (+0.40) V_c.
  - The peak U is mesh-converged (GCI 0.05 % and 0.01 % at 60° and
    77.5°), and the peak's outward shift matches at every station.
  - The upstream profile itself can't be matched better than 0.048 by
    any plug-inlet development length.  The measured profile has a
    higher core and faster near-wall fluid than any developing laminar
    one.
  - So the remaining differences are the inlet condition and the
    measurement, not the mesh.
  - Is 5 % right for this data?  The report gives up to 3 % systematic
    on U/V_c near gradients.  Or should the gate be relative to the
    upstream mismatch (e.g. the RMS growing by no more than X through
    the bend)?
- **Q2. The inlet:** a plug at the rig's 7.5 D_h, or the matched
  12.6 D_h used here?  The rig length gives RMS 0.089 at X_H = −0.50
  (k = 2).  A measured-profile inlet would need the profile at
  X_H = −0.75, which isn't tabulated.

**Design answers** (2026-11-06; the user: "yes").  Principle: a gate
isn't moved after its result is known.
- **Q1:** keep the 5 % RMS comparison and record it as missed at five of
  seven stations, with the numbers.  The case is accepted on what the
  mesh controls, gated:
  - mesh convergence of the peak U (GCI, as measured);
  - the peak's position and its outward shift through the bend, per
    station.

  The RMS against the experiment is reported, with the upstream
  mismatch (0.048 at X_H = −0.50) as its floor, like the O-H rectangle
  levels in `rect_duct`.  A gate on the RMS growth through the bend is
  a fair idea for a future case, set before its runs, not here.
- **Q2:** gate on the rig's plug inlet at 7.5 D_h.  The 12.6 D_h run was
  chosen to match the upstream data, so it is kept as a reported
  sensitivity, not gated.
- Then: rerun what Q2 needs (the gated level at 7.5 D_h if it isn't
  already complete), update `RESULTS.md` and `case.json` gates, and
  finish.

- **Q3. Design's gates fail in part on the rig inlet**
  (`validation/square_bend/RESULTS.md`).
  - **The peak U at θ = 60° isn't converging:** 1.5123, 1.5220, 1.5358
    at k = 1, 2, 3.  The fine-pair difference (0.0138, ratio 1.5)
    exceeds the coarse pair's (0.0097, ratio 2).  At θ = 77.5° it
    converges: order 3.89, GCI 0.08 %.
  - **The peak position misses** at X_H = −0.50 and −0.25 (computed
    g = 0.7, measured 0.5) and at θ = 77.5° (0.3 against 0.1).  It
    matches at the other four stations.
  - The cause looks like the inlet, not the mesh.  7.5 D_h from a plug
    at Re 790 the flow is still developing, with off-centre maxima.  The
    measured profile is more developed: the match needed 12.6 D_h.
  - On the matched inlet, every one of these gates passes.  Its peak U
    converges at both stations (GCI 0.05 %, 0.01 %), and the peak
    position matches at all seven.
  - The principle says the gates don't move.  So is the case
    **rejected** on the rig inlet, with the matched-inlet results
    reported?  Or is something else intended?  A finer fourth level
    (k = 4, about 1.2M cells, roughly an hour) could show whether θ = 60°
    reaches its asymptotic range.  It wouldn't change the position
    misses.

**Design answer to Q3** (2026-11-06; the user: "yes").  This reverses
the Q2 answer above, which was too strict.
- **Gate on the matched inlet.**  The plug's development length
  (12.6 D_h) is fitted to the first measured station alone, the
  X_H = −0.50 profile, and the case says so.  Fitting the inflow to
  upstream data and predicting the bend from it is ordinary validation
  practice: the fit uses no station that is gated.
- **The gates are unchanged** and apply from X_H = −0.25 onward: the
  peak U's GCI at 60° and 77.5°, and the peak position and its outward
  shift per station.  X_H = −0.50 is the inlet's calibration station:
  reported, not gated.
- **The rig inlet (7.5 D_h)** is reported as a sensitivity run, with its
  failures: θ = 60° not converging (fine-pair difference 0.0138 against
  0.0097), and the peak position missing at X_H −0.50 / −0.25 and
  77.5°.  The plug at the rig's length models an inflow the experiment
  evidently didn't have (the measured profile is more developed).  Its
  misses upstream of the bend test that inflow model, not the mesh.
- No fourth level (k = 4).
- The 5 % RMS comparison stays reported (Q1's answer).

## Outcome

_Blocked on Q3 (Q1–Q2 answered); both inlet series and their results are complete.  The tables below are the matched inlet (k = 3); the rig inlet is in RESULTS.md._

- **Files:**
  - `validation/square_bend/`: `run.py`, `README.md`, `RESULTS.md`,
    `case.json`, `results.json`, and `data/` (Table I, 350 rows, with a
    README);
  - `docs/references.bib` (`taylor_and_whitelaw_etal_1981`).
- **For RESEARCH §7.8:**

  | station | RMS k = 1 / 2 / 3 (V_c) | peak g (measured = computed) |
  |---|---|---|
  | X_H = −0.50 | 0.081 / 0.048 / 0.047 | 0.5 |
  | X_H = −0.25 | 0.114 / 0.082 / 0.076 | 0.5 |
  | θ = 30° | 0.098 / 0.050 / 0.048 | 0.5 |
  | θ = 60° | 0.084 / 0.077 / 0.093 | 0.3 |
  | θ = 77.5° | 0.168 / 0.109 / 0.098 | 0.1 |
  | X_H = +0.25 | 0.203 / 0.114 / 0.082 | 0.1 |
  | X_H = +0.40 | 0.197 / 0.109 / 0.081 | 0.1 |

  Mesh: the H section, 12/24/36 cells per side, 23k / 184k / 622k cells,
  non-orthogonality ≤ 1°.  Peak U on the symmetry plane converged to
  1.620 (60°) and 1.679 (77.5°).
- **Run time (4 MPI processes):** about 15 min for the inlet match and
  all three levels; SIMPLEC took ~200 steps per level.
- **Surprises:**
  - the task's NTRS number pointed at the S-duct report;
  - the rig's plug inlet is too flat.
- **Not done:** X_H = +2.50 isn't transcribed (different layout).  The
  "across the symmetry plane" comparison is covered by the z/z½ profiles.
