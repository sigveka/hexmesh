# 0037 — Capability boundaries: sections own their layout, shapes own their behaviour

- **Status:** accepted (2026-11-02 by the user: "accept 0037 with
  sections as its own package")
- **Date:** 2026-11-02
- **Tasks:** 0081, 0082, 0083; design notes added to 0066 (item 4) and
  0060 (item 5).  Related: decision 0036 (needs item 1), decision 0035
  (needs item 1), decision 0032 (item 4 is its §8).

## Context

RESEARCH §12 surveys the package (hexmesh `8b0dc98`, 16 900 lines).
**What holds:** the package graph is layered (no two packages import each
other), GMSH is confined to realisation code, and fittings are thin
descriptions behind a duck-typed contract.

**What doesn't, ranked by what it blocks:**
1. **No section capability.**  The O-H face is described in nine
   modules, twice over: GMSH builders in `faces/`, and an independent
   `BlockLayout` version in `blocks.face_vertices`.  Its geometry
   constants are duplicated.  Every new section type (decision 0036's H
   face, decision 0035's multi-core) touches all nine.
2. **Shape behaviour is type-switched:** about 108 shape-specific sites
   in 17 modules, 89 outside the shape and face builders.  The worst
   are `interchange/build.py` (25), `tee.py` (15) and `spec.py` (13).
3. **Private names cross packages:** `interchange` imports
   `assembly.fittings._with_radii` and `assembly.wye._IN_MARGIN`.
4. **`io` straddles the layers:** the assembly imports `io.writers`,
   while `io.readers` imports `interchange`.  That's a package cycle
   via `io`.
5. **Low-cohesion modules:**
   - `interchange/build.py` (1 309 lines);
   - `fittings.py` (1 033 lines, seven fittings);
   - `Assembly` (45 methods, 30 GMSH calls);
   - `tee.py` (the duct taps' front end inside the pipe tee's class, against DESIGN
     §6: variants are new templates).
6. **Smaller:**
   - two module cycles hidden by function-level imports;
   - the assembler names fitting types;
   - DESIGN §9's deviations table is stale.

Nothing here is a crisis.  But items 1–2 sit on the path of every
planned section type, and items 3–5 grow with each feature.

## Options

### A. Fix opportunistically
No plan; refactor when touched.  Cheap now.  But without a target and a
check, the type switches and leaks keep spreading: 0060–0063 add to
`tee.py`, and 0066 adds to `interchange`.

### B. Named capabilities with contracts, refactored in behaviour-preserving stages, enforced by architecture tests
The capabilities and their dependencies (each depends only on those to
its left):

`core` (shapes, specs) → `sections` → `fittings` (descriptions) →
`assembly` (graph, validation, realisation) → `interchange` (model,
importers, builder) → `study`; `io.writers` is a leaf used by
`assembly`.

1. **`hexmesh.sections`: one object per section layout** (O-H now; H,
   multi-core later).  Each owns:
   - its signature (kind, counts, symmetry);
   - its corner and patch description for `BlockLayout`;
   - its GMSH face build;
   - its predicted quality.

   `faces/*` become its realisation, and `interface.build_face` and
   `blocks.face_vertices` delegate to it.  `CrossSection` becomes
   generic: patches, port curves, named corners.  The O-H anatomy
   (inner points, radials) moves into the O-H layout.
2. **Shapes own their behaviour:** a `Shape` protocol (outer radius,
   half extent at an angle, hydraulic diameter, side counts, outline,
   `to_dict`).  The `isinstance` switches outside `core.shape` and
   `sections` go away.
3. **Public contracts between packages:**
   - no private name imported across packages;
   - `_with_radii` becomes a `PipeSpec` method;
   - margins move to `limits.py`;
   - `_occ` is declared an internal shared module (renamed, or listed
     as allowed).
4. **Readers move to `interchange.importers`** (decision 0032 §8).
   `io` keeps the writers, as a leaf.
5. **Split by cohesion when next touched:**
   - `fittings.py` into one module per fitting family;
   - `interchange/build.py` into parts-graph analysis, insulation
     planning and the mapping to fittings;
   - the duct taps' front end out of `Tee` into `duct_tap.py`;
   - `Assembly` stays the façade but delegates GMSH work to a
     realisation module.
6. **Architecture tests** (pure Python, in the normal suite):
   - the layer order above;
   - no cross-package private imports;
   - no new module cycles;
   - a ceiling on shape-specific sites outside `core.shape` and
     `sections`, lowered as stage 2 lands.

   Start from today's counts as the baseline, so the tests pass on day
   one and stop growth.
7. **DESIGN §9** lists real deviations again.

Each stage is accepted the way decision 0032's stage 1 was: tests
unchanged, and identical `to_dict()` and meshes for every fixture.

### C. Restructure in one go
Rejected: the coding sessions run concurrently with tasks 0060–0066 in
flight, so a large move would conflict with them.  It would also
mix behaviour changes into a refactor.

## Decision

**Accepted 2026-11-02: B, with `sections` as its own package** (it calls
GMSH for realisation; `core` never does).

**Refinement at acceptance:** DESIGN §6.1 says "not built on
speculation": shared protocols are derived from working instances.  So
task 0082 gathers the **one** existing layout (O-H, with its circle,
rectangle and blend shapes) into `sections` as a single description
used by both the GMSH builders and the block layouts.  It does **not**
define a generic section interface.  That interface is derived when the
second layout arrives (decision 0036's H face).  Shapes already have
three implementations, so their protocol (item 2, task 0083) can be
defined now.

**Order:**
1. **Item 6 (architecture tests at today's baseline)** and **items 3–4**
   (cheap leaks).  Independent of the in-flight tasks except 0066, which
   should do item 4 as part of interchange 1b.
2. **Items 1–2 (sections, shape protocol)** before decision 0036's
   prototype and before any decision 0035 stage.  This is the one that
   pays: it turns "a new section touches nine modules" into "a new
   section is one module".
3. **Item 5** as each module is next touched (tee during 0060–0063;
   `build.py` during 0066).
4. **Item 7** with the first DESIGN amendment.

**Tasks:**
- **0081:** architecture tests at today's baseline; the cross-package
  leaks (item 3); the assembler stops naming fitting types.
- **0082:** `hexmesh.sections`, the O-H layout in one place (item 1).
- **0083:** the shape protocol (item 2); lowers 0081's cap.
- **Notes in existing tasks:**
  - 0066: readers move to `interchange.importers`, with a re-export at
    `hexmesh.io.readers` (public in API.md); split `build.py` while
    there;
  - 0060: the duct taps' front end leaves the pipe tee's class.

## Consequences

- **DESIGN.md (applied 2026-11-02):**
  - §3.1 "Capabilities": the map, its four rules and the architecture
    test;
  - §6.1: "Sections" as the fifth shared piece;
  - §9: the stale legacy rows removed, and the current deviations
    listed with the task that removes each.
- **New rule:** shapes and section layouts own their behaviour, with no
  type switches on them elsewhere.  Enforced by the architecture tests.
- **Harder:** each stage costs a coding session with no user-visible
  feature, and in-flight tasks must rebase onto the moved modules.
  Hence the staging, and item 5 only when a module is touched.
- **Effect on future expansions:**
  - 0018 (vascular): constraint 1 (shape is geometry behind one
    abstraction) is met by item 2; contour shapes join as protocol
    implementations.
  - 0019 (agent SDK): stable public contracts (item 3) are what a tool
    schema binds to.
  - 0021 (flow restrictions): constraint 4 (one section-geometry
    abstraction) is met by items 1–2; eccentric cores become a section
    layout or a shape.
  - 0030 (simulation suite): the capability map is the generator
    layer's internal structure; no effect on its contracts.
  - 0035 (multi-core): item 1 is its prerequisite ("fittings sweep any
    blocked section").

## Verified vs. assumed

- **Verified:** the import graph, cycles, fan-in and fan-out, private
  cross-package imports, the shape-specific site counts and the
  duplicated ring-inset formula (RESEARCH §12, measured on `8b0dc98`).
- **Assumed:**
  - that a section object can serve both the GMSH builders and
    `BlockLayout` without loss: their two descriptions agree today,
    but nothing checks it;
  - that the refactor stages are mesh-identical (checked per stage by
    fixtures).
