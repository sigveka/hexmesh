# 0129 — Two error messages that say where and what to do: a spline that bends too tightly, and a roll with no straight to take it

- **Status:** ready
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

## Questions for design

## Outcome
