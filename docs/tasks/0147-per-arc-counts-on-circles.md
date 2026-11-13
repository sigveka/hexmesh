# 0147 — Per-arc counts on `CircleShape`

- **Status:** in progress (Q6, the signature's pattern: asked; the rest goes on)
- **Decision:** [0041](../decisions/0041-per-side-counts-on-rectangles.md),
  option C, in the form fixed under *C's form* (2026-11-06) and taken off
  hold by its amendment (2026-11-08, with decision 0042: "per-arc count
  yes").  [0042](../decisions/0042-road-to-1-0.md) exit criterion 3,
  milestone 0.7.
- **Depends on:** none.  Not alongside another task that edits
  `core/shape.py` or `sections/`.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  1.0 freezes the description schema.  Per-arc counts add a field
and a topology rule, so they must exist before the API review (task
0150), even though they are additive.  Their main users come later:
- multi-core sections (decision 0035 stage B), whose cells have sides
  of unequal length;
- a round duct tap on a rectangle;
- a circle → rectangle `Transition` with unequal sides.

**The form is fixed** (decision 0041, *C's form*; don't build a narrower
version):
1. **General per-arc counts:** each of a circle's arcs carries its own
   count, not two alternating ones.
2. **In `CircleShape`,** as an optional field.  `CircleShape(radius,
   nang=…)` keeps its meaning (one count on every arc).  No second
   circle type: the shape-switch cap (DESIGN §9) only goes down.
3. **Fittings opt in.**  A fitting that doesn't handle unequal arcs
   rejects them with a coded error, as `check_supported` did for
   `n_outer = 8`.
4. **Topology and density:** the count *pattern* (which arcs are equal,
   and their ratios) is topology, and part of the section signature.  A
   uniform multiplier is density, so `Reducer` and `refined(k)` keep
   working.

**Do.**
1. **The field, its validation and its description schema entry**, with
   a format note (saved descriptions without it load unchanged).
2. **The signature:** the count pattern enters the topology class; the
   counts' multiplier stays density.
3. **Support, in this order:**
   - `Straight`, `Bend` and `Reducer` (the sweeps);
   - `Transition` (circle ↔ rectangle with unequal sides: the case that
     motivated it);
   - every other fitting rejects with a coded error (`counts_unsupported`
     or a better name: say which), naming the fitting.
4. **Junctions:** rejected.  Say what a tee would need, under *Agent
   notes*, for later.
5. **Docs:**
   - API (`CircleShape`, `PipeSpec`'s circle layers);
   - GUIDE (a short example: a circle meeting a 2:1 rectangle with
     unequal counts);
   - CHANGELOG;
   - CLAUDE.md's *Parameter separation* gains the pattern-is-topology
     sentence (decision 0041, point 4).
6. **Tests:**
   - the schema round trip;
   - the signature;
   - each supported fitting meshed with counts (2, 4, 2, 4) on a circle
     and on a two-layer stack;
   - the rejections;
   - `refined(2)` nests.

**Accept.**
- Every example mesh byte-identical, and every existing port signature
  unchanged (decision 0041 point 5).
- New tests pass; full suite: no new failures.

**Out of scope.**  `n_outer = 6` (hexagonal cells); ellipses (decision
0041: an idea only); junction support.

## Agent notes

- **Read before building** (2026-11-13), no code written:
  `core/shape.py` (`CircleShape`), `core/spec.py` (`side_counts`, the
  stack count checks), `sections/oh.py` (`levels`, `patches`,
  `node_grids`, `section_cells`), `assembly/signature.py`.
- **The O-H core is one transfinite centre patch** (`oh.patches`: the
  core's corners `(0, 0..3)`; `node_grids` builds it as one Coons patch
  of the four inner curves; `section_cells` counts it as `c[0] × c[1]`).
  A transfinite quad needs equal counts on opposite sides, and each ring
  patch carries its arc's count from the centre to the wall.  So a
  circle's four arcs must satisfy `c[0] == c[2]` and `c[1] == c[3]`:
  (2, 4, 2, 4) meshes, (2, 3, 4, 5) can't, on any n_outer = 4 O-H face.
  With n_outer = 8 the 2×2 core gives the same constraint on each half.
- **The signature already carries two counts** (`nang_w`, `nang_h`,
  period 180° when they differ), and a count difference is class 2
  (density).  Point 4 of the form ("the pattern is topology") needs
  a pattern change to be class 3, so the signature gains a pattern
  field (the counts divided by their gcd), or the classifier compares
  ratios.

## Questions for design

- **Q1. General per-arc counts against the transfinite core.**  The
  form says "each of a circle's arcs carries its own count, not two
  alternating ones", but today's O-H face can only mesh opposite-equal
  counts (above).  Proposal: the field holds four general counts, so
  the schema frozen at 1.0 is the general one.  `PipeSpec` (the O-H and
  H layouts) rejects `c[0] != c[2]` or `c[1] != c[3]` with a coded
  error (`arc_counts_not_opposite`), whose hint says what does mesh.
  A section that meshes general counts comes with stage B's section
  abstraction (decision 0035), which isn't tied to the O-H face.  Is
  that the general form, as the decision means it?
- **Q2. How many arcs?**  A Voronoi cell (the stated main user) has 5,
  6 or 7 sides, not four quarter arcs, and needs `n_outer = 6` and
  more.  Is the field four quarter-arc counts (as `nang` is "per 90°
  arc"), or one count per outer corner (`len == n_outer`)?  The second
  makes the shape depend on `n_outer`, which it doesn't today
  (`side_count(k, n_corners)` gets it from the spec).  Proposal: four
  quarter arcs now, since `n_outer` only takes 4 and 8; a polygon
  outline for stage B carries its own counts.
- **Q3. `nang` with per-arc counts.**  Proposal:
  `CircleShape(radius, arcs=(2, 4, 2, 4))` with `nang` left out
  (`nang=None` stored, `to_dict` writes `arcs` instead of `nang`).
  Giving both raises `arcs_with_nang`.  `PipeSpec`'s density for such a
  circle is `nang_w`/`nang_h`, as for a rectangle (`angular_counts`
  returns those), so the stack checks and `refined(k)` (which already
  scales `nang_w`/`nang_h`) need no new parameter.  Is a circle setting
  `nang_w`/`nang_h` acceptable, or should `PipeSpec` get an `arcs`
  parameter of its own?
- **Q4. `n_outer = 8` with unequal arcs:** proposal, rejected
  (`arc_counts_need_n_outer_4`) in this task, as junctions are.  The
  partition's node corrections (task 0088) assume one count per arc.
- **Q5. The signature.**  Proposal: `Signature` gains `pattern`, the four
  counts divided by their gcd ((1, 1, 1, 1) for every existing
  section, so existing signatures change only by that field, and
  equality and classes don't change).  A different pattern is class 3
  ("a change of section topology"), a uniform multiple stays class 2.
  Acceptance says "every existing port signature unchanged": does an
  added field with the same value everywhere count as unchanged, or
  should the pattern be left out when it is uniform?

Nothing else waits on 0147; I'm switching to 0148.

- **Q6 (2026-11-13, after the answers). Q5's pattern breaks the
  motivating Transition.**  A `Transition` needs equal signatures at
  its ends (class 0; `fittings.py`, `Transition.check`).  With the
  pattern stored only for circles with unequal arcs, a 2:4 rectangle
  (no pattern: its signature is unchanged) and a circle with arcs
  (2, 4, 2, 4) (pattern (1, 2, 1, 2)) differ, so a class-3 error stops
  the case the task was opened for (step 3).  And "absent means
  uniform" is false for that rectangle.
  - **Proposal (B): no `pattern` field in this task.**  While only
    opposite-equal arcs mesh (Q1), the pattern is fixed by the
    signature's `nang_w` and `nang_h`, which a circle with arcs now
    sets.  A circle's ratio change is then class 2, like a rectangle's
    (neither has a fitting; only the message differs).  This is the
    inconsistency the note leaves to the API review.  Every signature
    stays as it is, and the Transition is class 0.  The field comes with
    general patterns (stage B), when they can no longer be derived.
  - **(A):** a `pattern` for every outline with unequal side counts,
    rectangles too.  Existing 2:1 rectangle signatures then gain the
    field, and a rectangle's ratio change becomes class 3, a behaviour
    change before the review.
  - Until the answer: everything else in 0147 is built (B); a
    `pattern` is added afterwards if the answer is (A).

**Answered (the design session, 2026-11-13; the user: "yes"):** all five
proposals, as written above, with Q5's pattern **left out when uniform**
(absent means uniform, so existing signatures stay byte-identical).  Q2:
the four counts are saved as a list.  Recorded in decision 0041's note
of 2026-11-13, which is the reference.

## Outcome
