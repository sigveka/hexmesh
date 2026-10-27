# 0024 — API ergonomics: port names, absolute orientation, angle units, axial cell size

- **Status:** accepted
- **Date:** 2026-10-27 (accepted by the user: "Evaluate the developer
  and AI ergonomics of the API" → "yes" to recording items 3–6)
- **Tasks:** 0039 (two validation bugs, found in the same review), 0040
  (port names, orientation, angle units), 0041 (axial cell size)

## Context

Review of the public API on 2026-10-27 (design session): `API.md`,
exports, docstrings, and about 25 deliberate mistakes run against the
API without meshing.

Strengths to keep: every check and the exact cell count before GMSH;
errors that name the fitting; a JSON replay log that rejects unknown
fields; a small model (`PipeSpec`, `Assembly`, `add`).

Problems found:

1. **Bug:** `validate()` accepts two fittings on one interface
   (`add(a.inlet, Straight(…))` after the inlet is already used): the
   pipes overlap.
2. **Bug:** `write()` / `check_quality()` outside a `Session` print ~70
   lines of "Gmsh has not been initialized", then fail with
   "RuntimeError: curve 1 has 0 end points".
3. **Outlet names by position.**  `names=["main", "branch"]` relies on
   each fitting's port order; after a multi-outlet fitting the tail
   moves to the first outlet without saying so.
4. **Orientation is relative.**  `roll` turns about the current `up`,
   which changes after every fitting.  `Tee` and `Wye` have no `roll`
   at all: a tee's branch always points along the incoming `up`
   (`tee.py`, `ports`), so a sideways tap off a horizontal header needs
   an extra elbow (`examples/networks/pipe_network.py`).
5. **Angle units are mixed.**  Every angle is in degrees except
   `PipeSpec(rot=…)`, in radians.  A bend angle given in radians
   (`Bend(angle=1.57)`) silently builds a 1.57° bend.
6. **`n_layers` is required on every sweep fitting**, the most repeated
   argument and the usual source of stretched cells.  An axial cell
   size already exists in `extend_open_ends(cells_per_diameter)` and in
   the PCF reader's `axial_cell`.

Items 7–10 of the review (structured errors, named references, schema,
geometry summary) are decision 0019's items 1–4 and stay there.

## Options and choices

### Port names
- **Chosen:** each multi-outlet fitting declares `port_names` (`Tee`:
  `("main", "branch")`; `Wye`: `("left", "right")`), listed in its
  docstring and `API.md`.  `add(…, names=…)` takes a list (as today) or
  a dict keyed by port name; an unknown key is an error listing the
  valid ones.  The tail rule stays, but is stated in `add`'s docstring
  ("continues on the first port, `main`").

### Absolute orientation
- **A. Replace `roll` with directions.**  Breaks every saved file;
  rejected.
- **B. Add `toward=` as an input that resolves to `roll` at `add()`.**
  The JSON stores the resolved `roll`, so the saved description stays
  canonical and deterministic (decision 0019, constraints 2 and 5).
- **Chosen: B.**
  - `Bend`, `Elbow`, `MiterBend`: `toward=(x, y, z)`, the absolute
    direction to turn toward.  Its component perpendicular to the inlet
    normal sets `roll`; nearly parallel to the normal is an error.
  - `Tee`, `Wye`: a new `roll` field, **restricted to multiples of the
    section's symmetry period** (90° for a circle; decision 0010).  Only
    then do the junction's corners land on the inlet face's corners
    (DESIGN §7: corners at 0°/90°/180°/270°), so the joint stays
    conformal with no twist.  `toward=` picks the multiple closest to
    the given direction and is rejected if the branch would be off it by
    more than a tolerance, naming the angle.
  - Arbitrary branch orientations would need a twisting fitting.  A
    twisted straight with ruled sides is not exact (DESIGN §6), so it's
    out of scope here.

### Angle units
- **Chosen:** `PipeSpec(rot=…)` in **degrees**, like every other angle.
  Saved files at format version 1 store radians; version 2 stores
  degrees, and `from_dict` converts version 1.  Fitting angles are
  validated against a limit table (decision 0019, constraint 6), and a
  bend angle below 2π° (6.28°) gives a `UserWarning` ("looks like
  radians?"), not an error, since small field bends exist.

### Axial cell size
- **Chosen:** `Assembly(…, axial_cell=None)`.  A sweep fitting with
  `n_layers=None` gets `max(min_layers, ceil(L / axial_cell))` at
  `add()` (at `close()` for `Closure`), where `L` is its centreline
  length and `min_layers` its own validation floor (e.g. a bend's
  per-layer turn limit).  The resolved count is stored in the fitting
  and the JSON, so `cell_count()` stays exact and `refined(k)` unchanged.
  `n_layers=None` without `axial_cell` is an error naming the fitting.
  `Tee`/`Wye` keep their own count defaults.

## Consequences

- `API.md`, `README.md`, examples and the gallery change (examples can
  drop most `n_layers`).
- Saved files: format version 2 (`rot` in degrees); version 1 still
  loads.
- Task 0037 (PCF branches) gains `roll` on `Tee`: a set-on branch at a
  multiple of 90° from the incoming `up` maps directly; any other angle
  is rejected with the angle named (note added to 0037).
- **Effect on future expansions:**
  - 0019 (agent SDK): directly serves it: named ports (constraint 4),
    absolute directions (easier for agents than relative roll),
    canonical JSON (constraints 2, 5), limits as data (constraint 6).
  - 0018 (vascular): `axial_cell` is what a centreline import needs
    (cells from length); vascular bifurcations will want arbitrary
    branch planes, which the period restriction doesn't give: a twist
    fitting stays an open question for 0018.
  - 0021 (flow restrictions): none.

## Verified vs. assumed

- **Verified (2026-10-27):** items 1, 2 and 5 by running them; the Tee
  branch direction from `tee.py`; `roll` and `rot` units from code and
  `API.md`.
- **Assumed:** that a `Tee`/`Wye` rolled by a multiple of the period
  joins its inlet conformally with no other change (decision 0010's
  corner identity suggests so; task 0040 checks it by meshing).
