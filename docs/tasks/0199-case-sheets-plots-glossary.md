# 0199 — Case sheets, standard plots, a glossary and a scorecard for every validation case

- **Status:** ready
- **Decision:** [0060](../decisions/0060-validation-readable-and-solver-neutral.md)
  points 1 and 2
- **Depends on:** none: it works from the stored `results.json`.  The flow
  pictures need fields, so they come where a level runs (0198's
  `extract`, or a run already planned).
- **Blocks:** none.  Before 1.0.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-28): validation should be "easy to understand
for humans (both the code, setup and results)", and asked for more
visualisation.

**Do.**
1. **The glossary** (`validation/GLOSSARY.md`, and on the docs site), in
   plain words, a short paragraph each, with a small picture where it
   helps:
   - gate; V1–V4; a miss;
   - level and `refined(k)`; the fixed-wall family;
   - observed order; Richardson extrapolation; GCI; oscillatory
     convergence;
   - y⁺ and wall functions;
   - steady plateau against time mean; flow-through;
   - export check.
2. **The standard plots** (`validation/tools/plots.py`, one style), from
   `results.json`:
   - **result against reference,** with the gate band shaded and the
     verdict in the title;
   - **convergence:** each gated quantity against h (cells^(-1/3)),
     with the extrapolated value and its GCI band.  An oscillatory
     series is drawn as such, with its range;
   - **time history** where a level stores one (the bend's and the tee's
     transients), with the averaging window and the stop;
   - SVG for the sheet, PNG for the gallery.
3. **The case sheet**, generated (`python3 -m validation sheet <case>`)
   into the top of each case's README, between markers, so the
   hand-written method stays below.  Every case has the same layout:
   - the question in one sentence;
   - a dimensioned sketch of the geometry (from the assembly: lengths,
     D, radii, as a simple 2-D drawing);
   - the mesh picture with its named groups coloured (the gallery's
     renderer);
   - the boundary conditions in physical words, one line per group;
   - the reference, with its citation;
   - the gates;
   - the verdict;
   - the plots from step 2;
   - links to the glossary and to `RESULTS.md`.
   Write a one-sentence question and the boundary-condition lines for
   each case in its `case.json` (new fields, schema updated), so the
   sheet is data, not prose in the generator.
4. **The flow pictures:** for the bend, the tee, the helical pipe, the
   square bend and the stenosis.  Use a slice from the finest level that
   runs next anyway (0186's level 2, 0197's levels), or the cheapest
   level that shows the feature, if it runs in under an hour.  Render it
   offscreen in a pinned container (pyvista or ParaView), never as a
   hexmesh dependency.  List which cases got one and which wait.
5. **The scorecard** on the Validation page and the docs site: every case
   × verdict, and each gate's margin as a bar (how far inside or outside
   the band).  Export checks in their own table (decision 0057).
6. **Check for a newcomer:** have someone, or a fresh agent session with
   only the sheet, answer "what does this case test, and did it pass,
   and how sure are we?" for three cases.  Record the answers and fix
   what they got wrong.
7. Tests: every case's sheet generates; each plot is written for a case
   that has the data; `case.json`'s new fields are in the schema.
   CHANGELOG.

**Accept.**
- Every case has a sheet with its plots.
- The glossary is on the site.
- The scorecard shows every case.
- The newcomer check is recorded.
- Flow pictures listed (done or waiting, with the run they wait for).

## Agent notes

## Questions for design

## Outcome
