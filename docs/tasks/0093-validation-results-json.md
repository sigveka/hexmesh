# 0093 — Each validation case keeps its full-precision results next to RESULTS.md

- **Status:** done
- **Decision:** [0012 — OpenFOAM validation cases](../decisions/0012-openfoam-validation-cases.md); [0015 — how convergence is judged](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) (amendments 2 and 3); proposed by task 0089
- **Depends on:** 0089 (done: the shared `validation/tools/convergence.py`)

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `validation/` and `tests/`.

**Why.**  Task 0089 rechecked every accepted case from what was stored,
and that was mostly RESULTS.md's rounded tables (RESEARCH §7.12).
- heated_pipe's dT_b/dx came out at order 1.54 from the table against
  2.03 measured: two rounded errors (−0.0074, −0.0014 %) are too few
  digits for a Richardson ratio.
- Only rect_duct (task 0071's JSON) and stenosis (its 2 GB `work/`) had
  more.
- `work/` is gitignored and machine-local, so even that is lost on
  another checkout.

Every driver already writes its results with `--json FILE`, but nothing
keeps the file.  A recheck or a change of gate (decision 0015's
amendments) should never need an OpenFOAM rerun.

**Where.**  `validation/<case>/results.json` (new, committed);
`validation/results.schema.json` (new); a shared writer and loader in
`validation/tools/`; the eight `run.py` drivers;
`tests/test_validation_meta.py`.

**Do.**
1. **The file**, `validation/<case>/results.json`, one per case,
   committed:
   - `levels`: every level's reported quantities at full float
     precision, as the driver computes them, with the level's
     parameters (k, nang, nrad, n_layers, cells, mesh series);
   - small 1-D profiles a gate or table uses (centrelines, wall lines,
     plane samples) at full precision.  **No fields:** nothing per cell;
   - `environment`: hexmesh commit (`hexmesh.study.manifest`'s helper),
     gmsh, OpenFOAM version and runner, Python, date of each level;
   - `format` and `version`, with `validation/results.schema.json`.
   - Size cap: 1 MB per case.  If a case needs more, stop and ask
     under *Questions for design*.
   - JSON written deterministically: sorted keys, `indent=1`, a
     trailing newline, `encoding="utf-8"` and `newline="\n"` (decision
     0039).
2. **Drivers write it by default.**  `--json` keeps working (it names
   another path); the default becomes the committed file.  Levels
   already in the file are reused, as rect_duct and heated_pipe do
   today: one shared helper in `validation/tools/`, not eight copies.
   - **Drivers clean up `work/` by default** (the user, 2026-11-02:
     the machine is storage constrained).  When a level's results are
     in `results.json`, delete that level's case directory.
     `--keep-work` keeps it for debugging.  A failed level keeps its
     directory and says where it is.
3. **RESULTS.md's tables come from it.**  Richardson rows and gates are
   computed from `results.json` through `validation/tools/convergence.py`,
   so RESULTS.md and the stored numbers can't disagree.  Where a driver
   writes RESULTS.md by hand today, add a check instead of rewriting the
   prose.
4. **Fill it for the accepted cases** from what exists, in this order:
   1. JSON from the original runs, if any are still on this machine
      (`validation/*/work/`, the drivers' default `--json` paths);
   2. stenosis: its stored fields in `work/` (read only, as task 0089
      did);
   3. otherwise RESULTS.md's tables, marked
      `"precision": "rounded from RESULTS.md"` per level.

   - **Then delete `validation/stenosis/work/`** (2.0 GB; approved by
     the user, 2026-11-02).  Delete it only after its `results.json`
     is written, validates, and reproduces its gates (step 5).  Delete
     by that exact path; never with a pattern.  Record the space freed.
   - Any other `validation/*/work/` you find: same, once its data is
     in `results.json`.

   **Don't rerun OpenFOAM** for this task.  List under *Outcome* each
   case and level whose data is only rounded, with the rerun's cost
   (from RESULTS.md's timings), so the user can schedule reruns on a
   quiet machine.
5. **Recheck tool:** `python3 -m validation.tools.recheck [case …]`
   recomputes every Richardson row and gate from the stored files and
   prints a table like task 0089's.  No OpenFOAM.

**Accept.**
- Each of the eight cases has a `results.json` valid against the
  schema, under 1 MB.
- `tests/test_validation_meta.py`:
  - every case has one;
  - the recheck reproduces each case's gates from it.  A case marked
    rounded must reproduce RESULTS.md's gate verdicts, not its digits.
- One driver run end to end (the cheapest: heated_rod or
  layered_conduction, no OpenFOAM time to speak of) writes the file,
  and a second run reuses every level.
- *Outcome*: the table of cases × levels with their precision (full /
  rounded) and, for rounded ones, the rerun cost.
- `validation/stenosis/work/` is gone, and the driver's default run
  leaves no `work/` behind (tested on the cheap case).
- Full suite: no new failures.

**Out of scope.**  Rerunning OpenFOAM cases; storing fields or meshes
(the `.msh` recipe of task 0091 covers rebuilding meshes); changing any
gate.

## Agent notes

- **Tests:** they went into `tests/test_validation_meta.py`, as **Where**
  says.  The recheck test is step 3's check: for a rounded case the
  stored digits are RESULTS.md's, so only the verdicts are compared.
- **Driver wiring.**  Each driver uses `validation/tools/results.py`:
  `Store`, `run_level`, `add_arguments`.
  - Level names: heated_rod `{series}-{k}`; layered_conduction
    `{variant}-{k}`; heated_pipe `k{k}`; poiseuille and stenosis by
    level; womersley `k2`, `k2-dt2`; stenosis_pulsatile `k2`,
    `k2-co0.25`; rect_duct `ar{r}_k{k}` and `cart_ar{r}_k{k}`, as their
    case directories.
  - Case-wide values go in `extra`: exact solutions, rect_duct's series
    check, the pulsatile phases, and the stenosis reference centreline
    (the database file carries no licence, so only the 18 centreline
    values used by the gate are stored).
  - womersley and stenosis_pulsatile keep the halved level's case until
    the Δt-halved run, which warm-starts from it, has finished.
  - Each driver's `recheck(data)` gives the rows `validation.tools.recheck`
    prints, exit 1 on a failing gate.
- **Filling** (scratch script, not committed):
  - full: heated_rod (driver run end to end on v1912, e54faae);
    rect_duct (task 0071's JSON, all 18 levels);
  - stenosis rebuilt from its stored k2–k4 fields and logs, read only.
    Steady times, wall times, step counts and every flow value equal
    RESULTS.md.  `min_scaled_jacobian` comes from RESULTS.md (it needs
    the mesh), `changes` holds the last pair of states only;
  - the rest from RESULTS.md's tables, `rounded from RESULTS.md`.
    stenosis_pulsatile's flow-feature verdicts are stored as RESULTS.md
    judged them (`extra.feature_verdicts`); the profiles they came from
    are lost.
- **Encodings:** the 42 text opens in `validation/` now pass
  `encoding="utf-8"`, and the architecture rule covers `validation/`
  (task 0092's CI found the same gap in `tests/` and `docs/`).

## Questions for design

Neither blocks this task: they are readings to confirm before a rerun
relies on them.

1. **Gate readings.**  Three gates in RESULTS.md are words; the recheck
   needs a number.  I used:
   - layered_conduction "L2 order ≈ 2": within ±0.2 (`ORDER_TOL`);
   - layered_conduction "balanced": |energy balance| ≤ 1e-8
     (`BALANCE_TOL`; stored values are 5e-12 to 1.2e-9);
   - rect_duct's control "observed order near 2": within ±0.2.

   Every case passes with these readings, at margins of 0.07 or more.
   Confirm them, or set them, before a rerun relies on them.

   **Design answer (2026-11-03): accepted as read** (the user: "accept
   the 0093 gate readings").  They are now the gates, written as
   numbers in `case.json` and so in `docs/GALLERY.md`:
   - layered_conduction, L2 order per region: 2 ± 0.2;
   - layered_conduction, energy balance: |imbalance| ≤ 1e-8, relative
     to the heat in;
   - rect_duct's control, observed order: 2 ± 0.2, with status
     `converging` (task 0089).

   `run.py`'s `BALANCE_TOL` and `ORDER_TOL` match.  Their comments still
   call them a reading and say that no tolerance was set in advance;
   update them when the files are next touched.
2. **stenosis_pulsatile's feature gate** can't be recomputed from what is
   stored: it is RESULTS.md's judgement.  A rerun will store
   `comparison`, with `features` and `dns_features` per phase.  Should
   the recheck derive "present as in the DNS" from them, and by what
   rule?

## Outcome

Done 2026-11-03.

**Files.**
- New:
  - `validation/tools/results.py`: the store, the shared
    reuse/cleanup helper, deterministic capped writes, recheck rows;
  - `validation/tools/recheck.py`;
  - `validation/results.schema.json`;
  - eight `validation/<case>/results.json`.
- The eight `run.py` drivers: write `results.json` by default, reuse full
  levels, delete each level's case once stored (`--keep-work` keeps it,
  a failure keeps it and says where), `recheck(data)`; `encoding=`.
- `tests/test_validation_meta.py`: +23 tests (every case has a file,
  valid, ≤ 1 MB, no CR, byte-identical rewrite; the recheck's gates
  pass per case; the CLI exits 1 on a failing gate; schema rejections;
  the store reuses, reruns rounded levels, removes `work/`, keeps a
  failed case, refuses over 1 MB).
- `tests/test_validation.py`: the OpenFOAM tests read the new shape.
- `tests/test_architecture.py`: the encoding rule covers `validation/`.

**Stored results.**  `*` marks levels rounded from RESULTS.md.

| case | levels | size | rerun cost of the rounded levels (RESULTS.md) |
|---|---|---|---|
| poiseuille | coarse\*, medium\*, fine\* | 3.4 kB | not recorded; minutes (v1912, 0.33 M cells at most) |
| heated_rod | uniform-1…16, graded-1…16 | 12.7 kB | — (full) |
| layered_conduction | fixed-1\*, -2\*, -4\*; convection-1\*, -2\*, -4\* | 5.2 kB | not recorded; minutes (7.3 k cells at most) |
| heated_pipe | k1\*, k2\*, k3\* | 2.5 kB | 833 + 7 631 + 50 507 s solver time: about 16 h |
| womersley | k1\*, k2\*, k4\*, k2-dt2\* | 5.2 kB | per period 30 s, 140–240 s, 8 500–9 700 s, 250–370 s; 3, 3, 2, 2 periods: about 6 h |
| stenosis | k2, k3, k4 | 274 kB | — (full, from the stored fields) |
| stenosis_pulsatile | coarse\*, k2\*, k3\*, k2-co0.25\* | 3.2 kB | 3 periods at 2.5 min, 48 min, 6.8 h, and 2 at 95 min: about 26 h on 4 cores |
| rect_duct | ar{1,2,4}_k{1,2,4}, cart_… (18) | 22.8 kB | — (full) |

heated_pipe's dT_b/dx (order 1.54 from the rounded table, 2.03
measured, task 0089) is the reason to rerun heated_pipe first.

**Recheck** (`python3 -m validation.tools.recheck`): every gate of the
eight cases passes, exit 0.  The Richardson orders match task 0089's
table: equal for rect_duct, and equal to its precision for the rounded
cases.  heated_rod's orders (1.30 and 1.35) are RESULTS.md's; 0089's
1.286 and 1.371 came from the rounded per-level errors.  stenosis's
x_sep order 3.53 is RESULTS.md's; 0089's table had 4.026, also from
rounded values.

**Acceptance.**
- Eight `results.json`, valid against the schema, 2.5–274 kB.
- Meta tests: 28 passed in `test_validation_meta.py`.
- heated_rod run end to end wrote the file; a second run reused all ten
  levels; no `work/` remained.
- `validation/stenosis/work/` is deleted (see Disk space).
- Full suite: 2270 passed, 15 skipped, no failures (with task 0092's
  Windows fixes).  The files changed after that run pass again:
  test_architecture, test_validation_meta, test_validation and
  test_convergence, 79 passed.  A heated_rod rerun reused all ten
  levels, left `results.json` byte-identical and left no `work/`.

**Surprises.**
- `json.dumps(sort_keys=True)` sorts int keys numerically (1, 2, 4,
  …, 1000), but they read back as strings, which sort lexically.  So a
  rewrite of rect_duct's file wasn't byte-identical.  `results._finite`
  now makes keys strings first; the meta test checks the rewrite.
- `dict.get(key, default)` evaluates its default, so a rounded level
  without the raw fields raised in womersley's recheck; now an explicit
  `if key in`.

**Disk space.**
- Freed: `validation/stenosis/work/`, 2 098 390 904 bytes (2.10 GB);
  free space 41 → 43 GB.
- Used: the stenosis repost read the fields in place.  heated_rod's run
  wrote under its `work/`, removed by the driver.  rect_duct's scratch
  (674 MB in this session's scratchpad) is deleted after the commit.
- Committed: 330 kB of `results.json`.

**Proposed follow-ups.**
- Rerun the rounded levels on a quiet machine, heated_pipe first.  A
  plain `run.py` rerun replaces each rounded level, and keeps the full
  ones.
- The validation drivers write OpenFOAM dictionaries without
  `newline="\n"`.  That is harmless on Linux, but on Windows with the
  Docker runner they would be CRLF (decision 0039, as task 0092 did for
  `io/writers/openfoam.py`).
