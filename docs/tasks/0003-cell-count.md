# 0003 — Exact cell count before GMSH

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The mesh is structured, so the cell count is known exactly from
topology and density.  Reporting it in validation enforces DESIGN P4, and it
makes "refinement ×2 ⇒ 8× cells" (CLAUDE.md) visible before meshing.

**Where.**  `Assembly.validate()` at `assembler.py:173`; fittings in
`assembly/fittings.py` and `assembly/tee.py`.

**Do.**
1. Add `cell_count(frames, spec) -> int` to the fitting protocol (frames,
   like `validate`, because block layouts need them): per-layer
   cross-section quads × axial layers for sweeps, the sum over blocks for
   `Tee`.  Derive cross-section quad counts from
   `n_outer`/`nang`/`nrad`; no GMSH.  For block layouts this is generic:
   `BlockLayout` already solves the division classes, so a block's cells
   are the product of its three class counts.
2. Add `Assembly.cell_count()` (the sum) and
   `Assembly.validate(max_cells=None)`, which raises `AssemblyError` naming
   the total and the largest fitting when the budget is exceeded.

**Accept.**
- For every case in the conformance kit, `cell_count()` before GMSH equals
  the number of 3-D elements after `mesh()`.  Add this as a kit test so
  every future fitting must implement it.

## Agent notes

- Sweeps: `section_cells(spec) = a² + n_outer·a·Σnrad` with
  `a = nang // (n_outer/4)`, times `sum(path.layers)`.  `Closure` and
  `Bend` count their actual station layers.
- `BlockLayout.cell_count()` multiplies each block's three solved
  division classes.  It is pure, so `Tee.cell_count` delegates to it.
- Added `Assembly.cell_counts()` (per edge index) alongside
  `cell_count()`.  The budget error uses it to name the largest fitting.

## Questions for design

_None._

## Outcome

Commit `7c4e9f7`.

- **Files:** `assembly/sweep.py` (`section_cells`, `Sweep.cell_count`),
  `assembly/blocks.py` (`BlockLayout.cell_count`), `assembly/tee.py`,
  `assembly/assembler.py` (`cell_counts`, `cell_count`,
  `validate(max_cells=)`), `tests/test_fitting_conformance.py` (kit
  asserts predicted == meshed), `tests/test_cell_count.py` (new).
- **Tests:** full suite 456 passed, 10 failed (the known
  `TestYJunctionQuality` failures), 4 xfailed.
- **Measured:**
  - Predicted equals meshed for all 11 kit cases, including the tee
    (912 cells at nang=4, nrad=3).
  - Doubling every density parameter gives exactly 8× the cells.
  - The over-budget test is rejected (832 cells against a budget of 700).
