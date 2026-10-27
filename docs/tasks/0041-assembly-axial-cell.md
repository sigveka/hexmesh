# 0041 — `Assembly(axial_cell=…)`: `n_layers` from a target cell size

- **Status:** done
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

- **Mechanism.**  The resolution hook from 0040 (`fitting.resolve`,
  called in `add()`, `close()` and now `prepend()`) takes
  `axial_cell` and, for `close()`, the target frame.  `Sweep.resolve`
  returns `replace(self, n_layers=n)` with `n` the smallest count
  `>= max(1, ceil(L / axial_cell − 1e-9))` that passes `layers_ok(n)`.
  The `1e-9` matches the PCF reader's rule, so an exact multiple is not
  rounded up.  Each fitting provides `centreline_length` (default
  `self.length`) and, where it has one, `layers_ok`:
  - `Bend`/`Elbow`: `|angle| / n < 180°`.  **The task's "per-layer turn
    limit of a bend" does not exist in validation** (exact arcs, no chord
    limit); the only floor is that a 180° slab has antiparallel faces
    (`corners.frame_offset`).  So a coarse 180° bend gets 2 layers,
    270° gets 2, 170° gets 1, and all validate;
  - `SplinePipe`, `Closure`: per-slab turn `<= MAX_CHORD_TURN` (30°);
    `L` is the curve's arc length;
  - `Reducer` with a profile: the chord tolerance (the same test as its
    `check`);
  - `MiterBend`: `L` is one end leg, `radius·tan(cut/2)`, since
    `n_layers` counts an end leg's cells (inner segments get 2×).
- **Defaults.**  `n_layers` defaults to `None` on `Straight`, `Bend`,
  `Reducer`, `Transition`, `SplinePipe`, `Closure` (it was required, so
  no existing call changes).  `Elbow` (8) and `MiterBend` (2) keep their
  defaults, so they need an explicit `n_layers=None`; changing the
  defaults would change existing meshes.  See the follow-up below.
- **Unresolved `None`** reaching `check()` (a fitting used outside an
  assembly) raises "n_layers=None is resolved by Assembly.add() …".
- **`stack_changes` with `n_layers=None`:** rejected; no clean rule
  (fractions would need rounding that could merge two changes).
- **JSON:** `axial_cell` saved at top level (only matters for fittings
  added after loading); `refined(k)` divides it by k.
- **PCF reader:** now passes its cell (`axial_cell` or the outer radius)
  to `Assembly(axial_cell=…)` and adds every component with
  `n_layers=None`.  One difference: a kinked run's `SplinePipe` used to
  be divided by the polyline length of its pipes; now it is the spline's
  arc length (slightly longer), and the 30°-per-layer floor applies.  On
  the test inputs (`LINE`, `ELBOW_45`, the kinked PCF and the bathymetry
  route) every layer count is identical before and after.

## Questions for design

_None._

## Outcome

- **Done** 2026-10-27.
- **Files:**
  - `hexmesh/assembly/sweep.py` (`Sweep.resolve`, `centreline_length`,
    `layers_ok`, `_check_n_layers`, `MAX_RESOLVED_LAYERS`),
    `fittings.py` (the per-fitting hooks, `n_layers=None` defaults,
    `_arc_length`, `_max_turn`), `assembler.py` (`axial_cell`, resolve in
    `close`/`prepend`), `intent.py` (`axial_cell` saved, scaled by
    `refined`), `tee.py`/`wye.py` (hook signature),
    `io/readers/pcf.py` (uses the assembly's `axial_cell`);
  - tests: new `tests/test_axial_cell.py` (25);
  - `API.md`, `README.md`; `examples/networks/pipe_rack.py` (no
    `n_layers` anywhere, `toward=` for its three bends; 14 280 → 13 872
    cells, min SICN 0.078 → 0.100) and its gallery entry.
- **Accept:**
  - per fitting (`Straight`, `Bend`, `Elbow`, `MiterBend`, `Reducer`,
    `Transition`, `SplinePipe`, `Closure`): resolved count as specified;
    floors tested for bends (180°, 270°, 170°, `Elbow(180)`), a sharp
    spline (one layer fewer fails "use more axial layers") and a cosine
    reducer (one fewer fails "use n_layers >= N");
  - `to_dict()` → `from_dict()`: identical cell count and description;
    the saved fittings hold the numbers;
  - missing `axial_cell`: `AssemblyError` naming `Bend(radius=0.3, …)`;
  - explicit counts unchanged: every existing test, example and kit case
    passes as before;
  - a resolved network (straight, `toward` bend, reducer, straight)
    meshes = predicted with quality ok.
- **Tests:** full suite 1339 passed, 5 skipped, 0 failed (1314 before,
  +25).
- **Surprises:** bends have no turn-per-layer validation limit, only the
  180° antiparallel case (above).
- **Follow-ups (proposed, for design):**
  1. `Elbow`/`MiterBend` default `n_layers=None`, falling back to 8 / 2
     when the assembly has no `axial_cell`?  Keeps old code unchanged and
     drops the explicit `n_layers=None`, at the cost of the "None
     without `axial_cell` is an error" rule for these two.
  2. A quality-based floor for bends (e.g. ≤ 45° per layer) when
     resolving from `axial_cell`: a 170° bend at a coarse cell gets one
     layer, which validates but is poor.
