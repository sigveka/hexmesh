# 0008 — Profiled sweep: a varying-radius fitting

- **Status:** accepted
- **Date:** 2026-10-24 (accepted 2026-10-26 by the user: "I accept the
  two tasks")
- **Tasks:** 0031, 0032; 0055 (bulges, amendment 2026-10-28)

## Context

Many pipe components are axisymmetric, with a radius that varies along the
axis: venturis, flow nozzles, smooth orifice-like constrictions,
simplified valve seats, stenoses.  The standard smooth-constriction
benchmark (Varghese et al. 2007, RESEARCH §7.3) has a cosine profile and
public DNS data.  It would make a good first OpenFOAM validation of
hexmesh output.

What exists (task 0013, done except for `Transition`):
- `Reducer` is a `Sweep` with one station per axial layer.  Radii are
  linearly interpolated (`fittings._with_radii`).  Corners at the same
  angle are joined by straight lines, which are generators of the cone,
  so every wall node is on the cone to 1e-12.
- The reducer changes **radii only**.  Everything else in the spec must
  match: `n_outer`, `rot`, `nang`, `mbmp`, layer names, `nrad`, `mprg`
  (`fittings._density`).
- Measured quality: min SICN 0.178 for 0.1 → 0.06 over 0.15; 0.090 for a
  74° half-angle cone.  No cone-angle limit has been needed.
- The whole cross-section scales with the radius (core square at
  `OH_RATIO · r`).

`../geometry_valve/` (2018 `.geo`) shows the alternative: the core square
stays at a **constant** radius (half the throat radius), and only the ring
follows $R(x)$ (RESEARCH §7.3).

## Options

### Fitting shape

**A. Generalise `Reducer` to take a profile.**
`Reducer(length, n_layers, profile=None)`: `None` keeps the linear cone,
and a callable gives $R(s)/R_\text{in}$ (or the outer radius) for
$s \in [0, 1]$.
- One class, and the reducer's tests and kit cases carry over.
- Port specs come from $R(0)$ and $R(1)$, so a constriction that returns
  to the inlet radius has identical port types.

**B. A new `ProfiledPipe` fitting.**
Same machinery, separate name.  Clearer in the graph and in readers (a
venturi is not a reducer), but duplicates the reducer.

### Wall exactness between stations

Stations lie exactly on the surface of revolution.  Between stations:
- **C1. Straight chords** (as now).  The error is about
  $h^2 |R''| / 8$ for station spacing $h$.  Bound it in `validate()` with
  a tolerance, and add stations (axial layers) until it holds.  No new
  machinery.
- **C2. Exact or spline axial wall curves** through the profile: a new
  axial curve kind for `Sweep`, like `Arc` for bends.
- **C3. Leave it to the native backend** (decision 0007 option C), which
  places wall nodes analytically.

### Core behaviour

- **D1. Scale everything with the radius** (current `Reducer`).  Simple,
  and the mesh topology is unchanged.  At a strong throat, the core
  square shrinks with the wall, and so do the ring's radial cells.
- **D2. Constant core, ring absorbs the change** (`geometry_valve`).
  The core size is set by the minimum radius, and the ring thickness
  varies.  This likely gives more uniform cells at a strong throat, but
  ring cells become thin at the throat and thick elsewhere, and the
  ring's `nrad` is fixed.  Untested in hexmesh.

## Decision

**Accepted 2026-10-26: A + C1 + D1, with D2 measured.**

- A: a profile is the general case of the cone.  The reducer *is* the
  linear profile.
- C1 keeps exactness explicit and checkable before GMSH, with no new curve
  kind.  Revisit when decision 0007 settles the backend.
- D1 first, because it is what the reducer does.  Then measure D2 on the
  benchmark geometry (75 % area reduction) and keep it only if min
  quality at the throat improves.

Settled at acceptance:
1. **Profile input: named shapes plus a sampled table**, both
   serialisable (task 0006).  Named: `"cosine"` (constriction fraction
   s₀) and `"venturi"` (standard proportions, to be cited).  A table is
   (s, R/R_in) pairs, interpolated smoothly.  No callables in saved
   networks.
2. **Benchmark length:** task 0032 checks L against the Varghese paper
   before using it (Purdue page: L = 2D; `geometry_valve`: L = D).
3. **D2 is an experiment inside the same fitting** (a core-mode option),
   kept only if it measures better at the throat.
4. **Exactness under decision 0015:** one axial layer per station slab,
   so no surface carries interior nodes; wall nodes are exact at every
   station, and chords between stations are bounded in `validate()`.

### Amendment (2026-10-28, accepted by the user): bulges

`("cosine", s0)` also takes **s0 ≤ 0**: a smooth symmetric bulge with
largest radius `(1 − 2·s0)·R` at the middle; s0 = 0 is a plain pipe.
Allowed range **−1 ≤ s0 < 0.5**, so the bulge is at most 3 R.
- **Why.**  Outward bulges are real geometries:
  - fusiform aneurysms (abdominal aortic aneurysms), and the dilatation
    downstream of a stenosis;
  - expansion chambers and pulsation dampeners;
  - strainer housings;
  - corroded or overpressured pipe sections.
- **For studies.**  One parameter then spans constriction → plain pipe
  → bulge with a single mesh topology: node-aligned variants for a
  surrogate, whose response changes character at s0 = 0.
- **Meshing is unchanged:** every layer scales with r(s), and the
  chord-error check applies as before.
- **The name stays** (`"cosine"`); its docstring says "constriction
  (s0 > 0) or bulge (s0 < 0)".
- **Validation reference for later:**
  [`salsac_and_sparks_etal_2006`], in-vitro PIV in symmetric idealised
  abdominal aortic aneurysms of increasing size (pulsatile, not a steady
  DNS); RESEARCH §7.5.

## Consequences

- DESIGN §6.1 sweep table: the Reducer row becomes "Reducer / profiled
  pipe | two frames + profile | line (chords, bounded error) |
  interpolated" (applied 2026-10-26).
- Stage 0 of the flow-restriction plan (decision 0021).
- **Task 0031:** profile support in `Reducer`: named shapes and table,
  chord-error bound, kit cases (cosine constriction, venturi), a test
  that every station's wall nodes are on R(s), and the D1 vs D2
  measurement.
- **Task 0032:** OpenFOAM run of the Varghese geometry at Re = 500
  against the Purdue data, after task 0020's re-run.  Setup and
  comparison go to RESEARCH §7.3.

## Verified vs. assumed

- Verified: reducer behaviour, exactness and quality figures (task 0013
  Outcome).  `geometry_valve` profile, topology and mesh conformity
  (checked 2026-10-24).  Citations via Crossref.
- Assumed: the chord-error estimate (standard interpolation bound, not
  measured here); D2's quality benefit; L = 2D.
