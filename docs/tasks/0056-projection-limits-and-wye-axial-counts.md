# 0056 — Projection follow-ups: inversion check, move warning, wye axial counts

- **Status:** ready (after 0051 is committed)
- **Decision:** [0029 — Wall exactness by node projection](../decisions/0029-wall-exactness-by-node-projection.md), amendment 2026-10-29
- **Depends on:** 0051.  Before 0053 (the wye's shells use the same
  projection and counts).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Task 0051's *For design* items, answered in decision 0029's
amendment:
- a move limit in cell heights rejects valid fine meshes (a legitimate
  move grows with `nrad`);
- condition 2 requires a bad projection to fail loudly without a
  separate `check_quality` call;
- the wye's knee (the hub's spherical cap) is resolved by `n_run` only,
  so its chords stay at 8–10 % R at any `nang`.

**Where.**  `hexmesh/assembly/limits.py`, `assembler.py`
(`_check_projection`, `mesh()`), `projection.py`, `wye.py` (`resolve`,
counts), `refined_dict` (`AXIAL_COUNTS`), tests, `API.md`.

**Do.**
1. **Move warning, not limit** (revised 2026-10-29 after 0051's item 4:
   narrow wyes move 0.47–0.77 R legitimately).  Replace
   `WALL_PROJECTION_MAX_MOVE` with `WALL_PROJECTION_WARN_MOVE = 1.0`, as
   a fraction of the wall's local radius at the node (the tube radius the
   projector used).  Above it, a `UserWarning` naming the fitting and the
   largest move; `projection_report` records the largest move per fitting
   either way.  No rejection by distance.
2. **Inversion check in `mesh()`.**  After `generate(3)`, compute the
   min corner SJ of the cells of every fitting that was projected
   (`quality_hex`, those volumes only).  If any is ≤ 0, raise
   `AssemblyError` naming the fitting and the worst value.  Measure the
   cost on the kit wyes and tees (should be milliseconds).
3. **Wye axial counts from arcs.**  `n_run`, `n_branch` and `n_split`
   default to `None`, resolved in `resolve()` so that each axial edge
   (including the hub cap's arc) is no longer than the angular cell size
   at the wall, `(π/2)·R / nang`, or `axial_cell` when the assembly sets
   one, whichever is smaller.  The resolved counts are stored, so the
   JSON stays explicit.  Explicit counts keep today's meshes.
4. **Measure:**
   - the hub-cap chord error (as 0051's "elsewhere" table) at `nang`
     4 / 8 / 16 with the resolved counts;
   - cell counts and build time against today's defaults;
   - the **crotch chord error at 30°, 35° and 40°** (0051 measured only
     60° and 90°).  Narrow wyes move nodes up to 0.77 R, so their
     crease may be worse.  If it's above 1 % R at `nang` 8, report it
     under *Questions for design* (decision 0029, item 5: the layout
     follow-up).

**Accept.**
- A deliberately folding projector (test double) is rejected by the
  inversion check, naming the fitting; a projector that sends nodes
  across a branch (test double) is rejected by the inversion check
  and/or warns on the move.
- Valid wyes pass without warnings at `nrad` 3, 9 and 15, and at 30°,
  35°, 40°, 60°, 90° and 120°.
- With resolved counts the hub-cap chord error falls with `nang`
  (second order), and is below about 1 % R at `nang` 8.
- Explicit counts: meshes unchanged (node coordinates to 1e-12).
- Full suite: no new failures.

**Out of scope.**  The wye's layout; the tee's pinned plates.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
