# 0047 — Quality limit for rings with skewed corner lines (aspect-ratio sweep)

- **Status:** blocked (limit proposed; see Questions for design)
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

_Partial: steps 1–4 done; step 5 waits for the answers above._

**Measurements.**  324 cases: 3 pairings × w/h {1, 1.5, 2, 3, 4, 6} ×
gap {0.1, 0.3, 1} × nang {4, 8} × straight / easy / hard.  All are
all-hex with meshed = predicted.  The table shows, per pairing, aspect
ratio and gap, the minima over the three fittings (SJ split by nang) and
the maximum non-orthogonality.  The script (`--md`) writes every case
as its own row.

| pairing | w/h | gap | min SJ nang 4 / 8 | min SICN | max non-orth (°) | worst cell (lowest SJ) |
|---|---|---|---|---|---|---|
| circle-in-rect | 1 | 0.1 | 0.583 / 0.742 | 0.080 | 42.1 | corner line (easy) |
| circle-in-rect | 1 | 0.3 | 0.672 / 0.807 | 0.201 | 39.3 | corner line (hard) |
| circle-in-rect | 1 | 1 | 0.703 / 0.786 | 0.201 | 38.0 | corner line (hard) |
| circle-in-rect | 1.5 | 0.1 | 0.491 / 0.704 | 0.060 | 66.9 | long side (hard) |
| circle-in-rect | 1.5 | 0.3 | 0.639 / 0.748 | 0.153 | 60.9 | long side (hard) |
| circle-in-rect | 1.5 | 1 | 0.645 / 0.702 | 0.161 | 55.4 | long side (hard) |
| circle-in-rect | 2 | 0.1 | 0.416 / 0.657 | 0.048 | 75.1 | long side (hard) |
| circle-in-rect | 2 | 0.3 | 0.562 / 0.704 | 0.121 | 70.1 | long side (hard) |
| circle-in-rect | 2 | 1 | 0.567 / 0.632 | 0.131 | 64.5 | long side (hard) |
| circle-in-rect | 3 | 0.1 | 0.319 / 0.545 | 0.033 | 81.3 | long side (hard) |
| circle-in-rect | 3 | 0.3 | 0.453 / 0.595 | 0.085 | 77.9 | long side (hard) |
| circle-in-rect | 3 | 1 | 0.456 / 0.519 | 0.094 | 73.6 | long side (hard) |
| circle-in-rect | 4 | 0.1 | 0.259 / 0.466 | 0.026 | 83.9 | long side (hard) |
| circle-in-rect | 4 | 0.3 | 0.379 / 0.515 | 0.065 | 81.3 | long side (hard) |
| circle-in-rect | 4 | 1 | 0.381 / 0.440 | 0.073 | 77.9 | long side (hard) |
| circle-in-rect | 6 | 0.1 | 0.188 / 0.361 | 0.017 | 86.2 | long side (hard) |
| circle-in-rect | 6 | 0.3 | 0.286 / 0.406 | 0.044 | 84.5 | long side (hard) |
| circle-in-rect | 6 | 1 | 0.287 / 0.337 | 0.050 | 82.1 | long side (hard) |
| rect-in-circle | 1 | 0.1 | 0.339 / 0.472 | 0.083 | 41.2 | corner line (easy) |
| rect-in-circle | 1 | 0.3 | 0.533 / 0.650 | 0.220 | 41.2 | corner line (easy) |
| rect-in-circle | 1 | 1 | 0.627 / 0.683 | 0.214 | 41.2 | corner line (hard) |
| rect-in-circle | 1.5 | 0.1 | 0.211 / 0.321 | 0.061 | 41.2 | corner line (hard) |
| rect-in-circle | 1.5 | 0.3 | 0.380 / 0.503 | 0.164 | 41.2 | corner line (hard) |
| rect-in-circle | 1.5 | 1 | 0.494 / 0.568 | 0.165 | 43.4 | corner line (hard) |
| rect-in-circle | 2 | 0.1 | 0.148 / 0.237 | 0.047 | 41.2 | corner line (hard) |
| rect-in-circle | 2 | 0.3 | 0.289 / 0.403 | 0.128 | 41.2 | corner line (hard) |
| rect-in-circle | 2 | 1 | 0.401 / 0.478 | 0.132 | 47.2 | corner line (hard) |
| rect-in-circle | 3 | 0.1 | 0.091 / 0.154 | 0.032 | 48.6 | corner line (hard) |
| rect-in-circle | 3 | 0.3 | 0.191 / 0.284 | 0.088 | 47.1 | corner line (hard) |
| rect-in-circle | 3 | 1 | 0.285 / 0.357 | 0.092 | 51.9 | corner line (hard) |
| rect-in-circle | 4 | 0.1 | 0.065 / 0.113 | 0.025 | 56.0 | corner line (hard) |
| rect-in-circle | 4 | 0.3 | 0.142 / 0.217 | 0.067 | 54.2 | corner line (hard) |
| rect-in-circle | 4 | 1 | 0.220 / 0.282 | 0.070 | 54.6 | corner line (hard) |
| rect-in-circle | 6 | 0.1 | 0.041 / 0.073 | 0.016 | 63.4 | corner line (hard) |
| rect-in-circle | 6 | 0.3 | 0.093 / 0.148 | 0.045 | 61.5 | corner line (hard) |
| rect-in-circle | 6 | 1 | 0.150 / 0.198 | 0.047 | 57.6 | corner line (hard) |
| rect-in-rect | 1 | 0.1 | 0.889 / 0.902 | 0.080 | 41.2 | core (hard) |
| rect-in-rect | 1 | 0.3 | 0.894 / 0.905 | 0.199 | 41.2 | core (easy) |
| rect-in-rect | 1 | 1 | 0.856 / 0.867 | 0.214 | 41.2 | corner line (easy) |
| rect-in-rect | 1.5 | 0.1 | 0.896 / 0.906 | 0.060 | 41.2 | core (easy) |
| rect-in-rect | 1.5 | 0.3 | 0.899 / 0.908 | 0.156 | 41.2 | core (easy) |
| rect-in-rect | 1.5 | 1 | 0.860 / 0.869 | 0.179 | 41.2 | corner line (easy) |
| rect-in-rect | 2 | 0.1 | 0.899 / 0.909 | 0.047 | 41.2 | core (hard) |
| rect-in-rect | 2 | 0.3 | 0.900 / 0.910 | 0.127 | 41.2 | corner line (hard) |
| rect-in-rect | 2 | 1 | 0.863 / 0.871 | 0.152 | 41.2 | corner line (easy) |
| rect-in-rect | 3 | 0.1 | 0.895 / 0.913 | 0.033 | 41.2 | core (hard) |
| rect-in-rect | 3 | 0.3 | 0.895 / 0.913 | 0.091 | 41.2 | corner line (hard) |
| rect-in-rect | 3 | 1 | 0.867 / 0.874 | 0.114 | 41.2 | corner line (easy) |
| rect-in-rect | 4 | 0.1 | 0.893 / 0.915 | 0.025 | 41.2 | core (hard) |
| rect-in-rect | 4 | 0.3 | 0.892 / 0.915 | 0.071 | 41.2 | corner line (hard) |
| rect-in-rect | 4 | 1 | 0.871 / 0.877 | 0.090 | 41.2 | corner line (easy) |
| rect-in-rect | 6 | 0.1 | 0.891 / 0.917 | 0.017 | 41.2 | corner line (hard) |
| rect-in-rect | 6 | 0.3 | 0.890 / 0.918 | 0.049 | 41.2 | corner line (hard) |
| rect-in-rect | 6 | 1 | 0.875 / 0.880 | 0.063 | 41.2 | corner line (easy) |

**Observations.**
- Easy versus hard bend changes min SJ by at most 0.02; the hard way is
  usually the worse.  The section decides quality, not the bend.
- nang 8 raises min SJ by 0.05–0.2.  Gap matters most for a rectangle
  in a circle, and for a circle in a rectangle only below gap 0.3.
- Max non-orthogonality of 41.2° in every rectangle-in-rectangle case is
  the O-H core's, not the ring's.

**Files.**  `benchmarks/outline_quality.py` (new);
`docs/integrations/openfoam.md` (non-orthogonality reproduction;
`checkMesh` needs fvSchemes and fvSolution).  No code under `hexmesh/`
changed, so the full suite was not rerun.
