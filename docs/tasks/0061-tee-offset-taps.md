# 0061 — General branches, stage 2: `Tee(offset=…)`, tangential and offset taps

- **Status:** done
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 2); PCF mapping from [0023](../decisions/0023-pcf-branched-networks-insulation-equipment.md)
- **Depends on:** 0060.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Offset and tangential set-ons are real plant fittings (PCF
SKEYs TOSO/TORF and TTSO/TTRF, `docs/integrations/pcf.md`), rejected by
the PCF reader today.

**Where.**  `hexmesh/assembly/tee.py`, `projection.py`, `limits.py`,
`hexmesh/io/readers/pcf.py`, kit, `API.md`, `docs/integrations/pcf.md`.

**Do.**
1. **Field** `offset` (length, default 0): the distance h between the
   branch axis and the main axis, along the main's local `right` after
   the roll.  Valid for |h| + r < R (RESEARCH §3.1), with a margin set
   by measurement.
2. **Geometry:** the full P(φ) of RESEARCH §3.1 with h ≠ 0 (and any α
   from 0060).  Tips move by arcsin(h/R) around the main axis (§3.2).
   Decide how the junction's block corners follow: they stay on the
   branch diagonals; record how the main's ring blocks absorb the
   asymmetry.  Shells and projection as 0060.
3. **Measure:** predicted corner SJ and non-orthogonality over
   h/R ∈ {0, 0.2, 0.4, 0.6} with r/R ∈ {0.3, 0.5}, at α 90° and 45°.
   Propose the margin on |h| + r under *Questions for design*.
4. **PCF:** map TOSO/TORF (offset) and TTSO/TTRF (tangential: the
   largest offset the margin allows, or reject naming the margin) to
   `offset`.  Update the reader's rejection tests and `pcf.md`.

**Accept.**
- `offset=0` meshes identically to before (to 1e-12).
- Kit cases at h/R 0.3 (α 90° and 45°): all-hex, meshed = predicted,
  class-0 ports, walls exact on the final mesh, quality ok.
- A PCF fixture with an offset set-on builds and meshes.
- The quality table and the proposed margin.
- Full suite: no new failures.

**Out of scope.**  Twist (0062), ducts (0063).

## Agent notes

- **Geometry (step 2).**  The branch axis passes through (0, hy, 0) in the
  layout's frame, hy = −offset (the layout's ey is the main's −right).
  The saddle is RESEARCH §3.1's P(φ) with y = hy + r sin φ, z = √(R² − y²)
  (`saddle_point(…, hy)`); `tip_reach` samples it when a lateral is
  offset (3601 φ).  The branch tube, its walls and its port start at the
  branch foot `ob` (`_branch_axes` returns it).
- **How the blocks absorb the asymmetry.**  The block corners stay on
  the branch diagonals, on the offset saddle.  Each station's two sides
  get their own x and their own height on the main cylinder (an offset
  lateral's diagonals meet the main at different x); the station's
  bottom edge is an arc when both sides share x and a spline on the
  cylinder otherwise.  The junction core's top follows the branch axis
  (λ = 1), and its bottom follows by `_BOTTOM_SHIFT` = 0.25 of it.
  Measured over λ, μ: μ = 0 folds the wide side's ring at r/R 0.3,
  h/R 0.4–0.6, and μ ≥ 0.5 folds the bottom ring.  The main's ring
  blocks take the rest: they are wider on one side than the other.
- **offset = 0 is bit-identical**: the nodes of six tees and laterals
  (1–3 shells, nang 4 and 8, oblique, roll 90) equal HEAD's to 0.0.
- **The margin is on h/r, not |h| + r** (step 3).  `--map` (72 cases,
  r/R 0.2–0.9 by h/R 0–0.7, 90° and 45°, before the margin existed) and
  a finer probe found every meshing failure at h ≥ 1.38 r: a folded wall
  projection, failed B-spline fills, and a plane face whose edge OCC
  rebuilds with no end points (InternalError "curve 157 has 0 end
  points"; `docs/integrations/gmsh.md`).  They are erratic: r/R 0.3
  fails at h/R 0.42, 0.45, 0.48, 0.55 and 0.6 but meshes at 0.58, 0.59,
  0.61 and 0.65.  With h ≤ r all 90 probed cases (r/R 0.25–0.85 at 90°,
  0.55–0.8 at 45°) mesh, or are rejected by their predicted SJ (45°,
  r/R 0.55, h/R ≥ 0.28).  Up to h ≤ r, |h| + r just below R is fine:
  r/R 0.5–0.9 mesh at |h| + r = 0.98 R.  So I implemented the margin as
  `limits.TEE_MAX_OFFSET_RATIO` = 1.0 (|h| ≤ r), next to |h| + r < R.
  Both raise `tee_offset_out_of_range`.  See *Questions for design*.
- **PCF (step 4).**  The guide (p. 94, figures A and B) puts
  `BRANCH1-POINT` on the branch axis, beside `CENTRE-POINT`: the two
  points don't fix h.  The builder takes the branch direction from the
  straight (pipe, fitting or reducer) that leaves `BRANCH1-POINT`.  h is
  BRANCH1's distance from the plane of that direction and the host axis,
  signed along the Tee's right.  A branch axis that misses
  `CENTRE-POINT` along the host, or a set-on with no such straight, is
  `seton_offset_branch`.  Tangential set-ons go the same route, and the
  Tee rejects them (h = R − r).  `seton_offset_unsupported` is retired.
- **Duct taps reject `offset`** (`offset_on_duct_tap`): they would have
  ignored it.
- `smallest_ratio`'s bisection now stops below r = R − |h|, so a lateral's
  hint stays inside the offset's range.

## Questions for design

1. **Confirm the offset margin: |h| ≤ r (`TEE_MAX_OFFSET_RATIO` = 1.0),
   with |h| + r < R.**  The step asked for a margin on |h| + r.  The
   measurements put it on h/r instead: the first failures are at h/r
   1.38, and there's no failure with h ≤ r even at |h| + r = 0.98 R.  The
   bound has a geometric reading: with h ≤ r, the branch's footprint
   still covers the main's top line.  It gives about 30 % headroom
   below the first failure.  It is implemented and documented as
   proposed.  A tighter or looser value is one constant.
2. **Tangential set-ons (TTSO/TTRF) are rejected, naming the range**,
   not clamped to the largest allowed offset.  Clamping would move the
   branch by r − h or more without saying so, and the downstream
   branch pipe would then miss the port (the builder checks port
   positions).  Is rejection the intended reading of step 4's "or"?
   Building them needs h = R − r at the wall: a separate layout, outside
   this task.

**Design answers (2026-11-09, the user: "yes"):** both confirmed, and
recorded in decision 0031's amendment of 2026-11-09.
1. |h| ≤ r (`TEE_MAX_OFFSET_RATIO` 1.0) with |h| + r < R stands.
2. Rejection is the intended reading: no silent move off the file's
   point.  A tangential layout is asked about if plant files show it.

## Outcome

**Files.**
- `hexmesh/assembly/tee.py`: the `offset` field; offset saddle,
  `tip_reach`, branch foot, station sides, and core shift; the checks.
- `hexmesh/assembly/limits.py`: `TEE_MAX_OFFSET_RATIO`.
- `hexmesh/assembly/duct_tap.py`: `offset_on_duct_tap`.
- `hexmesh/errors.py`, `API.md`: codes `tee_offset_out_of_range`,
  `offset_on_duct_tap` and `seton_offset_branch` added;
  `seton_offset_unsupported` retired.
- `hexmesh/interchange/build.py`, `graph.py`: the PCF offset set-on
  mapping (`_offset_branch_dir`, `_offset_side`, `_Comp.branch_dir`).
- `validation/tools/tee_offset.py` and `tee_offset.json`: the quality
  table and the `--map`.
- `hexmesh/agent/support.json`: regenerated; the Tee repr gains
  `offset=0.0`.
- Docs: `API.md` (Offset taps, the limits table, the PCF rows),
  `docs/integrations/pcf.md`, `docs/integrations/gmsh.md` and
  `CHANGELOG.md`.

**Tests.**
- Kit (`tests/test_fitting_conformance.py`), 3 new cases:
  `tee-0.5-offset-0.3`, `tee-0.5-offset-0.3-3layer-oblique`
  (h = −0.3 R) and `lateral-45-0.6-offset-0.3`.  All pass: all hex,
  meshed = predicted, class-0 ports, walls exact, order-independent.
  `_tee_deviation` now measures the branch cylinder from its foot.
- `tests/test_tee.py`: 13 new tests: offset saddle points, even reach,
  branch port, both rejections, the lateral hint, and the duct tap.
- `tests/test_pcf_junctions.py`: 5 new tests (offset set-on build and
  mesh ×3, tangential, missed centre); the TOSO rejection test is
  updated.
- Full suite: see below.

**Quality table** (nang 8, single layer, `run_length=None`; pSJ/pNO
predicted, mSJ/mNO meshed; the projector moves ≤ 2e-3 R):

| α | r/R | h/R | run | pSJ | mSJ | pNO | mNO | verdict |
|---|-----|-----|-----|-----|-----|-----|-----|---------|
| 90 | 0.3 | 0   | 0.80R | 0.150 | 0.150 | 73.7 | 74.2 | warns |
| 90 | 0.3 | 0.2 | 0.80R | 0.141 | 0.144 | 74.1 | 74.8 | warns |
| 90 | 0.3 | 0.4 | 0.80R | 0.136 | — | 73.8 | — | h > r: rejected |
| 90 | 0.3 | 0.6 | 0.80R | 0.130 | — | 72.1 | — | h > r: rejected |
| 90 | 0.5 | 0   | 1.00R | 0.258 | 0.258 | 62.8 | 63.1 | warns |
| 90 | 0.5 | 0.2 | 1.00R | 0.231 | 0.236 | 64.5 | 65.1 | warns |
| 90 | 0.5 | 0.4 | 1.00R | 0.209 | 0.232 | 64.8 | 65.6 | warns |
| 90 | 0.6 | 0   | 1.10R | 0.313 | 0.316 | 57.4 | 58.4 | ok |
| 90 | 0.6 | 0.2 | 1.10R | 0.276 | 0.283 | 59.9 | 60.4 | warns |
| 45 | 0.3, 0.5 | 0–0.4 | ~2R | < 0 | — | 73–80 | — | predicted SJ: rejected (0060's floor is r/R 0.50) |
| 45 | 0.6 | 0   | 2.85R | 0.100 | 0.118 | 70.4 | 70.5 | warns |
| 45 | 0.6 | 0.2 | 3.30R | 0.100 | 0.108 | 71.8 | 72.2 | warns |

- The predicted SJ falls slowly with h: about 20 % at h/R 0.4 for
  r/R 0.5 (90°).
- The meshed SJ is at or above the prediction everywhere.
- The meshed non-orthogonality is within 1° of the prediction.
- A 45° lateral's resolved run grows with h to stay at
  `PREDICTED_SJ_MIN` (2.85 R → 3.30 R).

**Surprises.**
- The failures depend on h/r, not on |h| + r.
- OCC's plane-face edge rebuild (see `gmsh.md`) can't be reproduced
  outside the full model.

**Proposed follow-ups.**
- If design wants h > r: a layout whose core leaves the main's top line
  (the branch clear of the axis plane).
- The tangential layout (h = R − r, the walls flush).
