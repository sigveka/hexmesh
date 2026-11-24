# 0193 — The animated hero, polished: no ghosting, a matching still, a dark-theme version, a social-preview still

- **Status:** done (2026-11-24)
- **Decision:** none needed (gallery and README only).
- **Depends on:** 0192 (done).
- **Blocks:** none.  Before the 1.0 release, which shows the hero.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-24) asked for five improvements to 0192's
hero.  The design session made the README's part: a reduced-motion
source, a short alt text and a caption.  It also added the release-notes
and social-preview steps to RELEASING.  This task is the rendering part.

**Do.**
1. **Ghosting.**  Lossy inter-frame coding leaves faint residue: below
   the clock and a yellowish streak to its right in the mid-front frame
   (`t = 920 s`), visible at 3× zoom.
   - Re-encode with settings that remove it: higher `quality`,
     `allow_mixed=True`, or lossless for the overlay.
   - Choose the smallest file that shows no residue in a blank-strip
     check: pixels in the background regions stay white in every
     frame.  Add that check as a test on the assembled frames, if it can
     run without the solve.
   - Stay under about 3 MB.
2. **The still matches the animation.**  `hero.png` becomes the
   animation's first frame: the mesh with its material legend, at the
   same size and crop.  `build.py --hero` writes it that way, so the
   reduced-motion and non-WebP fallbacks show what the animation opens
   on.
3. **A dark-theme version.**
   - Render `hero-dark.webp` and `hero-dark.png` on GitHub's dark
     background (#0d1117), with light ink for the clock, the colour bar's
     labels and the legend.
   - Check the mesh edges and the colour map's dark end (the cold
     insulation) still read against it.  If the cold colour vanishes
     into the background, outline the geometry or lift the map's low
     end, and say which.
   - **README:** four `<source>` lines in the `<picture>`, in this
     order:
     1. dark and reduced motion → `hero-dark.png`;
     2. reduced motion → `hero.png`;
     3. dark → `hero-dark.webp`;
     4. the default → `hero.webp`.
     The `<img>` stays `hero.png`.  `tests/test_readme.py` already
     follows `srcset` links; check it covers all four.
4. **`build.py --social OUT`:** a 1280×640 PNG of the mid-front frame,
   centred on white, written to *OUT* and not committed.  RELEASING step
   6 names it.  The design session made a stand-in by hand for now.
5. **The rerun:** 0192 deleted its case, so items 1 and 3 need the
   2.7 h solve again (`docs/gallery/hero_run.py` resumes if cut off).
   - Check memory, the other session's runs and disk first (CLAUDE.md),
     and get the user's go-ahead.  Run it when 0186 isn't using the CPU.
   - Keep the frames until the user has seen both themes, then delete
     the case and frames by exact path.
6. **Show the user** the light and dark versions (paths in your
   scratchpad, and a still of each) before committing the images.
7. CHANGELOG *Unreleased* (Docs): one line.

**Accept.**
- No residue in the blank-strip check.
- `hero.png` equals the opening frame.
- Light and dark versions, each under about 3 MB, approved by the user.
- Four sources in the README, and their links tested.
- `--social` works.

**Out of scope.**  A new simulation or camera; video formats.

## Agent notes

- 2026-11-24, the rerun: `hero_run.py` as in 0192, 6945 s (1.9 h) in one
  go on one core; case 164 MB, frames for both themes 32 MB.  Rendering
  both themes' frames takes about 9 min.
- **Ghosting: lossy WebP can't keep the background clean.**  The check
  (background pixels at least 4 px from anything drawn, every decoded
  frame) found residue at every lossy setting: quality 80 → 26 levels,
  90 with `allow_mixed` → 26, 95 → 30, 100 → 10; every frame a key frame
  (`kmax=1`) → 8–10, the ringing by the overlays alone.  Lossless is
  clean but 8.3 MB; 256-colour frames, lossless, 5.4 MB.
- **What does it: a transparent background.**  WebP's alpha plane is
  lossless, so a pixel that is background in its own frame (1 px from
  anything drawn) is transparent, and the page's colour shows through
  exactly: white, or GitHub's #0d1117 for the dark version.  The colour
  stays lossy at quality 80.  The mask is per frame: with one mask for
  all frames, the pixels a longer clock ("t = 1,500 s") covers stayed
  opaque in every frame and smudged at 3× zoom.  Result: residue 0 in
  both themes; 2.29 MB light, 2.04 MB dark.  The check composites each
  frame on its background, so it measures what a page shows.
- **Dark theme:** plasma's cold end (the insulation, #0d0887 lit) reads
  against #0d1117, edges included; no outline and no lifted low end.
- `hero.png` and `hero-dark.png` from `--hero` are byte-identical to the
  animations' opening frames.  The animation is encoded with the hold
  merged into the last field frame, so it has 1 + 9 + 56 frames.
- `--social OUT` needs the frame index, so `--hero-anim` writes
  `img/hero.json` (the mid-front frame, times, encoding; 318 bytes).

## Questions for design

## Outcome

- **Files:** `docs/gallery/build.py` (`HERO_THEMES`, `hero_window`,
  `hero_opening`, `hero_blank`, `hero_residue`, `run_social`;
  `hero_worker` writes both stills; `hero_animation(theme)` with the
  transparent background; `--anim-frames DIR`, `--social OUT`);
  `docs/gallery/img/hero.png` (now the opening frame), `hero-dark.png`,
  `hero.webp`, `hero-dark.webp`, `hero.json`; README's four sources;
  `tests/test_readme.py` (the sources' order and links);
  `tests/test_validation_meta.py` (clean background on stand-in frames, a
  planted smudge caught, the social preview's size and centring);
  CHANGELOG.
- **Tests:** `tests/test_readme.py` and `tests/test_validation_meta.py`,
  153 passed.
- **Surprise:** no lossy setting is clean; transparency is.
- **Approved** by the user (2026-11-24), both themes.  The case (164 MB)
  and the frames (32 MB) are deleted.
