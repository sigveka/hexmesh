# 0192 — An animated hero for 1.0: a hot front through the insulated network, in two versions for the user to pick

- **Status:** done (2026-11-24)
- **Decision:** none needed (gallery and README only; no API).
- **Depends on:** none.  It shares the machine with 0186: run its solve
  when 0186's runs aren't using the CPU.
- **Blocks:** none.  It ships with the 1.0 release but doesn't hold it.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-23) wants the README's hero image to
celebrate 1.0 with a simulation on top of it, and asked for two versions
to choose from:
- **B:** a hot front through all three layers of the hero network;
- **C:** the same, opening on today's mesh image, which fades into the
  temperature field.
The hero is `sections.insulated_network`: fluid, steel and insulation
through a tee and a wye, conformal hexes.  A conjugate heat transfer run
shows what only a layered conformal mesh gives.  `validation/heated_pipe`
already drives `chtMultiRegionFoam` on layered pipes.

**Do.**
1. **The run** (an illustration, not a validation case):
   - **Mesh:** the hero network as `build()` gives it.  If the cell
     count makes the run long, use the coarsest density that still
     looks like today's hero, and say which.
   - **Physics:** laminar water-like fluid at Re of a few hundred
     (pick one; it goes in the caption), with steel and insulation as
     solids, and `chtMultiRegionFoam` as in `heated_pipe`.
   - **Start:** everything cold, then a hot step at the inlet.
   - **Outer surface:** a convective loss to cold ambient, so the
     insulation's job shows.  Outlets: zero gradient.
   - **Two time scales:** the front advects in seconds, and the heat
     soaks into the steel and insulation much more slowly.  Write
     fields often during the front, then sparsely (log-spaced) for the
     soak, so both phases get frames.
   - **Check:** before the long run, check memory and the other
     session's runs (CLAUDE.md), and get the user's go-ahead.  Record
     `wall_s` and peak memory.
2. **Rendering**, in `docs/gallery/build.py` beside `hero_worker`:
   - the same camera, size and quarter cut-away as `hero.png`, so the
     static image and the animation line up;
   - temperature on the cut faces and the outer surfaces, in a
     perceptually uniform sequential colour map, with a small colour
     bar and a clock (the simulated time, in s);
   - the mesh edges kept faintly visible over the field, so the cells
     still show;
   - about 60–80 frames: roughly two thirds on the front and one third
     on the soak, with a short hold on the last frame.
3. **Two versions:**
   - **B:** the field animation alone;
   - **C:** about 1–1.5 s of today's mesh image, a crossfade from the
     material colours into the field at t = 0, then B.
   Write both as animated WebP (GitHub's README plays it, without
   GIF's banding on gradients), each under about 3 MB at the hero's
   width.  If WebP is over budget, drop frames before colours.
4. **For the user to pick:**
   - render both into the session's scratchpad, not the repository;
   - give the user the two file paths, plus a still of each at the
     front's midpoint;
   - commit nothing visual until they choose.
5. **After the pick:**
   - **in the repository:** the chosen file as
     `docs/gallery/img/hero.webp`, and `build.py --hero-anim` rendering
     it from the stored frames' source;
   - **the run's script** goes in `docs/gallery/hero_run.py` (or a
     subcommand), so the animation can be rebuilt.  Store only small
     inputs, not the OpenFOAM case.
   - **README:** the hero shows the animation, with alt text saying
     what it is: laminar, Re, an illustration, the time span.
     `hero.png` stays as the fallback (PyPI, the wheel's description,
     and places that don't animate).
   - **Disk:** delete the OpenFOAM case and the frames by exact path
     (CLAUDE.md: disk is limited).
6. **Tests:** the README's image links resolve, and `build.py
   --hero-anim` without a stored run says what to run first.  No
   OpenFOAM in CI.
7. CHANGELOG *Unreleased* (Docs): one line.

**Accept.**
- Both versions delivered to the user, with stills.
- After the pick: one animated hero in the README under 3 MB, the
  static fallback kept, the run reproducible from the repository, and
  the case deleted.

**Out of scope.**  Turbulence; a validation claim; video formats
(GitHub doesn't autoplay them from a repository).

## Agent notes

- 2026-11-23/24, the run (`docs/gallery/hero_run.py`): `insulated_network`
  as the gallery builds it, 18012 cells (min scaled Jacobian 0.156);
  `chtMultiRegionFoam` (v2406, Docker, 1 process), laminar, Re 300 in the
  header (1.5 mm/s), water in, steel k 50, insulation k 0.04, outer loss
  h 10 W/m²K to 20 °C; 80 °C at the inlet from t = 0.  Fixed Δt 2 s.
  Two phases: the front to 1500 s written every 20 s, the soak to 6000 s
  every 250 s.  ASCII output: `of.read_internal` reads ASCII only.
- Wall time about 2.7 h on one core (front 23 min; the soak in two parts,
  37 min and 100 min, the first cut by my own one-hour timeout and
  resumed from 2750 s: `startFrom latestTime`, and the script now skips a
  phase that is already written).  The 10-step probe (0.1–0.3 s/step)
  underestimated by about 10x: the PIMPLE steps grow to about 1.8 s once
  the front moves.  Case 163 MB.  Peak memory not measured: the run's
  child is the Docker client, whose RSS (41 MB) says nothing about the
  solver.
- Rendering (`build.py --hero-anim CASE`): 56 frames (front every 40 s,
  soak every 250 s), 1 min 43 s.  B: 1.08 MB, 6.5 s a loop.  C: 1.30 MB,
  8.4 s a loop.  The front's midpoint (half the fluid above the mid
  temperature) is at t = 880 s.
- 2026-11-24, the pick: **C**.  The user asked for a legend on the opening
  mesh image (the colours of fluid, steel wall and insulation) and a
  longer hold on it: 2.5 s, not step 3's 1–1.5 s.  The legend fades out
  with the material colours.  `--hero-anim` now writes only `hero.webp`
  (version C); B and the stills were for the pick and aren't kept.
- README: a `<picture>` with `hero.webp` as its `<source>` and `hero.png`
  as the `<img>`, so a renderer that drops `<picture>` still shows the
  static image.  The link test now also reads `<source srcset>`.

## Questions for design

## Outcome

- **Files:** `docs/gallery/hero_run.py` (new: the run, phases, resume);
  `docs/gallery/build.py` (`hero_mesh`/`hero_scene` split out of
  `hero_worker`, with `hero.png` pixel-identical; `hero_anim_worker`,
  `hero_overlay`, `hero_legend`, `hero_animation`, `--hero-anim CASE`,
  `--anim-out`); `docs/gallery/img/hero.webp` (1.31 MB, 56 field frames,
  9.7 s a loop); README hero; `tests/test_readme.py` (links in
  `<source srcset>`, with a planted one); `tests/test_validation_meta.py`
  (`--hero-anim` without a run names the command to run first);
  CHANGELOG.
- **Tests:** `tests/test_readme.py` and `tests/test_validation_meta.py`,
  149 passed.  No OpenFOAM in CI: the animation is built locally.
- **Measurements:** the solve took about 2.7 h on one core (Agent notes);
  rendering took 1 min 43 s.
- **Surprise:** the 10-step probe underestimated the solve about 10x.  A
  probe has to run past the start-up transient before it means anything.
- **Disk:** the case (163 MB), the frames and the try-out renders are
  deleted.
- **Follow-up:** none needed.  Rebuilding the animation takes the 2.7 h
  solve; the script resumes from the latest written time if it's cut off.
