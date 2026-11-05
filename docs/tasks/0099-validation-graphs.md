# 0099 — Validation results as graphs: convergence, layouts, and the stenosis against DNS

- **Status:** ready (after 0098)
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
