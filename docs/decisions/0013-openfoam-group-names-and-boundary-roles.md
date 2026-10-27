# 0013 — OpenFOAM output: group names and boundary roles

- **Status:** accepted
- **Date:** 2026-10-25 (accepted 2026-10-25 by the user)
- **Tasks:** 0022, 0023
- **Answers:** task 0005's *Questions for design* 1 and 2

## Context

Task 0005 (`docs/integrations/openfoam.md`, Known quirks) found two
problems in the OpenFOAM path:

1. **Name clash.**  hexmesh names material-interface groups
   `<a>_to_<b>` (`core/cross_section.interface_names`,
   `assembly/blocks.py:420`).  That is exactly the name
   `splitMeshRegions` gives its own interface patches.  When the groups
   are written, `gmshToFoam` turns each into an empty patch, and
   `splitMeshRegions` reuses those instead of creating `mappedWall` pairs.
   In the insulated pipe this lumped both steel interfaces into one patch
   and merged an interface into the outer wall, **while every region
   still passed `checkMesh`**.  `write_openfoam` works around it by
   leaving the groups out (`interfaces=False`).
2. **Wall types.**  `gmshToFoam` writes every boundary patch as type
   `patch`.  A wall left as `patch` gets no wall treatment (wall
   functions, `wall` group membership), **silently**.  Only hexmesh knows
   which groups are walls: fittings declare them (DESIGN A7), and with
   per-fitting walls (task 0009) there are many wall names.

## Options

### Group names
- **A. Keep `<a>_to_<b>`, always omit from OpenFOAM output.**  It works
  today, but the clash stays for `interfaces=True` and for any other tool
  using the same convention.
- **B. hexmesh-owned names: `interface_<a>_<b>`** (inner → outer order,
  `[A-Za-z0-9_]` only).  This removes the root cause.  Keep omitting them
  from OpenFOAM output by default (the split rebuilds interfaces as
  `mappedWall`), and make `interfaces=True` safe for faceZone users.

### Wall types
- **C. Leave it to the user** (`changeDictionary`, `foamDictionary`).
  Silent errors if forgotten; users must guess roles from names.
- **D. hexmesh retypes after conversion** by running OpenFOAM tools.
  Needs the OpenFOAM environment from Python, and can't be tested
  without it.
- **E. hexmesh writes a role manifest and retypes `polyMesh/boundary` in
  plain Python.**  `write_openfoam` writes a JSON manifest next to the
  `.msh` that maps every physical group to its role (`wall`, `open_end`,
  `interface`, `volume`).  A plain-Python function then rewrites
  `constant/polyMesh/boundary`, and each region's after a split:
  - walls → `type wall;` with `inGroups 1(wall);`;
  - open ends stay `patch`;
  - `mappedWall` patches made by `splitMeshRegions` are left alone.
  No OpenFOAM process is needed, so it's testable on text fixtures.

## Decision

**B and E**, accepted 2026-10-25.

- Interface groups are named **`interface_<inner>_<outer>`** by one
  shared helper, used by sweeps and block layouts alike.
- `write_openfoam` keeps `interfaces=False` as its default.
- Boundary roles come from the graph (A7) and are exported as a
  manifest.  Retyping is a plain-Python step on the converted case.
- `0/` boundary-condition files are **not** part of this decision.  They
  depend on solver and physics, and wait for the `write_openfoam_case`
  successor, informed by task 0020.

## Consequences

- DESIGN A7: names for material-interface groups; roles exported with
  the mesh (applied 2026-10-25).
- **Task 0022:** rename interface groups.
- **Task 0023:** role manifest and boundary retyping.
- Task 0020 (Poiseuille) waits for 0023 and uses the helper instead of
  retyping by hand.
- Breaking change: anyone matching `<a>_to_<b>` group names must update.
  Note it in the changelog or release notes when they exist.
- `splitMeshRegions`' own `mappedWall` names (`fluid_to_steel`, …) are
  OpenFOAM's and don't change; tests asserting them stay.

## Verified vs. assumed

- Verified (task 0005, v1912): the clash and its effect; the empty patch
  plus faceZone for internal groups; every patch written as `patch`.
- Verified in code: `<a>_to_<b>` is generated in two places
  (`core/cross_section.py:187`, `assembly/blocks.py:420`), and
  `io/writers/openfoam.py`'s docstring relies on it.
- Assumed: `inGroups 1(wall);` plus `type wall;` is all `boundary` needs
  for walls in v1912 and later lines.  Check against a `blockMesh`-made
  case.
