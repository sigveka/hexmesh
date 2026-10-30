# 0071 — Validation (V1): fully developed laminar flow in rectangular ducts

- **Status:** ready
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (category V1); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V1 (exact: rectangular-duct series)
- **Depends on:** rectangular sections (task 0028); the shared OpenFOAM
  helpers (0043); toolchain v2406 in Docker (0012's amendment).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The duct counterpart of Poiseuille (task 0020): an exact
solution that validates the rectangular O-H section, before any duct
fitting.

**Exact solution.**  Fully developed flow in a rectangle of half-sides a
(across) and b (height) satisfies μ∇²u = dp/dx with u = 0 on the walls.
Its Fourier series (e.g. for a ≥ b)

u(y, z) = (16 a² / (μ π³)) (−dp/dx) Σ_{n odd} (−1)^{(n−1)/2} / n³ ·
[1 − cosh(nπz / 2a) / cosh(nπb / 2a)] · cos(nπy / 2a)

gives the velocity field, the flow rate and f·Re on the hydraulic
diameter (≈ 56.9 for a square; 96 in the parallel-plate limit).  Derive
and check it in the driver (sum to a stated tolerance; the square's
f·Re = 56.91 is the check).  Write the formula and its source in
README.md (Shah & London 1978, RESEARCH §7.8).

**Where.**  `validation/rect_duct/` (`run.py`, `README.md`,
`RESULTS.md`, `case.json`, `meshes()`), on `hexmesh.study.openfoam`
with the v2406 runner.

**Do.**
1. Aspect ratios **1, 2 and 4** (half-sides a/b), laminar, Re ≈ 100 on
   the hydraulic diameter.  Straight duct long enough to be fully
   developed at the measuring stations (as Poiseuille: inlet length plus
   two stations, or a developed inlet).
2. **Inlet:** the exact profile (via `timeVaryingMappedFixedValue` or a
   uniform `fixedValue` field written once; there are no coded BCs), or
   a uniform inlet with enough development length (say which).
3. **Compare:**
   - Δp between two stations (hence f·Re), against the exact value;
   - the velocity field on a cross-section against the series (max and
     RMS error as % of the centre velocity).
   - As for Poiseuille, compare against the meshed geometry too (the
     rectangle is exact, so there's no polygon deficit; say so).
4. **Convergence:** three levels with `refined(k)`; Richardson / GCI on
   f·Re and the centre velocity.

**Accept** (V1 gates, as Poiseuille):
- extrapolated f·Re and centre velocity within **0.1 %** of exact;
- finest-level errors below 1 %;
- observed order reported (decision 0015: not gated on O-H sections);
- `case.json` (category V1, tags `laminar`, `flow`, `section:rect`,
  `straight`); RESULTS.md; *Outcome* table for RESEARCH.

**Out of scope.**  Heated ducts (a follow-up with Shah & London's Nu);
developing flow.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
