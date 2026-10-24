# 0015 — PCF and bathymetry readers build an Assembly

- **Status:** done
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0012, 0013

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `io/readers/pcf.py:113` builds a legacy `Network` from
`Straight`, `Bend` and `Reducer`.  `io/readers/bathymetry.py` builds on
`NetworkSpec`.  Both stop working when legacy code is deleted.

**Where.**  `io/readers/pcf.py` (`NetworkSpec`, `ComponentSpec`,
`_elbow_params`); `io/readers/bathymetry.py`;
`io/writers/physical_groups.py`, which uses `core.region.RegionSet`.

**Do.**
1. Replace the `NetworkSpec` → `Network` builder with `Assembly`:
   `Straight`, `Bend` (or `Elbow`, task 0012) and `Reducer`.
2. PCF gives absolute end points.  Build each fitting from them, then
   check that each placed outlet matches the next component's start.
   Report a mismatch as an `AssemblyError` that names the component.  Do
   not snap silently.
3. Find out whether `io/writers/physical_groups.py` and `core/region.py`
   are used by anything that survives task 0017.  Delete them or keep
   them, and record which.
4. Keep this task to building the assembly.  Saving and loading the
   network description is task 0006.

**Accept.**
- Test: a small PCF fixture (straight → elbow → reducer → straight)
  builds, validates and meshes, with the predicted cell count.
- Bathymetry: the existing tests still pass (optional dependencies
  skipped).

## Agent notes

- **The PCF parser never worked.**  The number pattern `[-\d.]+` also
  matched the hyphen in the keywords (`END-POINT`, `CENTRE-POINT`), so
  `read_pcf` raised `ValueError: could not convert string to float: '-'`
  on every line with coordinates.  Nothing tested it.  The pattern is now
  `pcf._NUMBER`, a signed decimal with an optional exponent.
- **The legacy `to_network` was wrong in three more ways:**
  - it skipped reducers ("user handles manually");
  - it ignored the elbow plane, so every elbow bent toward `up`;
  - it dropped `ignored` fittings, leaving gaps and chaining the next
    pipe from the wrong place.

  Replaced by `NetworkSpec.to_assembly(spec, axial_cell=None,
  kinks="error", tol=1e-4, lc=None)`.
- **Mapping.**
  - pipe, and fittings such as flanges and valves (they occupy pipe
    length) → `Straight`;
  - elbow → `Bend`, radius and angle from the centre point, with the roll
    computed so the bend direction points at the centre;
  - concentric reducer → `Reducer`;
  - eccentric reducer → `AssemblyError`.

  `spec` is a `PipeSpec` (a reducer outlet scales the core radius by
  `end_bore / bore` and keeps the shells) or a callable `bore → PipeSpec`.
- **No snapping.**  Each component is placed from the previous outlet.
  Its start and end points, and the outlet direction, are checked to
  `tol` (default 0.1 mm, for PCF coordinate rounding).  A mismatch raises
  `AssemblyError` naming the component index, type and position.
  `_sort_by_connectivity` still appends disconnected components, but the
  builder then reports them as a gap.
- **Bathymetry.**  `read_bathymetry` returns a polyline of pipes that
  change direction at every vertex with no fitting, which the legacy
  builder chained as a straight line.
  - With `kinks="spline"`, each maximal run of pipes becomes one
    `SplinePipe` through its end points.  The run's end tangent is the
    next component's start direction; for an elbow, that comes from its
    centre point.
  - With the default `kinks="error"`, the kink is reported.
- **Step 3.**
  - `io/writers/physical_groups.py` and `core.region.RegionSet` are used
    only by legacy (`connectors/`, `network.py`); for 0017, delete both.
  - `core/region.py` stays for `MaterialGraph`, which `PipeSpec` uses.
  - `io/writers/openfoam.py` doesn't depend on legacy (task 0005).

## Questions for design

## Outcome

- **Files:** `io/readers/pcf.py` (`to_assembly`, `_build_assembly`,
  `_start_direction`, `_NUMBER`, `ComponentSpec.record_type`; `to_network`
  removed), `io/readers/bathymetry.py` (docstring),
  `tests/test_io_readers.py` (new, 7 tests: full PCF line through a
  flange, an elbow needing roll 180°, a reducer and a pipe; a bore →
  spec callable; gap and wrong elbow end point named; eccentric rejected;
  kinks rejected or splined; a bathymetry route meshed end to end).
  Predicted cells equal meshed cells in every meshing test.
- **Tests:** 530 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
- **For 0017:** delete `io/writers/physical_groups.py`, the
  `write_physical_groups` export in `io/__init__.py` and
  `io/writers/__init__.py`, and `core.region.RegionSet`.
