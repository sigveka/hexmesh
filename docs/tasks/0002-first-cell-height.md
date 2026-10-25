# 0002 — Radial grading from first-cell height

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** 0000

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `PipeSpec` takes a radial progression `mprg`, but CFD users
specify a first-cell height at the wall.

**Where.**  `hexmesh/core/spec.py` (`core()`/`shell()` take `nrad`, `mprg`).
Depends on task 0: before it, `mprg` has no effect in the assembly
pipeline.

**Do.**
1. Add a pure function such as
   `progression_for_first_cell(thickness, n_nodes, h_first) -> float`.  It
   solves `h1 * (q**(n-1) - 1) / (q - 1) = t` for `q` by bisection or
   Newton, returning 1.0 when `h1 == t/(n-1)`.  Raise a `ValueError` when no
   `q > 0` exists.
2. Add an optional `first_cell=` kwarg next to `mprg` on the core and shell
   builders.  It is mutually exclusive with `mprg`, and the resulting `q`
   is stored in `mprg`.
3. Document which wall the first cell is at (the outer wall of the layer)
   and how this relates to the existing `mprg` convention ("> 1 refines
   …", `spec.py:51`).  Check the existing direction before choosing a sign.

**Accept.**
- Unit tests: round trip (`q` → `h1` → `q`); uniform case; an impossible
  input raises.
- One realisation test: the measured first radial cell height of a meshed
  `Straight` matches `h_first` within 1 %.

**Note.**  This sets a first-cell height, not y+.  y+ depends on flow
velocity; don't add a y+ API.

## Agent notes

- **`n_cells`, not `n_nodes`.**  `nrad` counts cells (the face builders
  give each radial curve `nrad + 1` nodes; `section_cells` multiplies by
  `nrad`), so the solver is
  `progression_for_first_cell(thickness, n_cells, h_first)` in the new
  pure module `core/grading.py`, with its inverse `first_cell_height`.
  Bisection in log q; it exists exactly when `0 < h < t` (or `h = t` for
  one cell) and raises `ValueError` otherwise.
- **Direction checked (step 3).**  Radial curves run inner → outer
  (`sweep.face_grading` signs them that way) and GMSH's "Progression"
  grows cells from the curve start, so `mprg > 1` refines toward the
  inner side, as `spec.py` documents.  A first cell at the layer's outer
  wall is therefore stored as `mprg = 1/q < 1`.
- **`mprg` default is now `None`** on `core()` / `shell()` (resolved to
  1.0), so `mprg=1.0, first_cell=…` is caught as a conflict.  Stored
  values are unchanged.
- **Core thickness.**  The core grades its four corner radials, of length
  `(1 - OH_RATIO) * radius` = 0.4 R.  Between corners the inner arcs bulge
  inward and the core reaches 0.491 R at mid-arc.  Transfinite
  interpolation keeps the corner fractions, so wall cells scale with the
  local span (measured to 1 %).  Shells are exact all round.
- **Option (b) applied** (the user chose it on 2026-10-25, answering
  question 1 below).  The core progression is solved on the mid-arc span,
  `core.shape.oh_core_wall_span(radius)`, so `first_cell` is the largest
  wall cell; at the corners it is 0.81 of it.  First version (commit
  `36cf45f`) solved on the corner span instead (a): corners exact,
  mid-arc 1.23× larger.  `first_cell` on an `n_outer = 8` core now raises
  (its inner arcs differ).
- **`OH_RATIO`** moved to `core/shape.py` as the single source; the face
  builder's default, the block layout and the tee use it.
- Rectangular cores raise `TypeError` for `first_cell` (their inner
  geometry differs, and the assembly rejects them anyway until decision
  0009).
- `Reducer` scales radii and keeps `mprg`, so through a reducer the
  first-cell height scales with the radius.

## Questions for design

1. **Core wall cell.**  *Answered by the user, 2026-10-25: option (b).
   Implemented; for the design session to record in a decision or
   RESEARCH if wanted.*  `first_cell` is exact at the core's corner
   radials and up to 1.23× larger at mid-arc.  For y⁺ targets a user
   usually wants an upper bound, not a value met at four lines.  Options:
   (a) keep it (documented); (b) solve on the mid-arc thickness, so
   `first_cell` is the largest wall cell (corners then ~19 % smaller);
   (c) remove the variation, by making the inner arcs concentric
   with the wall near it (e.g. an O-grid ring of constant thickness
   around the OH core, which is a face-topology change).  (b) is a one-line
   change; (c) would need a decision.  Not blocking: the task's accept
   criterion holds at the graded curves.
2. **Which wall of a shell.**  The task says the outer wall of the layer.
   For a solid shell in CHT the critical side is often the inner one (the
   fluid–solid interface).  Should `shell()` take
   `first_cell_at="inner" | "outer"`?

## Outcome

- **Files:** new `hexmesh/core/grading.py`; `core/shape.py`
  (`oh_core_wall_span`); `core/spec.py`
  (`first_cell=` on `core()`/`shell()`, `_wall_progression`);
  `core/shape.py` (`OH_RATIO`); `faces/oh_circle.py` and
  `assembly/blocks.py` (use it); new `tests/test_first_cell.py` (29
  tests); `README.md`, `API.md`.
- **Measured** on a meshed `Straight`, `first_cell = 1.5 mm`, option (b):
  core mid-arc 1.5 mm and, over every wall node, the largest radial gap
  1.5 mm (< 1 %); core corners 1.22 mm = 0.814 × (the span ratio); shell
  at 0°, 45°, 60°, 75° 1.5 mm (< 1 %).
- **Tests:** 373 passed, 0 failed (after option (b)).
