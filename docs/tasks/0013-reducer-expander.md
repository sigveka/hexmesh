# 0013 — Reducer, expander and transition

- **Status:** ready
- **Decision:** [0004 — Retire the legacy API](../decisions/0004-retire-legacy-api.md)
- **Depends on:** 0011

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Diameter changes are common in plant piping.  The PCF reader
needs `Reducer` (`io/readers/pcf.py:114`).

**Where.**  Legacy: `connectors/fittings.py` (`Reducer(outlet, length,
n_layers)`, `Expander`, `Transition`; `_taper_connect` at `:164`).  New:
`assembly/fittings.py`.

**Do.**
1. A `Sweep` whose two ports have different specs.
   - `ports()` returns the outlet spec, as `Tee` already does for its
     branch.
   - Internal stations interpolate the radii.  `Path` already has
     per-station specs (`Path.specs`, `spec_at`).
2. Port types (A4): the two specs must share their topology: `n_outer`,
   `rot`, the layer names and their order, and `nang`.  Density may
   differ only where an axial edge does not cross it.  Check what legacy
   `_check_nang_compatible` allows.  Reject anything else in `validate`,
   with a message that names the differing field.
3. `Expander` and `Transition` become aliases or thin variants, only if
   they differ in behaviour.  Otherwise keep one class, named in the
   docstring.

**Accept.**
- Kit cases: a reducer, an expander, and a two-layer reducer.
- Test: wall nodes of every station lie on the straight cone between
  the two radii.
- Test: a spec with a different topology is rejected before GMSH.

## Agent notes

## Questions for design

## Outcome

_Not done._
