# 0078 — README: generated numbers, validation table, hero image and checks

- **Status:** done (2026-11-07)
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

- **The blocks** are written by `write_readme()` in `build.py`, after
  GALLERY.md on every run.
  - It replaces only the content between each pair of markers, and fails
    if a pair is missing or duplicated.
  - It writes only when the text changes, so a second `--markdown-only`
    prints "README.md unchanged".
  - A check that strips both blocks found the rest of the README
    byte-identical.
- **Metrics:** the hand-written format is kept.
  - The fitting comes from `min_sj_fitting` ("#1 Tee" → "the tee").
  - "one core" means `jobs == 1`, as before.
  - The date is now `metrics.json`'s, 2026-11-05.  The hand line said
    2026-10-30.
  - The cell count uses `fmt_int`, the gallery's narrow no-break space
    (U+202F), where the README had a plain space.  It renders the same.
- **Validation table:** one row per `case.json`, in category order, then
  by task.
  - *Case* is its `title`; *Result* is its `headline`.
  - *Reference* is "kind (Vn), citation".  The kind is the primary
    source's leading word when it is one ("exact", "manufactured", "DNS"),
    otherwise the category's ("simulation", "experiment").  The citation
    comes from `docs/references.bib` by the reference's `key`, or by the
    source's first word when that is a key.
  - *Status* is an icon and the status.
  - The planned tasks (`planned_cases`, as in GALLERY.md) are collapsed
    into one row.
- **The headlines** were checked against each RESULTS.md, the authority.
  `recheck` re-derives the extrapolated values from `results.json`, and
  for the cases it marks "(rounded)" those differ in the last digits.
  The heated pipe's shell ΔTs, for example, are +0.0014 % / −0.0022 %
  there, against −0.0001 % / −0.0008 % in RESULTS.md.
  - Corrected from the hand-written lines:
    - stenosis: "11.12 D vs 11.03 D (+0.9 %)" was k2's τ_w = 0 value.
      The accepted gate is 10.970 D by u(0.48 D) = 0, −0.50 % (k4);
    - heated rod: "within 0.1 %" was the gate.  It is −0.007 % and
      −0.010 %, now "within 0.01 %";
    - Womersley: "≤ 1 %" was the gate.  It is 0.31 % at worst;
    - pulsatile stenosis: "separation and recirculation as in the DNS at
      all six phases" became "the five flow features of its §3.1 as in
      the DNS", which is Gate 2's wording.
  - Kept: Poiseuille, layered conduction and heated pipe (+0.080 %;
    −0.0001 %, −0.0008 %).
  - New: rect_duct, square_bend, turbulent_pipe, mms and helical_pipe.
    `helical_pipe` says "the nang 24 level is running"; update it when
    0075 ends.
- **Hero:** `hero_worker` meshes `insulated_network` and drops every hex
  whose centroid has y < 0 and z > 0.
  - Whole cells, not a VTK clip: in the straights the cut planes are
    mesh planes, and in the junctions real cell faces show.
  - Faces are coloured by material with the gallery's `PALETTE`, as in
    the section images.
  - About 12 s.  A full gallery run renders it; `--hero` renders only it.
- **The README code block test** runs the block with `exec` in a
  `tmp_path`.  The fast test drops the `asm.write…` line.  The slow one
  (`-m slow`) runs the block as written and checks the `.msh`.  Both
  compare it with `insulated_tee.build()`: cell count and fitting types,
  and the count against the metrics table.  The `slow` marker's
  description in `pyproject.toml` now covers both slow tests.
- **Link test:** headings are slugged as GitHub does: lowercase,
  punctuation dropped, spaces to hyphens, `-1` for repeats.
  `<a id=…>` counts too.  Code spans and fences are skipped.  42 links
  are checked (README 23, WHY 7, GUIDE 12); a planted test checks that a
  missing file, image and anchor are each caught.
- **Not touched:** the README's "With an agent" section (the design
  session's, 6712f95).  An earlier version of this note called it empty:
  a misreading of two partial views of the file.  It is complete; its
  numbers are hand-written (task 0110).

## Questions for design

_None._

## Outcome

- **Files:**
  - `docs/gallery/build.py`: the README blocks, the hero, `--hero`;
  - `README.md`: the two blocks regenerated, and the hero as the first
    image;
  - `docs/gallery/img/hero.png` (new, 263 KiB);
  - `validation/case.schema.json` (`headline`) and the 12 `case.json`
    files;
  - `tests/test_readme.py` (new);
  - `hexmesh/__init__.py` (points to `docs/GUIDE.md`);
  - `pyproject.toml` (the `slow` marker's description);
  - `CHANGELOG.md`.
- **Accept:**
  - `build.py --markdown-only` rewrites the two blocks and nothing else;
    a second run prints "README.md unchanged";
  - the hero shows the core, steel and insulation through the tee and
    the right-hand wye leg;
  - `tests/test_readme.py`: 6 passed, plus the slow block test, which
    passed when run with `-m slow` (the whole file in 11 s);
  - full suite (3 workers, beside the 0075 run): 3684 passed, 15
    skipped, 0 failed.  That is 6 more than 0107.
- **Surprises:**
  - the validation table had five cases wrong or missing, and three
    result lines quoted gates or stale values (see *Agent notes*);
  - `recheck`'s values for "(rounded)" cases differ in the last digits
    from RESULTS.md.
- **Proposed follow-ups:**
  - when 0075 finishes, update `helical_pipe`'s `headline` and status,
    then run `build.py --markdown-only`;
  - ~~the README's "With an agent" section is empty~~: wrong, see
    *Agent notes*.
