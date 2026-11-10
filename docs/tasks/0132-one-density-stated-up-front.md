# 0132 — One density per network: say so up front, in the docs and in the error

- **Status:** done (the design session, at the user's request, 2026-11-11)
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

- **No new code.**  `switch_class_not_declared` stays: the message
  changed and a hint was added, `where` and `value` unchanged.  A more
  specific code would split one rule (a port pair's class isn't
  declared) by which class it is; the hint carries the difference.
- **Where the words live:** `signature.BRIDGES` (what each class needs:
  for 2 and 3, "… which no fitting makes"), `DENSITY_HINT` and
  `TOPOLOGY_HINT`.  `Transition`'s own class check (`fittings.py`, task
  0135's file) reads `BRIDGES`, so its message follows without an edit.
- **Left for task 0136:** `assembler.py`'s docstring near line 538 still
  says a network "needs density switches (decision 0003)"; the split
  moves that code, so it's fixed there rather than in a conflicting edit.
- **Tests:** `test_signature.py`'s two Reducer cases (nang 4 → 8; nrad
  3 → 5 with a grading change) now also check the plain message (no
  "density switch"), the code and the hint; one regex followed the
  wording ("grading-only" → "radial grading (mprg) only").

## Questions for design

## Outcome

**Status:** done.

- **Files:** `README.md` (a paragraph after the 8× note, linking the
  GUIDE), `docs/GUIDE.md` ("One density per network" under *Resolution
  and cell count*, with the 300 mm / 50 mm worked example; a line in
  *Current limitations*), `API.md` (`nang`, `nang_w`/`nang_h` and the
  core's `nrad` say one per network; the class table and the two quoted
  messages), `hexmesh/assembly/signature.py` (`BRIDGES` for classes 2
  and 3, `DENSITY_HINT`, `TOPOLOGY_HINT`), `tests/test_signature.py`,
  `CHANGELOG.md`.
- **Tests:** the affected files (signature, reducer, assembly, errors,
  architecture, readme, transition, agent schema): 279 passed.  Full
  suite (`-n 4`, 2026-11-11): 4069 passed, 15 skipped, 0 failed,
  26.6 min.
- **Meshes:** unchanged (messages and docs only).
- **Surprises:** none.  Follow-up: `assembler.py`'s docstring (Agent
  notes) goes with task 0136.

