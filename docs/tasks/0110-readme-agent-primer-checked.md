# 0110 — The README's agent primer: its numbers checked

- **Status:** done (2026-11-08)
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md); follow-up of task 0078
- **Depends on:** 0078, 0107 (done).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The README's "With an agent" section (design, `6712f95`) quotes
numbers from real runs on 0.4.0: the hero network (`insulated_network`)
at 18 012 cells, and `advise` for water at 0.01 m/s, `fine`, budget
200 000, giving 641 680 → 536 432 (axial aspect 6 → 12) → 72 048 cells
at `medium`, `nang` 12, `nrad` 6.  They are written by hand, so nothing
catches them going stale.  Since 0107 the light commands need no gmsh
and run in about 0.3 s, so a test can recompute them cheaply.

(0078's *Outcome* said the section was empty.  It isn't; it was committed
in `6712f95`.)

**Where.**  `tests/test_readme.py`; `README.md` only if a number is
wrong.

**Do.**
1. **A test** that builds `hexmesh.examples.sections.insulated_network`,
   runs `estimate`, and runs `advise` with the primer's inputs, through
   the CLI functions (no GMSH), and checks every number the section
   quotes: the cell counts, the budget steps, the density and the
   accuracy it fell back to.
2. **The numbers in the README** are matched by text (a regex per
   number, or a small marked block), not regenerated: the section is
   prose.  On a mismatch the test names the number and the value it
   now gets.
3. Check the plain-English description in the primer still matches the
   example (bore, layer thicknesses, lengths, angle).  Report any
   difference under *Questions for design* rather than editing the prose.

**Accept.**
- The test passes, and a planted wrong number fails it with a message
  that names it.
- It runs in under 5 s and without gmsh.
- Full suite: no new failures.

## Agent notes

- **The test** is in `tests/test_readme.py`, "the agent primer":
  - a module fixture runs the primer's session through `cli.main`:
    `validate`, `estimate`, `advise`, `apply`, `validate` on the result;
  - the inputs come from the primer's own request (velocity, accuracy,
    budget), read by regex, so a changed request is checked too;
  - each quoted value is one regex in `CLAIMS`, on the section with its
    blockquote marks dropped and whitespace collapsed (the prose wraps
    mid-number in places);
  - a mismatch reads "README primer: the cells advised is 72049; the
    commands give 72048", which is what the planted test checks;
  - **no gmsh:** the fixture patches `hexmesh._gmsh.load` to fail.  Every
    gmsh access goes through it, and the CLI turns the failure into an
    error the test names ("hexmesh build: … reached gmsh"; tried once by
    hand with `build`).
- **Every number in the primer is current** (0.4.0, this tree): 18 012;
  641 680 → 536 432 (axial aspect 6 → 12) → 72 048 at `medium`, `nang`
  12, `nrad` 6.  `validate` gives no errors and no warnings, before and
  after `apply`, and the calibration-scope note is there.  README.md is
  unchanged.
- **Dimensions** (step 3): the bore, the steel and insulation
  thicknesses, the first and header straights, the branch's 120 mm and
  where it drops its insulation, the wye's 60° and the legs' 0.3 m
  straights match the example and are asserted.  Two lengths differ
  from what the prose implies (*Questions for design*).
- **Time:** the four tests take 5.0–5.1 s on an idle machine, pytest's
  start included; the fixture alone 4.6–4.8 s.  At first the dimension
  test rebuilt the network (0.7 s more), so it now uses the fixture's.
  Under xdist each worker that gets one of the tests runs the fixture.

## Questions for design

These don't hold the task: the numbers are checked, and the prose is
design's.
1. **Two lengths in the primer differ from the example.**
   - "a tee to a 120 mm branch": the branch is the tee's 0.3 m stub,
     then a 0.4 m straight.  The prose gives no length.
   - "a 60° wye into two 0.3 m legs": each leg is the wye's 0.4 m
     daughter, then a 0.3 m straight, so 0.7 m from the split.
   An agent following the prose would build a different network, with a
   different count than 18 012.  Should the prose give the lengths
   ("a 0.3 m branch, then 0.4 m bare"; "legs of 0.4 m, then 0.3 m"), or
   the example change to the prose?
2. **`advise` is slow on any network with a wye**, and the test sits at
   the 5 s line because of it.  In a cProfile of the fixture, `Wye.layout`
   is 18 of 21 s:
   - it runs 9 times, building 2 430 wall points with `Skeleton.to_wall`;
   - each point marches, then bisects 60 times, for 187 632 scalar
     `Skeleton.nearest` calls with three `np.linalg.norm` each;
   - `layout` isn't cached, and `cell_count` and `validate` call it.
   A fix is in `assembly/wye.py`: cache the layout per (frames, spec), or
   vectorise the march, or both.  The vectorised march could move wall
   nodes by rounding, so it touches the meshes; a cache doesn't.  A task?

**Design answers (2026-11-08, the user: "yes"):**
1. The prose changes to the example: it now gives the branch (0.3 m, then
   0.4 m that goes bare after its first cell) and the wye (0.15 m of run,
   0.4 m legs, each followed by 0.3 m).  The dimension test asserts the
   new phrases and the tee's, tap's and wye's lengths (design, with the
   README edit).
2. The cache: task 0112, after the launch.  Vectorising waits for its
   measurement.

## Outcome

- **Files:** `tests/test_readme.py` (4 tests: the numbers, the
  validations and the calibration note, a planted wrong number, the
  network's dimensions).  README.md unchanged: every number is current.
- **Tests:** `tests/test_readme.py` 10 passed (the slow block test
  deselected), 5.0–5.1 s for the four new ones on an idle machine.  The
  full suite: see the commit.
- **Surprise:** the primer's five commands, with the network's build,
  take 4.6–4.8 s, most of it the wye's wall projection (Q2; 18 of 21 s
  under cProfile).  The "about 0.3 s" in this task's *Why* holds for
  commands that resolve no wye.
- **Proposed follow-ups:** the primer's lengths (Q1); a wye layout
  cache (Q2).
