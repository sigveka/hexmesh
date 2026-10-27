# 0011 — Port-face signatures and topology-switch strategies

- **Status:** accepted
- **Date:** 2026-10-25 (accepted 2026-10-25)
- **Tasks:** 0019

## Context

DESIGN A4 says every port touching an interface must match its type
exactly, and that type changes happen *inside* a fitting.  It says
*where* a change may happen, but not *which* changes a fitting can make,
or at what cost.  Several open threads are the same question in
different forms:

| Thread | What changes between the fitting's two port faces |
|---|---|
| `Reducer` (task 0013, done) | radii only |
| profiled pipe (0008) | radii along a profile |
| circle ↔ rectangle `Transition` (0009) | boundary shape (same 5-patch layout) |
| `n_outer` sub-partition (0005) | block boundaries only |
| layer termination (0006, accepted; task 0018) | an outermost layer stops or starts |
| O-grid circle → plain grid in a square duct (0009 follow-up) | an O-ring of cells disappears |
| density breaks (0003) | `nang`/`nrad` counts |
| equipment (0003) | anything: non-conformal |

RESEARCH §9.1 and §9.6 give the theory.  In the dual view a face's quad
mesh is a set of chords.  Whether and how a fitting can join two faces
depends only on how their chords differ.  A conformal fill always
*exists* for pipe sections (even quad counts by construction;
`mitchell_1996`, `erickson_2014`).  The practical limits are templates
and cell quality.

**Two partial signatures already exist in code:**
- `interface.port_type(spec)`: exact type key for matching at an
  interface (`assembler.py:216`).  It includes geometry (`repr` of the
  core shape, so the radius).
- `fittings._density(spec)`: "everything except radii", the reducer's
  private class-0 test.  It names the first differing field in errors.

## Options

### A. Keep A4 as is; each fitting checks its own port pair ad hoc
What happens now (`_density` in the reducer).  Each new fitting
re-invents the check and its error messages.  Nothing says which
changes are possible in principle.

### B. A mesh signature per face, a class per port pair, and a declared strategy per fitting
1. **Mesh signature**, computed from a `PipeSpec` in pure Python, never
   from GMSH:
   - layout kind per layer (5-patch O-grid core, annulus ring, plain
     grid, …);
   - chord-family counts (`nang` around; core grid `nang × nang`, or
     `nang_w × nang_h`; `nrad` per layer);
   - the layer stack (names, order).

   It excludes geometry (radii, shape dimensions, aspect ratio) and
   node distribution (`mprg`, `mbmp`); see open question 3.
2. **Class of a port pair** (RESEARCH §9.6), from comparing signatures:

   | Class | Signatures differ by | Strategy that bridges it |
   |---|---|---|
   | 0 | nothing (only geometry or block boundaries differ) | **sweep**: every sheet continues |
   | 1 | closed rings of cells (O-rings, outermost layers) | **pillow / unpillow**: add or remove capped sheets |
   | 2 | counts within the same layout | **refinement template** (fixed ×2 or ×3) |
   | 3 | anything else | **declared non-conformal joint** |

3. **Each fitting declares the strategies it implements** (part of the
   fitting description, next to `template` in DESIGN §6).  `validate()`
   computes the class of every port pair before GMSH.  It accepts the
   pair if the fitting implements a strategy for that class.  Otherwise
   it rejects the pair, naming the difference and the strategy that
   would bridge it.
4. **Interfaces are unchanged.**  Both sides of an interface still
   share one face, and `port_type` equality there stays exact (A1, A4).

### C. Full dual-graph analysis (chords computed from the actual quad mesh)
General, but it needs GMSH or a mesh, so it can't run in validation
(P3/P4).  It's also unnecessary: hexmesh faces come from a small family
of builders whose chord structure follows from the spec.

## Decision

**Option B, implemented incrementally**, accepted 2026-10-25 by the user
("this is what I want").

- **Build the signature and classifier first**, with no new strategies.
  Fittings declare only what they already do:
  - `Straight`, `Bend`, `Closure`, `Reducer`, `MiterBend`: class 0;
  - layer termination (task 0018): class 1, restricted to outermost
    layers ending on a wall;
  - `Tee`: class 0 on each port.
  The reducer's `_density` check becomes "class 0 required", with the
  same field-naming errors.
- **New strategies only with a concrete fitting** (DESIGN §6.1, "not
  built on speculation"):
  - class 1 O-ring removal arrives with the square-duct follow-up of 0009;
  - class 2 and class 3 wait for decision 0003.

Open questions, and how they were settled at acceptance:
1. **A4 wording: settled.**  Applied as written.  Proposed: *"Every port that touches an interface
   must match its type exactly.  Between a fitting's own ports, the
   signatures may differ only in ways covered by a strategy the fitting
   declares (decision 0011)."*
   DESIGN A4 now has the class table; the old "type changes happen
   inside a fitting" sentence is kept as a consequence.
2. **Signature granularity for class 1: investigated in task 0019;
   settled by [decision 0016](0016-class-1-granularity-and-grading-changes.md)** (one class 1).
   Default: one class 1, with the signature difference recording
   whether the ring caps inside the fitting or ends on a wall.  Is "outermost layer present
   on one side only" enough to describe layer termination?  Or does it
   need its own subclass, because its sheet ends on a wall rather than
   capping inside the fitting?
3. **Is grading part of the signature?  Investigated in task 0019;
   settled by [decision 0016](0016-class-1-granularity-and-grading-changes.md)** (yes; sweeps may
   bridge grading-only class 2).
   Default: grading stays in the signature (today's reducer
   behaviour) unless the task shows interpolation is safe.  `_density` currently requires
   equal `mprg`/`mbmp` across a reducer.  Grading changes node positions,
   not connectivity, so it could be excluded from the signature and
   interpolated along the sweep like radii.  Check that station faces
   with different gradings still meet transfinite constraints on axial
   curves.

## Consequences

- DESIGN A4, §6 (`strategies` member) and §6.1 (conformance check):
  **applied 2026-10-25.**
- **Task 0019** (first task): `signature(spec)`, `classify(sig_a, sig_b)`, a
  `strategies` declaration on existing fittings, `_density` replaced, and
  kit checks.  No new geometry.
- Decisions 0003, 0005, 0008 and 0009 can state their needs as classes:
  0005, 0008 and 0009 are class 0; the 0009 duct follow-up is class 1;
  0003 is class 2 or 3.

## Verified vs. assumed

- Verified in code: `port_type` contents and use at interfaces;
  `_density` contents and field-naming errors in `Reducer`.
- From the literature: existence results and the strategies' basis
  (RESEARCH §9.3–9.6).
- Assumed: every face builder's chord structure follows from its spec
  alone (true for O-grid, annulus and plain-grid builders by
  construction; not checked against `square_shell`).  The class
  boundaries are my framework, not taken from a single paper.
