# 0078 — README: generated numbers, validation table, hero image and checks

- **Status:** ready
- **Decision:** none (documentation).  The layout was agreed with the
  user on 2026-10-31; the README and `docs/WHY.md` were drafted by the
  design session.
- **Depends on:** the gallery (`docs/gallery/build.py`, `metrics.json`,
  `case.json` files).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The README now leads with numbers: cells, quality, build
time, validation results.  Hand-copied numbers drift.  The design
session wrote them by hand from `metrics.json` and the RESULTS files,
between marker comments, so the gallery build can own them.

**Where.**  `docs/gallery/build.py`; `README.md` (only between
`<!-- readme:…:start -->` and `<!-- readme:…:end -->`); `tests/`.

**Do.**
1. **`readme:metrics`.**  The gallery build regenerates the metrics
   table from `metrics.json` for `sections.insulated_tee`:
   - cells predicted = meshed;
   - regions, min scaled Jacobian and the fitting holding it, min SICN;
   - build time;
   - the gmsh version, cores and date line.

   Keep the hand-written format.
2. **`readme:validation`.**  Regenerate the table from the `case.json`
   files and the planned validation tasks:
   - case title, reference with its category, status with icon;
   - a one-line **result**.  Add an optional `headline` field to the
     `case.json` schema (e.g. "reattachment 11.12 D vs 11.03 D
     (+0.9 %)") and backfill it from each RESULTS.md.  The README's
     hand-written lines are the starting values: check each against its
     RESULTS.md and correct it if it is wrong;
   - planned cases collapsed into one row, as now.
3. **`readme:features`:** stays hand-written.  Don't generate it.
4. **Hero image.**  Render `docs/gallery/img/hero.png` from
   `insulated_network` with a **cut-away**:
   - clip away the front quarter so the O-H core, the steel and the
     insulation show through the tee and the wye;
   - material colours as the section images.

   Replace the README's first image with it, keeping the section image
   beside it.  Add it to the gallery build (`--hero`, or always).
5. **Checks** (in the suite):
   - **README code block:** the first `python` block runs in a
     `tmp_path`.  `cell_count()` equals the metrics table's cells, and
     the block builds the same network as
     `hexmesh.examples.sections.insulated_tee` (compare cell counts and
     fitting types).  It writes into `tmp_path`.  Mark it slow if it
     meshes;
   - **links:** every relative link and image in `README.md`,
     `docs/WHY.md` and `docs/GUIDE.md` resolves, anchors included.  The
     design session used a small checker; make it a test.
6. **`hexmesh/__init__.py`** says "See ``README.md`` and ``API.md``".
   Point it to `docs/GUIDE.md` as well.

**Accept.**
- `build.py --markdown-only` rewrites the two generated README blocks
  (and nothing else in the README).  A second run changes nothing.
- The hero image shows the layers through both junctions.
- Link and README-code tests pass; full suite passes.

**Out of scope.**  Licence and citation are settled (2026-11-01, the
user): BSD-3-Clause (`LICENSE`, `pyproject.toml`), and `CITATION.cff`.
If the version changes, bump `CITATION.cff`'s `version` with
`pyproject.toml`'s; a test that they match is welcome.

## Agent notes

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
