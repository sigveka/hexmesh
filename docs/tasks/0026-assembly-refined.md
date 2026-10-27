# 0026 — `Assembly.refined(k)`: uniform refinement for convergence studies

- **Status:** done
- **Decision:** [0015 — Exact walls in straight slabs, and how convergence is judged](../decisions/0015-exact-straight-slabs-and-convergence-studies.md) (Q3)
- **Depends on:** —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  A grid-convergence study needs the same network at k× the
resolution in every direction.  hexmesh has no global refinement
(CLAUDE.md, "Resolution and cell count").  Task 0020 scales `nang`,
`nrad` and every `n_layers` by hand; every study on a real network
would repeat that, fitting by fitting.

**Where.**
- `hexmesh/assembly/assembler.py`: `Assembly`, next to `to_dict` /
  `from_dict`.
- `hexmesh/assembly/intent.py`: the fitting registry and fields.
- `hexmesh/core/spec.py`: `PipeSpec` (perhaps a `PipeSpec.refined(k)`
  helper).
- `API.md` (Assembly), `README.md` (a short note), tests.

**Do.**
1. `Assembly.refined(k: int) -> Assembly`: a new assembly, built from the
   saved description (`to_dict` → scale → `from_dict`).  The original is
   unchanged.  `k` is an integer ≥ 1; reject anything else with a
   message.
2. **What scales**, everywhere a spec or fitting appears (the inlet
   spec, `Reducer` outlets, drum nozzle specs, …):
   - `nang` × k and every layer's `nrad` × k;
   - every axial count × k: `n_layers` of every fitting, and `Tee`'s
     `n_run`, `n_branch` and `n_turn`.  For `MiterBend`, `n_layers` is
     per end leg (inner segments get twice that), so × k keeps the
     ratio;
   - radial `mprg` → `mprg ** (1 / k)` and `axial_grading` →
     `axial_grading ** (1 / k)`, so the graded spacing keeps its shape:
     every coarse cell is split into k cells of the same growth.
3. **What doesn't:** geometry (radii, lengths, angles, `roll`, poses),
   layer names and order, `n_outer`, `rot`, `mbmp`, and every fitting
   type.  So topology is unchanged (DESIGN: topology vs density).
   - `first_cell` is stored as the resolved `mprg`, so after
     `refined(k)` the first cell is smaller.  Say so in the docstring.
   - Check whether any fitting has an axial count that × k would break
     (a validation limit such as the 30° per layer turn only gets
     easier).  Record anything found.
4. Docstring and `API.md`: one line on cost.  Doubling every count gives
   8× the cells, so `refined(k)` gives k³ × the cells.
5. Use it in `validation/poiseuille/run.py` in place of the hand-scaled
   `assembly(factor)`, if task 0020 hasn't been re-run yet; otherwise
   leave a note for it.

**Accept.**
- `refined(k).cell_count() == k**3 * cell_count()` exactly, for every
  conformance-kit case and k = 2, 3.
- `refined(1).to_dict() == to_dict()`.
- `refined(2)` passes `validate()` and meshes for every kit case with
  meshed = predicted (a subset if the run is too slow; record which).
- Port-face signatures (task 0019) of `refined(k)` differ from the
  original only in counts and grading: switch class 2, never 3.
- Graded spacing: for a `first_cell` spec, the radial node positions of
  `refined(2)` include every node of the original (each coarse cell is
  split in two, to 1e-12 R).  Same for an axially graded `Straight`.
- Full suite: no new failures.

**Out of scope.**  Non-integer factors, per-direction factors, and
refining part of a network (that needs density switches, decision 0003).

## Agent notes

- **Where.**  `intent.refined_dict(d, k)` (with `refine_spec_dict` and
  `AXIAL_COUNTS`) scales a `to_dict()` description, and
  `Assembly.refined(k)` wraps it.  No `PipeSpec.refined` was needed.
  - The rejection is one `ValueError` ("k must be an integer >= 1") for
    0, negative, float, string, bool and None.  `np.integer` is
    accepted.
- **What scales**, beyond the task list:
  - **`stack_changes` indices** (task 0018) are axial cell indices, so
    cell i becomes k·i, and their specs are refined too.  Kit case
    `straight-insulation-gap` covers it;
  - **drum nozzle specs** (`from_nozzle`): all of them, not only the
    one used;
  - **specs:** `nang_w` / `nang_h` (rect cores) and the shape's own
    `nang`.
  - `MiterBend.n_cuts` is geometry and does not scale.  Its `n_layers`
    does, which keeps the inner/end ratio.
- **Axial counts that could break: none found.**  Every limit is an
  upper bound on turn per layer, so k ≥ 1 only helps.  Every kit case
  validates and meshes at k = 2.
- **Graded nesting is 1e-8 R, not 1e-12 R.**  gmsh's `Progression`
  puts nodes about 1e-9 × the curve length off the closed-form series
  (coarse and fine alike).  Measured on a bare line, recorded in
  `docs/integrations/gmsh.md`.
  - Measured on a graded straight + reducer (`first_cell`,
    `axial_grading` 1.3 / 0.8): coarse nodes are found in `refined(2)`
    to 5.2e-10 m (4.4e-9 R).
  - Uniform meshes nest to rounding (1e-17), which a separate test
    checks.
  - `refined()` itself is exact: q^(1/k) gives the same closed-form
    positions.
- **Signatures:** every interface of every kit case is class 2 between
  original and `refined(2)`.  The differences are only `nang`, `nrad`
  and `mprg` (fields are named per layer, e.g. "core nrad").
- **Step 5:** task 0020 was re-run before this task, so
  `validation/poiseuille/run.py` keeps its hand-scaled `assembly(factor)`.
  It is equivalent here (uniform spacing, same counts).  Switching it to
  `assembly(1).refined(factor)` is a one-line change when it is next
  touched.

## Questions for design

_None._

## Outcome

- **Files:**
  - `hexmesh/assembly/intent.py` (`refined_dict`, `refine_spec_dict`,
    `AXIAL_COUNTS`);
  - `hexmesh/assembly/assembler.py` (`Assembly.refined`);
  - `tests/test_refined.py` (new, 168 tests);
  - `README.md` ("Convergence studies"), `API.md`;
  - `docs/integrations/gmsh.md` (the Progression entry; untracked).
- **Accept:**
  - cell count k³× for every kit case, k = 2 and 3: pass;
  - `refined(1).to_dict() == to_dict()`: pass;
  - **`refined(2)` validates and meshes, meshed = predicted, for all 27
    kit cases:**
    - 20 run in the suite (94 s);
    - the 7 slow ones (spline and closure cases, `bend-as-closer`) were
      checked once, 15–50 s each: all equal;
    - min SICN at k = 2, for instance: `closure-twisted` 0.1167 (0.1146
      at k = 1), `spline-3d-2layer` 0.2972.
  - signatures: class 2 only, never 3;
  - nesting: pass at 1e-8 R (see *Agent notes*; **the 1e-12 R target is
    below gmsh's own Progression accuracy**).
- **For design:** the nesting tolerance in the acceptance criteria.
  1e-8 R is what gmsh allows; nothing to decide unless a tighter nesting
  is needed (it would mean placing graded nodes ourselves).
- **Tests:** full suite 851 passed, 2 skipped (tee exactness), 0 failed.
