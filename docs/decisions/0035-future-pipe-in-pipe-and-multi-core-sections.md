# 0035 — Future expansion: pipe-in-pipe and multi-core sections (umbilicals, bundles)

- **Status:** proposed (future expansion; staged plan, no tasks).
- **Date:** 2026-11-01.  Recorded at the user's request, after the
  survey in [RESEARCH §11](../RESEARCH.md#11-pipe-in-pipe-umbilicals-and-rod-bundles-surveyed-2026-11-01-design-session).
- **Tasks:** none.

## Context

The user asked about umbilicals.  The survey (RESEARCH §11) separates
two topologies:

- **Concentric: pipe-in-pipe (PiP).**  An inner flowline, an annulus
  (gas, partial vacuum or insulation) and a carrier pipe.  Bulkheads
  seal the annulus at intervals; spacers carry the inner pipe.  The
  section is a layer stack, which hexmesh has.
- **Multi-core.**  N circular inclusions inside one outer boundary:
  - umbilicals (fluid in steel tubes, solid cables, solid filler, a
    round sheath, helical lay);
  - carrier bundles;
  - tube-bundle heat exchangers;
  - nuclear rod bundles (solid rods, coolant in the gaps, a polygonal
    duct).

  The region between the inclusions is multiply connected, so the
  5-patch O-H face can't represent it.

**Where hexmesh stands out:**
- No published method gives a conformal all-hex 3-D umbilical mesh.
  Industry practice is 2-D cross-section thermal analysis, plus beam
  models for mechanics.  3-D matters at terminations, bend stiffeners,
  J-tube entries and burial transitions.
- Rod bundles have established hex methods (slice-and-stack; mesh the
  straight bundle, then deform it), and their defining features aren't
  sweepable (wire contact points, spacer grids).

## The plan, staged

**Stage A: pipe-in-pipe.**  Mostly existing machinery.
1. A layer may be a **second fluid region** (the annulus gas), with its
   own patches and CHT region.  Check what the layer stack and the
   OpenFOAM writer assume today; fix the assumptions if any.
2. **Bulkheads:** a layer whose material changes along a run.  This is
   decision 0021's stage 1 (layer name vs material).  It reuses
   `stack_changes`.
3. **Spacers:** local solid features in the annulus.  Out of the first
   cut, like the later stages of 0021.
4. **Validation:** an annulus natural-convection case, e.g. the
   concentric horizontal annulus of Kuehn & Goldstein (to be confirmed
   in RESEARCH before it's tasked).

**Stage B: multi-core sections, straight.**
1. **A cell-decomposed section** (RESEARCH §11.5):
   - every inclusion gets the Voronoi cell of the inclusion centres,
     clipped by the outer boundary;
   - each cell is an O-grid around its circle, with the polygon as its
     outer outline.  That generalises decision 0026's circle-in-
     rectangle to circle-in-polygon;
   - neighbours share edges with equal counts, so the section is
     conformal by construction.
2. **Inclusions carry their own layer stacks:** a tube with its fluid
   core and steel wall; a cable with its conductor, insulation and
   armour.
3. **Lay-ups to start with:** one central core plus one ring of 6, 8 or
   12; regular lattices (square, triangular) for bundles.
4. **Straights only.**  Prove the section, the port signature, groups,
   regions and the OpenFOAM writer.

**Stage C: routes and helical lay.**
1. **Fittings that sweep any blocked section:** `Bend`, `SplinePipe`
   and `Straight`, with port signatures that identify a section's
   block graph.  This is the hard part: today's fittings sweep the
   5-patch O-H face.
2. **Helical lay:** every station rotates the section by 2π per lay
   length.  The skew is small for umbilical lay lengths (5–30 m against
   0.1–0.3 m diameters).
3. **No junctions.**  Umbilicals and bundles end at terminations; a
   termination is the end of the model.

**Not planned:** wire-wrap contact and spacer grids (rod bundles),
armour-wire mechanics, and fitting-level umbilical terminations.

## Prerequisites per stage

| Stage | Needs |
|---|---|
| A | decision 0021 stage 1 (layer name vs material); a check of the fluid-layer assumptions |
| B | the layer-outline machinery (decision 0026); a section abstraction that isn't tied to the O-H face (as 0021, constraint 4); **per-arc counts on a circle** ([decision 0041](0041-per-side-counts-on-rectangles.md) option C, in its general form), for irregular Voronoi cells; `n_outer = 6` for hexagonal cells |
| C | stage B; the generalised port signatures; the sweep machinery shared with profiles (0008) and stack changes (0006) |

## Constraints for decisions going forward

1. **Don't hard-wire the 5-patch O-H face** into new interfaces, port
   signatures or the conformance kit.  Treat it as one section type
   among several: compare a section's block graph and counts, not a
   fixed patch list.
2. **A layer's role (fluid or solid) belongs to its material,** not
   its position in the stack (the core isn't always the only fluid).
   It is the same split 0021 needs.
3. **Groups and regions are named per inclusion as well as per layer**
   (e.g. `tube3_fluid`, `tube3_wall`).  Naming schemes shouldn't assume
   one core per section.
4. **Per-station frames keep their roll explicit,** so a twist along
   the run (helical lay) is a per-station rotation, not a new fitting
   type.
5. **The cell count stays exact before meshing** (`cell_count()`),
   for multi-core sections too.

## Consequences

If accepted later:
- the Fittings and Sections pages gain section types; DESIGN.md §7's
  port-face rule is generalised;
- a new example category (subsea: PiP flowline, umbilical termination,
  carrier bundle).

**Against the future expansions:**
- **0018 (vascular):** not affected.  Its constraint on shared sweep
  machinery is the same as Stage C's.
- **0019 (agent SDK):** sections become a tool argument with a schema.
  Keep section types data, not classes with hidden state.
- **0021 (flow restrictions):** Stage A depends on its stage 1.  Both
  need the section abstraction (its constraint 4).
- **0030 (suite):** a multi-core section is a natural parametric
  family for studies (lay-up, tube sizes, filler conductivity).
- **0034 (secondary solvers):** rod-bundle users are Nek5000 users.
  Second-order export would then need multi-core sections too.
