# 0193 — The animated hero, polished: no ghosting, a matching still, a dark-theme version, a social-preview still

- **Status:** ready
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

## Questions for design

## Outcome
