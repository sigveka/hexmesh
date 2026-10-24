# 0015 — PCF and bathymetry readers build an Assembly

- **Status:** ready
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

## Questions for design

## Outcome

_Not done._
