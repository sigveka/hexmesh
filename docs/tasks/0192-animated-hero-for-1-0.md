# 0192 — An animated hero for 1.0: a hot front through the insulated network, in two versions for the user to pick

- **Status:** ready
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

## Questions for design

## Outcome
