# 0060 — General branches, stage 1: `Tee(angle=…)`, laterals

- **Status:** done (2026-11-07)
- **Decision:** [0031 — General branch junctions](../decisions/0031-general-branch-junctions.md) (stage 1)
- **Depends on:** the tee as of task 0052 (shells, predicted-quality
  limit) and 0051 (node projection).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  45° laterals are common in plant piping, and the Štigler
lateral benchmark covers 30°–90° (RESEARCH §7.2).  `Tee` is
perpendicular only.

**Where.**  `hexmesh/assembly/tee.py`, `projection.py` (`TubeUnion`
with a branch ray at angle α), `blocks.py`, `limits.py`, kit, `API.md`,
DESIGN §7.1 (design applies the wording).

**Do.**
1. **Field** `angle` (degrees, default 90): the angle between the run's
   downstream direction and the branch axis.  `toward=` resolves the
   roll as today; `angle` sets the lean in the branch plane.
2. **Geometry:** saddle points from RESEARCH §3.1 with h = 0, P(φ) for
   the given α (sampled splines, as today).  Station positions along the
   run become asymmetric (s(0) ≠ s(π)); turn faces follow.  The branch
   port frame leans by α.  Shells: the same formula at R + T_l and
   r + T_l (decision 0028); walls and shell boundaries by node
   projection (`TubeUnion` with the branch as a ray at α).
3. **Room checks:** the branch clears the run's ends at the acute side,
   and the turning station clears the main's outer shell, along the
   leaning axis.  Name the limit.
4. **Measure:** predicted corner SJ and max non-orthogonality over
   α ∈ {30, 45, 60, 75, 90}° × r/R ∈ {0.3, 0.6, 0.9} × 0 / 2 shells,
   `nang` 4 and 8.  Locate the worst cell (acute crotch, obtuse side,
   core).
5. **The tee's ratio cut-off τ** (decision 0031's amendment): extend the
   quality table to r/R ∈ {0.9, 0.95, 0.97, 0.99} at 90° and 45°, and
   set `TEE_MAX_RATIO` in `limits.py` where the predicted quality stops
   being acceptable (about 0.95 expected).  `Tee` rejects
   τ < r/R < 1 with the hint "an equal tee, or a branch radius ≤ τ·R",
   and r = R with "equal tees are planned through the wye-family
   layout".
6. **Limit:** the two tiers of 0052 (reject < 0.1, warn < 0.3, with the
   shortest `run_length` hint) apply unchanged.  Propose a lower bound
   on α under *Questions for design* if the tiers alone don't make a
   clean rule.

**Accept.**
- `angle=90` meshes identically to today's tee (node coordinates to
  1e-12).
- Kit cases at 45° and 60° (single-layer and with two shells): all-hex,
  meshed = predicted, class-0 ports, every wall and interface node on
  its analytic surface (1e-6 R), quality ok.
- The branch outlet's frame matches the analytic axis (to 1e-9).
- The quality table and, if needed, a proposed α bound.
- Full suite: no new failures.

**Out of scope.**  Offsets (0061), twist (0062), ducts (0063), equal
tees, crosses.

**Design note (2026-11-02, decision 0037 item 5; DESIGN §6, §9).**
The duct taps' block layouts are already in `duct_tap.py`, but their
front end lives inside the pipe tee's class.  `Tee` carries
`_duct_geometry`, `_full_width`, `_tap`, `_resolve_duct`, `_check_duct`
and `meshed_sj_check`'s duct case: 15 shape switches in `tee.py`.
DESIGN §6: "new fitting variants are new templates, not special cases
inside existing ones".
- **Before adding `angle`**, move the duct-tap front end into
  `duct_tap.py`, so `Tee` only picks the template (pipe tee or duct
  tap) and delegates.  Keep the shared helpers (`thicknesses`,
  `branch_spec`, `tee_wall`) public in `tee.py` or a small shared
  module.
- `Tee(...)` stays the one user-facing entry point (decision 0027).
- No behaviour change in the split (task 0065's method over the tee and
  duct-tap tests' builds).  Make it a separate commit before the
  lateral work.
- Lower `tests/test_architecture.py`'s shape-site cap by what leaves.
- **Done in task 0086** (`92c0787`, 2026-11-04).  `duct_tap.TapTemplate`
  holds the front end, and `Tee` picks the template and delegates.  The
  template asks the shape protocol, so the shape-site cap is 15 → 7.
  No behaviour change: 334 of 334 tee meshes and 339 of 339 messages
  identical (the 0065 method, 21 files).  0060 starts at the `angle`
  work.

## Agent notes

- **Frame.**  The branch axis is d = cos α ex + sin α ez (ex the run,
  ez the rolled inlet's up), through the T-point; the branch port's up is
  the axis's in-plane normal u = sin α ex − cos α ez, which is ex at 90°.
  `branch_length` is measured along d.  `toward=` resolves the roll from
  its component across the run, as before.
- **Geometry.**  `saddle_point(R, r, cos α, sin α, φ)` is RESEARCH §3.1
  with h = 0; φ is measured from u (downstream at 90°) toward +y, so the
  branch diagonals keep their φ and the block topology is the tee's.
  Station levels sit at the saddle's diagonal x, which differs up- and
  downstream.  The junction core's top face slides to x = zq cos α / sin α,
  centred on d.  The turning station is normal to d, at the distance where
  its acute-side rim clears the outer main shell by (r + T)/2:
  `(R + T + (r + T)/2 + (r + T) cos α) / sin α`.
- **Bit identity at 90°.**  `lean(90)` returns exactly (0, 1), and the
  90° branches compute every coordinate by the old expressions.  Check: 12
  assemblies (r/R 0.3, 0.5, 0.9 × 0 / 2 shells × axis and oblique), meshed
  at HEAD (a scratch worktree) and with the change: node coordinates
  identical, max difference 0.0.
- **Tried and dropped:** tilting the core's top face with the lean (0 to
  1 × (90 − α)) lowers the SJ at every angle (45° r/R 0.9: 0.176 → 0.152
  at full tilt); the turning height has almost no effect (×3: 0.176 →
  0.184).  The limit is local to the acute crotch.
- **Room checks** (step 3): `run_length` must exceed the outer hole's
  reach downstream (`tip_reach`, the φ = 0 tip, larger than r + T for
  α < 90), and `branch_length` the turning station's distance.  Both name
  "the acute side" in the message; at 90° the messages are unchanged.
- **Duct taps** reject `angle` ≠ 90 at `add()` (`angle_on_duct_tap`,
  pointing to 0063).
- **`run_length=None`** resolves to max(tip reach + R/2, the shortest run
  reaching `PREDICTED_SJ_WARN`), the same rule as before at 90°.
- **`run_length=None` fallback.**  Where no run reaches the warning tier
  (every lateral below about 57°), the default used to stay at reach +
  R/2, which can be below the minimum (45°, r/R 0.6: SJ 0.010).  It now
  takes the shortest run that passes `PREDICTED_SJ_MIN`.  At 90° that run
  is always shorter than r + T + R/2: over 76 cases (r/R 0.21–0.57 where
  the warning tier is unreachable, T 0–0.05), the closest was 13.8 mm
  shorter.  So no tee's default changes.
- **Hint** (design's Q1 answer): a lateral's tier message adds "at angle
  α°; r/R q or more reaches it there, or a larger angle" (or "no ratio up
  to TEE_MAX_RATIO 0.95 reaches it there"), from `Tee.smallest_ratio`
  (bisection on the prediction at a long run).  The 90° messages are
  unchanged.
- **JSON.**  Saved tees now carry `"angle"` (90.0 by default).
- **Codes.**  New: `tee_angle_out_of_range`, `tee_ratio_above_max` and
  `angle_on_duct_tap`.  r = R reuses the network reader's
  `equal_tee_unsupported`, with the task's hint.

### Quality table (step 4)

At the plateau run (reach + 2R) and branch length (turning station + R),
R = 0.1, shells 2 × 0.02.  The predicted SJ is the same at nang 4 and 8,
and the meshed SJ equals it (to 1e-3) everywhere below r/R 0.95.  The
worst cell is the turn block at the acute crotch (the downstream station's
top corners).  At 90° the two sides tie, so the label there is arbitrary.

| α | r/R | predicted SJ (0 / 2 shells) | meshed SJ | max non-orth., nang 4 / 8 (0 shells) | worst cell |
|---|---|---|---|---|---|
| 30° | 0.3 | 0.008 / 0.030 | rejected | - | - |
| 30° | 0.6 | 0.051 / 0.053 | rejected | - | - |
| 30° | 0.9 | 0.074 / 0.077 | rejected | - | - |
| 45° | 0.3 | 0.063 / 0.064 | rejected | - | - |
| 45° | 0.6 | 0.118 / 0.120 | 0.118 | 69.9° / 71.8° | acute |
| 45° | 0.9 | 0.176 / 0.180 | 0.176 | 66.1° / 69.4° | acute |
| 60° | 0.3 | 0.102 / 0.103 | 0.102 | 76.5° / 78.3° | acute |
| 60° | 0.6 | 0.200 / 0.201 | 0.200 | 64.0° / 66.7° | acute |
| 60° | 0.9 | 0.308 / 0.311 | 0.308 | 56.3° / 59.7° | acute |
| 75° | 0.3 | 0.134 / 0.134 | 0.134 | 74.4° / 76.5° | acute |
| 75° | 0.6 | 0.273 / 0.273 | 0.273 | 59.3° / 63.9° | acute |
| 75° | 0.9 | 0.432 / 0.432 | 0.432 | 47.1° / 49.5° | acute |
| 90° | 0.3 | 0.150 / 0.150 | 0.150 | 73.3° / 75.3° | acute |
| 90° | 0.6 | 0.316 / 0.316 | 0.316 | 55.6° / 62.2° | acute |
| 90° | 0.9 | 0.509 / 0.509 | 0.509 | 40.2° / 46.0° | tie |

The smallest r/R reaching each tier, by bisection on the prediction:

| α | `PREDICTED_SJ_MIN` 0.1 | `PREDICTED_SJ_WARN` 0.3 | SJ at r/R 0.95 |
|---|---|---|---|
| 35° | 0.875 | none | 0.109 |
| 40° | 0.65 | none | 0.146 |
| 45° | 0.50 | none | 0.187 |
| 50° | 0.403 | none | 0.232 |
| 60° | 0.293 | 0.88 | 0.329 |
| 75° | 0.223 | 0.655 | 0.461 |
| 90° | 0.202 | 0.574 | 0.543 |

### The ratio cut-off τ (step 5)

| α | r/R | predicted | meshed nang 4 / 8 (0 shells) | meshed nang 4 / 8 (2 shells) |
|---|---|---|---|---|
| 45° | 0.9 | 0.176 | 0.176 / 0.176 | 0.180 / 0.180 |
| 45° | 0.93 | 0.183 | 0.183 / 0.183 | 0.187 / 0.187 |
| 45° | 0.95 | 0.187 | 0.187 / 0.187 | 0.191 / 0.191 |
| 45° | 0.97 | 0.192 | 0.192 / 0.192 | 0.196 / 0.196 |
| 45° | 0.99 | 0.197 | 0.197 / 0.166 | 0.127 / 0.122 |
| 90° | 0.9 | 0.509 | 0.509 / 0.509 | 0.509 / 0.509 |
| 90° | 0.93 | 0.530 | 0.530 / 0.530 | 0.530 / 0.527 |
| 90° | 0.95 | 0.543 | 0.543 / 0.536 | 0.543 / 0.519 |
| 90° | 0.97 | 0.557 | 0.549 / 0.486 | 0.537 / 0.486 |
| 90° | 0.99 | 0.571 | 0.412 / 0.301 | 0.412 / 0.301 |

The straight-edge prediction keeps rising toward r/R = 1, but the
meshed SJ pulls away from it once the saddle's sides curve hard: within
0.025 up to 0.95, 0.07 at 0.97, 0.27 at 0.99.  `TEE_MAX_RATIO` = 0.95.

### Predicted vs meshed at the lowest passing angles (design's Q1 condition)

Meshed min corner SJ at the edge of `PREDICTED_SJ_MIN` (plateau run):

| α | r/R | nang 4: pred / mesh (0 sh.) | 2 sh. | nang 8: 0 sh. | 2 sh. |
|---|---|---|---|---|---|
| 35° | 0.875 | 0.100 rejected | 0.103 / 0.103 | 0.100 rejected | 0.103 / 0.103 |
| 35° | 0.88 | 0.101 / 0.101 | 0.104 / 0.104 | 0.101 / 0.101 | 0.104 / 0.104 |
| 35° | 0.9 | 0.103 / 0.103 | 0.107 / 0.107 | 0.103 / 0.103 | 0.107 / 0.107 |
| 45° | 0.50 | 0.100 rejected | 0.102 / 0.102 | 0.100 rejected | 0.102 / 0.102 |
| 45° | 0.51 | 0.102 / 0.102 | 0.104 / 0.104 | 0.102 / 0.102 | 0.104 / 0.104 |
| 45° | 0.55 | 0.109 / 0.109 | 0.111 / 0.111 | 0.109 / 0.109 | 0.111 / 0.111 |

They agree to 1e-3 in every case, so no margin or cap is needed.  (At
exactly 0.875 and 0.50 the single-layer prediction rounds to the floor,
0.0999…, and is rejected.)  Max non-orthogonality there: 71–75°.

## Questions for design

**Q1 — answered by design (2026-11-07, decision 0031 amendment):** no
`TEE_MIN_ANGLE`, because the usable angle depends on r/R.  The hint names
the angle and the smallest r/R that passes at it (done, above).
Condition: predicted and meshed SJ agree at the lowest passing angles
(confirmed, table above).  30° is held.  Follow-ups are tasks 0103
(network angled tees) and 0104 (junction non-orthogonality).

The original proposal:

**Q1 (proposal, not blocking): a lower bound on α?**  The two tiers
already give a rule: they reject 30° at every ratio and 35° below
r/R 0.875, and their message names the angle ("a larger angle or a larger
branch ratio raises it").  So no separate bound is needed for safety.
Two things the tiers don't say plainly:
- the Štigler benchmark's 30° lateral (RESEARCH §7.2) can't be built with
  this layout at all;
- every lateral below about 57° warns, at any ratio.

Proposal: no `TEE_MIN_ANGLE`.  Instead, the DESIGN §7.1 wording (design
applies it) gives the effective range, about 40°–90° for r/R ≥ 0.65, and
names 30° laterals as needing a different crotch layout (a split acute
turn block, for example) in a later stage.  If design prefers an explicit
bound, 35° matches the data.

## Outcome

- **Files:**
  - `hexmesh/assembly/tee.py`: `angle`; `lean`, `saddle_point`,
    `tip_reach`; `turning_height(…, angle)`; `_branch_axes`; the layout,
    ports and room checks; the ratio cut-off.
  - `hexmesh/assembly/limits.py`: `TEE_MAX_RATIO`.
  - `hexmesh/assembly/duct_tap.py`: the `angle` guard.
  - `hexmesh/errors.py`: three codes.
  - `hexmesh/agent/support.json`: regenerated; only the tee's repr gained
    `angle=90.0`.
  - `tests/test_tee.py` (+16), `tests/test_fitting_conformance.py` (4
    lateral cases, `_tee_deviation` on the leaning axis).
  - `API.md`, `CHANGELOG.md`.
- **Acceptance:**
  - 90° identical: max node difference 0.0 over 12 assemblies.
  - Kit cases `lateral-45-0.9`, `lateral-45-0.9-3layer-oblique`,
    `lateral-60-0.6`, `lateral-60-0.9-3layer`: 24 of 24 pass.  That
    covers all-hex, meshed = predicted, class-0 ports, every fill order,
    and walls and interfaces exact (their nodes at 1e-15 R in the probe
    run).
  - Branch outlet frame on the analytic axis to 1e-9 (oblique assembly).
  - Quality table above; the α proposal under Q1.
  - Full suite: 3664 passed, 15 skipped, 0 failed (28 min), before the
    last two changes (the smallest-ratio hint and the `run_length=None`
    fallback).  The 34 test files that build a tee were re-run after
    them: 1932 passed, 1 skipped, 1 failed.  The failure was
    `test_shape_sites_cap`: `smallest_ratio` added a ninth
    `spec.core_shape.radius`.  Fixed with a shared `main_radii(spec)`,
    used by `shortest_run` too, so the count is back at the cap of 7.
    `test_architecture.py` and `test_tee.py` pass after the fix (99).
- **Surprises:**
  - Max non-orthogonality is high in small-ratio junctions at every angle
    (78° at 60°, r/R 0.3, nang 8; 75° at 90°).  The tee has no
    non-orthogonality check, so nothing reports it.  This predates 0060:
    the 90° rows are today's tee.
  - The network reader still rejects angled tees (`tee_branch_angled`).
- **Follow-ups:** now tasks 0103 (the network builder passes angled
  tees to `Tee(angle=…)`) and 0104 (junction non-orthogonality predicted
  in `validate()`).  The 30° crotch layout is held.
