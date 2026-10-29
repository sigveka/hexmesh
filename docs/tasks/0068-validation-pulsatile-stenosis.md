# 0068 — Validation: pulsatile flow through the cosine stenosis (Varghese et al., Part 2)

- **Status:** ready (after 0067 and 0032)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
