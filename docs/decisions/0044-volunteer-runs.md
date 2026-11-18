# 0044 — Volunteer runs: heavy validation cases that others can run and we can check

- **Status:** accepted (2026-11-09, the user: "Let us try to create some
  volunteer cases.  They must be easy to understand, clear about
  requirements (wall time etc.) and simple both to set up and to
  validate")
- **Date:** 2026-11-09
- **Tasks:** 0119 (the volunteer tool and the helical pipe's card);
  0120 (the Vattenfall T-junction, stage (a), and its card)

## Context

Some validation cases need more than the user's machine (8 cores, 15 GB,
limited disk): the helical pipe's last level (task 0075, held), and the
LES of the Vattenfall T-junction (decision 0012's amendment below).
Someone with cluster time could run them, but today that person would
need to read a driver, adapt it to a batch queue and a cluster's
OpenFOAM, and send back numbers we'd have to take on trust.

What exists (decision 0012, tasks 0089, 0090, 0108): one driver per
case, `--np` parallel runs, resumable chunks (0075), each level stored
with its environment (hexmesh commit, gmsh, Python, OpenFOAM, runner,
date), and `recheck`, which recomputes the convergence analysis and the
gates from `results.json` without OpenFOAM.  Missing: a runner for
clusters (no Docker; OpenFOAM from a module, or Apptainer), stages that
fit a batch queue, a proof that the volunteer's mesh is ours, a small
return package, and stated requirements.

## Options

### A. A how-to page only
Explain the drivers and let volunteers adapt them.  Cheap, but each
volunteer redoes the same work, and nothing proves what ran.

### B. One volunteer tool, a card per case, and a mechanical check (chosen)
A single command with the same four steps for every case; each case
states its requirements in a card; what comes back is one small file
that a maintainer checks with one command.

### C. Hosted runs (CI on rented hardware)
Not available without an account and money; out of scope.

## Decision (accepted: B)

**For the volunteer: five commands, the same for every case.**

```bash
git clone --branch <tag> https://github.com/sigveka/hexmesh && cd hexmesh
pip install -e .
python3 -m validation.volunteer list                      # cases and their requirements
python3 -m validation.volunteer prepare <case> <level> --dir run/   # mesh, case, job script
sbatch run/job.sh        # or: bash run/job.sh  (resumable: run it again after a stop)
python3 -m validation.volunteer collect run/              # writes one .contrib.json
```

They send the `.contrib.json` file back (a pull request, an issue
attachment, or e-mail).  Nothing else.

**The card** (`validation/<case>/volunteer.json`, one per offered
level), shown by `list` and in `validation/VOLUNTEERS.md` (generated;
a test fails when it is stale):
- one paragraph: what the case is, what it checks, and why it needs
  more hardware than ours;
- **requirements:** cores (recommended and minimum), peak memory, peak
  disk, **wall time at the recommended cores**, OpenFOAM version, the
  container image (or module), and the pinned hexmesh tag and gmsh
  version;
- **where each number comes from:** *measured* (on which machine, cores
  and date) or *estimated* (from which measured run, by what scaling).
  No unlabelled number;
- what is sent back, and its size;
- the gates, quoted from the case (fixed; a result is reported whether
  it passes or not).

**Runners** (`hexmesh.study.openfoam`, decision 0012's toolchain):
- `native` keeps sourcing a bashrc, now configurable
  (`HEXMESH_OPENFOAM_RC`), for installs outside `/usr/share/openfoam`;
- `path`: OpenFOAM already in the environment (a cluster `module load`);
- `apptainer:<image>` (e.g. `docker://opencfd/openfoam-default:2406`):
  Apptainer/Singularity, which clusters offer instead of Docker.
- Every runner checks the OpenFOAM version against the card's, and
  refuses a different one unless `--allow-version` is given; the
  version is recorded either way.

**Stages:**
- `prepare` (laptop or login node; gmsh, no MPI): the mesh, the
  OpenFOAM case, the mesh's SHA-256, and `job.sh` (Slurm directives from
  the card's requirements, commented so it also runs with `bash`).
- `run` (inside `job.sh`): the solve, resumable from the latest written
  time by running it again; it deletes old times as the driver does.
- `collect`: the `.contrib.json`, then it offers to delete the case.

**The contribution file** (`<case>-<level>.contrib.json`, JSON only,
well under 1 MB): the case and level; the level's results exactly as the
driver stores them; the environment; the mesh's SHA-256 and checkMesh's
summary; cores, wall time and peak memory; the last 200 lines of the
solver log; an optional contributor name for the credit.

**The check, for maintainers:** `python3 -m validation.volunteer check
<file>` validates the file against a schema, recomputes the mesh hash
locally (`prepare --mesh-only`, same hexmesh tag and gmsh version),
runs `recheck` on the level, and with `--merge` stores it in the case's
`results.json`, with the contributor's credit and the environment.
- **Accepted only if** the schema passes, the mesh hash matches and
  `recheck` reproduces the stored numbers.  A level that misses a gate
  is accepted and reported as a miss; the gates were fixed before.
- `check` reads data only: it never executes anything from the file.

**Which cases are offered:** a case gets a card only when its gates are
fixed and its driver has run a smaller level here, so the card's
numbers can be measured or scaled from a measured run.  First: the
helical pipe, Re 3000 at nang 24 (task 0119).  Next: the Vattenfall
LES, after its stage (a) (task 0120).

## Consequences

- **New:** `validation/volunteer.py` (the tool), `validation/<case>/
  volunteer.json` (cards), `validation/VOLUNTEERS.md` (generated),
  `validation/contrib.schema.json`.  A GitHub label, `volunteer-run`,
  with one issue per offered card (the user creates them).
- **`hexmesh.study.openfoam`:** the `path` and `apptainer:` runners and
  the configurable bashrc.  `HEXMESH_OPENFOAM` keeps its meaning.
- **CONTRIBUTING.md:** a short section pointing to VOLUNTEERS.md;
  contributed results are under the project's BSD-3 licence.
- **Credit:** `RESULTS.md` names the contributor and their machine for
  each contributed level.
- **Future expansions:** 0030 (simulation suite) is helped; the stages
  are the suite's batch shape.  0018, 0021, 0035, 0040: none.

## Verified vs. assumed

- **Verified:** the drivers' `--np`, resumable chunks and environment
  records (tasks 0090, 0075); `recheck` works from `results.json`
  alone; meshes are byte-identical for the same description, hexmesh
  and gmsh version and system (0.5.0 *Stability*).
- **Assumed:**
  - that the mesh hash matches across systems for the same hexmesh and
    gmsh versions (Linux to Linux; CRLF on Windows is known, so the
    hash is taken over the mesh's nodes and cells, not the file bytes,
    if the bytes differ: task 0119 checks);
  - that the `apptainer:` runner works as the Docker one does: no
    Apptainer is installed here, so the first volunteer run is also its
    first real test unless the user installs it (task 0119 says so);
  - the helical pipe's requirements beyond what 0075 measured (peak
    memory isn't recorded).

## Note (2026-11-18): the machine recorded automatically

The first volunteer run (task 0173: Windows 11, v2406 in Docker on 16
processes) showed two gaps in the contribution file.
- **The machine was free text, typed afterwards.**  The number that set
  the speed (Docker's VM had 20 CPUs and 31 GB of the host's 64 GB) is in
  the file only because the user knew to write it.  Times from different
  volunteers can't be compared without it.  The cards' "measured (on
  which machine …)" rule needs it too.
- **`wall_s` isn't solver time.**  It added up four `run` invocations,
  37 minutes of laptop sleep, and the restarts after the Windows fixes:
  12 730 s, against about 4 190 s of solving.

So (the user, 2026-11-18: "yes, write the decision note and the task"):
1. **`run` records the machine it runs on**, every time it starts.
   Through the Python standard library and the runner, without a new
   dependency:
   - the OS and its version, the architecture;
   - the CPU model, the logical CPUs, and the memory;
   - for a `docker:` runner, the engine's own CPUs and memory and its
     kind (`docker info`).  On Windows and macOS that is a VM, often
     smaller than the host, and it is what the solver gets;
   - on a scheduler, the node and task counts it gives (Slurm's
     `SLURM_JOB_NUM_NODES`, `SLURM_NTASKS`).
   `run` records it, not `collect`: on a cluster, `prepare` and
   `collect` run on a login node and the solve on compute nodes.
2. **An allow-list, nothing else.**  No hostname, user name, path,
   serial number, IP or MAC address, or job ID.  The CPU model string
   is kept as the system gives it.  `collect` prints the details before
   writing the file, and `--no-machine` leaves them out.  `--machine`
   stays: a free-text label ("HP ZBook laptop") beside the details.
3. **Solver time, apart from wall time:** `solve_s`, summed from the
   solver logs' `ClockTime` per chunk, for speed comparisons.  `wall_s`
   keeps its meaning.
4. **The file format stays version 1.**  The new fields are optional:
   `check` is always the maintainer's current code, and contributions
   from the volunteer tags simply lack them.  `check` reports a missing
   machine as a note, never a rejection.  The fields are stored with the
   level, and the credit in RESULTS.md is drawn from them when there is
   no label.

**Also learned from that run:** the mesh hash matched across systems,
Windows to Linux (Re 3000 at n_arc 24, merged with `check --merge`).
That was an assumption above (*Verified vs. assumed*), and it now holds
for that pair.

**Future expansions:** 0030 (the simulation suite) may want the same
record for its own runs.  The record lives in one self-contained
function under `validation/`, not in the public `hexmesh` API (frozen
at 1.0, decision 0042).  It can move to `hexmesh.study` as an addition
in 1.x if the suite asks for it.  0018, 0019, 0021, 0035: not affected.

## Note (2026-11-18): every heavy case gets a card, and one card to try the workflow

The user (2026-11-18): "make sure all of them are volunteer tasks.  I
also want a volunteer "test" that runs quickly and people can use to
test the workflow."
- **Cards:** every validation case with levels too heavy for the
  project's machine gets a card under the rule of *Which cases are
  offered* (the gates fixed, a smaller level run here).  These are the
  junction-flow points (task 0168, the hold lifted), the turbulent bend
  (0050), the Taylor bubble (0079) and the Vattenfall LES (0120).
- **A try-out card** (task 0176).  It is the exception to *Which cases
  are offered*, because it validates nothing new:
  - one level, a minute or two on a laptop.  It runs the whole path a
    real level takes: `prepare`, `run` on 2 MPI processes (so
    decomposition, `mpirun` and the processor clean-up are exercised:
    two of task 0173's Windows bugs were there), `collect`, and `check`,
    which the volunteer runs themselves on their own file;
  - its level is marked as a try-out in the card.  `check` accepts or
    rejects it as for a real level, but `--merge` refuses it: nothing
    from it is stored, and it gives no credit;
  - `list` and VOLUNTEERS.md show it first, as the step before picking
    a real level;
  - the CI job with OpenFOAM in Docker runs it end to end, so the
    volunteer path is tested on every push, not only at a tag.
