# 0100 — Trace why rectangle side counts are tied next to circles and shells

- **Status:** done
- **Decision:** [0041 — Per-side counts on rectangles](../decisions/0041-per-side-counts-on-rectangles.md) (step 1)
- **Depends on:** none.  Investigation only: no library change.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0098 found `nang = nang_w = nang_h` in two cases:
- a `Transition` from a circle to a rectangle;
- a rectangular core with shell layers ("the spec's own rule").

The tie makes `hvac_branched` 10M cells and `cooling_channels` 20M at
"medium".  Decision 0041 picks a fix per case (B for shells, C for
transitions, A otherwise), but only once the cause of each tie is
known.  The design session found no tying check in `core/spec.py` on a
quick look.

**Do.**
1. **For each case, find what forces the tie**, naming the file and line:
   - a validation check (which one, which error code);
   - a construction that can't build otherwise (which function, and what
     fails when the counts differ: an error, a non-conformal face, an
     invalid transfinite surface);
   - or only the advisor's choice (`hexmesh/agent/advise.py`).
2. **Try untied counts** on a minimal case of each, in a scratch script
   (not committed):
   - a rectangle with `nang_w ≠ nang_h` and one shell (`dR`), then a
     rounded shell and a circular outer outline if supported;
   - a circle → rectangle `Transition` with `nang_w ≠ nang_h` on the
     rectangle.
   - For each: does it build, mesh and pass `validate()` and the meshed
     checks?  If it fails, record the error or the defect.
3. **Other tie sites.**  Search for any other place where per-side
   counts must equal `nang` (the O-H ↔ H switch, `Reducer`, junctions
   on ducts, `BundleSpec`).  List each with its reason.
4. **Estimate the gain.**  With `advise` (water at 2 mm/s, "medium"),
   recount the five tied examples as if the tie were lifted where step
   2 shows it can be.  Use the cell count only; don't mesh them.

**Accept.**
- A table under *Outcome*: per tie site, the cause (check / construction
  / advisor), file:line, and whether untied counts build and mesh.
- The five examples' cell counts, tied and untied.
- No library change; full suite unchanged.  Scratch meshes deleted.

**Out of scope.**  Lifting any tie.  That is a follow-up task per
option, written by the design session from this outcome.

## Agent notes

- **Method:** scratch scripts in the session's scratchpad (not
  committed).
  - Step 2 builds each minimal case twice: with the checks as they are,
    and with the tying check bypassed by monkeypatching
    (`PipeSpec._check_counts` replaced by a no-op; `Transition.check`
    skips only its `counts_mismatch` raise).
  - Every case runs `validate()`, `mesh()` and
    `check_quality("scaled_jacobian")`.  A conformity check on the gmsh
    mesh covers: hex count against `cell_count()`, non-hex 3-D
    elements, interior faces in only one hex and not on a boundary quad,
    faces in more than two hexes, and coincident nodes.
  - Step 4 calls `advise` on the five examples (water, 2 mm/s,
    "medium").  `_tied` is patched to drop the shell reason (B), or
    every reason (an upper bound on the gain).  `_check_counts` is
    bypassed so that the untied B stacks validate.
- **A rectangle grown by `dR` stays a rectangle** (`RectShape.grown`,
  `core/shape.py:334`): there is no rounded shell, so none was tried.
- **The advisor names one reason:** `_tied` returns the first.  The four
  examples tied by a Transition are reported under it, even where they
  also have shells.

## Questions for design

_None._

## Outcome

**Done.**  No library change; scratch meshes deleted.

**Tie sites:**

| # | Tie | Cause | Where | Untied counts (check bypassed) |
|---|---|---|---|---|
| 1 | rectangular core + shells (`dR`, or a rectangular `outer`), H or O-H layout | **check**: `PipeSpec._check_counts`, `rect_stack_counts_unequal` (decision 0026 item 3) | `core/spec.py:571` (raise at 587–591; called at 541) | **build, validate, mesh, conformal.**  8 × 4 core: one `dR` shell in H (320 hexes) and O-H (608); two shells (416); a rectangular `outer` (320); a straight + 90° bend (720).  Hexes = predicted, no non-hex, 0 open faces, 0 coincident nodes, worst SJ 0.63–0.71 |
| 2 | rectangular core + a **circular** shell | **construction**: a `CircleShape` carries one count, `counts = (nang, nang)` (`core/shape.py:182`), so its arcs can't match unequal sides | `assembly/assembler.py:92`, `curve_constraint_conflict` (the circle's arc of 9 nodes against the side's 5) | **fails** at meshing; `validate()` passes.  Needs C |
| 3 | `Transition` circle → rectangle | **check**: `Transition.check`, `counts_mismatch` | `assembly/fittings.py:797–803` | **fails** past the check: `switch_class_not_declared` (`assembly/signature.py:217`).  The untied rectangle's combinatorial period is 180°, the circle's 90° (`signature.py:120`), so class 3.  Underneath is the same one-count circle as #2.  Needs C |
| 4 | `Transition` rectangle → rectangle | none | — | **builds and meshes** with 8 × 4 at both ends (624 hexes, conformal) |
| 5 | **round** duct tap on a duct | **check**: `counts_mismatch`, main `nang_w == nang_h ==` branch `nang` | `assembly/duct_tap.py:615–621` | not tried; same one-count circle as #2.  Needs C.  It stopped `hvac_branched` in step 4's untied run |
| 6 | rectangular duct tap | per-side counts must equal the main's, not each other | `assembly/duct_tap.py:622–627` | not a tie |
| 7 | `BundleSpec` cell: a circular core in a rectangular outer | the same check as #1, then #2's circle | `core/spec.py:819` | a square tile is natural; a non-square tile needs C |
| 8 | the advisor | **advisor**: takes the largest count for every section when `_tied` finds a Transition or a shelled rectangle | `agent/advise.py:594` (`_tied`), `:356–359` (`_density`) | follows #1/#3 |

Not tie sites:
- tees on circles (`assembly/tee.py:251–255`: the branch `nang` equals
  the main's, both circles);
- the O-H ↔ H `Switch` (`assembly/switch.py`: the same `nang_w` ×
  `nang_h` on both layouts);
- `Reducer` (sizes only, counts equal).

None of these force `nang_w == nang_h`.

**Conclusion for decision 0041:**
- The shell tie (#1) is **only a spec rule**, so B applies: lift
  `rect_stack_counts_unequal` for rectangular shells, and drop the
  shell reason from `_tied`.
- The circle ties (#2, #3, #5, #7) are **geometric with today's
  one-count `CircleShape`**: C is what lifts them.
- The rectangle → rectangle transition (#4) is already untied.

**The five examples** (`advise`, water at 2 mm/s, "medium"; cell counts
only, not meshed):

| example | tied by | tied | B (shells untied) | upper bound (every tie lifted, circles keep their own `nang`) |
|---|---|---|---|---|
| `lagged_duct` | shells | 936 000 (60 × 60) | **526 500** (60 × 30) | 526 500 |
| `duct_transition` | Transition | 2 620 800 | 2 620 800 | 244 872 |
| `hvac_supply` | Transition | 2 667 600 | 2 667 600 | 644 472 |
| `hvac_branched` | Transition (and a round duct tap) | 10 046 880 | 10 046 880 | — (the round tap rejects it, #5) |
| `cooling_channels` | Transition | 19 954 146 | 19 954 146 | 599 352 |

- **B alone** helps only `lagged_duct` (−44 %).  The other four are
  tied by circle → rectangle transitions, which only C lifts.
- **The last column isn't C.**  It lets each circle keep its own
  calibrated `nang` (12) beside a 60 × 30 rectangle, which is option D,
  and none of those assemblies validate (`counts_mismatch`).  Under C
  the circle's arcs take the rectangle's counts (60, 30, 60, 30), so
  C's count lies between this bound and the tied count.  It can't be
  computed until a circle can carry unequal arcs.
- **Proposed follow-ups (for design):**
  - a B task: the spec rule, `_tied`, and the 0098 example re-measure;
  - a C task: per-arc counts on `CircleShape`, its signature period,
    `Transition` and the round duct tap.

