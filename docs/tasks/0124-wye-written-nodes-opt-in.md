# 0124 — Written nodes for `Wye`, opt-in: measure a B3 layout, and offer it only where it beats the hub

- **Status:** held (after 0122 and 0123; decision 0043, amendment 2026-11-10)
- **Decision:** [0046](../decisions/0046-gmsh-meshes-hexmesh-corrects.md) (rules 3–5); [0043](../decisions/0043-wye-layout-redesign.md) (its gates, unchanged)
- **Depends on:** 0117 (done: B3 is feasible), 0123 (the notice), 0122
  (the cube, whose topology a written layout may reuse).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-10): B3 is "an interesting special case …
for Wye we may want to facilitate it", opt-in, "with a hint to the user
when it may be necessary".  Today's hub builds symmetric wyes with
warnings (60°: SJ 0.156, crease 2.9 % R) and can't take unequal or
asymmetric daughters (task 0116).  With written nodes, hexmesh places
the junction's nodes, so grid lines can follow the crease.

**Where.**  A private layout module; `wye.py` (the field); the
harness `validation/tools/wye_redesign.py` and its JSON; `limits.py`;
`errors.py` (hints); docs.

**Do.**
1. **Measure first, no API:** a written-node layout for the 0116/0118
   cases (60° control, A3 unequal ±30° R/√2, A2 equal lateral, A1 equal
   tee for comparison), `nang` 8, single and shelled, on 0117's
   mechanism (port nodes read from the ports' meshes and reused by tag).
   Candidates: the cube's topology with crease-following nodes, or
   Marcinnó's placement (RESEARCH §4.2).  Report against **decision
   0043's gates, unchanged**, beside the hub and the cube.
2. **The rule, fixed now:** the opt-in is built only for the cases where
   the written layout meets every gate and the hub doesn't.  If none,
   report and stop; nothing is added to the API.
3. **If built:** `Wye(…, written_nodes=False)` (stored in the
   description); the notice and report from 0123; second order and
   `refined(k)` by rewriting the nodes (0117's step-5 notes); the hint on
   the hub's error or warning for exactly the measured cases (decision
   0046, rule 4), coded.

**Accept.**  Set by design when the task is released, from step 1's
numbers.

**Out of scope.**  Making written nodes a default anywhere (decision
0046); tees (0122).

## Agent notes

## Questions for design

## Outcome
