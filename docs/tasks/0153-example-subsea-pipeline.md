# 0153 — Example: a subsea pipeline over a sandwave field (the bathymetry reader)

- **Status:** ready
- **Decision:** [0032](../decisions/0032-network-interchange.md) (the
  bathymetry importer).  The user, 2026-11-12: "do a subsea reader
  example".  The full subsea case, with umbilicals, waits for decision
  0035 stage B.
- **Depends on:** none.  After 0145 and 0146 in the coding session's
  order.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `read_bathymetry` (a seabed surface plus a 2-D route, returning
a network model) is used by no example.  The gallery shows the PCF
reader (`pcf_line`) but not this one.  A pipeline laid over an uneven
seabed is also the most striking picture of `SplinePipe` following real
terrain.  Free spans over sandwave crests are a real design concern for
subsea pipelines.

**Do.**
1. **The seabed: generated, not downloaded.**  The example writes a
   small XYZ file (to a temporary directory or next to its output, not
   into the package):
   - a sandwave field: a gentle slope plus sinusoidal crests across the
     route.  Wavelength and height come from a cited source on
     sandwaves (typically hundreds of metres and a few metres); say
     which values are choices;
   - plus a route of a few waypoints that crosses the crests at an angle
     and turns once.
   - Name a public bathymetry source (e.g. GEBCO) in the docstring for
     users with real data, without depending on it.
2. **Read and build:**
   - `read_bathymetry(xyz, route, burial_depth=…)` (exposed: 0, or a
     shallow burial; say which);
   - `model.to_assembly(spec, kinks="spline")`;
   - **the section:** a subsea line's typical layers: the fluid, a steel
     wall, an anti-corrosion coating and a concrete weight coat.  Typical
     thicknesses for a stated pipe size, cited or said to be typical.
3. **The riser (if it fits):** at the route's end, a `Bend` up and a
   vertical `Straight` toward the surface, named `riser`.  If the model's
   assembly can't be extended after `to_assembly`, say so under *Agent
   notes* and stop at the seabed end: that finding matters for the
   interchange API (decision 0032).
4. **Show what the reader did:** the build report's `tol_source` and
   snap tolerance (task 0138), and the route's length and largest slope,
   in the gallery text.
5. **Mesh and report** as the other examples.  A long, thin network: use
   the gallery's `fit` rendering, and add a cut-away or a close-up of one
   crest if the overview is unreadable.
6. **Register** in `hexmesh.examples.applications`, the gallery and
   `tests/test_examples.py`.  APPLICATIONS.md says which reader made it.

**Accept.**
- The example builds and meshes, from a generated seabed, with no
  network access.
- Sources cited; choices said to be choices.
- Gallery entry and tests; full suite: no new failures.

**Out of scope.**  Umbilicals and pipe-in-pipe (decision 0035); seabed
soil as a mesh region; real survey data in the repository.

## Agent notes

## Questions for design

## Outcome
