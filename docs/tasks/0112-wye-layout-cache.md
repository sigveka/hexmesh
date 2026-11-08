# 0112 — Cache the wye's layout, so the light commands stay light

- **Status:** ready (after 0108)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (the light commands, amendment 2026-11-07); follow-up of task 0110, Q2
- **Depends on:** 0107, 0110 (done).  After the launch.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0110 measured the README primer's session (validate,
estimate, advise, apply, validate) at 4.6–4.8 s, against about 0.3 s per
command on networks without a wye (0107).  Under cProfile, `Wye.layout`
is 18 of 21 s:
- it runs 9 times (`cell_count`, `validate` and `advise` each call it,
  with no cache);
- each run builds 2 430 wall points with `Skeleton.to_wall`, marching
  and then bisecting 60 times: 187 632 scalar `Skeleton.nearest` calls,
  three `np.linalg.norm` each.

An agent's validate → estimate → apply loop on any network with a wye
pays seconds per call.

**Where.**  `hexmesh/assembly/wye.py`; tests; `CHANGELOG.md`.

**Do.**
1. **Cache `Wye.layout`** per (the wye's parameters, the inlet frame,
   the spec), keyed on values, not object identity, so an equal wye at
   an equal frame reuses it and any change misses.  A mutated spec or
   frame must never return a stale layout: a test changes each input and
   checks the layout changes.
   - Bounded (e.g. an LRU of a few dozen), so a long study doesn't grow
     memory.
   - If `layout` returns mutable objects that callers change, copy on
     the way out, or document why it's safe.
2. **Measure again:** the profile of 0110's fixture, and the primer's
   commands one by one, before and after.  Report how many `layout`
   runs remain and what is now the largest cost.
3. **Vectorising `to_wall`'s march:** don't, in this task.  If the cache
   leaves a single layout run above about 0.5 s, propose it under
   *Questions for design*, with what it would do to wall nodes (rounding
   moves them, which changes meshes).

**Accept.**
- The 28 gallery meshes are byte-identical before and after.
- The staleness tests pass.
- The primer's session time, before and after, in *Outcome*; the README
  test's time too.
- Full suite: no new failures.  Check memory first (`free -g`), and run
  it serially if another heavy run is active.

**Out of scope.**  Caching other fittings' layouts (propose if the
profile shows one).
