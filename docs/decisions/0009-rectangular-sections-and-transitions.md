# 0009 — Rectangular sections and circle ↔ rectangle transitions

- **Status:** accepted
- **Date:** 2026-10-24 (accepted 2026-10-26 by the user: "yes" to
  starting single-layer rectangular ducts and transitions)
- **Tasks:** 0028, 0029.  Answers task 0013's design question (user chose
  option 2: a separate decision for rectangular sections, with
  `Transition` as one of its tasks).

## Context

- **DESIGN §1 scope** includes "circular and rectangular pipes" and
  "transitions".  The assembly supports circular cores only:
  `interface.check_supported` rejects non-circle cores, `n_outer ≠ 4` and
  `square_shell` layers.
- **Task 0013** ported `Reducer` (done), but not the legacy `Transition`
  (circle → square shell), because the assembly can't build those faces.
- **Task 0017** (delete legacy) planned to delete the unused face
  builders `faces/oh_rect.py`, `faces/square.py` and
  `faces/square_shell.py`.  This decision needs the first two of those
  kept, so step 2 of task 0017 is amended.

Existing builders (legacy, not yet used by the assembly):

| Builder | Topology | Use |
|---|---|---|
| `build_oh_rect` (`faces/oh_rect.py`) | **Same 5-patch OH layout as `build_oh_circle`**: same point and curve order (NE/NW/SW/SE; top/left/bottom/right), lines instead of arcs.  Separate counts `nang_w`, `nang_h` (`RectShape`). | Rectangular ducts |
| `build_square_shell` (`faces/square_shell.py`) | A layer wrapping a circular section in a square outer boundary (4 patches, arc → straight). | Tube-bundle tiling: neighbouring cells share flat faces |
| `build_square` (`faces/square.py`) | **Single patch**.  Its own docstring says it is incompatible with the OH layout. | None in the assembly |

DESIGN A4 already lists rectangular boundaries and `nang_w`/`nang_h` in
port types.

## Options

### A. Rectangular cores in the assembly
`PipeSpec` with a `RectShape` core, using `build_oh_rect`.  Straights,
bends, closures and reducers work unchanged as sweeps, because they only
need frames and a face builder.

Points that differ from circles:
- **Corner identity (§6.1).**  Rectangle corners are not at
  `π/4 + rot + k·π/2`; they are at ±atan(h/w).  Corner *k* must be
  defined by **index** (the k-th corner, NE first) with the frame giving
  the orientation, not by angle.
- **Roll symmetry (§8).**  A non-square rectangle has 180° symmetry
  only, so roll is absorbed modulo π, not π/2.  A square keeps 90°.
  `roll_mismatch` and `Closure` must use the section's actual symmetry.
- **Port type (A4).**  `nang_w` and `nang_h` replace `nang`.
- **Bends** of rectangular ducts have a plane of bending, so frame `up`
  decides whether a bend is "hard way" or "easy way".  No new
  machinery, but the docs must say so.

### B. Circle ↔ rectangle `Transition` as a sweep
Both faces have the same 5-patch layout, so a transition is a sweep
between topologically identical faces, like `Reducer`, with stations
interpolating the shape.
- Counts must match: **`nang_w = nang_h = nang`**.  The circle has `nang`
  on every arc.  The rectangle's *aspect ratio* may differ, but not its
  counts.
- Station shapes: blend circle and rectangle outer curves, e.g. a
  superellipse $|x/a|^p + |y/b|^p = 1$ with p from 2 to a large value, or
  a linear blend of matching nodes.  Choose by measured quality.
- Inner layers (wall, insulation) blend the same way.  The assembly's
  annulus builder then needs a rectangular variant, and `build_annulus`
  currently assumes circular boundaries.  Check this before promising
  multi-layer transitions.

### C. Square-shell layers (tube bundles)
A circular pipe wrapped in a square outer layer, so pipes tile into a
bundle with conformal flat faces between neighbours.  This is a
**different feature**: multi-pipe tiling, with its own assembly questions
(several pipes sharing faces).  The legacy `Transition` targets this
(circle → square shell).

### D. Single-patch square (`build_square`)
Incompatible with the OH layout.  No use in the assembly.

## Decision

**Accepted 2026-10-26**, as recommended:
- **A and B: accepted**, single-layer first.  Multi-layer rectangular
  sections wait until task 0028 has assessed the annulus builder.
- **C: deferred** to its own decision, when tube bundles become a
  target.  Keep `build_square_shell` and `SquareShellSpec` until then.
- **D: dropped.**  `build_square` may be deleted.

**Shape is geometry, not connectivity** (settled at acceptance, with
decisions 0011 and 0016).
- A circular and a rectangular O-H core have the same 5-patch layout
  (`oh_core`).  The signature records counts per side (`nang_w`,
  `nang_h`; a circle has both equal to `nang`).
- The signature's symmetry period is the **combinatorial** one, from the
  counts: 90° when `nang_w = nang_h`, else 180°.  Roll handling (§6.1,
  §8) keeps using the **geometric** P from decision 0010's table.
- So a circle ↔ rectangle (or rectangle ↔ rectangle) transition with
  equal counts is **class 0**: a plain sweep like `Reducer`, conformal,
  no new strategy.  Unequal counts are class 2 and stay out of scope.
- This is not the class-3 case of decision 0016: that one is the
  square-*shell* follow-up (option C), where a ring layer changes kind.

**Station shape:** settled by measurement in task 0029 (superellipse vs
node blend, min SICN at 1:1 and 2:1).

To settle first:
1. ~~Corner identity by index~~: **settled by decision 0010**
   (2026-10-25); DESIGN §6.1 updated.
2. ~~Roll symmetry per section shape~~: **settled by decision 0010**;
   DESIGN §8 updated.
3. **Transition station shape** (B): superellipse or node blend.  Pick by
   measured quality (min SICN) on a 1:1 and a 2:1 aspect ratio.

## Consequences

- DESIGN §1: unchanged (already in scope).  DESIGN §6.1 and §8: done
  by decision 0010.  The first task must make `frame_offset` and
  `roll_mismatch` take P from the spec.  DESIGN
  A4: no change (it already lists `nang_w`/`nang_h`).
- DESIGN A4: one sentence added (shape is geometry; the signature's
  period is combinatorial), applied 2026-10-26.  §6.1's note on
  decision 0009 updated to "accepted".
- Tasks:
  1. **0028**, rectangular cores in the assembly (A).
  2. **0029**, `Transition` (B), single-layer.
  3. Multi-layer rectangular sections: no task until 0028's annulus
     assessment.
- Task 0017 keeps `faces/oh_rect.py`, `faces/square_shell.py`,
  `RectShape` and `SquareShellSpec` (amended 2026-10-24).

## Verified vs. assumed

- Verified in code: the `oh_rect` layout matches `oh_circle` (docstring
  and point/curve order); `check_supported` rejections; `square.py`'s
  incompatibility note; legacy `Transition` is circle → square shell
  only; task 0017's deletion list.
- Assumed: sweeps (bend, closure, reducer) need no change beyond corner
  identity and roll symmetry; `build_annulus` needs a rectangular
  variant for multi-layer sections (not checked in detail).
