# 0070 — Duct taps: the pillowed tap in `Tee`

- **Status:** done
- **Decision:** [0033 — Junction layout for duct taps](../decisions/0033-duct-tap-topology.md) (result and decision, 2026-10-30); fields from [0027](../decisions/0027-duct-tees.md)
- **Depends on:** 0069 (the prototype `hexmesh/assembly/duct_tap.py`).
  0057 (full-width taps) follows; 0059 (HVAC example) after both.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The prototype works for rectangular and round taps inside the
face; it becomes part of the public `Tee`.

**Where.**  `hexmesh/assembly/tee.py`, `duct_tap.py`, `blocks.py`
(`face_vertices` for rectangular faces), `limits.py`, kit, `API.md`,
`README.md` limitations.

**Do.**
1. **One `Tee`:** `Tee(…, branch=RectShape(…) | CircleShape(…),
   face="wide" | "narrow", …)` on a rectangular main builds the pillowed
   layout.  Existing pipe-tee fields and behaviour unchanged; `roll`
   0 / 180 picks the side.
2. **Dispatch by across ratio:**
   - q/a ≤ `DUCT_TAP_MAX_RATIO` (ρ_max): the pillowed tap;
   - q = a: the full-width tap (task 0057; until it exists, rejected with
     "full-width taps: task 0057");
   - in between: rejected, naming the ratio and the hint ("a tap up to
     ρ_max·a, or a full-width tap").
   - **Set ρ_max** where the ±y tube blocks get too thin: measure ratio
     0.9, 0.93, 0.95, 0.97 on the 1:1, 2:1 and 3:1 ducts.
3. **Tunables** (margin, dome, sheet) resolved in `add()` as in the
   prototype, stored in the JSON (explicit), and overridable.
4. **Quality:**
   - the two predicted-SJ tiers (reject < 0.1, warn < 0.3, with a
     hint);
   - **for round taps, also the meshed SJ** in `mesh()` (the prediction
     overestimates by up to 0.11): warn or reject on the same tiers,
     naming the fitting;
   - a narrow-face tap on a duct of aspect ≥ 3 warns, naming the cause
     and suggesting the wide face.
5. **`face_vertices`** gains the rectangular case (the prototype's
   `rect_face_vertices`); check no other caller relied on circular
   corners for ducts.
6. **Docs:** document the branch frame's orientation (the branch keeps
   the main's counts per side) in `API.md`; README limitations
   (narrow-face quality, cells 1.6–2.3× a plain run, no full-width yet).
7. **Kit:** rectangular and round taps on 2:1 (wide and narrow) and 3:1
   (wide) ducts; the prototype's tests move into `test_tee.py` or stay
   in `test_duct_tap.py`, as reads better.

**Accept.**
- Kit cases: all-hex, meshed = predicted, class-0 ports, walls exact,
  quality ok or warned as specified.
- Pipe tees unchanged (node coordinates to 1e-12).
- ρ_max set, with the measurements in *Outcome*.
- Full suite: no new failures.

**Out of scope.**  Full-width taps (0057), shelled duct taps (decisions
0026/0028 later), angled shoe taps (0063).

## Agent notes

- `DuctTap` stays in `duct_tap.py` as the layout engine, no longer a
  fitting: `Tee._tap()` builds it from the tee's fields; checks, quality,
  fill and ports dispatch on a rectangular main (`_is_duct`).  The
  prototype's `rect_face_vertices` became the rectangular branch of
  `blocks.face_vertices`.  It is identical to the prototype's to 0.0, and no
  other caller passes a duct spec (wye and pipe tee call `_check_circle`
  first).
- **Added a fourth stored count, `n_wall`** (cells from a station to the
  hole).  Its default is a ceiling, so `refined(2)` gave 7.79× the cells,
  not 8×.  `add()` now resolves it like the tunables, the JSON stores it,
  and refinement scales it with the axial counts (`AXIAL_COUNTS`).
- `branch=` serialises as its shape's `to_dict()`; `_tuples` reads back a
  dict tagged with a shape `type`.  Refinement scales the shape's counts.
- On a pipe, `branch=CircleShape(…)` is accepted as the long form of
  `branch_radius` (it resolves to the same fitting).
- The default `run_length` is the tap's reach along the main plus 4 ring
  thicknesses: room for the largest tuning margin (3 t) and one more.

## Questions for design

_None._

## Outcome

Done 2026-10-30.

**Files.**
- `hexmesh/assembly/tee.py`: fields `branch`, `face`, `margin`, `dome`,
  `sheet`, `n_wall` (all omitted from a pipe tee's JSON).  Dispatch on a
  rectangular main covers resolve, check, ports, layout, quality and fill.
  New: `_check_duct`, `_duct_quality`, `meshed_sj_check`.
- `duct_tap.py`: now the layout engine, with `tuned` and `wall_cells`.
- `blocks.py`: `face_vertices` has a rectangular case.
- `limits.py`: `DUCT_TAP_MAX_RATIO` 0.93, `DUCT_TAP_NARROW_ASPECT_WARN` 3.
- `assembler.py`: `_check_meshed_sj`, the tiers on meshed cells for round
  taps, naming the fitting.
- `intent.py`: shape fields serialised; refinement scales the branch's
  counts and `n_wall`.
- Docs: `API.md`, `README.md` limitations, `GALLERY.md` and the
  `rect_duct` example note.

**Tests.**
- Kit: 6 duct-tap cases (rectangular and round; 2:1 wide and narrow, 3:1
  wide, one oblique; both rolls), giving 78 kit tests.  All are all-hex,
  meshed = predicted, with class-0 ports and walls exact (new
  `_duct_tap_deviation`).
- `test_duct_tap.py`: 22 tests covering dispatch, all rejections, roll and
  side, the JSON round trip, `refined(2)` = 8× the cells, the narrow-face
  warning and the forced meshed-SJ reject.
- `test_rect_duct.py`: the stale "rectangular tees" expectation is updated.
- Pipe tees: the 5 kit tee cases give node coordinates identical to HEAD
  (max difference 0.0).
- Full suite: 2085 passed, 14 skipped, 0 failed (was 1983 passed).

**ρ_max measurements** (prototype engine, `nang` 4, tunables tuned):
predicted / meshed min corner SJ.

| tap, duct, face | 0.90 | 0.93 | 0.95 | 0.97 |
|---|---|---|---|---|
| rect 1:1 | 0.20 / 0.20 | 0.15 / 0.15 | 0.10 / **0.095** | 0.063 |
| rect 2:1 wide | 0.42 | 0.35 | 0.26 | 0.17 |
| rect 2:1 narrow | 0.20 | 0.15 | 0.10 | 0.063 |
| rect 3:1 wide | 0.28 | 0.28 | 0.27 | 0.26 |
| rect 3:1 narrow | 0.16 | 0.15 | 0.10 | 0.063 |
| round 1:1 | 0.21 / 0.20 | 0.19 / 0.17 | 0.18 / 0.14 | 0.17 / 0.12 |
| round 2:1 wide | 0.36 / 0.36 | 0.34 / 0.31 | 0.32 / 0.27 | 0.31 / 0.23 |
| round 2:1 narrow | 0.21 / 0.20 | 0.19 / 0.17 | 0.18 / 0.14 | 0.17 / 0.12 |
| round 3:1 wide | 0.26 / 0.14 | 0.25 / 0.12 | 0.24 / **0.11** | 0.24 / 0.20 |
| round 3:1 narrow | 0.15 | 0.16 | 0.16 / 0.14 | 0.16 / 0.12 |

Rectangular taps: meshed = predicted except 1:1 at 0.95.  At 0.95 a
rectangular tap meshes below `PREDICTED_SJ_MIN`; at 0.97 even the
prediction is below it.  At 0.93 every case is ≥ 0.12, so ρ_max = 0.93.
Non-orthogonality at 0.93 is at most 80.5° (3:1 narrow).

**Surprises.**
- `n_wall` isn't linear in the counts (a ceiling), so it is stored like
  the tunables (*Agent notes*).
- Round 3:1 wide overestimates by 0.13 at ratio 0.9 (0.26 vs 0.14 meshed),
  more than 0069's 0.11.  The meshed check catches it either way.

**Follow-ups.**
- Task 0057 (full-width taps) plugs into the `ratio == 1` rejection in
  `Tee._check_duct`.
- Round narrow-face taps warn twice (predicted, then meshed) on similar
  numbers.  A design call: keep both, or let the meshed check replace the
  predicted warning for round taps.
