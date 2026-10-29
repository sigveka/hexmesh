# 0057 — Duct tee: rectangular straight tap on a rectangular duct

- **Status:** blocked (Q1: the pipe tee's layout doesn't port to a tap narrower than the duct)
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

**2026-10-30: stopped before coding; step 2's layout doesn't port (Q1).**
Checked on paper against `tee.py`'s layout before prototyping, since
decision 0027 lists the port as assumed.  No code written.

Canonical frame: main axis x, duct half-extents a (across, y) and b
(height, z), branch on the face z = b, hole half-extents p (along x) and
q (across, y).

- **Pipe:** the approach station's level-1 corners 0, 1 are the hole's
  OH corners.  The slab's corner edges carry them from the main's 45°
  corners at the port to the hole corners at the station.  This works
  because the main's corners are arbitrary points on a smooth wall.
- **Duct:** the main's O-H corners are the duct's creases (the edges y =
  ±a, z = ±b).  A block face on the wall must not cross a crease, or it
  is folded and not a plane (step 5's exactness fails).  With q < a, the
  pipe layout's faces cross it in two places:
  - The station's side edge, corner 1 → 2, runs (−p, q, b) → (−p, a, −b).
    On the wall that's the polyline (q, b) → (a, b) → (a, −b), so the
    S± blocks' wall faces fold along y = a, z = b.
  - The slab's corner edge k = 1 runs from the port's (a, b) to the
    station's (q, b).  The crease y = a, z = b then runs diagonally
    across the slab's side wall face.
- **Making the creases block edges doesn't work either:**
  - At the station, the outer loop then needs six vertices (four duct
    corners and two hole corners) where the port has four.
  - The extra vertices propagate along x to the port face, which then
    isn't the standard 5-patch O-H face (DESIGN §7.1: "All three ports
    keep the standard OH pattern").
  - Ending them inside the slab needs triangular patches (prisms) or a
    new split of the ring and core.
  - Keeping four station corners at the duct corners makes the turn
    block's wall face a trapezoid from width 2a at z = b to 2q at the
    turning station: a flared neck, not the hole.
- **With q = a (a tap as wide as the duct across, any p) the layout
  ports exactly:**
  - the station's top corners are the duct's corners;
  - the slab corners run along the creases;
  - S± walls are the side planes y = ±a;
  - the turn blocks' walls are the planes x = ±p;
  - the branch's ±y walls continue the duct's side planes.
  Every wall face is planar, the ports are standard and the counts match
  (the branch's across count = the main's `nang_w`).  This is the
  "bullhead" case that decision 0027 D rules out.
- **The round tap (0058) has the same problem:** its O-H corners sit on
  the hole circle inside the face, so the station's side edge crosses
  the crease too.


## Questions for design

**Q1. Which layout for a duct tap narrower than the duct?**  The pipe
tee's layout (step 2) puts a crease of the duct inside block faces
whenever the tap is narrower than the duct across (*Agent notes*), so
the walls aren't planes and the step-5 exactness fails.
- **A. Full-width taps first.**  Allow q = a (the tap's across extent =
  the duct's), any along-axis extent p within the room checks.  The
  pipe layout ports unchanged and every wall is a plane.  Narrower taps
  wait for B.  A narrower branch run can follow a full-width neck
  through a `Reducer`; that's a stepped tap, not a sharp one.  This
  reverses decision 0027 D's "full-width branches are out".
- **B. A new junction layout for q < a.**  Keep the creases and the hole
  corners as block vertices without changing the port faces.  For
  example, a collar of blocks around the hole on the top wall, with
  valence-3 vertices that take the station's six-vertex loop back to the
  port's four.  It has to split the top ring (and possibly the core)
  through the junction.  That's a new topology to prototype, as decision
  0017 did for the wye.  It also covers 0058's round tap.
- **C. Fold the faces and project nodes onto the box** (decision 0029).
  This works today, but the crease is cut by one cell width near the
  junction: the walls aren't exact.  Not recommended.
- **Recommendation:** A now (0057 as a full-width tap, the rest of the
  task unchanged), and B as its own decision before 0058.


## Outcome

_Not done._
