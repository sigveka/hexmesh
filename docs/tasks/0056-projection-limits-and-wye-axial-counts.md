# 0056 — Projection follow-ups: inversion check, move warning, wye axial counts

- **Status:** blocked (Q1: `n_split`; Q2: creases). Steps 1–2 committed.
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

**Steps 1–2 done (2026-10-29).**
- **Move warning:** `limits.WALL_PROJECTION_WARN_MOVE = 1.0` local wall
  radii (`TubeUnion.local_radius`: the radius of the tube the projected
  node lies on).  Above it, a `UserWarning` naming the fitting, also
  appended to `Assembly.warnings`.  `projection_report[name]` holds
  `move`, `ratio` (move / radius) and `min_sj`.  The cell-height measure
  and the position matching it needed are gone.
- **Inversion check:** after `generate(3)`, the min corner SJ
  (`quality_hex.min_scaled_jacobians`, new, vectorised) of every hex of
  each projected fitting **and of its neighbours**.
  - A test double that mirrors nodes through the hub left the wye's own
    cells valid (min SJ 0.117).  It moved the port nodes, which must
    never move, and folded the neighbouring Straights.
  - SJ ≤ 0 is an `AssemblyError`: "Wye1: wall projection folded N
    cell(s), min corner scaled Jacobian …".
- **Test doubles** (`tests/test_projection.py`):
  - neighbouring nodes swapped: small moves, folds, rejected;
  - mirrored through the hub: moves of 14 R, warns and is rejected.
- **Cost of the check:** 9–27 ms for the kit-sized wye (1.2–3.5k
  cells, plus neighbours), 70–95 ms at 13k cells, 0.5–0.65 s at 90k:
  about 6 µs per checked cell, 10–15 % of the mesh time.  Not
  milliseconds on large fittings.  It could check only the cells that
  touch moved nodes if that matters.

**Step 3 implemented, then held back** (patch in this session's
scratchpad, `0056/step3-wye-counts.patch`; not committed).
- `BlockLayout.edge_lengths()`: every edge's length along its declared
  geometry, with its class count.
- `Wye.resolve`: builds the layout once with a distinct sentinel per
  unset count, so each edge's class count names the parameter that
  divides it.  Each count is then `ceil(longest edge / h)`, with
  h = min((π/2)·R/`nang`, `axial_cell`).
- **Resolved counts** (run 4 R, branch 7 R; `n_run`, `n_branch`,
  `n_split`): 60° gives 9/11/9 at `nang` 4, 17/22/17 at 8, 34/44/33 at
  16.  The wye's cells go from 1168 / 3488 / 13120 (3/3/3) to
  3344 / 16288 / 90624.
- **Two problems, *Questions for design*:**
  - `n_split` degrades and, at 120°, folds the turning blocks (Q1);
  - the remaining wall error is a crease, not the hub cap's resolution
    (Q2).

**Step 4 measurements** (wye run 0.4, branch 0.7, R 0.1, `nrad` 3; chord
error = largest distance from the canal surface of wall-quad centres and
edge midpoints; "resolved" = step 3's counts, "3/3/3" = today's
defaults):

| angle | `nang` | crease, 3/3/3 | crease, resolved | rest of wall, 3/3/3 | rest of wall, resolved | min SJ 3/3/3 → resolved | move |
|---|---|---|---|---|---|---|---|
| 30° | 4 / 8 / 16 | 4.8 / 3.1 / 3.1 % | 4.8 / 2.8 / 1.2 % | 2.9 / 2.9 / 3.0 % | 2.9 / 2.2 / 1.1 % | 0.065 → 0.065 / 0.056 / 0.047 | 0.77 R |
| 35° | 4 / 8 / 16 | 4.3 / 2.1 / 0.8 % | same | 3.9 % | 2.9 / 2.0 / 1.2 % | 0.086 → 0.083 / 0.068 / 0.058 | 0.60 R |
| 40° | 4 / 8 / 16 | 3.9 / 1.7 / 0.5 % | same | 4.9 % | 3.0 / 2.0 / 1.2 % | 0.109 → 0.094 / 0.077 / 0.068 | 0.47 R |
| 60° | 4 / 8 / 16 | 2.8 / 0.85 / 0.23 % | same | 10.2 % | 4.5 / 2.3 / 1.2 % | 0.211 → 0.129 / 0.107 / 0.096 | 0.18 R |
| 90° | 4 / 8 / 16 | 3.2 / 0.88 / 0.24 % | same | 6.0 / 7.9 / 8.2 % | 5.4 / 2.4 / 1.5 % | 0.236 → 0.153 / 0.124 / 0.101 | 0.13 R |
| 120° | 4 / 8 / 16 | 2.0 / 0.52 / 0.13 % | same | 11.6 / 13.5 / 13.6 % | 6.0 / 3.5 / **folds** | 0.155 → 0.113 / 0.102 / **−0.684** | 0.14 R |

- **Crotch crease at narrow angles** (step 4's third item): at `nang` 8,
  3.1 % (30°), 2.1 % (35°) and 1.7 % (40°), all above the 1 % threshold;
  1.2 / 0.8 / 0.5 % at `nang` 16.  So decision 0029 item 5's layout
  follow-up applies to wyes below about 50°: Q2.
- Build time, resolved against 3/3/3: about +0.1 s at `nang` 4, +1 s at
  8, +3 s at 16 (90k cells).
- All moves are under 1 R: no warnings for valid wyes at any angle.

**Min corner SJ against `n_split` alone** (`n_run` = `n_branch` = 3;
projection off / on):

| angle, `nang` | 3 | 6 | 10 | 14 | 20 | 27 |
|---|---|---|---|---|---|---|
| 30°, 8 | 0.065 | 0.065 | 0.065 | 0.065 | 0.060 | 0.057 |
| 60°, 8 | 0.211 | 0.156 | 0.124 | 0.112 | 0.103 | 0.098 |
| 90°, 8 | 0.258 / 0.233 | 0.164 | 0.135 | 0.122 / 0.124 | 0.102 / 0.116 | 0.089 / 0.109 |
| 120°, 8 | 0.155 | 0.117 | 0.106 | 0.094 / 0.102 | 0.071 / **−0.606** | 0.055 / **−0.585** |
| 120°, 16 | 0.155 / 0.149 | 0.112 / 0.117 | 0.066 / 0.103 | 0.038 / 0.081 | 0.012 / **−0.648** | −0.006 / **−0.684** |

`n_run` and `n_branch` don't affect the min SJ (120°, `nang` 16: 23 or
56 layers, 0.155).  The worst cells sit at the hub's back corners
(the five-block radial edges), upstream of O.

## Questions for design

**Q1. Resolving `n_split` from arcs lowers quality, and folds 120°
wyes.**  The turning block's cells degrade as `n_split` grows, at every
angle (table under *Agent notes*): 60° goes from 0.211 at 3 layers to
0.10 at 20.  At 120° the projection folds them from 20 layers (−0.61 at
`nang` 8, −0.68 at 16), and the mesh is already degenerate without
projection at 27 (−0.006).  The step 3 rule asks for 14–17 at `nang` 8
and 27–51 at 16, so a default 120° wye at `nang` 16 is rejected by the
new inversion check.  Options:
- (a) resolve `n_run` and `n_branch` as specified, and keep `n_split`
  from the turning block's shortest edge, or cap it (about 6: SJ ≥ 0.11
  at every angle measured).  The knee arcs then stay coarse, about
  (2–3)× the angular cell.
- (b) as (a), with the axial grading in the turning block toward the
  hub, if gmsh's transfinite grading can do that there.
- (c) a turning-block layout that keeps its quality as it refines (out
  of this task's scope).
I'd take (a) with a cap of 6 for now, and (c) as the follow-up.

**Q2. The rest of the wall error is a crease, and narrow crotches are
over 1 %.**
- With resolved counts the "elsewhere" error isn't the hub cap.  It is
  the mitre crease where the inlet cylinder meets each daughter, at the
  top and bottom of the hub, upstream of O at about (±0.67, ±0.78) R.
  The faces cross it, so the error is first order in `nang`: 4.5 / 2.3 /
  1.2 % at 60°, above 1 % at `nang` 8 at every angle.
- The crotch crease of 30°–40° wyes is 1.7–3.1 % at `nang` 8.
- Both are decision 0029 item 5's case: crease on block edges, a wye
  layout follow-up.  Does design open it now (before 0053), or after?

## Outcome

**Partial (2026-10-29): steps 1–2 done; step 3 blocked on Q1, Q2.**
- **Move warning** above 1 local wall radius (no rejection by
  distance), and the **inversion check** in `mesh()` over projected
  fittings and their neighbours.  Both name the fitting.
- **Files:** `hexmesh/assembly/assembler.py` (`_project_walls`,
  `_check_projection`), `limits.py` (`WALL_PROJECTION_WARN_MOVE`
  replaces `WALL_PROJECTION_MAX_MOVE`), `projection.py`
  (`local_radius`), `hexmesh/quality_hex.py` (`min_scaled_jacobians`),
  `API.md`.
- **Tests:** `test_projection.py`: two test doubles (fold rejected;
  across-branch warns and is rejected) replace the cell-height limit
  test, and the fold test also checks for no warnings and `min_sj > 0`.
- **Suite:** 1893 passed.
- **Step 3** (wye counts from arcs) is implemented but held back.  It
  would make default 120° wyes at `nang` 16 fail the inversion check
  (Q1).
