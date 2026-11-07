# 0099 — Validation results as graphs: convergence, layouts, and the stenosis against DNS

- **Status:** done (2026-11-07)
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); [0015](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) (what a series shows); [0036](../decisions/0036-cartesian-rectangular-section.md) (the H section's evidence)
- **Depends on:** 0098, which edits `validation/tools/` and the
  `poiseuille` and `rect_duct` `results.json` files.  Start after its
  commits.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user asked whether the validation results can be shown as
graphs.  Every case's results are numbers in `RESULTS.md` tables and
`results.json` (task 0093).  The only images are mesh renders
(`validation/<case>/img/`).  The data is enough for proper graphs:

- per-level errors and cell counts in all eight cases;
- 30 `rect_duct` levels over four layouts (H, graded H, O-H, the
  Cartesian control) and three aspect ratios;
- a 284-point centreline per `stenosis` level, with the DNS reference
  stations and the reattachment length;
- per-level peaks against DNS in `stenosis_pulsatile`, and amplitude
  and phase errors in `womersley`;
- uniform and graded `heated_rod` series (10 levels).

The gallery already shows `validation/<case>/figure.png` when it exists
(`docs/gallery/build.py:622`).

**Where.**  New `validation/tools/plots.py`; each case's `figure.png`
and `img/*.png`; the cases' `RESULTS.md`; `tests/test_validation_meta.py`;
`validation/README.md`.

**Do.**
1. **`validation/tools/plots.py`:** one module, with functions shared
   by every case, reading only `results.json` (and `case.json` for
   titles and gates).
   - `python3 -m validation.tools.plots [case …]`, or all cases when no
     case is given.
   - It needs no OpenFOAM and no GMSH: plots come from the stored
     numbers only.
   - matplotlib with the `Figure` and Agg API, as task 0097's
     `preview` does: no `pyplot` global state.  matplotlib comes from
     the existing `preview` / `dev` extras.
2. **The graphs.**
   1. **Convergence, every case**, in `figure.png` (the gallery's
      slot):
      - |error| of each gated quantity against the representative cell
        size h = (V/N)^(1/3), or cells^(−1/3), on log–log axes;
      - reference slopes of order 1 and 2 through the finest point;
      - the gate's tolerance as a horizontal band where it is a
        percentage;
      - the observed order and the Richardson status (task 0089) in
        the legend.
   2. **`rect_duct`, the layouts** (`img/layouts.png`): f·Re error
      against cells for H, graded H, O-H and the Cartesian control.
      One panel per aspect ratio (1, 2, 4), on shared axes.  It shows
      decision 0036's finding: O-H converges irregularly, while H and
      the control fall on the same second-order line.
   3. **`stenosis`, against DNS** (`img/centreline.png`): the
      centreline velocity along x for each level, with the DNS
      reference stations as markers.  Mark the throat, and the
      reattachment length per level against the reference's.
   4. **`stenosis_pulsatile` and `womersley`** (`img/periodic.png`):
      the throat peak (pulsatile) and the pressure-gradient amplitude
      and phase (Womersley) per level, against the reference values.
   5. **`heated_rod`** (`img/series.png`): the uniform and graded
      series on one convergence plot.
   - Where a quantity's stored data doesn't support a graph as
     described, note it under *Agent notes* and skip that graph.  Don't
     add data to `results.json` in this task.
3. **Style, for every graph:**
   - a colour-blind-safe palette (Okabe–Ito), with a different marker
     per series as well as colour;
   - axis labels with units, a title from `case.json`, and the gate in
     the caption;
   - one size (e.g. 1600 × 1000 px at 200 dpi) and a white background;
   - the same series in the same colour in every case (for example H
     always the same colour);
   - each PNG under 250 kB.
4. **Deterministic, and staleness checked.**
   - The PNG metadata holds no software or time chunk (`metadata=` as
     in 0097).  Instead it holds a `source-sha256` text chunk: the
     hash of the `results.json` it was drawn from.
   - A meta test reads each committed figure's `source-sha256` and
     compares it with the current `results.json`.  A stale figure
     fails with the command to regenerate it.
   - Bytes aren't compared across machines, since matplotlib's output
     differs between versions.  The figures are regenerated and
     committed on Linux.
5. **`RESULTS.md`:** each case embeds its graphs under a short
   "Graphs" heading, between `<!-- graphs:start -->` and
   `<!-- graphs:end -->` markers, which the module rewrites, as the
   gallery does for the mesh section.  Add a one-sentence caption per
   graph saying what it shows.
6. **Rebuild the gallery's validation section** (`docs/gallery/build.py
   --markdown-only`), so it shows the new `figure.png` files.
7. **`validation/README.md`:** a line on how to regenerate the graphs.

**Accept.**
- Every accepted case has `figure.png`, and the four extra graphs exist
  (or are noted as unsupported).
- Two runs on one machine give byte-identical PNGs.
- The staleness test passes, and fails on a planted change to one
  `results.json`.
- The gallery and `RESULTS.md` show the graphs.
- No `results.json` or `case.json` changes; no gate or recheck result
  changes.
- Full suite: no new failures.
- *Outcome*: the list of graphs, their sizes, and anything the data
  couldn't show.

**Out of scope.**
- Pictures of the flow fields (contours, streamlines).  The runs were
  deleted (CLAUDE.md, disk rule), so they need reruns.  Add them case by
  case when a case is rerun anyway, as a small PNG rendered with VTK.
- Interactive plots.

## Agent notes

- **The x-axis is h/h₁ = 1/k, not N^(−1/3).**  `layered_conduction`
  doesn't refine axially: its cells grow 4×, not 8×, per halving of h.
  So N^(−1/3) gave it an apparent order of 3.02 where the recheck says
  2.01.  `plots._h` takes h from each level's `k` or `factor`, or from
  its `nang` (helical_pipe).  The Richardson ratios come from the same
  h, so every legend order equals the recheck's (checked case by case).
- **Cases with no exact solution** plot a distance:
  - `square_bend`: from the stored extrapolated value (its gate is the
    Richardson status);
  - `turbulent_pipe`: f and U_c/U_b from their extrapolated values,
    and f from McKeon;
  - `stenosis`, `stenosis_pulsatile`, `helical_pipe`: from the
    DNS or the correlation, without reference slopes, since the error
    has a floor there, not an order.
  The legend's Richardson status is then of the values themselves, as
  in the recheck.
- **Gate bands:** where a gate is on the extrapolated value, not on a
  level, the band says so ("gate tolerance, on the extrapolated
  value").  Levels above it don't fail.
- **`periodic.png` lives in `stenosis_pulsatile/img/`** and is embedded
  in both RESULTS.md files.  It draws on two results files, so each PNG
  records a `sources` chunk (the case names) next to `source-sha256`,
  the hash over those files in order.  The staleness test reads both.
- **`heated_rod`:** `figure.png` already holds the gated ΔT₀ for both
  series on one plot.  So `img/series.png` holds the field's L2 and
  maximum errors per series (reported, not gated), rather than a
  duplicate.
- **`layered_conduction`:** only the fixed-wall variant is drawn; the
  convection variant's numbers lie on the same lines (caption).
  `mms`: 16 fittings, more than the six colours, so four panels of four
  (straight runs, size and shape changes, tees and taps, wyes).  The
  duct taps' k = 4 levels didn't converge and are left out, as in the
  recheck.
- **Not drawn:** the time-step levels (`womersley` k2-dt2,
  `stenosis_pulsatile` k2-co0.25) and `square_bend`'s rig inlet.  The
  gapwise peak positions aren't drawn either; they are a categorical
  match, already in the table.  `helical_pipe` is in progress: its
  figure has nang 8, 12 and 16 and goes stale when nang 24 lands.
- **PNGs are 256-colour** (Pillow median cut, no dither): 35–83 kB
  against 100–260 kB as RGB, where `mms` exceeded 250 kB.  matplotlib
  draws, and Pillow writes, so the only chunks are IHDR, pHYs, tEXt
  (`sources`, `source-sha256`), IDAT and IEND.
- **Palette:** Okabe–Ito without yellow, which is too faint on white;
  black is the reference.  H is always blue and the Cartesian control
  orange (open markers, since it coincides with H); O-H is vermilion,
  graded and graded H sky blue.  The palette validator passes CVD
  separation (worst adjacent ΔE 9.6).  Contrast against white is below
  3:1 for orange, purple and sky blue, so every series also has its own
  marker and a legend entry.
- **`validation/README.md` didn't exist**; it is new, with the recheck
  and plots commands.

## Outcome

**Done.**

**Graphs (16):**

| File | Size |
|---|---|
| `figure.png` for all 12 cases (10 accepted, plus `mms` and `helical_pipe` in progress) | 35–83 kB |
| `rect_duct/img/layouts.png` | 55 kB |
| `stenosis/img/centreline.png` | 49 kB |
| `stenosis_pulsatile/img/periodic.png` (also in `womersley`'s RESULTS.md) | 51 kB |
| `heated_rod/img/series.png` | 49 kB |

**Files:**
- `validation/tools/plots.py` (new);
- the PNGs above;
- the 12 `RESULTS.md` files: a "Graphs" section before the first `##`
  heading, between markers;
- `validation/README.md` (new);
- `docs/GALLERY.md` (`--markdown-only`: the 12 `figure.png` lines);
- `tests/test_validation_meta.py`: +19 tests (16 graphs current, small
  and embedded; coverage; a planted change makes a graph stale with the
  command; determinism).

**Acceptance:**
- Two runs of `python3 -m validation.tools.plots` give byte-identical
  PNGs (sha256 of all 16).
- The staleness test passes, and fails on a planted change to
  `poiseuille/results.json`.
- No `results.json` or `case.json` changes, and the recheck is
  unchanged.

**Suite:** 3582 passed, 15 skipped, no failures.

**What the data couldn't show:** nothing asked for was missing.  The
graphs that wanted the time-step levels, the rig inlet or the gapwise
positions weren't asked for and weren't drawn.

**Surprises:** N^(−1/3) misstates h for cases that don't refine axially
(see the notes); hence the relative h.

**Follow-ups (proposed):** regenerate `helical_pipe`'s figure after the
nang 24 run, which the staleness test enforces.
