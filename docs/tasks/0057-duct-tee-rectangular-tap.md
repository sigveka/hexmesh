# 0057 — Duct tee: rectangular straight tap on a rectangular duct

- **Status:** ready
- **Decision:** [0027 — Tees in rectangular ducts](../decisions/0027-duct-tees.md)
- **Depends on:** —  (0058 and 0059 build on it)

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Ducts can't branch: `Tee` rejects rectangular specs.  HVAC
supply runs and cooling-channel manifolds need taps.

**Where.**  `hexmesh/assembly/tee.py` (fields, `check`, `layout`,
`ports`, `branch_spec`), `blocks.py`, `hexmesh/core/shape.py`
(`RectShape`), `limits.py`, kit, `API.md`, `README.md` limitations.

**Do.**
1. **Fields:** `Tee(…, branch=RectShape(half_w, half_h, nang_w,
   nang_h) | None, face="wide" | "narrow")`.  `branch_radius=` stays as
   the shorthand for a circular branch on a circular main.  A
   rectangular main with `branch=None` and `branch_radius` is an error
   naming `branch=`.
2. **Layout:** the pipe tee's block layout (DESIGN §7.1: continuous ring
   layer, turn faces bisecting the re-entrant corner, standard O-H port
   faces) with straight edges where the pipe tee has arcs.
   - **The hole** is the branch rectangle on the chosen flat face; the
     saddle becomes a planar rectangle.
   - **`face`** selects the wide or narrow face; `roll` 0 / 180 picks
     the side (a non-square duct's period is 180°, task 0040).
   - **Counts:** the branch shares the main's counts per side (equal
     counts, as decision 0026).  Say which counts must match along which
     edges, and reject mismatches naming them.
3. **Room checks** before GMSH: the branch fits inside its face with a
   margin, both ways; the run and branch lengths clear the junction
   (as `Tee` does for pipes).  Name the limit and the face.
4. **Quality limit:** the layout's predicted corner SJ, with task
   0052's two tiers (reject < 0.1, warn < 0.3, with the shortest
   `run_length` hint), and `run_length=None` resolving to a safe
   default.
5. **Walls:** every wall face is a plane, so exact as OCC surfaces (ruled
   or planar).  Check it with the kit's exactness check.
6. **Measure:** quality over branch/face ratio ∈ {0.3, 0.6, 0.9} × duct
   aspect ∈ {1, 2, 3} × wide / narrow face, `nang` 4 and 8.

**Accept.**
- Kit cases (square duct; 2:1 duct, wide face and narrow face): all-hex,
  meshed = predicted, class-0 ports, wall nodes on their planes, quality
  ok.
- Rejections named: branch too wide for its face, count mismatch,
  `face` on a circular main.
- Pipe tees unchanged (node coordinates to 1e-12).
- The quality table; a proposed limit if the two tiers aren't enough.
- Full suite: no new failures.

**Out of scope.**  Round taps (0058), shells, angled or offset taps
(decision 0031), full-width ("bullhead") branches.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
