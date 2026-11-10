# 0132 — One density per network: say so up front, in the docs and in the error

- **Status:** ready
- **Decision:** [0003](../decisions/0003-drum-body-and-shell-nozzles.md) (note 2026-11-10); DESIGN A5; [0042](../decisions/0042-road-to-1-0.md) (1.0 surface)
- **Depends on:** none.  Pairs with 0131 (branch grading), whose GUIDE
  section this one can point to.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user (2026-11-10): one density per network is acceptable,
"and we need to be clear and up-front with users about it".  Today it is
a design rule (DESIGN A5) and one line in the limitations; a user finds
it by hitting `switch_class_not_declared`, whose message names "a
density switch (decision 0003)" that doesn't exist.

**Where.**  `README.md`, `docs/GUIDE.md`, `API.md`,
`hexmesh/assembly/signature.py` (the message, a hint), `CHANGELOG.md`,
`tests/`.

**Do.**
1. **README:** in the overview (not only "Not yet"), one short paragraph:
   `nang` and `nrad` are the same across a connected network; radial
   grading can differ; circumferential cell size scales with the pipe's
   radius, so a network with a 10× radius range has 10× wider cells
   around the large pipes; what to do (set `nang` for the smallest pipe
   that matters, grade walls with `first_cell`, mesh a large vessel
   separately and couple it in the solver).  Plainly, no hedging.
2. **GUIDE:** the same, as a "Density" section near the parameter
   separation (topology vs density), with a worked number (e.g. a 0.3 m
   header and a 0.05 m branch at `nang` 8: the cells' widths around
   each); in *Current limitations*, a line pointing to it.
3. **API.md:** `PipeSpec`'s `nang`/`nrad` say "one per network".
4. **The error:** a count difference (`nang`, `nrad`) between ports or at
   an interface says so in plain words and gets a hint, e.g. "hexmesh
   meshes a network at one density: nang and nrad must match; radial
   grading may differ (first_cell, mprg); see GUIDE 'Density'".  Don't
   name a density switch as if it existed.  Keep the code
   (`switch_class_not_declared`); adding a more specific code is allowed
   (additive) if it reads better: say which under *Agent notes*.
   Class 3's "a topology switch (decision 0003)" gets the same honesty.
5. **Tests:** the message and hint for a `Reducer` whose outlet changes
   `nrad`, and one whose outlet changes `nang`.

**Accept.**
- A reader of the README's overview learns the rule before building
  anything; the error says what to do.
- Meshes unchanged; full suite: no new failures.

**Out of scope.**  Any density change (task 0133, after 1.0).

## Agent notes

## Questions for design

## Outcome
