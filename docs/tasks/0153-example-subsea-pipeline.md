# 0153 — Example: a subsea pipeline over a sandwave field (the bathymetry reader)

- **Status:** done (the design session, at the user's request, 2026-11-12)
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

**Out of scope.**
- **A flexible riser on a rigid flowline** (the user, 2026-11-12): every
  wall layer changes between the two, which needs decision 0021 stage 1
  (a material-change stack change; see its note of 2026-11-12).  Here
  the riser, if built, has the flowline's section.  The two-type line is
  this example's follow-up.
- Umbilicals and pipe-in-pipe (decision 0035); seabed soil as a mesh
  region; real survey data in the repository.

## Agent notes

- **The seabed:** Dronkers 2024 (Coastal Wiki): crest spacing most
  often 200–700 m, mean height ≈ 0.07 λ^0.8 (Flemming 2000).  λ = 300 m,
  H = 6.7 m.  Generated as XYZ in a temporary folder.
- **The section:** steel, coating and wet insulation (the user asked
  for a well-insulated flowline), typical values stated as such; no
  concrete weight coat.
- **Extending an imported network works:** `asm.add` on the open end
  `to_assembly` left; the riser bend's angle is taken from the arrival
  heading so the riser is vertical.
- **The reader's report:** `tol_source` came out `"relative"`
  (tolerance 0.055 m), not `"reader bathymetry"`: the relative tolerance
  exceeds the reader's floor on a 700 m network.  As task 0138 designed.
- **Bug fixed:** `_subdivide_route` called `float()` on a one-element
  array (a NumPy deprecation, an error in a future NumPy).  One line in
  `interchange/importers/bathymetry.py`; `tests/test_io_readers.py` 36
  passed with hexmesh's deprecations as errors.
- **The overview** is a hairline at true scale; the cut-away of the riser
  base, coloured by material, shows the layers.  It needed the gallery's
  new `by_material` cut-aways and per-example colours (task 0154).

## Questions for design

None.

## Outcome

- **Files:** `hexmesh/examples/applications/subsea_pipeline.py`; the
  bathymetry fix; registry, GUIDE table; `docs/references.bib`
  (`dronkers_2024`); the gallery entry.
- **Numbers:** 183 744 cells, min SJ 0.77, min SICN 0.003 and max
  aspect 985 (1.5 m axial cells against the 3 mm coating: a
  pipeline-scale mesh, said in the docstring); no `validate()` warning.
- **Tests:** `tests/test_examples.py` (the example meshes; registry, families and GUIDE table): 8 passed for the new examples and the listing checks.
- **Follow-ups:** the flexible riser on the rigid flowline, after
  decision 0021 stage 1.
