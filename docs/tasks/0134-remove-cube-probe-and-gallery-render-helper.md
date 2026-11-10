# 0134 — Housekeeping: one render helper in the gallery builder (`_cube_probe.py` stays)

- **Status:** done (the design session, at the user's request, 2026-11-10)
- **Decision:** [0043](../decisions/0043-wye-layout-redesign.md) (consequences: `_cube_probe.py` folded into the layout); DESIGN §3.1
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The architecture review (the design session, 2026-11-10, at the
user's request) found:
- `docs/gallery/build.py` defines `rgb()` three times, and `render`,
  `hero_worker` and `render_cutaway` each repeat the render-window,
  grab and crop code (the third copy from task 0121's cut-away hook).

**Not removed: `_cube_probe.py`.**  The review took it for dead code
(about 100 lines duplicate `cube.py`; nothing in `hexmesh/` or `tests/`
imports it).  The coding session pointed to
`validation/tools/wye_redesign.py`, which imports `CubeProbe` for the
asymmetric-wye cube (`theta_left`, `theta_right`, per-daughter ratios):
the harness task 0124 uses.  `cube.py` holds only the equal-tee case.
So it stays with `_wye_probe.py` until 0124 settles (decision 0043's
note of 2026-11-10).

**Where.**  `docs/gallery/build.py`.

**Do.**
1. In `build.py`: one module-level `rgb()`; one helper that renders a
   `vtkRenderer` off screen at a size and writes the PNG, and one that
   crops to the content with a margin and scales to a width.  `render`,
   `hero_worker` and `render_cutaway` use them.
2. **Check:** rebuild three gallery entries (one plain, `idealised_aorta`
   with its cut-away) and the hero into a scratch copy; the images match
   the committed ones pixel for pixel, or differ only where
   anti-aliasing can't be pinned (then say so, with the largest pixel
   difference).  Don't commit regenerated images or metrics for this.

**Accept.**
- `build.py` has one `rgb` and the two helpers; images unchanged.
- `tests/test_architecture.py` and the example tests pass.

**Out of scope.**  The probes (decision 0043, task 0124); the library
de-duplication (task 0135).

## Agent notes

## Questions for design

## Outcome

## Outcome

**Status:** done.

- **Files:** `docs/gallery/build.py` only.  One module-level `rgb()`
  (was three nested copies) and four helpers: `vtk_points`, `poly_actor`
  (the coloured, edged polygon actor `render` and `render_cutaway` each
  built), `snapshot` (off-screen window, grab, PNG) and `crop_to_content`
  (crop to non-white plus a margin, scale to a width).  `render`,
  `render_cutaway` and `hero_worker` use them.  87 lines added, 114 removed.
- **Images byte-identical** (`cmp`), rendered in a detached worktree at
  HEAD 95ea004, old builder against new: `tee`, `tee_section`,
  `idealised_aorta`, its section and cut-away, `hero`, and the
  `poiseuille` validation images (`coarse.png`, the cropped `fit=True`
  overview, and three sections).  Rendering was already deterministic:
  five of six re-rendered gallery images equal the committed ones; the
  committed `tee.png` is from an older build.
- **Not removed: `_cube_probe.py`** (see *Why*; decision 0043's note of
  2026-11-10).  The review's claim that nothing imports it was wrong:
  `validation/tools/wye_redesign.py` does, lazily; the coding session
  caught it.
- No regenerated images or metrics committed; the worktree and scratch
  images are deleted.

