# 0154 — Example: a buried district-heating pipe with graded soil; example colours in the gallery

- **Status:** done (the design session, at the user's request, 2026-11-12)
- **Decision:** none new.  The user, 2026-11-12: "both of those" (the
  rocket example, and a single buried pipe while the pair waits for
  decision 0035 stage B); earlier: "here colours in the mesh will matter
  more".
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The district-heating pair needs decision 0035 stage B.  A
single buried pipe, with its soil in the mesh, works today and shows the
layer stack at its most natural.  Its colours have to mean something
(hot red, steel grey, foam yellow, soil brown), which the gallery
couldn't do: it cycled five colours by material order.

**Done.**
1. `hexmesh/examples/applications/district_heating.py`: water, steel,
   PUR, casing (typical DN 100 values, said to be typical), a square of
   near soil and a rectangle of far soil, both graded outward; 3 m, a 90°
   bend, 3 m.  Its docstring describes the pair and why it waits.
2. **The gallery** (`docs/gallery/build.py`):
   - an example may set `GALLERY_COLOURS = {material: ("#rrggbb",
     "name")}`; the overview's open ends, the section image and the
     "Colours:" line use it;
   - a cut-away may set `"by_material": True`: every face of the kept
     cells takes its material's colour (edges darker), so a section's
     layers read apart.
   Examples without them render as before.

## Agent notes

- The pipe is centred in the soil: an off-centre core isn't a section
  today, and the pair's design (decision 0035's note) puts the depth in
  the far layer instead.
- The EN 253 table and the manufacturer's manual weren't reachable; the
  sizes are called typical, not checked.

## Questions for design

None.

## Outcome

- **Numbers:** 23 040 cells, min SJ 0.60 (the bend), min SICN 0.023,
  max aspect 127; no `validate()` warning.
- **Used by:** this example, `subsea_pipeline` and
  `rocket_injector_manifold` (colours and material cut-aways).
- **Tests:** `tests/test_examples.py` for the new examples and the
  listing checks: 8 passed.  The other gallery entries weren't re-run;
  their rendering is unchanged by construction (no `GALLERY_COLOURS`, no
  `by_material`).
