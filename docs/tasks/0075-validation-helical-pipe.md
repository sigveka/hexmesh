# 0075 — Validation (V3): laminar flow in a helical pipe (spline pipe)

- **Status:** blocked (held by the user: run nang 24 over nights, Q5; not started)
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

- **De Amicis et al. (2014), 2026-11-06.**  It is *Prog. Nucl. Energy*
  76, 206–215, with authors De Amicis, Cammi, L. P. M. Colombo,
  M. Colombo and Ricotti.
  - The open copy at re.public.polimi.it (handle 11311/861372 and its
    `/retrieve/…_Cammi.pdf` file) sits behind a Cloudflare JavaScript
    challenge.  The handle page returns 403, and the PDF link returns
    the challenge page instead of the PDF.  I didn't try to get around
    it.
  - A search found no other open copy.
  - Gelfgat (arXiv 1809.01367) compares against these data, but only as
    a figure (four coils, friction factor against Re, agreeing up to
    Re ≈ 3000).  It doesn't tabulate the coils or the values.
- Nothing is built yet: step 1 needs the paper's coil (d, D, pitch).
- **The paper, read 2026-11-06** (`docs/papers/deamicis_and_cammi_etal_2014.pdf`).
  This is for RESEARCH §7.9, which design maintains.
  - **The SIET coil** (Table 2; the paper's own measurements): inner
    diameter d = 12.53 mm, helix diameter 1000 mm, pitch 800 mm per turn
    (0.127 m/rad), tube length 32 m (about 10 turns).  κa = 0.0118,
    τa = 3.00e-3, λ = τ/κ = 0.255.  Water at ambient temperature,
    single phase.
  - **The other coils** (Table 6) are coils 02, 04, 06 and 08 from
    Cioncolini & Santini (2006), measured there, not in this paper.
  - **Ranges:** laminar data run from Re ≈ 1750 to the transition at
    Re ≈ 3200 (Figs. 3 and 12), so De = Re √(d/D) ≈ 200–360.  The paper
    reports no laminar SIET point below Re ≈ 1750.
  - **The data aren't tabulated.** The measured f_D appears only in
    figures: Fig. 3 (f against Re, the full range), Fig. 4 and Fig. 12
    (the laminar–transition range, with the correlations and the CFD).
    The error bars in Fig. 12 are about ±0.005–0.01 on f ≈ 0.04–0.07
    (roughly ±10–15 %) at the lowest Re.  The points scatter about 5 %
    about the correlations.
  - **The tables report** the correlations' RMS errors against the data
    (Table 3, Re ≤ 3200: Ito 4.14 %, White 3.70 %, Prandtl 3.57 %, Mori &
    Nakayama 4.88 %, Hasson 3.40 %, Barua 6.56 %, Srinivasan 9.53 %).
    The text names Ito's correlation as the best overall.
    - Table 7 gives the CFD's RMS errors: OpenFOAM 2.56 % on SIET, with
      a maximum error of about 5 % for every code.
    - Table 4 gives OpenFOAM's section-mesh sensitivity (SIET: dp/ds
      0.01557–0.01558 for 1125–2880 section elements).
- **Step 1, the spline (no flow yet):**
  - Geometry: a `SplinePipe` through points on the SIET helix (3.5
    turns), clamped to the helix tangent at both ends.  The distance from
    the spline to the true helix comes from a Newton projection onto the
    helix, at 10⁵ points along the spline.  The curve is hexmesh's own
    `_cubic_spline`.

    | points per turn | max deviation | interior (10–90 %) |
    |---|---|---|
    | 8 | 8.8e-2 d | 4.6e-2 d |
    | 16 | 5.5e-3 d | 2.6e-3 d |
    | 24 | 1.1e-3 d | 5.0e-4 d |
    | **32** | **3.4e-4 d** | 1.6e-4 d |
    | 48 | 6.7e-5 d | 3.1e-5 d |

  - At 32 points per turn the spline is within the task's 0.1 % of d.
    The error falls as h⁴, and it is largest near the clamped ends.
    Station centres lie on the spline.
  - Between stations, the meshed (faceted) centreline sags from the
    curve by s²κ/8.  That is 2.9e-3 d at a station spacing of s = 1 d,
    and it falls with axial refinement: it is discretisation, not
    geometry.
  - Cost: 432 cells per section at nang 12 and 768 at nang 16.  At about
    1 d per layer, 3.5 turns (906 d) is 0.4M / 0.7M cells, so three
    levels of 87k–700k cells are affordable.
- **The runs (2026-11-06, after the answer to Q2):**
  - `validation/helical_pipe/run.py`: 3 Re × nang 8, 12, 16, about
    2 h 45 min on 4 processes.
  - Every solve but Re 3000 at nang 8 met the residual target in
    210–720 SIMPLE steps.  That one ran the full 5000.
- **f from turn means of p:** under helical symmetry, the difference
  between consecutive turns' volume-mean pressures is exactly one turn's
  pressure drop.  Turns 2→3 and 3→4 agree to 10⁻⁶, so the flow is
  developed within the first turn.
- **The bulk velocity (a definition fixed after the coarse trial):**
  - The mesh carries 0.5–1.4 % more than the nominal U_B (by level): the
    faceted section is smaller than πa², and the inlet parabola is set
    at face centres.
  - So f and Re use the measured bulk velocity, and Ito is evaluated at
    that Re.
  - With the nominal U_B, the coarse trial read +6.9 % instead of +4.8 %
    from Ito.
  - This was decided on the single trial level (Re 2400, nang 8), before
    the study.  It changes the quantity's definition to the standard one,
    not the gate.
- **The data:** `data/deamicis_2014_fig12.csv` holds the paper's points,
  digitised by marker colour from a 600 dpi render (method in
  `data/README.md`).
- **The development length:** with a Poiseuille inlet, the 5 d straight
  and the first turn suffice.  More turns would only add cost.

## Questions for design

- **Q1. The reference can't be fetched by an agent** (Agent notes).
  Options:
  - (a) the user downloads the PDF in a browser into `docs/papers/`, and
    the task resumes as written;
  - (b) the case uses a coil chosen here, gated against Manlapaz &
    Churchill (1980) as a V4 correlation case, until the paper is in
    hand;
  - (c) another open laminar-coil dataset.

  With (a), nothing else changes.

**Design answer** (2026-11-06; the user: "yes"): **(a).**  The user
downloads the PDF into `docs/papers/`, and the task resumes as written.
The Manlapaz & Churchill correlation (b) isn't a substitute for the
paper's data.
- **Done 2026-11-06:** the user downloaded it:
  `docs/papers/deamicis_and_cammi_etal_2014.pdf` (gitignored, like the
  other papers), cited as `deamicis_and_cammi_etal_2014` in
  `docs/references.bib`.  The task resumes as written, from step 1 (the
  paper's coil: d, D, pitch).

- **Q2. The measured friction factors are only in a figure** (Agent
  notes).  The gate, "within 5 % of the measured value at each Re",
  needs measured values, so which reference?
  - (a) **Digitise** Fig. 12's laminar points (Re 1750–3200) by hand
    from a high-resolution render, into `data/`, with the reading
    uncertainty stated, and gate against them.  The points' own scatter
    and error bars (±10–15 % at low Re) are comparable with the gate.
  - (b) **Gate against a correlation** the paper validated on these data,
    and report the digitised points.  Ito, the one the paper recommends,
    has a 4.1 % RMS error against the data.  Manlapaz & Churchill isn't
    in the paper's comparison.
  - (c) Ask the authors or SIET for the tabulated data.

  A gate band against the points (a) would need setting before the
  runs.  Also, the three Re must lie in 1750–3200, the only laminar
  range measured.

**Design answer to Q2** (2026-11-06; the user: "yes"): **(b)**, with
the gate fixed now, before any run.
- **Gate:** the developed Darcy friction factor within **5 % of Ito's
  correlation** at three Re in the measured laminar range: **1800, 2400
  and 3000** (De ≈ 200–340), on the SIET coil (d 12.53 mm, D 1 m, pitch
  0.8 m per turn).  The paper validated Ito on these data (Table 3:
  4.14 % RMS) and names it the best overall.  The case is V4 on the
  correlation, with the measurement as its basis.
- **Also gated:** Richardson status `converging` (task 0089) for f at
  each Re; and the spline within 0.1 % of d of the helix (step 1:
  3.4e-4 d at 32 points per turn).
- **Reported:** the digitised Fig. 12 laminar points (Re 1750–3200),
  in `data/` with their reading uncertainty and the paper's error bars
  (about ±10–15 % at low Re).  They aren't gated: a 5 % band can't
  discriminate against points with ±10–15 % bars.
- (c), asking the authors for tabulated data, is optional and the user's
  to do.  If tables arrive, the gate against them is a new decision
  before any rerun, not a change to this one.

- **Q3. f converges too slowly at the higher Dean numbers**
  (`validation/helical_pipe/RESULTS.md`).
  - The Ito gate passes at all three Re: +0.36 %, +1.26 % and +1.92 % at
    nang 16.
  - Mesh convergence over nang 8, 12, 16:
    - Re 1800 converges (order 1.29, GCI 2.0 %).
    - Re 2400 is `converging` only formally (order 0.04, GCI 130 %).
    - Re 3000 is `diverging`: the fine-pair difference exceeds the
      coarse pair's.  **Fail.**
  - It isn't the Re drift between levels.  The error falls monotonically
    toward Ito at every Re, so the coarse levels are outside the
    asymptotic range at De 270–340.
  - Options:
    - (a) rerun on nang 12, 16, 24 (nang 24 is about 1.8M cells; roughly
      3–4 h for the three Re).  The gate is unchanged, on finer levels,
      chosen now that nang 8 is known to be too coarse;
    - (b) record the case as rejected on the convergence gate, as run;
    - (c) something else.

**Design answer to Q3** (2026-11-06; the user: "yes").
- **Rerun on nang 12, 16 and 24.**  The gate is unchanged (f
  `converging` at each Re, and f within 5 % of Ito).  Choosing levels in
  the asymptotic range is part of the convergence study; the Q2 answer
  didn't fix them.  At De 270–340 the secondary flow needs more than
  nang 8 to be asymptotic.
- **The outcome rule, fixed now, before the rerun:** if the 12/16/24
  series isn't `converging` at every Re, the case is recorded as
  rejected, with the Ito comparison and the digitised points reported.
  No further levels, and no change to the gate.
- **Before the run** (CLAUDE.md): check `df -h .` and for another
  session's heavy run.  Delete the OpenFOAM cases afterwards, keeping the
  numbers in `results.json` and the task.
- **The bulk velocity: agreed.**  f and Re use the bulk velocity the
  mesh carries (0.5–1.4 % above nominal), fixed before the study.
  Report the faceted section's area error beside it, per level, so the
  correction is visible.

**Q4: nang 24 costs about 5× my estimate, so the rerun stopped**
(2026-11-06).
- **What ran:**
  - The driver ran on LEVELS = (12, 16, 24), reusing the stored nang 12
    and 16 runs.  The faceted-area error is stored per level: nang 8
    0.64 %, 12 0.29 %, 16 0.16 %, 24 0.07 %.
  - Before the run, 31 GB was free and no other heavy run was active.
  - The first nang 24 case (Re 1800) hit the driver's 5 h timeout at
    step 306, unconverged.  Its p residual was 2e-6, falling about 2.4×
    per 25 steps, against a target of 1e-7.  The other two Re weren't
    started.
  - The case was deleted.  It had no fields written (the write interval
    is the end time), so it couldn't be restarted.
- **My estimate in Q3 was wrong.**
  - nang 24 is **2.71M cells**, not 1.8M.  `LAYERS_PER_TURN` scales
    with nang, so the axial count grows too.
  - At np 4 it takes **about 48 s per step** on a quiet machine (69 s
    while the full suite shared the CPU).
  - It would converge at about 390 steps, so **about 5 h per Re and
    15–16 h for the three**, against the 3–4 h I gave.  For comparison,
    nang 16 (0.80M cells) took 319 steps.
- **The outcome rule doesn't cover a level that wasn't run,** and the
  machine time is the user's to give, so I stopped.
- **Options:**
  - (a) run nang 24 as planned: about 16 h in one stretch, one case at a
    time, about 1.6 GB of disk per case, deleted after each;
  - (b) the same, but each nang 24 case starts from the nang 16 field,
    mapped (`mapFields`).  That likely needs fewer steps, at the cost of
    a driver change.  It wasn't measured, so it's a guess at 2–3 h per
    Re;
  - (c) another set of levels.  That is a change to the study design.

**Design answer to Q4** (2026-11-06; the user: "let us do b").  The
machine time is given (the user, via the coding session).
- **(b): start each nang 24 case from the converged nang 16 field,**
  mapped onto the nang 24 mesh (`mapFields` or the driver's own
  interpolation).  The flow is steady, so the start changes only the
  path to convergence, not the converged answer.  The convergence
  target (p residual 1e-7) and the gate are unchanged.
- **Re 1800 first.**  Record its wall time and steps against the
  unmapped run (306 steps, 5 h, unconverged), then run 2400 and 3000.
- **Timeouts:** set the driver's limit so that one case can finish
  (the user gave about 6–9 h for the set).
- **Addition to the Q3 outcome rule:** a level that doesn't finish
  leaves the case **blocked, undecided**, not accepted or rejected.
  Report what ran and stop.
- **As before:** check `df -h .` and for other heavy runs first.
  Delete each OpenFOAM case once its numbers are in `results.json`.
- (c), other levels, isn't taken: it would change the study after the
  coarse results, and a 16 → 20 step is too small to pin the order.

**Q5: the mapped nang 24 run didn't finish either; case blocked,
undecided** (2026-11-06, under the Q4 rule).
- **The driver** (uncommitted when run, committed with this note):
  - `MAP_FROM = {24: 16}`: the nang 16 fields from the first run had
    been deleted under the disk rule, so each Re first re-solves nang 16
    as a source in `work/`, outside the stored levels.
  - `mapFields <source> -consistent -sourceTime latestTime` then fills
    the nang 24 initial field.  The source is deleted after the target
    solve.
  - Each level now stores `wall_s` and `init_from`.  The sources go in
    `extra.map_sources`.
  - A 3-step smoke test (nang 8 → 12) checked the mapping.  The inlet's
    `uniformFixedValue` BC survives it.
- **Re 1800, run alone with a 4.5 h timeout:**
  - The nang 16 source took 319 steps in 48 min, with f 0.06668,
    identical to the stored level (`f_vs_stored` 0.0).
  - nang 24 from the mapped field was at **step 263** when the timeout
    hit, about 3.3 h of solving at 45 s per step.  Unconverged.
  - By then p was at 1.9e-7 (target 1e-7), and U at 3.6e-8–7.0e-8
    (target 1e-8).

  | step | p residual, unmapped | p residual, mapped |
  |---|---|---|
  | 26 | 2.6e-2 | 2.0e-2 |
  | 101 | 1.3e-3 | 4.0e-5 |
  | 201 | 4.2e-5 | 8.4e-7 |
  | 251 | 1.0e-5 | 1.9e-7 |
  | 301 | 2.1e-6 | — |

  - The mapped start gains about 1.5 decades in p by step 100.  After
    that, both fall at the same rate (about 2.2× per 25 steps).  U, not
    p, sets the stop.
  - **Estimate:** about 330 steps to converge (about 4.1 h), so about
    5 h for Re 1800 with its source.  Re 2400 and 3000 took 561 and 720
    steps at nang 16 (against 319), so at the same ratio they would need
    roughly 9 h and 11 h.  The set needs **about 25 h**.
- **The case was deleted.**  As in Q4 it couldn't be restarted, because
  the write interval is the end time.  A restartable driver would write
  fields periodically, e.g. every 50 steps, and resume from
  `latestTime`.
- **Per the rule, 0075 is blocked and undecided.**  Neither accepted nor
  rejected.  What ran: nang 12 and 16 at all three Re (stored), and two
  unfinished nang 24 attempts at Re 1800.
- **For design:** whether to spend about 25 h of machine time (perhaps
  over several nights, with restartable cases), or another route.

**Design answer to Q5** (2026-11-07; the user: "I choose 1 but hold off
on starting it for now").
- **The plan:** finish the study as designed: nang 24 at Re 1800, 2400
  and 3000, about 25 h in all, split over nights.
- **A restartable driver first:** write the fields every 50 steps, and
  resume from `latestTime`, so that no run is lost to a time limit.
  Also record f every 50 steps, as evidence of whether f has settled
  before the residual target.  It is reported, not a stopping rule: the
  convergence target (p 1e-7; U as the case sets it) is unchanged.
- **Held:** no long runs until the user says go.  Preparing the driver
  and testing it on a short case is fine; ask the user if in doubt.
- **As before:** check `df -h .` and for other heavy runs before each
  night's run.  Restart files for a 2.71M-cell case are large: keep only
  the latest time and delete the case once its numbers are saved.
- Shortening the pipe isn't taken: it would change the study and need
  the coarse levels rerun.

## Outcome

_Blocked on Q3; the runs and results for nang 8, 12, 16 are complete._

- **Files:** `validation/helical_pipe/` (`run.py`, `README.md`,
  `RESULTS.md`, `case.json`, `results.json`, and `data/`: Fig. 12
  digitised, with its README); `validation/tools/recheck.py` (the case
  added).
- **For RESEARCH §7.9 (the SIET coil, laminar, v2406):**

  | Re | De | f (nang 16) | vs Ito | fc/fs | convergence, nang 8 → 16 |
  |---|---|---|---|---|---|
  | 1800 | 201 | 0.06668 | +0.36 % | 1.884 | order 1.29, GCI 2.0 % |
  | 2400 | 269 | 0.05606 | +1.26 % | 2.112 | order 0.04 (not asymptotic) |
  | 3000 | 336 | 0.04918 | +1.92 % | 2.316 | diverging |

  The spline is 3.4e-4 d from the helix at 32 points per turn.  The
  digitised measured points lie 3.7 % below Ito on average.
- **Surprises:**
  - the bulk-velocity excess from the faceted inlet;
  - how quickly the flow develops (within one turn).

