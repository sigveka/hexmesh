# 0004 — Quality report per fitting, with hex metrics

- **Status:** done
- **Decision:** [0001 — Complete A5/A7 in the assembly prototype](../decisions/0001-complete-assembly-prototype.md)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  `Assembly.check_quality` (`assembler.py:329`) groups results by
**material** and uses only gmsh SICN.  DESIGN wants failures that name the
fitting.  `hexmesh/quality_hex.py` already has Verdict-style hex metrics,
but only the legacy `network.py:874` uses them.

**Do.**
1. Record volume tags **per fitting**: in `Assembly.fill`, keep each
   edge's `FillResult` (or its `volumes`) keyed by `edge.index` before
   merging.
2. Extend `check_quality(by="fitting" | "material")`.  The default stays
   "material", for backward compatibility.
3. Allow metrics from `quality_hex` as well as gmsh quality names.  Add
   **scaled Jacobian** (Knupp: minimum over the 8 corners of
   det(J)/(|e1||e2||e3|)) and **NES** (max of
   `(θmax−90)/90`, `(90−θmin)/90` over face angles); neither is in
   `quality_hex.py` yet (it has mean ratio, shape regularity and face
   metrics).  `BlockLayout.corner_jacobians()` already computes the
   scaled Jacobian per block corner before GMSH; reuse the formula.  These are the metrics used in `docs/RESEARCH.md` §4.2 and §7.1.
4. Report rows show the fitting index, type name and the worst value.

**Accept.**
- Unit tests for scaled Jacobian and NES: a unit cube gives 1 and 0; a
  sheared hex gives known values.
- An assembly with a `Tee` produces one report row per fitting, and the
  tee row is the worst.

## Agent notes

- **Metrics** (`quality_hex.py`):
  - `corner_scaled_jacobians` / `scaled_jacobian`: the task's 8-corner
    Knupp form.  Verdict's hex scaled Jacobian also includes the
    Jacobian at the element centre, so it can be lower on tapered cells;
    this is documented in the function.
  - `face_angles` / `nes`: over the 24 face angles, with θe = 90°, which
    is GAMBIT's EquiAngle skewness as in RESEARCH §4.2 and §7.2.
  - Both are added to `all_metrics`.
  - `BlockLayout.corner_jacobians` now calls `corner_scaled_jacobians`
    (one formula; the block `_IDX` table is gone).
- **Direction-aware reports.**  `quality_hex.METRICS` maps each metric to
  its function, direction and default "bad" limit (scaled Jacobian ≤ 0;
  NES ≥ 1; skewness ≥ 1; the unbounded lower-is-better metrics ∞).
  `RegionQuality` and `QualityReport` gained `higher_is_better`,
  `worst` / `best`, `worst_region` and `fitting`.  `min_quality` is kept,
  and the table prints `worst` / `best`.  `threshold=None` means the
  metric's default (0 for GMSH qualities, as before).
- **Per-fitting volumes.**  `Assembly.fill` keeps each edge's volumes
  (`fitting_volumes()`, edge index → tags) before merging.
- **Vertices** come from `quality_hex.hex_vertices(volumes)`, one node
  lookup and an (N, 8, 3) array; metrics are evaluated per element in
  Python, a few seconds for 10⁴ cells.
- **SICN vs shape metrics (finding).**  On Straight → Tee → (Bend, branch
  Straight), **SICN** ranks the branch `Straight` worst (0.149 against the
  tee's 0.189), because its cells are long against the 60 mm branch
  section; SICN penalises aspect ratio.  **Scaled Jacobian and NES**
  rank the tee worst (0.316 / 0.706 against 0.79 / 0.42), and score a
  stretched box as ideal.  So the accept test "the tee row is the worst"
  holds for the shape metrics, and the test uses those.

## Questions for design

1. **Which metric gates a fitting?**  Every fitting except the tee
   and the miter scores about the same, set by the OH cross-section itself
   (NES 0.417, an inner-square face angle of about 127.5°; scaled Jacobian
   0.79 at `nang = 6`).  Against the RESEARCH §4.2 targets (scaled Jacobian
   > 0.6, NES < 0.5):
   - the **tee fails both** (0.316, 0.706);
   - a **single 90° miter** is at the edge (0.531, 0.503).

   Should the conformance kit or `validate` enforce per-fitting limits
   (RESEARCH §7.1, "set limits per fitting")?  Which metric: SICN, which
   is aspect-sensitive, or the shape metrics?  Not blocking.

## Outcome

- **Files:**
  - `quality_hex.py`: `corner_scaled_jacobians`, `scaled_jacobian`,
    `face_angles`, `nes`, `Metric`, `METRICS`, `hex_vertices`, and the
    two new keys in `all_metrics`;
  - `assembly/quality.py`;
  - `assembly/assembler.py`: `fitting_volumes`, and `check_quality` with
    `by=` and the hex metrics;
  - `assembly/blocks.py`: `corner_jacobians`, reused;
  - tests: new `tests/test_quality_report.py` (13 tests), plus the
    updated key set in `tests/test_quality_hex.py`;
  - docs: `README.md`, `API.md`.
- **Unit checks:**
  - unit cube and stretched box: scaled Jacobian 1, NES 0;
  - shear by φ: scaled Jacobian cos φ, NES φ/90°;
  - folded corner: negative.
- **Per-example worst cell**:

  | Example | Scaled Jacobian (fitting) | NES (fitting) |
  |---|---|---|
  | smooth_bend | 0.792 (Bend) | 0.417 (Bend) |
  | miter_bend | 0.531 (MiterBend) | 0.503 (MiterBend) |
  | insulated_pipe | 0.792 (Elbow) | 0.417 (Elbow) |
  | reducer_network | 0.788 (Reducer) | 0.417 (Bend) |
  | tee | 0.316 (Tee) | 0.706 (Tee) |
  | loop | 0.790 (Bend) | 0.417 (Bend) |
  | spline_pipe | 0.792 (SplinePipe) | 0.417 (SplinePipe) |
  | pipe_network | 0.316 (Tee) | 0.706 (Tee) |

- **Tests:** 386 passed, 0 failed.
