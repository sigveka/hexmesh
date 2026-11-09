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
