# 0013 — Reducer, expander and transition

- **Status:** done
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

- **Step 2 refined: a reducer changes radii only.**  The outlet spec
  must equal the inlet in everything except the core radius and the shell
  thicknesses: `n_outer`, `rot`, `nang`, `mbmp`, layer names and order,
  `nrad` and `mprg` per layer.  `validate` names the first field that
  differs (`fittings._density`).  The legacy `_check_nang_compatible`
  checked only `nang`.  A different `nrad` or grading is a density change,
  which a reducer doesn't need, and a different layer stack is decision
  0006 (proposed).
- **Exact cone walls.**  There is one station per axial layer, with
  linearly interpolated radii (`fittings._with_radii`).  Corners at the
  same angle are joined by straight lines, which are generators of the
  cone, and radial faces are planar.  Every wall node is on the cone to
  1e-12 (tested), with no interior wall nodes.  The cell count is
  unchanged (`n_layers` slabs of one layer).
- **Step 3: one class.**  The legacy `Expander` is code-identical to
  `Reducer`, so there is only `Reducer` (a larger outlet makes it an
  expander, as its docstring says).
- **`Transition` is not ported.**  Legacy `Transition` is circle → square
  shell (`BoundaryType.SQUARE`, `faces/square_shell.py`), and the
  assembly rejects square shells (`interface.check_supported`).  See
  **Questions for design**.
- No cone-angle limit is needed so far.  A 74° half-angle (radius
  0.1 → 0.03 over 0.02) still meshes with min SICN 0.090, the same as a
  54° cone; `check_quality` reports quality.

## Questions for design

- **`Transition` (circle → square).**  It needs square-shell faces in the
  assembly, which DESIGN doesn't cover (rejected in
  `check_supported`).  Options:
  1. accept losing it in decision 0004.  It is used only by legacy
     tests (`test_connectors.py`, `test_quality.py::TestTransitionQuality`),
     not by examples or `io`.
  2. a separate decision to support square / rectangular sections in the
     assembly (ducts, bundle cells), with `Transition` as one of its
     tasks.

  Recommendation: 1 now, and 2 if ducts are a target.  Everything else
  in this task is done.  Only this question keeps it `blocked`.

  **Design answer (2026-10-24): option 2.**  `Transition` moves to
  [decision 0009](../decisions/0009-rectangular-sections-and-transitions.md)
  (rectangular sections and circle ↔ rectangle transitions, proposed),
  where it will get its own task.  This task is done without it.

## Outcome

(Reducer/expander done; `Transition` pending the question above.)

- **Files:** `assembly/fittings.py` (`Reducer`, `_density`, `_radii`,
  `_with_radii`), `assembly/__init__.py`, `tests/test_reducer.py` (new,
  8 tests), kit cases `reducer`, `expander`, `reducer-2layer`.
- **Tests:** 499 passed, 10 failed (the known `TestYJunctionQuality`
  failures), 4 xfailed.
- **Measured:**
  - Wall nodes lie on the cone to 1e-12 for both a reducer and an
    expander.
  - Predicted cells equal meshed cells for every taper tried.
  - Min SICN 0.178 (0.1 → 0.06 over 0.15), 0.203 (two-layer).
