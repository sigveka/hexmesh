# 0075 — Validation (V3): laminar flow in a helical pipe (spline pipe)

- **Status:** blocked (the measured f is only in a figure: Q2)
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

## Outcome

_Not done._
