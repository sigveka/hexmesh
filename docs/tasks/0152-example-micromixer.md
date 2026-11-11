# 0152 — Example: a lipid-nanoparticle T-mixer with a twisted mixing channel

- **Status:** ready
- **Decision:** none new.  The user, 2026-11-12: "yes to micromixer",
  after the design session proposed a T-junction followed by a twisted
  rectangular channel (passive mixing by swirl); "yes" to grounding it on
  the T-mixer benchmark and lipid-nanoparticle (LNP) formulation, after
  the design session's search (2026-11-12, below).
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

**What it is, in the gallery text.**  mRNA vaccines' lipid
nanoparticles form when a lipid-in-ethanol stream meets an mRNA-in-water
stream and the two mix fast.  Lab work uses microfluidic mixers
(T-junctions, herringbone, toroidal); production uses T-mixers and
impinging-jet mixers, and scaling between them by Reynolds number is an
open problem.  The design session's sources (2026-11-12; read the papers,
not the summaries):
- **The T: the engulfment benchmark.**  Hoffmann, Schlüter and Räbiger,
  *Chem. Eng. Sci.* 61 (2006) 2968–2976 (μ-PIV, μ-LIF); Bothe, Stemich
  and Warnecke, *Chem. Eng. Sci.* 61 (2006) 2950–2958 (simulation).  Below
  a critical Reynolds number the streams stay side by side; above it (Re
  ≈ 140–146 reported for a 2:1 mixing channel; up to ≈ 175 for other
  aspect ratios) they engulf each other.  Galletti et al. and Andreussi
  et al. give further geometries.
- **LNP context:** e.g. Jürgens et al. (University of Augsburg), a
  comparison of T-junction, herringbone and flow-focusing mixers.
- **Twisted channels:** Sivashankar et al., *Biomicrofluidics* 10 (2016)
  034120 (200 × 200 µm, but twisted by stacked quarter-circle units, not
  a twisted straight duct); twisted T-channel studies with 200 × 120 µm
  branches and up to 34 revolutions (seen as abstracts only).

**Do.**
1. **Sizes from the benchmark.**
   - **The T** takes the Hoffmann/Bothe geometry: inlet and mixing
     channel widths and the common height, checked in the 2006 papers
     (the design session saw a 2:1 mixing channel quoted, and couldn't
     confirm the dimensions).  Cite in the docstring and
     `docs/references.bib`.  Report the Reynolds number that the onset
     means at a stated flow rate of water.
   - **The twisted channel** is a modelling choice, inspired by the
     twisted-mixer papers rather than copying one: say so, and give its
     twist per length in revolutions per channel width.
   - Lengths that are choices are said to be choices, as task 0121 did
     for the aorta.
   - Build in metres (decision 0047).  Report whether the build at real
     size gives the same cells and quality as the same network × 1000
     (task 0139's result, checked on this geometry).
2. **Build it from fittings:**
   - **the T:** two inlets meeting head-on, the outlet leaving
     perpendicular.  The inlet line is the main and the mixing channel the
     branch: across the main's face it is as tall as the inlets (a
     **full-width tap**, task 0070), and along the main's axis it is
     twice the inlet width.  Check that a duct tap takes a branch longer
     along the axis than the main is wide, and the counts it needs; if
     not, ask under *Questions for design*.  Inlets `lipid_inlet` and
     `aqueous_inlet`;
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
- The engulfment benchmark as a validation case (V3, against Hoffmann
  et al.): a design-session follow-up.  This example's T is sized so it
  can become one.
- A twisted-duct validation case: a follow-up, once its references are
  checked.

## Agent notes

## Questions for design

## Outcome
