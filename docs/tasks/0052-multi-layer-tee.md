# 0052 — Multi-layer tee: shells as offset levels of the junction

- **Status:** done
- **Decision:** [0028 — Multi-layer junctions](../decisions/0028-multi-layer-junctions.md)
- **Depends on:** 0051 (exact walls).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A pipe wall and insulation must run through a tee (CHT,
insulated plant lines, PCF files).

**Where.**  `hexmesh/assembly/tee.py` (`branch_spec`, `check`, `layout`,
`ports`), `blocks.py` (`face_vertices`, `face_patches` are already
multi-layer), kit, `API.md`, `README.md` limitations.

**Do.**
1. **Branch spec:** the main spec with the core radius replaced by
   `branch_radius` and the same shells (names, `dR`, `nrad`, `mprg`).
2. **Levels.**  The layout has levels 0 (inner square) and 1 (wall).
   Add a level per shell, l = 2 … L, at cumulative thickness T_l:
   - station corners on the main cylinder R + T_l; the top corners on
     the saddle of cylinders R + T_l and r + T_l, at the branch
     diagonals (the level-1 rule, with R → R + T_l, r → r + T_l);
   - the turning station Z at `R + T + 0.5 (r + T)` (T total), with its
     corners at branch radius r + T_l;
   - edges: arcs about the station centres, saddle splines of the offset
     cylinders, cylinder splines on R + T_l (as `on_cylinder`), branch
     arcs;
   - blocks: every level-1 ring block (S+, S−, Bb, the four turn blocks,
     and the slab and branch-run patches via `face_patches`) gets one
     block per shell between level l−1 and l, with that shell's material.
3. **Exact surfaces** for every shell boundary, as 0051 does for the
   wall.
4. **Limits:** check before GMSH that the outer shell fits (run length
   and turning station clear it), naming the limit.  Measure quality over
   r/R ∈ {0.3, 0.6, 0.9} × total thickness T/R ∈ {0.05, 0.2, 0.5} × one
   and two shells, `nang` 4 and 8.  Report min corner SJ and max
   non-orthogonality (task 0047's metrics).  Propose a limit under
   *Questions for design* (the two-tier policy of 0047), with numbers.
5. Remove the single-layer rejection; keep `rot = 0`, `n_outer = 4`,
   circular shells only (rectangular shells rejected, naming decision
   0026).

**Accept.**
- Kit cases (fluid + steel; fluid + steel + insulation), r/R 0.5 and
  0.9: all-hex, meshed = predicted, `interface_*` groups continuous
  through the junction (one group per material pair, covering main and
  branch), every wall and interface node on its analytic surface (0051's
  tolerance).
- Port signatures class 0 against the neighbouring straights.
- Single-layer tee meshes unchanged (node coordinates to 1e-12).
- The quality table and a proposed limit.
- Full suite: no new failures.

**Out of scope.**  Branch shells with their own thicknesses; laterals;
`stack_changes` inside the tee.

## Agent notes

- **Levels as planned** (step 2).  Level l's station corners follow the
  level-1 rule with R → R + T_l and r → r + T_l.  So the stations bend
  outward: level l sits at x = ±(r + T_l)/√2.  Every ring block gets one
  block per shell between levels l − 1 and l.  The turning station sits
  at `turning_height(R, r, T)` = R + T + (r + T)/2.
- **Shell boundaries on their surfaces** (step 3).  `BlockLayout.wall`
  became `BlockLayout.walls`: level → projector.  A curved face whose
  four vertices `(prefix, l, k)` share a level l is a pinned plate on
  that level's surface.  The tee gives `tee_wall(R + T_l, r + T_l)` per
  level.  So the steel/insulation interfaces are on their offset
  cylinders like the wall: within 3e-4 R.  The wye sets no levels and is
  unchanged.
- **Single-layer tees are unchanged:** node coordinates and node
  numbering are identical to 705a35d (max difference 0.0, compared by
  tag on the kit cases).  At first the numbering differed: block order
  sets curve order.  The junction blocks keep their old order: C, rings,
  branch core, turn blocks.
- **The branch copies the main's shells** with an explicit `dR` (from
  `spec.outlines`, so an `outer=` circle works too).  A non-circular
  shell is rejected in `add()`, naming decisions 0026/0028: the branch
  spec needs radii.
- **Measured quality** (step 4; kit-like geometry, run = r + T + R,
  branch = turning height + R; two shells = ⅓ steel + ⅔ insulation;
  `benchmarks/outline_quality.py` metrics, which match `checkMesh`).
  Shells never lower the tee's min corner SJ, which stays in the fluid
  core: 0.150 / 0.316 / 0.509 at r/R 0.3 / 0.6 / 0.9, as single-layer.

  | r/R | shell min SJ (T/R 0.05 → 2) | shell max non-orth (°) | tee max non-orth (°), fluid core |
  |---|---|---|---|
  | 0.3 | 0.60 → 0.56 | 66 (1 shell) / 70 (2 shells) at T/R 0.05, falling to 40–48 at T/R 2 | 73–77 |
  | 0.6 | 0.63 → 0.56 | 52–54 at T/R 0.05, 39–48 at T/R 2 | 56–64 |
  | 0.9 | 0.60 → 0.50 | 40–52 | 40–52 (a shell cell at `nang` 8) |

  Both `nang` 4 and 8; full rows in this session's scratchpad
  (`quality.jsonl`, `quality_shells.jsonl`).  **Thin** shells at small
  r/R are the worst shells for non-orthogonality.  Thick shells barely
  change anything.
- **What limits shells is the run length.**  The level-l station moves
  toward the port as T grows, and a short run twists the shell's slab.
  Predicted (pre-GMSH) min corner SJ against `run_length`/R (R = 1, one
  shell):

  | r/R | T/R | 0.5 | 0.6 | 0.7 | 0.8 | 1.0 | 1.2 | ≥ 1.5 |
  |---|---|---|---|---|---|---|---|---|
  | 0.25 | 0 | 0.119 | 0.124 | 0.124 | 0.124 | 0.124 | 0.124 | 0.124 |
  | 0.25 | 0.05 | −0.038 | 0.062 | 0.124 | 0.124 | 0.124 | 0.124 | 0.124 |
  | 0.25 | 0.2 | −0.168 | −0.058 | 0.040 | 0.124 | 0.124 | 0.124 | 0.124 |
  | 0.25 | 0.5 | – | – | – | −0.091 | 0.089 | 0.124 | 0.124 |
  | 0.5 | 0 | – | 0.069 | 0.144 | 0.201 | 0.258 | 0.258 | 0.258 |
  | 0.5 | 0.05 | – | −0.052 | 0.080 | 0.184 | 0.258 | 0.258 | 0.258 |
  | 0.5 | 0.2 | – | – | – | 0.060 | 0.246 | 0.258 | 0.258 |
  | 0.5 | 0.5 | – | – | – | – | – | 0.216 | 0.258 |
  | 0.9 | 0–1 | – | – | – | – | 0.432 | 0.474 | 0.499–0.509 |

  "–": `run_length ≤ r + T`, rejected.  An inverted layout is already
  rejected before GMSH ("inverted or degenerate at a corner"), but that
  error doesn't name the run length.
- **PCF set-on tees** (task 0037) have run = the branch bore each side,
  about 2r.  With a pipe wall (R 0.05, r 0.0125, T 0.01) the steel's
  approach slab inverts (SJ −0.16).  The plain PCF `TEE` with a wall
  now validates.  Tests updated accordingly (`test_pcf_junctions`,
  `test_io_readers`); the PCF reader's own insulated-junction rejection
  stays for 0054, with its reason corrected.

**Note from design (2026-10-29, decision 0029):** junction walls may now
be made exact by **node projection** in `Assembly.mesh()` (task 0051
steps 5–8), not only by OCC surfaces.  For the tee's shell boundaries
(cylinders `R + T_l`, `r + T_l` and their saddle), either works.  Pinned
plates as in 0051's tee are fine for now; if 0051's step 8 drops the
plates in favour of projection, follow it.  Shell nodes must end on
their offset surfaces either way (the accept criteria are unchanged).

**Q1 answer implemented (2026-10-29).**
- **Limits:** 0047's `OUTLINE_SJ_MIN`/`WARN` are renamed
  `PREDICTED_SJ_MIN`/`WARN` and shared (`section_quality`, the
  benchmark, two tests' messages).
- **`Tee`:**
  - `predicted_sj(inlet, spec, run_length=None)`: the layout's min
    corner SJ (pure).
  - `shortest_run(inlet, spec, tier)`: bisection between r + T and
    r + T + 2 R, to 1e-3 R, rounded up.  It first checks the long end, so
    a tee that can't reach the tier costs one evaluation.  The bisection
    takes 0.2–0.3 s when it runs (13 ms per layout single-layer).
- **Fitting warnings:** `Tee.validate()` applies the tiers before the
  layout's own inversion check, so a short run gets the hint rather than
  "inverted or degenerate".  It returns its warnings, and
  `Assembly.validate()` records any a fitting returns in
  `Assembly.warnings`, as it does the outline ones.
- **`run_length=None`:** `run_length`, `branch_length` and
  `branch_radius` all default to `None`, so positional calls
  (`Tee(0.2, 0.25, 0.05)`, used widely) keep working.
  `__post_init__` makes the last two required (`TypeError`).
  `Tee.resolve` fills the run in on `add()`.
- **Plateau SJ against r/R** (single layer; shells don't lower it):

  | r/R | 0.3 | 0.4 | 0.5 | 0.55 | 0.6 | 0.7 | 0.8 | 0.9 | 0.95 |
  |---|---|---|---|---|---|---|---|---|---|
  | SJ | 0.150 | 0.203 | 0.258 | 0.286 | 0.316 | 0.377 | 0.441 | 0.509 | 0.543 |

  So **every tee with r/R below about 0.57 warns, at any run length**.
  That includes the plain r/R 0.5 tee of the kit, the examples and most
  tests, wider than "r/R ≲ 0.3" in the answer.  The message blames the
  branch ratio.
- **Default run reaches nearly the plateau:** r + T + 0.5 R gives 0.493 of
  0.509 at r/R 0.9, single layer; elsewhere the plateau itself.  No
  measured case needed the bisection's longer run: the closed form
  always passed 0.3 where the plateau did.
- **PCF set-on tee with a wall** (task 0037's spool): now rejected with
  "predicted corner scaled Jacobian −0.159 is below PREDICTED_SJ_MIN
  0.1; run_length 0.0385 or more reaches it (now 0.0254)", which is
  what 0054 needs.

## Questions for design

**Q1 (proposed limit, step 4).**  Clearance alone (`run_length > r + T`,
`branch_length > turning height`) is not enough: short runs invert the
shells' slabs (table in *Agent notes*).  The turning height and the shell
thickness themselves need no limit: shells stay at SJ ≥ 0.50 up to
T/R 2.  Proposal, on 0047's two tiers and the layout's predicted corner
SJ (pure, `BlockLayout.corner_jacobians`, already computed by
`validate()`):
- **reject** below 0.1, naming the tee, the predicted SJ, and the
  shortest `run_length` that reaches 0.1 (found by bisection on the pure
  layout);
- **warn** below 0.3, the same way.

Two consequences to weigh:
- Tees with r/R ≲ 0.3 warn at any run length: their fluid core is at
  0.12–0.15, with or without shells.  The same holds single-layer today.
  At r/R 0.3 their non-orthogonality is 73–77°, past 0047's 70° warning
  too.
- A PCF set-on tee with a pipe wall (run ≈ 2r) is rejected.  The reader
  could lengthen the run to the shortest valid one, or 0054 could decide.

Alternatively, a closed-form rule from the table:
`run_length ≥ r + T + 0.5 R` reaches the long-run SJ at every r/R and
T/R measured.  It is simpler, but conservative for large r/R.

### Design answer (2026-10-29): your proposal, plus a default run length

**Accepted as proposed:** the limit is on the layout's **predicted
corner SJ** (`BlockLayout.corner_jacobians`, already computed in
`validate()`), with task 0047's two tiers:
- **reject** below 0.1 (`AssemblyError`);
- **warn** below 0.3 (`UserWarning`, recorded so callers can read it).

Both name the tee, the predicted SJ and the **shortest `run_length`
that reaches the tier** (bisection on the pure layout).  The bisection
is the error's hint, which is what an agent needs (decision 0019,
constraint 3).  Put 0.1 / 0.3 in `limits.py` (reuse 0047's names if
they fit: `OUTLINE_SJ_MIN`/`WARN` → a shared `PREDICTED_SJ_MIN`/`WARN`).

**On your two consequences:**
- **Small r/R tees warn at any length.**  Accepted: it's the truth (the
  fluid core is at 0.12–0.15 single-layer too), and a warning is the
  right signal.  The warning should say the cause is the branch ratio,
  not the run length, when lengthening the run can't help (the bisection
  finds no length that reaches 0.3).
- **The non-orthogonality of 73–77° at r/R 0.3** isn't predicted before
  GMSH for junctions.  Leave it to the post-mesh quality report for
  now; no junction non-orthogonality predictor in this task.

**Added: `run_length=None`.**  The closed form you found, `run_length =
r + T + 0.5 R`, reaches the long-run SJ at every r/R and T/R you
measured.  Make it the default: `Tee(run_length=None, …)` resolves in
`add()` (the `resolve` hook from tasks 0040/0041) to
`max(r + T + 0.5 R, the bisection's 0.3 length)`, and stores the number,
so the JSON stays explicit.  An explicit `run_length` keeps today's
behaviour, with the limits above.

**PCF set-on tees** (run about 2r, rejected with a wall): that's 0054's.
The note added there: the reader takes the Tee's run from the host pipe,
so it should use the default (or the bisection's length) and reject only
if the host pipe is too short, naming the component.

**Do:** the limit in `validate()`, the hint, `run_length=None`, and
tests on each side of both tiers and for the default.  Then set the task
`done`.

## Outcome

**Q1 limit and `run_length=None` (2026-10-29): done.**

- **Two tiers on the predicted corner SJ, before GMSH:** reject below 0.1,
  warn below 0.3 (recorded in `Assembly.warnings`).  Each message names
  the tee, the SJ, and the shortest `run_length` that reaches the tier,
  or says the branch ratio limits it.
- **`Tee(run_length=None)`** resolves on `add()` to
  `max(r + T + 0.5 R, shortest run reaching 0.3)`, stored in the JSON.
- **Files:** `hexmesh/assembly/tee.py`, `limits.py`, `assembler.py`
  (fitting warnings), `section_quality.py` and
  `benchmarks/outline_quality.py` (renamed limits), `API.md`.
- **Tests:** `test_tee.py` +9: reject with hint, the hint passes; warn
  with hint, the hint is silent; ratio-limited warning; the default ×5
  (stored, at least the closed form, near the plateau); `None` outside an
  assembly, missing arguments.  Updated: `test_io_readers` (set-on
  message), `test_layer_outlines` and `test_study` (renamed limits).
- **Suite:** 1890 passed (before: 1881; +9 here).
- **For design:**
  - Tees with r/R below about 0.57 always warn (table in *Agent notes*):
    the kit tee, the examples, most PCF reducing tees.  If that's too
    noisy, options are a lower warning tier for junction cores (their
    plateau is the junction's own limit), or warning only when a longer
    run would help.
  - DESIGN's tee limits row can mention the predicted-SJ tiers.

**Shells (earlier, 2026-10-29): done.**  Any stack of circular shells runs through the tee.

- **Kit cases** `tee-0.5-2layer`, `tee-0.9-3layer` and
  `tee-0.5-3layer-oblique`: all-hex, meshed = predicted, class-0 ports,
  walls and interfaces within 1e-3 R of their offset cylinders (measured
  3e-4).  The kit's tee check is now per level.
- **Interfaces:** one group per material pair (`interface_fluid_steel`,
  `interface_steel_insulation`), covering all four fittings (both runs,
  the tee and the branch) as one edge-connected sheet of quads
  (`test_interfaces_continuous_through_tee`, r/R 0.5 and 0.9).
- **Single-layer tees identical** to before: node coordinates and
  numbering.
- **Cells:** for example 1296 → 1936 (+ steel) → 2896 (+ insulation) at
  `nang` 4.
- **Quality:** the tables in *Agent notes*.  The proposed limit is Q1.
- **Files:**
  - `hexmesh/assembly/tee.py`: `thicknesses`, `branch_spec` with
    shells, `turning_height`, the room checks, the per-level layout;
  - `hexmesh/assembly/blocks.py`: `walls` per level, `_level`;
  - docs: `API.md` (Tee shells and limits, outline note, PCF reason),
    `README.md` limitations;
  - `hexmesh/io/readers/pcf.py` (message only);
  - the tee example's docstring, the assembler comment;
  - tests: `test_tee.py` (+5: branch spec, continuity ×2, room ×2;
    the single-layer rejection test is now a circular-shell rejection),
    `test_fitting_conformance.py` (+3 cases), three updated rejections
    (`test_layer_outlines`, `test_pcf_junctions`, `test_io_readers`).
- **Suite:** 1859 passed, 3 skipped.  Before: 1809.  +23 here (kit and
  tee files 422 → 445); the other +27 are the stenosis example's tests
  from the other session's uncommitted files.
- **Follow-ups:**
  - Q1's limit;
  - the PCF set-on run length with a wall (0054);
  - 0051 step 8 may replace the pinned plates with node projection;
    shells then need a projector per level, which `walls` already has.
