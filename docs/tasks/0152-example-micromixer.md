# 0152 — Example: a microfluidic T-mixer with a twisted mixing channel

- **Status:** ready
- **Decision:** none new.  The user, 2026-11-12: "yes to micromixer",
  after the design session proposed a T-junction followed by a twisted
  rectangular channel (passive mixing by swirl).
- **Depends on:** none.  After 0145 and 0146 in the coding session's
  order.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The application examples are a process plant, HVAC, cooling
channels and the aorta, with a rocket feed line in progress (0140).  None
shows:
- rectangular channels at **micrometre scale**: task 0139 made a tee
  build down to 1:1000;
- **`Straight(twist=…)`** on a rectangle, a real geometry (the walls
  twist).  Twisted microchannels are a known passive-mixing idea: the
  twist drives secondary flow that folds the two streams' interface.

**Do.**
1. **Sizes from a cited source, not invented.**
   - Take a typical T-mixer channel (width, depth, aspect ratio) and a
     twisted-channel mixer's twist rate from an open paper or review on
     passive micromixers.  Cite each in the module's docstring and
     `docs/references.bib`.
   - Values that are modelling choices (lengths, the twist angle) are
     said to be choices, as task 0121 did for the aorta.
   - Build in metres (decision 0047).  Report whether the build at real
     size gives the same cells and quality as the same network × 1000
     (task 0139's result, checked on this geometry).
2. **Build it from fittings:**
   - **the T:** two inlets meeting head-on, the outlet leaving
     perpendicular.  A rectangular main with a duct tap: a
     **full-width tap** if the branch is as wide as the face (task 0070),
     otherwise a narrower tap.  Inlets `inlet_a`, `inlet_b`;
   - **the mixing channel:** a short `Straight`, then a twisted
     `Straight` (the twist from step 1, in several turns if the source
     calls for it; `validate()` names the `n_layers` it needs);
   - **optionally a serpentine:** a few 180° `Bend`s on the duct (check
     what a duct `Bend` takes: `roll` picks the bend plane), ending at
     `outlet`.  Leave it out if the twist alone makes the point, and say
     why.
   - **Layers:** fluid only (a chip's walls are usually not modelled), or
     a wall layer if the source's case is thermal.  Say which.
3. **Mesh and report** as the other examples: cell count before meshing,
   `validate()`, min SJ and max non-orthogonality.  The gallery entry
   gets the overview and a section through the twisted part.
4. **Register** in `hexmesh.examples.applications`, the gallery
   (`FAMILIES` if it shows a feature), and `tests/test_examples.py`.
   APPLICATIONS.md lists the fittings it uses.

**Accept.**
- The example builds, meshes and passes `validate()` without errors.
- Sources cited; choices said to be choices.
- The scale check reported.
- Gallery entry and tests; full suite: no new failures.

**Out of scope.**
- Flow or mixing simulations.  A mixing-index study would be a
  validation case of its own, against a published micromixer.
- A twisted-duct validation case (laminar flow in twisted square ducts):
  a design-session follow-up, once the references are checked.

## Agent notes

## Questions for design

## Outcome
