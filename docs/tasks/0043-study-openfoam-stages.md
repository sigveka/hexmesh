# 0043 — Study runner: OpenFOAM case and run stages, shared OpenFOAM helpers

- **Status:** ready (after 0042)
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

_None yet._

## Questions for design

_None._

## Outcome

_Not done._
