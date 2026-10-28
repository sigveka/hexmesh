# 0047 — Quality limit for rings with skewed corner lines (aspect-ratio sweep)

- **Status:** done
- **Decision:** [0026 — Layer outlines: shells of any shape](../decisions/0026-layer-outlines.md) (item 4)
- **Depends on:** 0045.  Can run alongside 0046.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Around a square, a ring's corner lines are radial.  Around a
flat rectangle they are skewed: from the circle's 45° corners to
rectangle corners at atan(h/w), and with equal counts on long and short
sides.  Quality falls with aspect ratio.  Decision 0017's approach:
measure, then set a practical limit.

**Where.**  A measurement script (e.g. `benchmarks/outline_quality.py`,
not in the suite); `hexmesh/assembly/limits.py` for the limit;
validation in the spec or assembly; `RESEARCH.md` table via *Outcome*.

**Do.**
1. **Sweep** for each pairing: circle core in a rectangle shell, and a
   rectangle core in a circle shell; aspect ratio w/h ∈ {1, 1.5, 2, 3,
   4, 6}; gap ratio (thinnest ring thickness / inner size) ∈ {0.1, 0.3,
   1}; `nang` ∈ {4, 8}; `nrad` 4.  Through a straight and an easy-way and
   a hard-way bend.
2. **Record** per case: min SICN, min scaled Jacobian, max
   non-orthogonality (from the hex metric in `quality_hex`, or
   `checkMesh` if simpler and available), and where the worst cell is
   (corner line, long side, short side).
3. **Rectangle in rectangle** (`dR` shells): the same table for aspect
   ratios, to confirm it is unaffected (corner lines on the diagonals).
4. **Propose a limit** under *Questions for design*: the aspect ratio
   (and, if it matters, the gap ratio) beyond which min scaled Jacobian
   falls below a value, with the numbers.  Compare with the tee and wye
   minima (DESIGN deviation rows, decision 0017).  Don't tune the
   builder; if an obvious improvement shows (e.g. a different corner-line
   rule), describe it with one measurement.
5. After design answers: put the limit in `limits.py`, check it in
   `validate()` with a message naming the layer, the ratio and the
   limit.

**Accept.**
- The measurement table, reproducible from the script, in *Outcome*.
- A proposed limit with its basis; after the answer, the check in
  `validate()` with a test on each side of the limit.
- Full suite: no new failures.

**Out of scope.**  Changing the ring builder's rule (unless design asks,
after step 4); unequal counts per side.

## Agent notes

- **Script:** `benchmarks/outline_quality.py`.  Run it with
  `PYTHONPATH=. python3 benchmarks/outline_quality.py --md out.md
  --json out.json` (all 324 cases; about 4 min).  Each section runs alone
  through the fitting.  Straight: 2·E long with 2·nang axial cells;
  bends: radius 3·E, 90°, 3·nang cells; easy = roll 0, hard = roll 90.
  Here E is the outer outline's largest extent.  Core and ring `nrad` = 4.
- **Definitions.**  Gap ratio is the thinnest ring thickness divided by
  the inner size.  The inner size is the circle's radius, the
  rectangle's half-diagonal inside a circle, and its half-height inside
  a `dR` rectangle.
- **Non-orthogonality** follows OpenFOAM's construction (face triangle
  fans, pyramid-weighted cell centres).  It matched `checkMesh` v1912 to
  four decimals on two meshes; recorded in
  `docs/integrations/openfoam.md`.  `quality_hex` has no
  non-orthogonality metric.
- **Worst cell:** the cell with the lowest scaled Jacobian.  It is
  "corner line" when it has a node on a ring corner line; otherwise it
  is placed by the ring block it lies in.
- **After the design answer (2026-10-28).**
  - *Benchmark:* the SJ column is now the corner scaled Jacobian
    (`quality_hex`'s Knupp form, vectorised over the hexes in
    `corner_sj`).  gmsh `minSJ` and SICN stay as labelled reference
    columns.  "Worst cell" is now placed by the lowest corner SJ, and a
    cell's layer comes from its physical group.  The benchmark switches
    the new check off (`assembler.check_section_quality`), because it
    measures past the limits.
  - *`section_quality`*, in `hexmesh/assembly/section_quality.py`,
    builds the face's quads as GMSH does:
    - `Bump` / `Progression` node fractions (`bump`, `progression`).
      Tested against GMSH's own 1-D meshes; Bump agrees to about 2e-8,
      because GMSH integrates it numerically.
    - Ring patches as the linear blend of their two boundaries, which is
      exact: their other two sides are straight corner lines.
    - The core's centre patch as a Coons patch on chord-length
      fractions.
    - Non-orthogonality from the quads' centroids and the shared edge's
      normal.  On an orthogonal extrusion this is OpenFOAM's 3-D
      construction exactly.

    A layer's non-orthogonality includes the faces it shares with the
    layer inside it.
  - *"Shells whose two outlines differ in shape"* (`changes_shape`):
    every `outer=` shell, except a circle round a circle.  `dR` shells
    are skipped: their outline is the inner one grown, so their corner
    lines are on the diagonals.  A rectangle round a rectangle of
    another aspect, given by `outer=`, is checked too; its corner lines
    are skewed in the same way.
  - *Check placement:* `validate()`, once per distinct spec (keyed by
    `to_dict()`), next to `check_supported`.  Messages are prefixed with
    the interface.  `Assembly.warnings` is reset on each `validate()`.

## Questions for design

**Q1. Which limit, and on what metric?**  The proposal is to bound the
min scaled Jacobian at 0.3 and the max non-orthogonality at 70°.  70° is
OpenFOAM's "severely non-orthogonal" threshold.  SICN is not usable as
the bound: it falls with cell aspect ratio alone.  It is 0.017 for a
rectangle in a rectangle at gap 0.1, a case that is otherwise the best
of the sweep (SJ 0.89).  For comparison, the minima elsewhere: the wye
prototype reaches min SJ ≈ 0.1 (decision 0017), the tee min SICN
0.16–0.38 (DESIGN), and published bifurcations min SJ ≈ 0.49
(RESEARCH §4.2).

**Proposed limits** (nang 4, the worse case; nang 8 is better
throughout):
- **Circle core in a rectangle shell:** w/h ≤ 2.  Non-orthogonality is
  what binds: 70.1° at w/h 2, gap 0.3; 75° at gap 0.1; 78° at w/h 3.
  SJ alone would allow w/h 3 (0.45 at gap 0.3).  The worst cells are on
  the long side, where the corner lines' skew shears the ring blocks.
- **Rectangle core in a circle shell:** w/h ≤ 1.5 at gap ratio ≥ 0.3,
  and no thin rings (gap < 0.3) at all past w/h 1.  SJ is what binds;
  non-orthogonality stays ≤ 64° everywhere.  SJ is 0.380 at w/h 1.5 /
  gap 0.3, 0.289 at w/h 2 / gap 0.3 (0.403 at nang 8), and 0.211 at
  w/h 1.5 / gap 0.1.  A thin circle round a rectangle is marginal even
  when square: 0.339 at w/h 1, gap 0.1.  The worst cells sit at the
  corner lines, where unequal arcs (53° / 127° at 2:1) with equal
  counts squeeze the cells at the rectangle's corners.
- **Rectangle in a `dR` rectangle:** no limit.  SJ is 0.86–0.92 for every
  aspect ratio and gap, and non-orthogonality stays at the O-H core's
  41.2°.

**Q2. Reject or warn?**  This is DESIGN's open question ("Reject or
degrade?").  The coding session would implement either one: an
`AssemblyError` from `validate()`, or a warning, naming the layer, the
ratio and the limit.

**Possible improvements (not measured; measuring would mean changing
the builder, which is out of scope):**
- Circle in a flat rectangle: corner lines leaving the circle in the
  rectangle's corner directions, atan(h/w), not 45°, would remove the
  skew.  But the core's O-H corners would leave 45°, which conflicts
  with junction corners (DESIGN §7), unless only the ring's inner end
  moves along the arc.
- Rectangle in a circle: ending the corner lines at 45° on the circle
  (equal arcs) instead of radially along the diagonal.

### Design answer (2026-10-28)

**First, a correction: the SJ column measured gmsh's `minSJ`, not
hexmesh's scaled Jacobian.**  `measure()` calls
`getElementQualities(tags, "minSJ")`.  The project's metric is the
corner scaled Jacobian in `hexmesh.quality_hex` (Knupp/Verdict form,
task 0004, RESEARCH §7.1; `check_quality("scaled_jacobian")`).  That is
the metric behind the wye's 0.1 and the published 0.49 the question
compares with.  The two disagree in both directions here: circle in a
3:1 rectangle, gap 0.1, is 0.327 by gmsh but **0.138** by corner SJ;
rectangle in a circle, 2:1, gap 0.3, is 0.307 by gmsh but **0.447**.
gmsh's `minSJ` also penalises taper and thin cells, so it falls with gap
and rises with `nang`.  Corner SJ doesn't: it is set by the corner
angles.

**Re-measured** (design session, 2026-10-28, your script's sections and
fittings, `check_quality("scaled_jacobian").worst`, min over straight /
easy / hard; non-orthogonality from your function).  Corner SJ is the
same at `nang` 4 and 8 to 0.001.

| pairing | w/h | corner SJ, gap 0.1 / 0.3 / 1 | max non-orth (°), gap 0.1 / 0.3 / 1 (nang 8) |
|---|---|---|---|
| circle-in-rect | 1 | 0.706 / 0.707 / 0.707 | 42.1 / 39.3 / 38.0 |
| circle-in-rect | 1.5 | 0.366 / 0.430 / 0.491 | 66.9 / 60.9 / 55.4 |
| circle-in-rect | 2 | 0.238 / 0.299 / 0.365 | 75.1 / 70.1 / 64.5 |
| circle-in-rect | 3 | 0.138 / 0.182 / 0.237 | 81.3 / 77.9 / 73.6 |
| circle-in-rect | 4 | 0.096 / 0.131 / 0.174 | 83.9 / 81.3 / 77.9 |
| circle-in-rect | 6 | 0.060 / 0.083 / 0.114 | 86.2 / 84.5 / 82.1 |
| rect-in-circle | 1 | 0.707 (any gap) | ≤ 41.2 |
| rect-in-circle | 1.5 | 0.554 | ≤ 43.4 |
| rect-in-circle | 2 | 0.447 | ≤ 47.2 |
| rect-in-circle | 3 | 0.316 | ≤ 51.9 |
| rect-in-circle | 4 | 0.242 | ≤ 56.0 |
| rect-in-circle | 6 | 0.164 | ≤ 63.4 |

- **Rectangle in a circle is much better than proposed.**  Its corner SJ
  is exactly `h / d = 1 / √(1 + (w/h)²)`: the sine of the angle between
  a rectangle side and the radial corner line.  It doesn't depend on
  gap or `nang`.  Non-orthogonality stays ≤ 64° even at 6:1.  The thin
  rings that gmsh's metric flagged pass OpenFOAM's checks: `checkMesh`
  v1912 gives max skewness 2.07 (2:1, gap 0.1) and 2.36 (1:1, gap 0.1),
  both "OK".
- **Circle in a rectangle** is about as proposed: both metrics cross
  their limits near w/h 2.
- `checkMesh` v1912 confirms the 70° threshold: it counts faces
  "severely non-orthogonal (> 70 degrees)", but still says "Mesh OK" at
  81.3°.  It fails a mesh only above 90°.

**Q1: limits on two named metrics, checked before GMSH from a predicted
section quality.**
- **Metrics:** OpenFOAM max non-orthogonality (solver-relevant; your
  construction matches `checkMesh` to 0.1°) and hexmesh's corner scaled
  Jacobian.  Not SICN or gmsh `minSJ`: both fall with aspect ratio and
  taper alone, as you found for SICN.
- **Predict, don't tabulate.**  A 2-D model of the ring reproduces the
  measured straight-pipe values: the ring's sides with uniformly spaced
  nodes, straight corner lines, and interior nodes by linear blend (what
  the transfinite fill does).  For an orthogonally extruded straight,
  the hex corner SJ equals the quad's minimum corner sine.
  - Circle in 3:1 rectangle, gap 0.1: 0.138 / 81.4° (measured
    0.138 / 81.3°).
  - Circle in 2:1, gap 0.3: 0.299 / 68.0° (0.299 / 68.1°).
  - Rectangle in 2:1 circle: 0.447 (0.447).

  Bends change these by ≤ 0.02 (your observation; also in the table).
  So the check is a pure-Python **section quality prediction**,
  `section_quality(spec)`, per layer, giving min corner SJ and max
  non-orthogonality.  Limits are then on the metrics, with no
  aspect-ratio tables.  This also works for any future outline (contour
  sections, decision 0018).
- **Values** (in `limits.py`): **warn** when predicted non-orthogonality
  > 70° or corner SJ < 0.3; **reject** when > 80° or < 0.1.
  - 70° is `checkMesh`'s severe threshold.
  - 80° is a practitioners' rule of thumb, not documented: beyond it,
    non-orthogonal correction struggles.
  - 0.3 is about where the proposal put it.
  - 0.1 matches the wye prototype's floor (decision 0017), so this
    doesn't reject what is already accepted elsewhere.
- What these bands mean for the sweep: circle in a rectangle warns from
  about w/h 1.5–2 (gap-dependent) and is rejected from about 3 (gap 0.1)
  or 4 (gap 0.3).  Rectangle in a circle warns past about 3:1 and is
  rejected only past about 10:1.  Rectangle in a `dR` rectangle: never.

**Q2: both, in two tiers.**  Reject below the hard floor
(`AssemblyError` from `validate()`, naming the layer, the metric, the
predicted value and the limit).  Warn in the band between the floor and
the soft limit (`UserWarning`, same content), and record it so callers
can read it.  This answers DESIGN's "Reject or degrade?" for layer
outlines only; applying it to the tee and wye needs their own predicted
or measured values (follow-up).

**Your improvement ideas.**
- *Rectangle in a circle, corner lines ending at 45°:* **don't.**
  Modelled in 2-D, it is much worse: corner SJ 0.05 at 2:1 gap 0.3, and
  folded (negative) at gap 0.1.  The radial rule is right.
- *Circle in a flat rectangle, corner lines starting at the circle node
  nearest the rectangle's corner direction:* this is the real fix, and
  it needs no change to the core.  The ring's long sides then get
  `nang + 2m` cells and the short sides `nang − 2m`.  Modelled at 2:1:
  corner SJ 0.24–0.37 → 0.44–0.48, and non-orthogonality 64–75° →
  56–62°.  At 3:1: SJ about 0.30, non-orthogonality about 70°.
  - It breaks decision 0026's "equal counts per side" for the outer
    outline, and so changes port signatures.  **Not in this task.**
    Design records it as a follow-up option.

**Do now** (replaces step 5):
1. Fix `benchmarks/outline_quality.py` to report the corner SJ
   (`quality_hex`), keeping gmsh `minSJ` as a separate, labelled column,
   and regenerate your table in *Outcome*.
2. `section_quality(spec)`: a pure-Python prediction per layer (core and
   rings) of min corner SJ and max non-orthogonality.  Check it against
   meshed straights for every sweep case: within 0.01 SJ and 1°.
3. The limits in `limits.py` (`OUTLINE_NONORTH_WARN` 70,
   `OUTLINE_NONORTH_MAX` 80, `OUTLINE_SJ_WARN` 0.3, `OUTLINE_SJ_MIN`
   0.1).  `validate()` applies them to every shell whose two outlines
   differ in shape.  Test on each side of both limits.
4. Report what the bands mean for each pairing (the aspect ratios where
   warnings and rejections start), for RESEARCH.

## Outcome

**Files.**
- New: `hexmesh/assembly/section_quality.py`: `section_quality(spec)`,
  `LayerQuality`, `check_section_quality`, `changes_shape`, `bump`,
  `progression`.
- `hexmesh/assembly/limits.py`: `OUTLINE_NONORTH_WARN` 70,
  `OUTLINE_NONORTH_MAX` 80, `OUTLINE_SJ_WARN` 0.3, `OUTLINE_SJ_MIN` 0.1.
- `hexmesh/assembly/assembler.py`: `validate()` applies the limits.
  Past a hard limit it raises `AssemblyError` before GMSH.  In the band
  it issues a `UserWarning` and records it in `Assembly.warnings`.
- `benchmarks/outline_quality.py`: corner SJ; predicted against
  measured, per layer, on straights; `--bands`.
- `tests/test_layer_outlines.py`: `TestSectionQuality` and
  `TestQualityLimits`, 24 tests:
  - GMSH node spacing;
  - predicted against meshed corner SJ on six specs, including graded
    and bumped ones;
  - non-orthogonality against `checkMesh`'s values;
  - each soft limit alone and both together, below and above;
  - both hard limits;
  - shells that are not checked;
  - warnings reset on each `validate()`.
- `docs/integrations/openfoam.md`: the non-orthogonality note (earlier
  work, plus design's thresholds).

**Prediction against the mesh.**  On all 108 straights of the sweep, per
layer, the largest differences are 4e-8 in corner SJ and 1e-5° in
non-orthogonality.  The required tolerance was 0.01 and 1°.  Bends
change min corner SJ by at most 0.0015 and max non-orthogonality by at
most 0.3°, so a straight's prediction stands for the fitting.

**Measurements** (`python3 benchmarks/outline_quality.py --md …`; 324
cases, all meshed = predicted cell count).  Minima and maxima are taken
over straight, easy bend and hard bend.

| pairing | w/h | gap | min corner SJ nang 4 / 8 | max non-orth (°) nang 4 / 8 | min gmsh minSJ | min SICN | worst cell (lowest corner SJ) |
|---|---|---|---|---|---|---|---|
| circle-in-rect | 1 | 0.1 | 0.706 / 0.706 | 41.5 / 42.1 | 0.583 | 0.080 | short side (easy) |
| circle-in-rect | 1 | 0.3 | 0.706 / 0.707 | 36.3 / 39.3 | 0.672 | 0.201 | corner line (easy) |
| circle-in-rect | 1 | 1 | 0.706 / 0.707 | 35.3 / 38.0 | 0.703 | 0.201 | corner line (easy) |
| circle-in-rect | 1.5 | 0.1 | 0.369 / 0.366 | 66.9 / 66.9 | 0.491 | 0.060 | corner line (easy) |
| circle-in-rect | 1.5 | 0.3 | 0.430 / 0.430 | 58.5 / 60.9 | 0.639 | 0.153 | corner line (hard) |
| circle-in-rect | 1.5 | 1 | 0.490 / 0.491 | 52.8 / 55.4 | 0.645 | 0.161 | corner line (easy) |
| circle-in-rect | 2 | 0.1 | 0.238 / 0.238 | 75.1 / 75.1 | 0.416 | 0.048 | long side (easy) |
| circle-in-rect | 2 | 0.3 | 0.298 / 0.299 | 68.1 / 70.1 | 0.562 | 0.121 | corner line (easy) |
| circle-in-rect | 2 | 1 | 0.365 / 0.365 | 62.4 / 64.5 | 0.567 | 0.131 | corner line (easy) |
| circle-in-rect | 3 | 0.1 | 0.137 / 0.138 | 81.3 / 81.3 | 0.319 | 0.033 | corner line (easy) |
| circle-in-rect | 3 | 0.3 | 0.182 / 0.182 | 76.5 / 77.9 | 0.453 | 0.085 | corner line (easy) |
| circle-in-rect | 3 | 1 | 0.237 / 0.237 | 72.1 / 73.6 | 0.456 | 0.094 | corner line (easy) |
| circle-in-rect | 4 | 0.1 | 0.096 / 0.096 | 83.9 / 83.9 | 0.259 | 0.026 | corner line (easy) |
| circle-in-rect | 4 | 0.3 | 0.131 / 0.131 | 80.3 / 81.3 | 0.379 | 0.065 | corner line (easy) |
| circle-in-rect | 4 | 1 | 0.174 / 0.174 | 76.8 / 77.9 | 0.381 | 0.073 | corner line (easy) |
| circle-in-rect | 6 | 0.1 | 0.060 / 0.060 | 86.2 / 86.2 | 0.188 | 0.017 | long side (easy) |
| circle-in-rect | 6 | 0.3 | 0.083 / 0.083 | 83.8 / 84.5 | 0.286 | 0.044 | corner line (easy) |
| circle-in-rect | 6 | 1 | 0.114 / 0.114 | 81.4 / 82.1 | 0.287 | 0.050 | corner line (easy) |
| rect-in-circle | 1 | 0.1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.339 | 0.083 | corner line (easy) |
| rect-in-circle | 1 | 0.3 | 0.706 / 0.707 | 37.0 / 41.2 | 0.533 | 0.220 | core (easy) |
| rect-in-circle | 1 | 1 | 0.706 / 0.707 | 37.0 / 41.2 | 0.627 | 0.214 | core (hard) |
| rect-in-circle | 1.5 | 0.1 | 0.554 / 0.554 | 37.1 / 41.2 | 0.211 | 0.061 | corner line (easy) |
| rect-in-circle | 1.5 | 0.3 | 0.554 / 0.554 | 37.1 / 41.2 | 0.380 | 0.164 | corner line (easy) |
| rect-in-circle | 1.5 | 1 | 0.554 / 0.554 | 37.0 / 43.4 | 0.494 | 0.165 | corner line (easy) |
| rect-in-circle | 2 | 0.1 | 0.446 / 0.447 | 37.1 / 41.2 | 0.148 | 0.047 | corner line (easy) |
| rect-in-circle | 2 | 0.3 | 0.446 / 0.447 | 37.1 / 41.2 | 0.289 | 0.128 | corner line (hard) |
| rect-in-circle | 2 | 1 | 0.446 / 0.447 | 37.0 / 47.2 | 0.401 | 0.132 | corner line (easy) |
| rect-in-circle | 3 | 0.1 | 0.316 / 0.316 | 48.6 / 47.2 | 0.091 | 0.032 | corner line (easy) |
| rect-in-circle | 3 | 0.3 | 0.316 / 0.316 | 47.1 / 44.8 | 0.191 | 0.088 | corner line (easy) |
| rect-in-circle | 3 | 1 | 0.316 / 0.316 | 41.8 / 51.9 | 0.285 | 0.092 | corner line (easy) |
| rect-in-circle | 4 | 0.1 | 0.242 / 0.242 | 56.0 / 54.4 | 0.065 | 0.025 | corner line (easy) |
| rect-in-circle | 4 | 0.3 | 0.242 / 0.242 | 54.2 / 51.8 | 0.142 | 0.067 | corner line (easy) |
| rect-in-circle | 4 | 1 | 0.242 / 0.242 | 48.5 / 54.6 | 0.220 | 0.070 | corner line (easy) |
| rect-in-circle | 6 | 0.1 | 0.164 / 0.164 | 63.4 / 61.8 | 0.041 | 0.016 | corner line (easy) |
| rect-in-circle | 6 | 0.3 | 0.164 / 0.164 | 61.5 / 59.0 | 0.093 | 0.045 | corner line (hard) |
| rect-in-circle | 6 | 1 | 0.164 / 0.164 | 55.3 / 57.6 | 0.150 | 0.047 | corner line (easy) |
| rect-in-rect | 1 | 0.1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.889 | 0.080 | corner line (easy) |
| rect-in-rect | 1 | 0.3 | 0.706 / 0.707 | 37.1 / 41.2 | 0.894 | 0.199 | corner line (easy) |
| rect-in-rect | 1 | 1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.856 | 0.214 | core (easy) |
| rect-in-rect | 1.5 | 0.1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.896 | 0.060 | corner line (hard) |
| rect-in-rect | 1.5 | 0.3 | 0.706 / 0.707 | 37.1 / 41.2 | 0.899 | 0.156 | corner line (hard) |
| rect-in-rect | 1.5 | 1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.860 | 0.179 | core (hard) |
| rect-in-rect | 2 | 0.1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.899 | 0.047 | corner line (hard) |
| rect-in-rect | 2 | 0.3 | 0.706 / 0.707 | 37.1 / 41.2 | 0.900 | 0.127 | corner line (hard) |
| rect-in-rect | 2 | 1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.863 | 0.152 | core (hard) |
| rect-in-rect | 3 | 0.1 | 0.706 / 0.707 | 37.2 / 41.2 | 0.895 | 0.033 | corner line (hard) |
| rect-in-rect | 3 | 0.3 | 0.706 / 0.707 | 37.2 / 41.2 | 0.895 | 0.091 | corner line (easy) |
| rect-in-rect | 3 | 1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.867 | 0.114 | core (easy) |
| rect-in-rect | 4 | 0.1 | 0.706 / 0.707 | 37.2 / 41.2 | 0.893 | 0.025 | corner line (hard) |
| rect-in-rect | 4 | 0.3 | 0.706 / 0.707 | 37.2 / 41.2 | 0.892 | 0.071 | corner line (hard) |
| rect-in-rect | 4 | 1 | 0.706 / 0.707 | 37.1 / 41.2 | 0.871 | 0.090 | core (hard) |
| rect-in-rect | 6 | 0.1 | 0.706 / 0.707 | 38.6 / 41.2 | 0.891 | 0.017 | corner line (hard) |
| rect-in-rect | 6 | 0.3 | 0.706 / 0.707 | 38.6 / 41.2 | 0.890 | 0.049 | corner line (hard) |
| rect-in-rect | 6 | 1 | 0.706 / 0.707 | 38.6 / 41.2 | 0.875 | 0.063 | core (easy) |

- Corner SJ is the same at `nang` 4 and 8 (±0.001), as design found.
  gmsh `minSJ` is the column the earlier table mislabelled "SJ".
- Rectangle in a circle: corner SJ is exactly `1/√(1+(w/h)²)` (0.447 at
  2:1, 0.316 at 3:1), independent of the gap.
- The 0.707 in every rectangle-in-rectangle row, and in the near-square
  rows, is the O-H core's 45° corner, not the ring's.

**Where the limits start** (`--bands`; the w/h at which each limit is
first crossed, to 0.01; "—" means not before w/h 50):

| pairing | gap | nang | SJ warn (< 0.3) | non-orth warn (> 70°) | SJ reject (< 0.1) | non-orth reject (> 80°) |
|---|---|---|---|---|---|---|
| circle-in-rect | 0.1 | 4 | 1.71 | 1.65 | 3.88 | 2.69 |
| circle-in-rect | 0.1 | 8 | 1.71 | 1.65 | 3.88 | 2.68 |
| circle-in-rect | 0.3 | 4 | 2.00 | 2.16 | 5.08 | 3.91 |
| circle-in-rect | 0.3 | 8 | 2.00 | 2.00 | 5.08 | 3.53 |
| circle-in-rect | 1 | 4 | 2.41 | 2.72 | 6.79 | 5.23 |
| circle-in-rect | 1 | 8 | 2.41 | 2.50 | 6.79 | 4.79 |
| rect-in-circle | 0.1 | 4 | 3.18 | 10.78 | 9.95 | — |
| rect-in-circle | 0.1 | 8 | 3.18 | 13.47 | 9.95 | — |
| rect-in-circle | 0.3 | 4 | 3.18 | 14.34 | 9.95 | — |
| rect-in-circle | 0.3 | 8 | 3.18 | 23.97 | 9.95 | — |
| rect-in-circle | 1 | 4 | 3.18 | — | 9.95 | — |
| rect-in-circle | 1 | 8 | 3.18 | — | 9.95 | — |

- **Circle in a rectangle** warns from w/h 1.65–2.7, depending on the
  gap.  Non-orthogonality binds the rejection: from w/h 2.7 (gap 0.1),
  3.5–3.9 (gap 0.3) or 4.8–5.2 (gap 1).  `nang` 8 has slightly worse
  non-orthogonality than 4: its finer cells sit closer to the skewed
  corner lines.
- **Rectangle in a circle** warns from w/h 3.18, where
  `1/√(1+(w/h)²)` = 0.3, at any gap.  SJ binds the rejection, from
  w/h 9.95, where it is 0.1.
- **Rectangle in a `dR` rectangle**: not checked; never near a limit.

**Effect on existing work.**  No example warns or is rejected.  Two
existing tests now warn (circle in a 2.08:1 block, 71.0°) but pass.

**Tests.**  Full suite: 1771 passed, 5 skipped (was 1747; +24).

**Follow-ups (design).**
- The variable-count corner-line fix (design answer; it changes port
  signatures).
- Applying the two-tier rule to the tee and wye (the design answer's
  follow-up).
- RESEARCH: the bands table above, and the exact rectangle-in-circle
  formula.
