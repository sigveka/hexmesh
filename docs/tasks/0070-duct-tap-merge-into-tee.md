# 0070 — Duct taps: the pillowed tap in `Tee`

- **Status:** ready
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
