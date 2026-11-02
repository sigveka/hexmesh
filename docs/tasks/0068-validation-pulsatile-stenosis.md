# 0068 — Validation: pulsatile flow through the cosine stenosis (Varghese et al., Part 2)

- **Status:** done (2026-11-02; accepted: every gate passes)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V2 (DNS: Varghese et al. Part 2)
- **Features:** `section:circle`, `straight`, `profiled-reducer`
- **Depends on:** 0032 (the stenosis driver, geometry, levels and
  steady results); 0067 (the pulsatile inlet machinery).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first time-dependent validation with a fitting, and the
canonical vascular case (decision 0018): pulsatile flow through a 75 %
stenosis, against DNS.

**Reference** ([`varghese_and_frankel_etal_2007b`]; RESEARCH §7.3).
- **Geometry and domain:** as 0032 (s₀ = 0.25, L = 2D, 3D up, 16D
  down).
- **Inlet:** 0067's Womersley profile: α = 7.5, A = 0.667, Re = 600
  on the **mean centreline** velocity (bulk Re 300).  Not Part 1's
  convention: get ν right (ν = u_c D / 600).
- **Data:** Purdue database `Axi_puls/vel_p1…p6.dat`: velocity profiles
  at six phases, x/D −2…15, normalised by u_i = 0.5 (check what u_i is
  relative to u_c here, against the inlet profile at x = −2D).  Download
  at run time; never commit (no licence).
- **Phases:** from the paper's fig. 1, t/T ≈ 0.09 + k/6, read by eye
  (±0.01).  Confirm the phase of each file by matching its x = −2D
  profile to the Womersley inlet at candidate times; report the phases
  found.
- **The paper's result:** laminar and axisymmetric throughout; peak
  throat velocity above 3.65 u_c.

**Where.**  `validation/stenosis/` (extend its driver with a pulsatile
mode) or `validation/stenosis_pulsatile/`; say which.

**Do.**
1. Mesh levels as 0032 (k = 2, 3, 4; drop k = 1 if it drifts off-axis
   as in the steady case).  Inlet as 0067.  `pimpleFoam`, second-order
   in time, Courant ≤ 0.5.
2. **Start** from the steady Re 500 solution (as the paper does), or
   from rest; run until periodic (phase values change < 0.5 % between
   periods).  Report the periods needed.
3. **Compare** at the six phases: the axial velocity profiles at x/D =
   −2, 0, 1, 2, 3, 4, 6, 10; the centreline velocity along x; the
   recirculation extent (from the near-wall velocity at r = 0.48 D, as
   in 0032).
4. **Convergence:** Richardson / GCI on the peak centreline velocity at
   T2 (peak flow) and on the recirculation length at one phase; the
   finest level also with Δt halved.
5. **Cost:** wall time per period per level, and cores (sets a
   pulsatile surrogate study's budget).

**Accept** (provisional gates; report and don't tune if missed):
- Upstream (x = −2D) profiles within 1 % of u_c of the Womersley inlet
  (this checks the inlet, as 0067).
- Downstream profiles: RMS difference within **5 % of u_c** at every
  phase and station at the finest level.
- Peak throat centreline velocity at peak flow within 3 % of the DNS.
- Laminar and axisymmetric (no jet drift), as the DNS.
- `RESULTS.md`; *Outcome* table for RESEARCH; opt-in test for one
  period at the coarsest level.

**Out of scope.**  The eccentric pulsatile case (transitional; decision
0021, stage 3); wall shear stress (not in the database).

## Agent notes

- **Where:** `validation/stenosis_pulsatile/` (a new driver, reusing
  `validation/stenosis/run.py`'s mesh and levels and
  `validation/womersley/run.py`'s inlet and schemes by import), so the
  steady case stays as accepted.
- **Database units:** `Axi_puls/vel_p*.dat` has columns (r, yp, u, v,
  w), w axial, 501 points across the diameter, stations x/D = −2 … 15
  every 1 D.  Its velocities are in u_c units already: u_i = 0.5 is the
  mean bulk velocity, u_c/2.  A free scale fitted to the six x = −2D
  profiles gives 1.00–1.01.
- **Phases, from the flow rate.**  Each file's flow rate is conserved
  along the straight pipe (to 0.3 %; the constriction stations miss it by
  up to 6 %, a sampling effect in the database).  So it fixes the file's
  phase on the inlet waveform:

  | file | nominal t/T | from flow rate |
  |---|---|---|
  | p1 | 0.090 | 0.052 |
  | p2 | 0.257 | 0.263 |
  | p3 | 0.423 | 0.418 |
  | p4 | 0.590 | 0.563 |
  | p5 | 0.757 | 0.755 |
  | p6 | 0.923 | 0.892 |

  p1, p4 and p6 are 0.03–0.04 off nominal, outside the "±0.01 by eye".
  The flow rate is double-valued over a period; the root nearer the
  nominal phase is taken.  The run writes at both sets of phases; the
  comparison uses the flow-rate phases.
- **The DNS's own x = −2D profiles are not the Womersley inlet** at
  either set of phases.  The max difference is 0.03–0.14 u_c; at peak
  flow (p2) the DNS centreline is 1.696 u_c, above the waveform's 1.663
  maximum at any phase.  No single scale, A or α fits all six (residual
  13 %).  Upstream influence of the constriction (1 D downstream) would
  change the shape but not the flow rate, which matches.  Our periodic
  run will show whether the computed x = −2D profile departs in the same
  way.
- **Running:** from rest; `adjustTimeStep` with maxCo 0.5;
  boundaryData every T/480 (linear-in-time error ~1e-5 u_c); one
  pimpleFoam run per sample time (writes exactly there); sampled by a
  `sets` function object (axis, r = 0.48 D, the station diameters),
  so a parallel case stays decomposed.  The processors read the root's
  `constant/boundaryData`: no re-decomposition per period.
- **Cost (coarse, 15 336 cells, 2 processes):** 1 640 steps and 149 s
  per period.

- **k2 measured** (122 688 cells, 4 processes, v2406 Docker, 2026-10-31):
  periodic after **3 periods** from rest (changes 0.60, then 4.8e-5);
  3 785–4 100 steps and about 48 min per period.  Laminar and
  axisymmetric: profile asymmetry ≤ 5e-3 u_c at every station and phase.

  At the flow-rate phases, RMS difference from the DNS (u_c) by station:

  | file | −2 | 0 | 1 | 2 | 3 | 4 | 6 | 10 | x = −2D vs Womersley: ours / DNS |
  |---|---|---|---|---|---|---|---|---|---|
  | p1 | 0.102 | 0.328 | 0.079 | 0.058 | 0.027 | 0.017 | 0.016 | 0.014 | 0.028 / 0.145 |
  | p2 | 0.022 | 0.455 | 0.163 | 0.085 | 0.053 | 0.053 | 0.103 | 0.015 | 0.015 / 0.034 |
  | p3 | 0.056 | 0.276 | 0.083 | 0.059 | 0.050 | 0.045 | 0.043 | 0.048 | 0.019 / 0.078 |
  | p4 | 0.075 | 0.067 | 0.017 | 0.015 | 0.015 | 0.017 | 0.020 | 0.031 | 0.023 / 0.117 |
  | p5 | 0.044 | 0.028 | 0.026 | 0.033 | 0.035 | 0.037 | 0.039 | 0.042 | 0.009 / 0.083 |
  | p6 | 0.015 | 0.089 | 0.010 | 0.011 | 0.011 | 0.011 | 0.010 | 0.010 | 0.021 / 0.027 |

  (The last column is the max difference.)  At the nominal phases p1, p4
  and p6 are much worse (p4: 0.17–0.36; p6: 0.09–0.40), which confirms
  the flow-rate phases.  Throat centreline at peak flow (p2, x = 0):
  4.517 against the DNS's 4.625 (−2.3 %).  The x = 0 column is suspect
  on the DNS side: its flow rate there is 6 % off the pipe's.
- **Cost, for the budget (Q3):** per period about 48 min (k2), about
  3.6 h (k3), about 11.5 h (k4, 981 504 cells) on 4 cores.  Three
  periods per level: k3 ≈ 11 h, k4 ≈ 35 h; Δt halved at k4, 2 periods
  warm, ≈ 46 h.  The whole task as written ≈ 4 days of this machine.

- **2026-11-02, after design's answers.**
  - Ran coarse (k1) and k3, then k2 with Δt halved, per Q3.  All from
    rest except the halved-Δt run, which starts warm from k2's periodic
    state and needs 2 periods.
  - **Bug, found and fixed:** the warm start began its periods at the
    restart time (49.0), not on a period boundary, so its targets sat
    0.04–0.07 T off their phases.  Its features gave it away (p6
    separated, against no reverse flow at k2 and in the DNS).  Fixed in
    `run_level` (the next period boundary), the run discarded and redone.
  - **k3 cost** 6.8 h per period, not the 3.6 h estimated: the steps per
    period grow 1.54× from k2 (the Courant limit at the throat), on top
    of 3.4× the cells.
  - **The coarse level** finished during a niced full-suite run
    (06:43–06:58 on 10-31); its third period's wall time (192 s against
    134 and 159 s) is inflated.
  - **The upstream reverse flow** at p4 and p5 is the Womersley inlet's
    own: at r = 0.48 D eq. 2.1 gives −0.078 and −0.047 u_c.  It is
    present in ours and the DNS, but doesn't test the stenosis's
    upstream influence (RESULTS.md).
  - **Opt-in test:** `test_pulsatile_stenosis_one_period`, the coarse
    level for one period from rest (5.7 min): the pipeline end to end,
    no accuracy (one period isn't periodic).

## Questions for design

**Q1 (blocking): the database's inlet is not eq. 2.1 as we read it.**
The DNS's x = −2D profiles differ from the Womersley inlet by
0.03–0.145 u_c (max), at the phases their own flow rates give.  Ours
differ by 0.009–0.028 u_c on the same mesh run, so the constriction's
upstream influence (real, up to 2.8 % here) doesn't explain it.  At
peak flow the DNS centreline (1.696 u_c) exceeds the waveform's maximum
at any phase (1.663), and no one scale, A or α fits all six files (best
residual 13 %).  The paper says the upstream profiles "closely
correspond" to eq. 2.1, and mentions upstream separation at −1D and
−2D in deceleration.  The downstream differences (up to 0.16 u_c past
the throat at k2) follow from the inlet at least in part.  Options:
- (a) keep eq. 2.1 (as now) and judge downstream at what it gives,
  stating that the DNS's inlet differs;
- (b) drive our inlet with an inlet fitted to the DNS's x = −2D profiles
  (six phases only: a fitted Fourier series in time, per radius), moving
  our inlet to −2D, or keeping −3D and accepting 1D of development;
- (c) another reading of eq. 2.1 (the sin(ωt) as printed?) that fits
  the database: we tried the obvious ones without success.

**Q2 (blocking with Q1): the gates.**
- "Upstream (x = −2D) within 1 % of u_c of the Womersley inlet": our own
  x = −2D departs by up to 2.8 % at k2, a physical upstream effect.
  Measure at −2.5D, or relax to the departure the mesh series converges
  to?
- "Downstream RMS within 5 % of u_c at every phase and station": with
  (a), it fails at k2 at x = 1–6D at peak flow (p2: up to 0.16).
- Phases: the comparison uses the flow-rate phases (Agent notes), not
  the nominal ones.  Recorded here so design can confirm.

**Q3 (for the user, via design): the budget.**  ≈ 4 days of this machine
for k2–k4 and Δt halved at k4 (Agent notes).  Cheaper: Δt halved at
k3 (≈ 15 h instead of 46 h), ≈ 2½ days total.

**Design answers (2026-10-31).**

**Q1: (a), keep eq. 2.1 as the inlet.**  The paper itself confirms the
mismatch.  §3.1 says the upstream centreline drops "to less than
0.3 u_c" at minimum flow, below eq. 2.1's minimum of 0.337 at any
phase.  Together with the agent's 1.696 > 1.663 at peak, the DNS's
upstream flow swings wider than the inlet the paper states.  We can't
tell whether that is an unstated inlet, upstream influence our run
doesn't reproduce, or a database artefact.
- **Not (b):** a Fourier fit through six phases has at most three
  harmonics, and it would validate against the database's upstream
  data instead of the paper's stated setup.  The six phases are the
  comparison data; they can't also be the boundary condition.
- **Not (c):** the obvious readings were tried, and no single A or α
  fits.
- State the discrepancy in README and RESULTS, with the x = −2D table
  (ours vs DNS vs Womersley) as evidence.

**Q2: the gates.**
- **Upstream:** drop "x = −2D within 1 % of Womersley".  Task 0067
  already verifies the inlet machinery.  Instead, **report** our −2D
  departure from Womersley per phase and its convergence over the
  levels.
- **Downstream: two tiers.**  Station-by-station profile RMS is
  **reported, not gated**: with the DNS's upstream differing by up to
  0.145 u_c, a 5 % gate downstream would test the inlet, not the mesh.
  The **gates** are quantities that depend less on the inlet's details:
  - peak throat centreline velocity at peak flow (p2, x = 0) within
    **5 %** of the DNS, and above the paper's 3.65 u_c (k2: 4.517 vs
    4.625, −2.3 %);
  - the **flow features** the paper describes, at the matching phases:
    - the jet and vortex ring in acceleration;
    - separation over the whole post-stenotic section in late
      deceleration;
    - a small **upstream separation at −1D and −2D** in deceleration
      (near-wall reverse flow);
    - no permanent recirculation;
    - laminar and axisymmetric throughout.

    State each as present or absent with the evidence.  If ours lacks
    the upstream separation, that is the finding (it may explain part
    of Q1's mismatch).
  - the solution-verification part as usual: GCI on the throat peak.
- **Phases:** confirmed.  Compare at the flow-rate phases, and list the
  nominal ones in RESULTS.
- **Category:** stays V2, with the inlet caveat stated in `case.json`'s
  notes.

**Q3 (the user, 2026-10-31): levels k1–k3, about 1 day.**
- Run k1 (coarse), k2 (done) and k3.  Check the time step at k2
  (Δt halved, one level only).  No k4.
- GCI from the three levels.  If k1 is outside the asymptotic range
  (Part 1's coarse level had no steady axisymmetric state), say so and
  report k2–k3 as an error band instead of an extrapolation.
- Three periods per level, as measured (periodic after 3).
- Check for another session's runs before starting (shared-machine
  rule).

## Outcome

**Accepted** (V2): every gate design set (Q2) passes.  Full numbers in
`validation/stenosis_pulsatile/RESULTS.md`.

**Files.**  `validation/stenosis_pulsatile/{run.py, README.md,
RESULTS.md, case.json}` (new); `tests/test_validation.py`
(`test_pulsatile_stenosis_one_period`, opt-in); README validation row;
`docs/GALLERY.md` regenerated; mesh images.  Full suite 2144 passed,
14 skipped; the opt-in test passes (5.7 min).

**Levels** (v2406 Docker, 4 processes, periodic after 3 periods from
rest at every level):

| Level | Cells | steps / period | wall time / period | throat peak, p2 (DNS 4.625) |
|---|---|---|---|---|
| coarse | 15 336 | 1 730 | 2.5 min | 4.363 (−5.7 %) |
| k2 | 122 688 | 3 980 | 48 min | 4.517 (−2.3 %) |
| k3 | 414 072 | 6 120 | 6.8 h | 4.566 (−1.3 %) |
| k2, Δt halved | 122 688 | 8 160 | 95 min | 4.516 (change 0.006 %) |

**Gates.**
- Throat peak within 5 % of the DNS and above 3.65 u_c: k3 −1.3 %;
  **pass**.  The coarse level is outside the asymptotic range (observed
  order 1.05; no post-stenotic reverse flow at peak flow), so per Q3 the
  convergence result is the k2–k3 band, 4.566 ± 0.050 (1.1 %).  Formal
  Richardson for the record: 4.661 (+0.8 %), GCI 2.6 %.  The time-step
  error is 0.5 % of the space change.
- Flow features (§3.1), at the flow-rate phases, k2 and k3 alike:
  jet and near-wall reverse flow in acceleration (p1, p2); reverse flow
  over the whole post-stenotic section in late deceleration (p3–p5);
  upstream reverse flow at −2.5 to −1 D (p4, p5); none at p6 (no
  permanent recirculation); asymmetry ≤ 1.2e-3 u_c.  All as in the DNS;
  **pass**.

**Reported.**
- x = −2 D against eq. 2.1, max: coarse 0.04–0.10, k2 0.009–0.028, k3
  0.004–0.013 u_c (order about 2); the DNS 0.03–0.145.
- Profiles against the DNS, k3, 1–10 D: RMS 0.005–0.149 u_c; 37 of 42
  station–phase pairs below 5 % of u_c, the rest p2 at 1–6 D.
- Recirculation ends: p2 8.23 D, p3 13.37 D (k2 to k3: 0.02, 0.04 D);
  DNS between its stations 7–8 D and 13–14 D.

**Surprises.**
- **Refinement moves the p2 jet away from the DNS at 3–6 D:** our jet
  decays more slowly (centreline at 6 D: k2 4.14, k3 4.20, DNS 3.93).
  Whether the DNS's different upstream flow explains it isn't resolved.
- The upstream reverse flow, a gated feature, is the Womersley inlet's
  own near-wall reversal at α 7.5, not the stenosis's upstream influence.
- k3 cost twice the per-period estimate (steps per period grow with the
  throat's Courant limit).

**Proposed follow-ups (for design).**
- **For RESEARCH §7.3:** the k2 cost (48 min per period on 4 cores, 3
  periods from rest) is the budget for a pulsatile surrogate study; k3 is
  8.5× that.
- **The jet decay:** the database can't supply the DNS's own inlet (six
  phases are too few; Q1's answer).  If the authors' actual inlet
  becomes available, rerun k2 and k3 with it.
- **The gated upstream separation** could be restated as "upstream
  near-wall reverse flow, as the inlet's", or replaced by the reverse
  flow at −1 D relative to the inlet's at the same phase.
