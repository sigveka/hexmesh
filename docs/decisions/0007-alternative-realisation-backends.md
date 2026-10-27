# 0007 — Alternative realisation backends

- **Status:** proposed
- **Date:** 2026-10-24
- **Tasks:** none (proposed decisions get no tasks)
- **Revised:** 2026-10-24, Cubit abandoned by user decision (option A
  rejected); B/C/D still open

## Context

gmsh with OpenCASCADE is the only realisation backend (pipeline steps
4–7, DESIGN §5).  It has cost real effort: OCC-version-dependent
`fragment()`, `getBoundary` ordering, gradings overwritten on re-apply,
filled surfaces off the true geometry by 3–21 % (see
`docs/integrations/gmsh.md`).  The proposal is to evaluate Cubit as an
alternative.

### Cubit facts (from the 17.10 manual in `docs/manuals/` and Sandia's licensing page)

- **Edition and licence.**  The local manual is **Sandia Cubit 17.10**
  (SAND2026-24135W).  Sandia Cubit is for **US government use only**:
  agencies, and contractors working under a US government contract
  (limited-term licences).  Universities can get non-commercial licences.
  Everyone else uses **Coreform Cubit**, the commercial edition with
  exclusive distribution rights.  A free non-commercial "Learn" licence
  was announced in 2020; current terms are unverified.
  ([Sandia licensing](https://cubit.sandia.gov/licensing/),
  [Coreform rebrand, 2020](https://www.digitalengineering247.com/article/coreform-rebrands-trelis-meshing-software))
- **Not installed here.**  Nothing can be tested locally yet.
- **Scripting.**  Python via `import cubit; cubit.init([...]);
  cubit.cmd("...")`, i.e. command strings, with the Cubit libraries on
  `sys.path` (manual, "Importing Cubit into Python").
- **Meshing that matches hexmesh's needs:**
  - map/submap and sweep schemes;
  - automatic interval matching across the model;
  - curve bias and dual bias (grading);
  - pillowing and conformal hex refinement (144 and 237 manual hits).
    The two refinement papers in RESEARCH §9.3 and §9.5 were implemented
    in Cubit;
  - Verdict quality metrics (scaled Jacobian and others), which Sandia
    originated;
  - boundary-layer meshing.
- **Direct element creation:** `create hex node 1,...,8 owner volume 1`.
  Externally computed elements can be loaded and exported.
- **Export:** Exodus, Fluent `.msh`, Abaqus, Nastran, I-DEAS, Patran,
  LS-DYNA, CGNS, STL.  **No OpenFOAM and no gmsh export** (0 mentions).
  The OpenFOAM path would be Fluent export → `fluentMeshToFoam`
  (unverified for multi-region CHT).
- **Conformity mechanism.**  Cubit normally makes shared faces conformal
  with **imprint and merge**, using a geometric merge tolerance (default
  1e-6).  That is a spatial match, which DESIGN P2 forbids.  Building
  volumes from pre-shared surfaces, or loading hexmesh-computed nodes and
  elements, would be needed to stay within P2.

### Current coupling to gmsh (measured)

- `assembly/fittings.py`, `assembly/tee.py`, `assembly/interface.py`:
  **no** gmsh calls.  The tee already produces a `BlockLayout`: corners,
  edges with curve kinds, divisions, gradings.
- gmsh calls are concentrated in:
  - `BlockLayout.realise()` (`blocks.py`);
  - the sweep slab fill (`sweep.py`, `corners.py`);
  - the face builders (`faces/_gmsh_helpers.py`, `oh_circle.py`);
  - `Assembly` meshing, physical groups and quality (`assembler.py`,
    17 calls).

## Options

### A. Cubit as a drop-in backend — **rejected**
**Rejected 2026-10-24 (user decision): Cubit is abandoned.**  The
reasons are recorded below.  Cubit is not to be used as a backend, a peer
mesher or an export step.

Port the face builders, slab fill and `BlockLayout.realise()` to
`cubit.cmd` strings.
- **Gains:** refinement and pillowing; FEA exports.
- **Costs:**
  - two code paths in every builder;
  - imprint/merge works against P2 unless avoided;
  - no OpenFOAM export;
  - licence-restricted, so most users and CI can't run it;
  - can't be tested here.

### B. A backend-neutral block description, then backends
Every fitting's `fill` emits a neutral description instead of calling
gmsh: blocks (8 corners), edges (curve kind and exact parameters,
divisions, grading, orientation), faces, and the physical group of each
entity.  `BlockLayout` is most of this already.  Backends consume it:
- **gmsh** (the current behaviour, moved behind the interface);
- **native** (option C).
- **Gains:**
  - P3/P4 work (cell count 0003, topology invariance 0007,
    serialization 0006) runs on the description with no GMSH at all;
  - backends become swappable and testable against each other.
- **Cost:** a refactor of the realisation layer.  Fittings mostly don't
  change.

### C. Native realisation: hexmesh places the nodes itself
The mesh is fully determined by exact curves and transfinite
interpolation (RESEARCH §5).  hexmesh already has every curve
analytically: lines, arcs, saddle curves, frames.  It can compute nodes
in numpy and write hexes directly:
- to MSH (for gmsh/OpenFOAM tools);
- to OpenFOAM `polyMesh` directly;
- to Exodus (for FEA users), if needed later.
- **Gains:**
  - wall nodes lie *exactly* on cylinders and tori, which removes the
    OCC filled-surface deviation (DESIGN §6) and the one-layer-per-slab
    workaround;
  - no CAD kernel, no OCC version quirks;
  - fastest;
  - deterministic node numbering (helps 0007's topology-invariance
    test).
- **Costs:** hexmesh owns TFI (simple, well-defined), face orientation
  and output writers.  It loses gmsh's GUI/geometry inspection unless
  gmsh is kept as a viewer, by loading the MSH.

### D. Stay gmsh-only
No work.  Keeps living with OCC quirks.

## Decision

Not decided (except option A: Cubit is rejected).  **Recommendation: B,
with C as the second backend.**

- B is the enabling step, and much of it exists (`BlockLayout`).  It
  pays off even with gmsh as the only backend: everything before meshing
  becomes pure Python.
- C targets hexmesh's actual pain points (OCC quirks, surface deviation)
  and adds no licence dependency.
- Refinement and pillowing (RESEARCH §9.3–9.5, decision 0003), the
  capabilities Cubit would have offered, must come from hexmesh's own
  templates if they are ever needed.

To settle first:
1. **Is gmsh still needed as a geometry kernel?**  Check that every
   fitting's exact geometry is available analytically (sweeps: yes; tee:
   saddle splines; future wye: Hermite curves and elliptic petals,
   RESEARCH §4.2).
2. **Spike for C:** TFI-mesh one `Straight` and one `Bend` in numpy,
   write MSH, and compare node positions and connectivity with the gmsh
   result.  Same spike-task question as decision 0005.

## Consequences (if the recommendation is accepted)

- DESIGN §3 "Realisation" layer: defined by the neutral block
  description, not by GMSH.  DESIGN §5 steps 4–7 become "backend" steps.
- DESIGN §6 "fill primitive is a transfinite volume built between
  existing faces": restated in backend-neutral terms.
- `docs/integrations/`: `gmsh.md` keeps its role; a native-writer file is
  added for output formats.  No `cubit.md`.
- Tasks 0003, 0006 and 0007 get simpler, because they work on the
  description without GMSH.  Re-check their steps when this is accepted.

## Verified vs. assumed

- **Verified from the local manual:** Python API form; schemes;
  bias; interval matching; pillow/refine; direct hex creation; export
  formats; no OpenFOAM or gmsh export; merge-tolerance-based merging.
- **Verified from Sandia's licensing page (web):** government-only
  distribution; Coreform as the commercial route.
- **Verified in code:** where gmsh calls are and aren't.
- **Assumed:** that every future
  fitting's geometry can be expressed analytically; native TFI node
  positions matching gmsh's.
