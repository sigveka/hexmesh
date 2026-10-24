# 0002 — Radial grading from first-cell height

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
