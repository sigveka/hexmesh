# 0120 — Validation: the Vattenfall T-junction (thermal mixing), stage (a): case, mesh, data and volunteer card

- **Status:** ready (after 0119)
- **Decision:** [0012](../decisions/0012-openfoam-validation-cases.md), amendment 2026-11-09; [0044 — Volunteer runs](../decisions/0044-volunteer-runs.md)
- **Depends on:** 0119 (the volunteer tool).  Category V3.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A turbulent T-junction against measurements, on a fitting
hexmesh builds today (a 90° tee, r/R ≈ 0.71).  The LES is too heavy for
this machine, so it is prepared here and offered as a volunteer run.

**Sources** (`docs/papers/`, all local): the specification
`oecdnea_2009.pdf` (geometry, Table A4 inlets, Table A5 thermocouples,
the upstream LDV tables), the report `smith_and_mahaffy_etal_2011.pdf`
(the comparisons, participants' meshes in Table 7), and
`kuczaj_and_komen_2008.pdf` (resolution).

**Where.**  `validation/vattenfall_tee/` (README, `case.json`,
`run.py`, `data/`, `volunteer.json`); `docs/RESEARCH.md` §7 (design
moves the findings there).

**Do.**
1. **Reference data into `data/`:**
   - the upstream LDV tables from the specification, as CSV (the inlet
     profiles), scaled to the benchmark's flow rates as the
     specification says;
   - the downstream measurements: look for tables (report, appendices,
     the specification's data list, the NEA pages).  If only figures,
     digitise the report's measured points (velocity at 1.6, 2.6, 3.6,
     4.6 D; the thermocouples' mean and RMS), with the digitising
     method and its uncertainty recorded.
2. **The case:** the rig's geometry from the specification (lengths,
   positions of the measuring planes), built with hexmesh's `Tee`;
   inlets from the LDV profiles; water properties from Table A2;
   pimpleFoam with a passive or Boussinesq temperature as the
   specification's buoyancy discussion supports (say which, and why).
3. **The mesh, sized by Kuczaj & Komen:** about 3–4 mm mean cell size
   in the mixing region (λ/3 with λ ≈ 10 mm), wall cells for wall
   functions at y+ ≈ 30, coarser upstream.  Report cells per level for
   three levels (e.g. 8, 4, 3 mm) and compare with the report's Table 7.
4. **A timing run here** (the 4 mm level, Docker runner, 4–8
   processes): enough steps to measure seconds per step and the time
   step (CFL as the specification or Kuczaj & Komen used), then scale to
   30 s physical time.  Measure peak memory and disk.  Delete the run.
5. **Proposed gates, for design** (under *Questions for design*, not
   fixed here): which quantities (mean and RMS velocity at which
   stations; mean and RMS wall temperature at which thermocouples), and
   which band (e.g. against the measurement's uncertainty, or the
   spread of the report's best LES).  Design fixes them before the card
   is offered.
6. **The volunteer card** for the 4 mm LES (decision 0044): every
   requirement measured or labelled as scaled from step 4.  Not listed
   in VOLUNTEERS.md until design has fixed the gates.
7. **Optional, cheap:** a steady RANS on the 4 mm mesh against the mean
   velocity at 2.6 D, reported only (RANS is known to miss the mixing
   fluctuations).

**Accept.**
- `data/` holds the inlet tables and the downstream reference, with
  provenance.
- The mesh levels' cell counts and quality (min SJ, non-orthogonality)
  are reported; the tee's warnings, if any, listed.
- The card's requirements are measured or scaled with the method
  stated; proposed gates are under *Questions for design*.
- No LES run kept; disk freed.

**Out of scope.**  The LES itself (stage (b), a volunteer run); the
dead-leg benchmark (after equal tees); conjugate heat transfer through
the Plexiglas (adiabatic walls, as Kuczaj & Komen).
