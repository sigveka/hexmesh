# 0112 — Cache the wye's layout, so the light commands stay light

- **Status:** done (2026-11-08)
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

## Agent notes

- **The cache** (`hexmesh/assembly/wye.py`):
  - `Wye.layout` wraps the old body, now `_layout`, with an LRU of
    `LAYOUT_CACHE_SIZE` = 32 layouts.
  - **Key, all by value:** every dataclass field of the wye (arrays by
    their bytes, the rest by `repr`, which is exact for floats); each
    frame's position, normal and up as bytes, read at the call, so a
    frame mutated in place misses; and the spec as `to_dict()` JSON plus
    `port_type`.
  - **Copy on the way out:** `fill` binds faces into the layout, so each
    call gets a `copy.deepcopy`.  That costs 0.02 s, against 0.55–0.67 s
    for a build.  A hit costs 0.016 s, and the key 40 µs.
  - A lock guards the dictionary for threaded callers.  None builds a
    layout today: the study's case stage uses threads, but for conversion.
- **An in-process cache helps within one command only.**  Each `hexmesh`
  command an agent runs is its own process.  Within one command, `advise`
  repeats its layouts (at each density it builds the network and counts
  it), and so do the build's `add` → `resolve` → `validate`.  An
  in-process session (Python API, the README test) also shares across
  calls.
- **What still misses:** `resolve`'s probe has sentinel counts, so it
  never equals the resolved wye, and each density `advise` tries is a new
  spec.  The primer session builds 4 distinct layouts (it built 9).
- **Before/after method:** the machine was shared, and the design
  session's test runs doubled wall times for a while.  So `to_wall` calls
  are the load-free measure.  Wall times are from runs at load < 1.5,
  with the cache off (`LAYOUT_CACHE_SIZE` = 0, i.e. the old behaviour plus
  a 0.02 s copy) and on, interleaved 3 times.
- **Tests** (`tests/test_wye.py`, 21 new):
  - equal values in new objects hit, and copies are independent;
  - each wye field changed (7);
  - each vector of each frame mutated in place (9);
  - the spec's nang, nrad, a shell, mprg, radius (5);
  - the bound.
  - Every change must miss and return what a fresh build gives.  Some
    changes don't move a vertex: `branch_length` at fixed frames, since
    the ports come from the frames, and `mprg`.  For those the test
    checks the miss only.

## Questions for design

1. **One layout build is still 0.55–0.67 s** (median 0.65 s, `insulated_network`'s
   wye at nang 6), above the task's 0.5 s line.  So, as step 3 asks:
   vectorise `Skeleton.to_wall`?
   - Today it does 270 calls per layout.  Each one marches out in R/16
     steps, then bisects 60 times, with a scalar `nearest` (three
     `np.linalg.norm` calls) at each step: 83 392 `nearest` calls for 4
     layouts.
   - Vectorised, it would march all of a curve's points at once and
     bisect them together, with `Skeleton.distance` (already vectorised)
     instead of `nearest`.  How much faster isn't measured.
   - **What it does to meshes:** the bisection runs down to 2⁻⁶⁰ of the
     step, so its last bits come from rounding, and vectorised sums round
     differently.  Wall nodes would move by rounding (by how much isn't
     measured), and the gallery meshes would no longer be byte-identical.
     That task would need a tolerance test on node positions in place of
     the byte check.
   - An alternative that keeps the bytes: cache the wall curves by
     geometry.  If `resolve`'s probe and the resolved wye share them
     (not checked: the counts may change the curves' points), that saves
     one more build per `add`, but not `advise`'s.

**Design answer (2026-11-08, the user: "add a note for the vectorizing so
it can be picked up in the future"):** held.  Vectorising moves wye wall
nodes by rounding, which conflicts with the stability statement 0115
publishes (reproducible meshes; node changes noted).  It is recorded in
RESEARCH §8 (proposed actions) with what a future task needs: the
speed-up measured first, a node-position tolerance in place of the byte
check for wye meshes, and a CHANGELOG note.  The curve-sharing
alternative isn't pursued: unverified, and it doesn't help `advise`.

## Outcome

**Done: the primer session's wall projection falls by 56 %** (2 430 →
1 080 `to_wall` calls).  In one process it goes from 5.7–6.1 s to
3.6–3.7 s, and `hexmesh advise` on its own halves.

| command | layouts built, before → after | `to_wall`, before → after | wall time, cache off → on |
|---|---|---|---|
| build + save | 1 → 1 | 270 → 270 | 0.95–1.06 → 0.93–1.11 s |
| validate | 1 → 1 | 270 → 270 | 0.59–0.73 → 0.83–0.89 s |
| estimate | 1 → 0 | 270 → 0 | 0.51–0.59 → 0.04–0.10 s |
| advise | 5 → 2 | 1 350 → 540 | 2.74–2.78 → 1.27–1.43 s |
| apply | 0 → 0 | 0 → 0 | 0.01 s |
| validate (applied) | 1 → 0 | 270 → 0 | 0.54–0.64 → 0.09–0.10 s |
| **session** | **9 → 4** | **2 430 → 1 080** | **5.69–6.06 → 3.62–3.74 s** |

(Wall times: 3 interleaved runs each, load < 1.5.  The first validate's
spread overlaps between off and on: a miss times like the old path,
0.52–0.67 s against 0.55–0.67 s, measured directly.)

- **As an agent runs them, one process per command** (cache off → on,
  the steadier of two pairs): `validate` 0.70 → 0.66 s, `estimate`
  0.58 → 0.60 s, `advise` 2.94 → 1.35 s.  Only `advise` gains across
  processes; the table above is one process, as in the README test and
  the Python API.
- **The README tests:** the four primer tests take 3.0–3.6 s, from 0110's
  5.0–5.1 s.
- **Largest cost now:** still the wye's wall projection (4 builds).
  Next, at about a fifth of it (0.59 s against 3.29 s under cProfile),
  is `Tee.predicted_sj`: 15 calls.  The out-of-scope rule says to propose such
  a cache, not do it; at that size it's worth one only after the wye's.
- **Gallery:** the 28 examples' `.msh` files have the same sha256 before
  and after.  The before hashes came out the same in two runs.
- **Files:** `hexmesh/assembly/wye.py`, `tests/test_wye.py`,
  `CHANGELOG.md`.
- **Tests:** `tests/test_wye.py` 61 passed (21 new).  The full suite:
  see the commit.
