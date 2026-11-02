# 0071 — Validation (V1): fully developed laminar flow in rectangular ducts

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md) (category V1); judged per [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) as amended
- **Category:** V1 (exact: rectangular-duct series)
- **Features:** `section:rect`, `straight`
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

5. **Cartesian control** (added by the design session, 2026-11-02;
   decision 0015 amendment 2).  The same case, the same three levels
   (ratio 2), on a uniform Cartesian `blockMesh` of the same duct, at
   about the hexmesh level's cell count per section and the same axial
   spacing.  Same inlet, planes, post-processing and Richardson.
   - Planes: put `blockMesh` block boundaries at the Δp and profile
     stations, so they're planes of faces, as in the hexmesh case.
   - Report per level and ratio: control error, O-H error, and their
     ratio at matching cell count.

**Design note (2026-11-02).**  The O-H levels measured so far fail the
original gates for reasons of the section, not the case: square f·Re
+2.65 / +1.97 / +1.16 % with growing differences (no Richardson
estimate); a/b = 2 non-monotone.  A 2-D control at the same cell count
converges at order 2 (RESEARCH §7.11).  So the gates move to the
control (decision 0015 amendment 2), and the O-H levels are reported.
A non-O-H hexmesh section is decision 0036 (accepted; the H face is the
default for ducts).  Task 0084 adds an H series to this case, gated like
the control.  RESULTS.md
should present both side by side.

**Accept** (V1 gates, as Poiseuille, **on the Cartesian control**; decision 0015 amendment 2):
- extrapolated f·Re and centre velocity within **0.1 %** of exact;
- finest-level errors below 1 %;
- observed order reported, and near 2 on the control (if not, the case
  setup is suspect: stop and report);
- the hexmesh O-H levels **reported, not gated**: signed errors, the
  observed order where defined, the ratio to the control;
- `case.json` (category V1, tags `laminar`, `flow`, `section:rect`,
  `straight`); RESULTS.md; *Outcome* table for RESEARCH.

**Out of scope.**  Heated ducts (a follow-up with Shah & London's Nu);
developing flow.

## Agent notes

- Step 2: the exact inlet profile as a nonuniform `fixedValue` at the
  face centres, scaled to the discrete flow rate, and the same profile as
  the initial field.  The duct is developed end to end, 10 D_h long.
- Step 5: the control is a four-block `blockMesh` split at the three
  planes.  It has `nz` × `nz`·(a/b) square cells per section, with `nz`
  = round(√(O-H section cells / (a/b))): 100 / 162 / 324 against the
  O-H's 108 / 180 / 324.  It has the same axial cells and is selected
  by `--meshes`.
- `extrapolate()` flags `differences_grow`.  Poiseuille's `richardson()`
  takes |log(ε32/ε21)|, so growing differences still give a positive
  order (0.24 on the O-H square).

## Questions for design

_None._

## Outcome

Accepted on the Cartesian control (2026-11-02, v2406 in Docker, gmsh
4.12.1; O-H at 1063b15, control at 6309d2c, no code change between).

**Files.**
- `validation/rect_duct/`: `run.py` (exact series,
  `--check-series`, O-H and control levels, Richardson,
  `versus_control`, `meshes()`), `README.md`, `RESULTS.md`,
  `case.json` (accepted) and `img/`.
- Tests: `tests/test_validation.py` has `test_rect_duct_coarse`
  (O-H regression) and `test_rect_duct_control_coarse`; both pass, 17 s.
  `tests/test_validation_meta.py` passes (5).
- `docs/GALLERY.md` and `docs/gallery/metrics.json` are regenerated.

**Series.**  f·Re 56.908 / 62.192 / 72.931 (Shah & London 56.91 /
62.19 / 72.93); a/b = 1000 gives 95.87 (plates: 96).

**For RESEARCH (signed f·Re error; k = 1 / 2 / 4; order;
extrapolated − exact):**

| a/b | Cartesian control | p | ext. | O-H | p | O-H ÷ control at k = 4 |
|---|---|---|---|---|---|---|
| 1 | −3.92 / −1.02 / −0.26 % | 1.93 | +0.011 % | +2.65 / +1.97 / +1.16 % | none (differences grow) | 4.50 |
| 2 | −3.09 / −0.80 / −0.20 % | 1.94 | +0.008 % | +0.45 / +0.70 / +0.48 % | none (non-monotone) | 2.36 |
| 4 | −2.65 / −0.68 / −0.17 % | 1.95 | +0.006 % | −0.66 / +0.08 / +0.15 % | none (sign change) | 0.85 |

- **u_c, control:**
  - fine-level errors −0.11 / −0.04 / −0.02 %; order 1.90–1.91;
  - extrapolated +0.080 / +0.096 / +0.083 %, which passes the 0.1 %
    gate;
  - the centre fit's own bias (+0.06–0.09 %, measured on the exact
    field) is almost all of that.  Net of it: +0.012 / +0.006 /
    +0.003 %.
- **u_c, O-H:** oscillatory at every ratio.  At k = 4 it is 3–9× the
  control's error.
- **Max field error at k = 4:** O-H 1.0–1.2 %, control 0.10–0.18 %.

**Surprises.**
- The O-H a/b = 2, k = 1 level ran to the 20 000-iteration cap.  Ux and p
  had settled (2.6e-7, 3.5e-5).  Uy and Uz, whose exact values are zero,
  stayed at normalised residuals ~1e-3.
- At coarse levels the O-H looks better than the control: the two errors
  have opposite signs, so the corners' error cancels part of the
  discretisation error.

**Proposed follow-ups.**
- Fix Poiseuille's `richardson()` to report growing differences (no
  order, no extrapolation) instead of |log|.  Poiseuille's own numbers
  are unaffected.
- Replace the centre fit with a direct estimate of u_c, or at least gate
  u_c net of the fit's measured bias, before the H series (task 0084)
  is gated like the control.
- Convergence on the transverse velocity components: base it on Ux and p,
  or on absolute residuals.
- Cost: the finest levels took 28 min (O-H) and 18 min (control) serial
  at 415k cells.  A parallel runner (`decomposePar`) would help 0072 and
  0084.
