# 0043 — Study runner: OpenFOAM case and run stages, shared OpenFOAM helpers

- **Status:** done
- **Decision:** [0025 — Study runner](../decisions/0025-study-runner.md)
- **Depends on:** 0042.  Coordinate with any validation task in
  progress (0034, 0035): they use the code being moved.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The validation scripts each carry their own case writer,
OpenFOAM runner and field readers (`validation/poiseuille/run.py`:
`write_case`, `foam`, `read_points` … `results`;
`validation/heated_rod/run.py` likewise).  A study needs the same, for
any case.

**Where.**  New `hexmesh/study/openfoam.py`; `hexmesh/study/stages.py`;
`hexmesh/io/writers/openfoam.py` and `openfoam_boundary.py` (role
manifest, `write_openfoam`); the two validation `run.py` files;
`docs/integrations/openfoam.md` (v1912 quirks: function objects abort,
coded BCs fail).

**Do.**
1. **Shared helpers** in `hexmesh/study/openfoam.py`, moved from the
   validation scripts (not rewritten): the dictionary header writer,
   running a utility with a log (`foam(cmd, case, log)`), mesh conversion
   (`gmshToFoam`, and `splitMeshRegions` for multi-region), and the
   readers for points, faces, owner/neighbour, zones, internal fields and
   patch values.  Port the Poiseuille and heated-rod scripts onto them
   and show their results are unchanged (re-run one level of each, or
   compare on saved cases).
2. **case stage:** the study file names a case template directory (an
   OpenFOAM case without a mesh).  Per variant: copy it, convert the
   mesh, retype the patches from the role manifest (decision 0013), and
   substitute `$name` placeholders from the variant's parameters in the
   template's dictionaries (whole tokens, the same rule as 0042).
3. **run stage:** the study file gives a command (run in the case
   directory, e.g. `./Allrun`), `cores_per_job`, and a post-processing
   function (`module:function`, called with the case path and the
   parameters, returning a dict).  At most `--jobs` cases at once, so
   that `jobs × cores_per_job` stays within the machine and the
   shared-machine rules.  Record exit status, wall time, log paths and
   the result dict in the manifest.
4. Before a run stage, check for another session's OpenFOAM or pytest
   runs (CLAUDE.md) and refuse with a message unless `--force`.
5. A failed case (non-zero exit, missing result) is recorded, not fatal.

**Accept.**
- Validation scripts on the shared helpers: results identical to their
  last `RESULTS.md` (or a stated reason).
- A 2-variant laminar straight-pipe study (`-m openfoam`, opt-in)
  goes through case and run stages: a manifest row each, with Δp from
  the post-processing function.
- Placeholders in a template dictionary substituted; an unknown one is an
  error naming the file.
- Re-running skips finished cases; a deliberately broken case is
  recorded as failed and the other completes.
- Default `pytest` run unchanged (OpenFOAM tests opt-in).

**Out of scope.**  Job schedulers (SLURM etc.), remote execution,
turbulence-model setup (lives in the user's case template).

## Agent notes

- **Moved, not rewritten.**
  - From the Poiseuille script: `header` (was `_header`), `foam`, the
    seven readers and `latest_time` (was `_latest_time`).
  - From the heated-rod script: `face_geometry` and `cell_geometry`.
  - The Poiseuille script imports the moved helpers under their old
    names, so the heated-rod script and the paused stenosis draft (0032)
    keep calling `pois.foam` and the rest.
  - `richardson` and `versions` stay in the Poiseuille script: they are
    analysis, not OpenFOAM.
- **New in the module:** `convert` (gmshToFoam with role retyping, and
  splitMeshRegions per region), `check_mesh`, `have_openfoam`,
  `openfoam_version` and `substitute_case`.
- **Placeholders in OpenFOAM dictionaries.**  OpenFOAM uses `$name`
  itself (`$internalField`, `$FOAM_CASE`), so "an unknown placeholder is
  an error" needs a rule for those.
  - A `$name` is OpenFOAM's when `name` is a keyword on another line of
    the same file, or starts with `FOAM_` / `WM_`.  Otherwise, without a
    parameter, it is an error naming the file.
  - `nu $nu;` is a placeholder: an entry can't refer to itself.
  - Substitution runs on whole tokens (`$D` vs `$Dmax`); `$$` is a
    literal `$`.
- **Stages** are now preflight → mesh → case → run.  The default
  `--stage` is the last stage the study file configures.  Each stage
  records a fingerprint:
  - a case is redone when the network, the template's files or the
    parameters change;
  - a run is redone only when the case or the command changes.

  A failed run is not retried automatically: change the case or
  command, or delete `run.json`.
- **Other sessions' runs** (step 4): `other_runs()` looks in `/proc` for
  pytest, `*Foam` and `mpirun` processes.  It leaves out this process,
  its ancestors and its own children; siblings, such as other xdist
  workers, count.  The opt-in test passes `force=True` for that reason.
- **`jobs × cores_per_job`** over `os.cpu_count()` is a `StudyError`, not
  a silent clamp.

## Questions for design

_None._

## Outcome

**Files.**
- New: `hexmesh/study/openfoam.py`.
- `hexmesh/study/stages.py`: `case_stage`, `run_stage`, `other_runs`,
  fingerprints, `load_case_run`.
- `definition.py`: `case` and `run` blocks.
- `__init__.py`: `run` through all four stages, plus `--force`.
- `manifest.py`: `run_exit` / `run_time` / `run_log` columns and
  `result.<key>` columns.
- `__main__.py`: `--force`.
- `validation/poiseuille/run.py` and `validation/heated_rod/run.py` now
  use the shared helpers.
- Docs: `API.md` and `README.md` (study runner).
- Tests: `tests/test_study.py`, +8: seven in the default run, and one
  opt-in `-m openfoam`.

**Validation scripts unchanged** (re-run 2026-10-28 on the shared
helpers):
- Poiseuille, coarse: Δp 8.036058e-05 and u_max 9.906548e-03, 125
  iterations, identical to `RESULTS.md` to every printed digit.
- Heated rod, level 1: uniform ΔT₀ error −1.3772 %, graded −1.7155 %,
  and the L2 and max errors, identical to `RESULTS.md`.

**Acceptance.**
- A laminar straight-pipe study (`-m openfoam`, about 2 s), Re 10 and 20
  plus one broken variant:
  - case and run stages give one manifest row each;
  - Δp from the post-processing function is within 10 % of Poiseuille,
    and doubles with U to 2 %;
  - the broken variant (`nu` = `"broken"`) is recorded `run_failed` and
    the other two complete;
  - re-running skips all three (no `run.json` rewritten).
- Placeholders are substituted.  An unknown one fails the case:
  "constant/transportProperties: unknown placeholder(s) $nu".
- Default `pytest` is unchanged apart from the new default-run tests.

**Suite:** 1805 passed, 5 skipped (was 1796; +8 here, the rest from another session's work in the tree).  Opt-in study test: 1 passed.

**Follow-ups.**
- 0032 (stenosis), 0034, 0035, 0049 and 0050 build on
  `hexmesh.study.openfoam`.
- The aligned export doesn't yet carry result fields: a `post` that
  returns arrays would need a convention (decision 0025, item 5).
