# 0075 — Validation (V3): laminar flow in a helical pipe (spline pipe)

- **Status:** ready (the paper is in docs/papers/, 2026-11-06)
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

## Outcome

_Not done._
