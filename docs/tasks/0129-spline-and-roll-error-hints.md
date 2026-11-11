# 0129 — Two error messages that say where and what to do: a spline that bends too tightly, and a roll with no straight to take it

- **Status:** done
- **Decision:** [0042 — The road to 1.0](../decisions/0042-road-to-1-0.md) (every user-facing error coded, with a hint a user can act on; task 0106's rules)
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Building the idealised aorta (task 0121; decision 0048's
context) took about ten trial runs on two errors whose messages said
*that* something was wrong but not *where*, or not *exactly* what to add:

1. **`SplinePipe` too tight** (`hexmesh/assembly/sweep.py`, the
   `bend_radius_below_outer_radius` check): "path bends with radius
   0.01107, tighter than the pipe outer radius 0.01325".  It doesn't say
   where along the spline, and its `where` (`field: radius`) and hint ("a
   bend radius above …") are a `Bend`'s: a spline has no `radius`.
2. **`toward` off the allowed rolls** (`hexmesh/assembly/assembler.py`,
   `toward_off_allowed`): the hint is "add Straight(…, twist=X) before
   the Tee".  The user doesn't know a length that works, and doesn't need
   to give `twist`: an untwisted `Straight` there takes the rest by
   itself (task 0062).

**Where.**  `sweep.py`, `assembler.py`, `errors.py` (only if a code is
added), `API.md` if a field is documented, `tests/`.

**Do.**
1. **The spline's tightest place.**  For a `SplinePipe` (any path whose
   tightness isn't a single `radius` field), the error names:
   - where the tightest radius is: the arc length from the inlet (and as
     a fraction of the length), the point (x, y, z), and the two input
     points it lies between (`points[i]`–`points[i+1]`);
   - `where`: `{"field": "points", "index": i}` (or `end_tangent` if the
     tightness is in the last segment and caused by it: say how that is
     decided);
   - a hint in the spline's terms: "move points[i+1] (or add a point) so
     the path turns over a longer distance; the radius must exceed R".
   The `Bend`/`Elbow` wording stays for fittings with a `radius` field.
   Keep the code; if a separate code reads better, say why under
   *Agent notes* (removing or renaming a code is breaking; adding one
   isn't).
2. **The roll's straight.**  When no untwisted `Straight` ends at the
   junction's inlet, the hint gives a working one: "add
   `Straight(L, n_layers=n)` before the *fitting*; hexmesh twists it by
   X° to reach `toward`", with the shortest L and n that keep that twist
   within the twist limits (decision 0031's 15° warn and 30° max, and any
   per-layer limit), computed from the inlet's spec.  If the rest can't
   be taken by any one straight under the limits, say so and name the
   limit.
3. **Tests:** each message on a small case: a spline with one tight
   segment (the error names its index and arc length); a tee with
   `toward` 1.3° off its roll and no straight before it (the hint's
   `Straight(L, n)`, added as suggested, builds without the error).

**Accept.**
- Both errors name where, and their hints, followed literally, fix the
  case (tests).
- No change to which inputs are accepted or rejected; meshes unchanged.
- Full suite: no new failures.

**Out of scope.**  Inserting the straight automatically, and the
centreline builder (decision 0048, proposed).

## Agent notes

- **Spline (step 1):** a hook `Sweep.tight_spot(a, b, spec, R)` returns
  `(where, hint, text)` or `None`; `Sweep.validate` uses it in the same
  error, same code.  Only `SplinePipe` implements it: the place is the
  sample of largest curvature (as `_min_radius` samples it), its segment
  from the chord-length knots.
  - **The point to move** is the segment's end nearer the tightest
    place, not always `points[i+1]` as the step says: a tight corner at
    an input point (the common case) lies at the start of the segment
    after it, and moving `points[i+1]` there doesn't help (tested: a 90°
    corner at `points[2]` is fixed by moving `points[2]`).  Never
    `points[0]` (the inlet).
  - **`end_tangent` is named** when the tightest place is in the last
    segment, `end_tangent` is given, and the same points with a free end
    (natural spline) have curvature below 1/R over that segment: the
    tangent is then what bends it.
  - **Closure left as is** (its message and `where = {"field": "radius"}`
    unchanged): its curve is set by two interfaces and `tension`, and a
    hint there would need its own wording and a test that it fixes a
    case.  Proposed follow-up.
- **Roll (step 2):** `Straight._shortest_twisted(spec, twist, at_least)`
  (private) gives `(L, n)`: n the fewest layers rolling at most
  `STRAIGHT_TWIST_WARN` each; L the shortest whose twist per length
  passes the wall-shear warn tiers the section itself passes (the rule
  `Straight._twist_quality` applies), rounded up to three figures.
  - **Floor at one outer radius** (my choice; design may want another):
    the shear tiers alone allow a sliver, 0.39 mm for 1.3° on R 0.05
    (10.7° per mm of twist rate passes).  A radius is a short but
    sensible straight; any per-layer limit holds either way.
  - "Can't be taken" happens only if no twist rate passes the tiers on
    the section (rate 0); the hint then says so and names the tiers.
  - `_twist_rate` searches below the probe's own twist per length (right
    for `_twist_quality`, which asks about the straight it has); here the
    probe is 1e-3 R long so the search starts above any passing rate (a
    first draft with a 1 m probe suggested 1 m).

## Questions for design

## Outcome

**Done 2026-11-11.**

- **Spline:** on a 90° corner at `points[2]` (R 0.05): "path bends with
  radius 0.02169, tighter than the pipe outer radius 0.05 at 0.303 along
  it (43% of 0.707), point (0.3001, 4.909e-05, 0), between points[2] and
  points[3]"; `where = {"field": "points", "index": 2}`; hint "move
  points[2] (or add a point between points[2] and points[3]) so the path
  turns over a longer distance; the radius must exceed 0.05".  Moving
  points[2] to (0.27, 0.03) builds (test).  An `end_tangent` across the
  last segment is named instead, and leaving it out builds (test).
- **Roll:** a tee 1.3° off its roll, R 0.1: hint "add Straight(0.1,
  n_layers=1) before the Tee; hexmesh twists it by 1.3° to reach
  toward" (the radius floor); 37°: n_layers 3.  Added as suggested, both
  build with no twist warning (test).
- **Files:** `hexmesh/assembly/sweep.py` (`tight_spot` hook),
  `fittings.py` (`SplinePipe.tight_spot`, `_tightest`,
  `Straight._shortest_twisted`), `_graph.py` (the hint), API.md,
  CHANGELOG, `tests/test_spline.py` (4 new), `tests/test_twist.py`
  (2 new, 2 hint expectations updated).
- **Accepted and rejected inputs unchanged**; no mesh code touched.
- **Tests:** full suite 4086 passed, 15 skipped, 1 xfailed (4080 + 6).
- **For design:** the one-radius floor on the suggested length (*Agent
  notes*); `Closure`'s message, still a `Bend`'s (proposed follow-up).
