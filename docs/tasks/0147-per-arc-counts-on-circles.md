# 0147 — Per-arc counts on `CircleShape`

- **Status:** ready
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

## Questions for design

## Outcome
