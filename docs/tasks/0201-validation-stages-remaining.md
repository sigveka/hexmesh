# 0201 — The remaining validation cases on stages, with bundles (after 1.0)

- **Status:** ready (after 1.0; after 0200)
- **Decision:** [0060](../decisions/0060-validation-readable-and-solver-neutral.md)
- **Depends on:** 0198, 0200.
- **Blocks:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Do.**  Convert every remaining case and export check to 0198's stages:
heated pipe, heated rod, helical pipe, layered conduction, MMS,
rectangular duct, square bend, the two stenoses, turbulent pipe,
Womersley, and the three export checks.  Do them one at a time, cheapest
first, each reproducing its stored levels.  Give each a bundle and a
`compare` test.  Retire the copied helpers as their last user leaves.
When the last case is done, remove the old layout's support and the
per-driver caches.

**Accept.**  Every case on stages, with a bundle; no copied helper left;
the volunteer tags still checked by `check`.

## Agent notes

## Questions for design

## Outcome
