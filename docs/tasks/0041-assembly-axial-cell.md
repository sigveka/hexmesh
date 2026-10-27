# 0041 — `Assembly(axial_cell=…)`: `n_layers` from a target cell size

- **Status:** ready (after 0039)
- **Decision:** [0024 — API ergonomics](../decisions/0024-api-ergonomics.md)
- **Depends on:** 0039 (same `add()` code).  Independent of 0040.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Every sweep fitting needs `n_layers`; choosing it per fitting
is repetitive and the usual cause of stretched cells.  The idea already
exists in `extend_open_ends(cells_per_diameter)` and the PCF reader's
`axial_cell`.

**Where.**  `hexmesh/assembly/assembler.py` (`__init__`, `add`,
`close`, `prepend`, `to_dict`/`from_dict`), `fittings.py` (centreline
lengths, minimum layer counts), `hexmesh/io/readers/pcf.py` (reuse),
`API.md`, `README.md`, examples, tests.

**Do.**
1. `Assembly(…, axial_cell=None)`, saved in the JSON.
2. `n_layers=None` on `Straight`, `Bend`, `Elbow`, `MiterBend`,
   `Reducer`, `Transition`, `SplinePipe`, `Closure`: resolved to
   `max(min_layers, ceil(L / axial_cell))` in `add()` (`close()` for
   `Closure`).  `L` is the centreline length; `min_layers` the
   fitting's own validation floor (e.g. the per-layer turn limit of a
   bend; `MiterBend`'s per-leg rule).  Record the resolved value in the
   fitting, so `to_dict()`, `cell_count()` and `refined(k)` see an
   ordinary count.
3. `n_layers=None` without `axial_cell`: `AssemblyError` naming the
   fitting.  An explicit `n_layers` always wins.
4. `stack_changes` index with `n_layers=None`: reject (indices need a
   known count) unless a clean rule is obvious; record the choice.
5. PCF reader: use the assembly's `axial_cell` instead of its own
   computation, if equivalent (record any difference).
6. Simplify a few examples (e.g. `pipe_rack`) to use `axial_cell`;
   regenerate their gallery entries.

**Accept.**
- For each sweep fitting: resolved count as specified, and at least its
  validation floor (a 180° bend with a coarse `axial_cell` still
  validates).
- `to_dict()` → `from_dict()` → identical cell count; the saved fitting
  holds the resolved number.
- Missing both → error naming the fitting.
- Existing code with explicit `n_layers` unchanged (every example and kit
  case meshes identically).
- Full suite: no new failures.

**Out of scope.**  Grading toward a target first cell along the axis;
`Tee`/`Wye` counts (they keep their defaults).

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
