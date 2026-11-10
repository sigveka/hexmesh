# 0119 — Volunteer runs: the tool, the runners, and the helical pipe's card

- **Status:** done
- **Decision:** [0044 — Volunteer runs](../decisions/0044-volunteer-runs.md); [0012](../decisions/0012-openfoam-validation-cases.md) (validation, toolchain)
- **Depends on:** 0075's driver (resumable, mapped start).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Decision 0044: someone with cluster time should be able to
run a held validation case with five commands, knowing beforehand what
it costs, and send back one small file that we check mechanically.  The
helical pipe's last level (Re 3000, nang 24; task 0075, held for
hardware) is the first card.

**Where.**  `validation/volunteer.py` (new), `validation/contrib.schema.json`
(new), `validation/helical_pipe/volunteer.json` and its driver,
`validation/VOLUNTEERS.md` (generated), `hexmesh/study/openfoam.py`
(runners), `validation/tools/results.py`, `CONTRIBUTING.md`,
`tests/`.

**Do.**
1. **Runners** in `hexmesh/study/openfoam.py`: `path` (OpenFOAM already
   on PATH), `apptainer:<image>`, and `native` with `HEXMESH_OPENFOAM_RC`.
   Each checks the OpenFOAM version against a required one (refuses a
   different one unless `--allow-version`) and records it.
   - `apptainer:` mounts as `docker:` does.  Apptainer isn't installed
     here: write the runner, test its command construction, and say in
     the card that it is unverified until a first run.  If the user
     installs Apptainer, verify it on a small level.
2. **The tool**, `python3 -m validation.volunteer`:
   - `list`: every card, with its requirements table;
   - `prepare <case> <level> --dir D [--mesh-only]`: mesh, case,
     the mesh hash, and `D/job.sh` (Slurm directives from the card,
     commented so `bash D/job.sh` also works);
   - `run D` (what `job.sh` calls): solve, resumable;
   - `collect D`: writes `<case>-<level>.contrib.json`;
   - `check FILE [--merge]`: schema, mesh hash recomputed with
     `prepare --mesh-only`, `recheck` on the level, and with `--merge`
     the level stored in `results.json` with the credit.
   It reuses the case's driver functions; a driver exposes `prepare`,
   `run` and `collect` hooks rather than the tool copying its logic.
3. **The mesh hash:** SHA-256 over the mesh as written.  Check that two
   `prepare --mesh-only` runs give the same hash, and that a Docker-run
   prepare and a native one do.  If bytes differ for reasons that aren't
   the mesh (e.g. a comment, a date), hash a canonical form (nodes
   rounded to 1e-12, cells, physical groups) instead, and say which.
4. **The contribution file** and its schema: as decision 0044 lists.
   `check` treats it as data only.
5. **The helical pipe's card** (`volunteer.json`), for Re 3000, nang 24
   (with its nang 16 mapped source, which `run` does first):
   - requirements from 0075's runs, each labelled *measured* or
     *estimated*: wall time (Re 2400 nang 24: 398 steps, 5.6 h on 4
     processes, measured; Re 3000 estimated from it), disk (about 1.6 GB
     per case, measured), cells (2.71M);
   - **measure peak memory** (`/usr/bin/time -v` or the scheduler's
     equivalent) on the nang 16 level here, and scale it to nang 24 by
     cells; label it estimated;
   - the gates quoted from `case.json`.
6. **`VOLUNTEERS.md`:** generated from the cards (like the gallery),
   with a stale-file test.  It opens with the five commands, then one
   section per card.  Plain words; no internal task numbers in the
   volunteer-facing text.
7. **A dry run end to end here** on a small level (nang 12, Re 1800, the
   Docker runner, 4 processes): `prepare` → `bash job.sh` → `collect` →
   `check --merge` into a scratch copy of `results.json`.  The merged
   level must equal the stored one within `recheck`'s tolerance.  Delete
   the run after.
8. **CONTRIBUTING.md:** a short "Run a validation case" section
   pointing to VOLUNTEERS.md (design reviews the wording).

**Accept.**
- The dry run passes `check` and reproduces the stored nang 12 level.
- `list` and VOLUNTEERS.md show the helical card with every requirement
  labelled measured or estimated.
- A tampered contribution (a changed number, a wrong mesh hash, a
  missing field) is rejected by `check`, each with a clear message
  (tests).
- Full suite: no new failures; no OpenFOAM needed for the tests except
  under `-m openfoam`.

**Out of scope.**  Running Re 3000 nang 24 here (held); the Vattenfall
card (task 0120); other schedulers than Slurm (the script also runs
with `bash`); creating GitHub issues (the user's).

## Agent notes

- **Order.**  The user chose 0119 next (2026-11-10).
- **The driver's hooks.**  `run_level` is split into `setup_level`,
  `_map_fields` and `solve_level` (the same steps, in the same order).
  `prepare`, `run`, `collect` and `recompute` reuse them.  A run
  directory holds the level's case in `case/` and, for a mapped level,
  the coarse start in `source/` until it is mapped.
- **`check`'s "recheck on the level"** is three mechanical steps:
  1. the driver's `recompute(values)` re-derives every number that
     follows from the level's raw ones (f per turn pair from the turn
     means, f, Re, Ito, the cell count from the assembly), each to
     1e-9 relative;
  2. where `results.json` already holds the level, the card's
     `reproduce` quantity (f) must agree within its tolerance (1e-4
     relative, fixed before the dry run);
  3. the case's `recheck` runs on a copy of `results.json` with the level
     merged, and its gate rows are printed.
- **What `check` can't prove:** that the solver ran.  Raw numbers
  invented consistently (turn means and bulk velocities) pass steps 1
  and 3.  They pass step 2 only for a level already stored.  The log
  tail and checkMesh's summary are evidence, not proof.
- **Step 3, the mesh hash: a canonical form, not the bytes.**
  - The `$Comments` block names the hexmesh and gmsh versions.
  - gmsh 4.15.2 writes 20 of the nang 8 mesh's 109 516 node lines one
    ulp away from 4.12.1's (at most 1.4e-17 m); elements and groups are
    identical (`docs/integrations/gmsh.md`).
  - So the hash covers the physical names, the elements, and node tags
    with coordinates rounded to 1e-12.
  - Measured:
    - two `prepare --mesh-only` runs of `re1800_n12` give the same hash;
    - so do gmsh 4.12.1 and 4.15.2 (`b3e271a7…`);
    - the dry run's prepare under Docker gave it as well.
  - Docker against native: the mesh is written by gmsh in Python before
    any OpenFOAM step, so the runner can't change it.  The native runner
    here is v1912, which `require_version` refuses without
    `--allow-version`.
- **Peak memory** is sampled every 2 s.  It is the sum over the run's
  child processes (`/proc`) plus its Docker containers (`docker stats`;
  their processes aren't children).  On Slurm, `sacct`'s MaxRSS is the
  scheduler's equivalent; the card says neither.
- **Runner choice** without `--runner`: `HEXMESH_OPENFOAM`, then
  OpenFOAM on PATH (`path`), the native bashrc, Apptainer, Docker (with
  the card's image), so the five commands need no runner flag.
- **Apptainer** isn't installed here.  The runner is written, and its
  command line is tested (binds, `--pwd`, `--cleanenv`).  The card's
  text doesn't call it verified.
- **Offered and other levels.**  `prepare` takes any level the driver
  knows.  A level without a card entry gets a note and a `job.sh`
  without time or memory lines.  The dry run used one.
- **The user (2026-11-10):** VOLUNTEERS.md says this is a trial of a
  volunteer framework, to take the validation cases beyond what the
  user can run alone (its opening paragraph, from `render()`).
- `job.sh` asks Slurm for 1.5 times the card's wall time and memory.  It
  runs the tool with the Python that prepared it (a volunteer's venv).

## Questions for design

1. **The hexmesh tag.**  The card's `hexmesh.tag` is `null`;
   VOLUNTEERS.md says "the first release with this tool".  The mesh
   check needs the volunteer's hexmesh to mesh as ours does, so the
   card should name a release.  Which one: a 0.5.1 with this tool, or
   the next minor?
2. **CONTRIBUTING.md wording** (step 8, for review): the new section
   "Run a validation case".
3. **The card's numbers are mostly estimates.**
   - Wall time: 8.3 h, scaled by steps from Re 2400.
   - Memory: 3.4 GB, the solve scaled from nang 16; making the fine mesh
     was measured at 3.2 GB.
   - Disk: 4 GB.
   - Is that enough for the `volunteer-run` issue, or should one Re 3000
     nang 16 solve be measured to completion first (about 1 h here)?

## Outcome

**The dry run passes** (nang 12, Re 1800, v2406 in Docker, 4 processes,
2026-11-10):

| stage | result |
|---|---|
| `prepare` | 3 min 13 s; mesh hash `b3e271a7…`; checkMesh OK, 338 688 cells |
| `bash job.sh` | converged in 211 steps (stored: 210), 17.8 min, peak memory 0.51 GB |
| `collect` | 16 kB contribution, 200 log lines, run directory deleted |
| `check --merge` (scratch copy of `results.json`) | accepted: mesh hash matches; f 0.0671523628 vs stored 0.0671523625, +4.9e-9 (tolerance 1e-4); all gates pass as before; merged with the credit under `environment.contributed` |

**The helical card** (`validation/helical_pipe/volunteer.json`, level
`re3000_n24`); every number is labelled:

| requirement | value | basis |
|---|---|---|
| cores | 4 | measured (our nang 24 runs) |
| wall time at 4 cores | 8.3 h | estimated: Re 2400's measured 52 min + 5.6 h, scaled by Re 3000's steps at nang 16 (720/561) |
| prepare time | 0.5 h | estimated: fine mesh 7 min measured; conversion scaled from nang 16's measured 4.5 min |
| peak memory | 3.4 GB | estimated: the solve at np 4 measured 1.0 GB at nang 16, scaled by cells; meshing nang 24 measured 3.2 GB |
| peak disk | 4 GB | estimated: the fine case's measured 1.6 GB, doubled while decomposed, plus the coarse start's 0.25 GB |
| cells | 2 711 232 | measured |

Measurements on this desktop (8 cores, 15 GB), 2026-11-10:
- `--mesh-only`, peak memory and wall time:
  - nang 12: 0.62 GB, 2.1 min;
  - nang 16: 1.15 GB, 3.2 min;
  - nang 24: 3.22 GB, 7.1 min.
- Setting up the nang 16 case: gmshToFoam with checkMesh peaked at
  0.75 GB; with meshing, 7.7 min.
- One 50-step chunk at nang 16 and np 4: 1.01 GB peak; the case is
  0.25 GB.

**Tests** (`tests/test_volunteer.py`, 25; no OpenFOAM):
- the `path` and `apptainer:` command lines, Docker-only container
  names, bad runners, `HEXMESH_OPENFOAM_RC`, `require_version`;
- every card requirement labelled, VOLUNTEERS.md current and free of task
  numbers, `job.sh` valid bash with Slurm lines;
- the mesh hash ignores comments, CRLF and last-digit differences, but
  not a moved node or a changed element;
- `check` accepts and merges a good contribution, and rejects each of
  these, with a message naming it:
  - a changed f;
  - a wrong mesh hash;
  - three missing fields;
  - a level that is consistent in itself but differs from the stored
    one;
  - an oversized file.

**Files.**
- `validation/volunteer.py` (new);
- `validation/contrib.schema.json` (new);
- `validation/helical_pipe/volunteer.json` (new);
- `validation/VOLUNTEERS.md` (generated);
- `validation/helical_pipe/run.py` (the hooks);
- `hexmesh/study/openfoam.py` (runners, `require_version`);
- `hexmesh/errors.py` and `API.md` (`openfoam_version_mismatch`; the
  runners);
- `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/integrations/gmsh.md`;
- `tests/test_volunteer.py`.

`validation/tools/results.py` didn't need a change: `Store.put(env=…)`
carries the credit.

**Suite:** 4021 passed, 15 skipped, 1 failed (27 min).  The failure,
`test_text_io_names_its_encoding` (decision 0039), was in this task's
new tests and in task 0117's evidence script, already pushed in
6dcc95e.  Both are fixed here (`encoding="utf-8"`, `newline="\n"` for
the OpenFOAM dictionaries).  After the fix, the architecture and
volunteer tests pass (94); the full suite wasn't rerun.

**Deleted:** the dry run, the measurement cases and meshes, the gmsh
4.15.2 venv.

**Follow-ups:**
- the `volunteer-run` issue for the card (the user's);
- an Apptainer run on a machine that has it;
- task 0120's Vattenfall card.

## Design answers (2026-11-10, the user: "yes, send them and create the tag")

1. **The tag:** `volunteer-helical-1`, an annotated tag on de1d477 (not
   a release: 0.6 waits for equal tees).  The card names it, and the
   "main branch" note is gone.  At the tag the card itself still says
   null and shows the estimates.  That is harmless: `prepare` and
   `check` never compare the card's tag with the checked-out code; the
   tag is only shown in VOLUNTEERS.md.
2. **CONTRIBUTING.md:** the first two sentences replaced with design's
   wording; the rest kept.
3. **Measure before the issue goes out:** run the card's first stage
   here (Re 3000, nang 16, about 1 h), then one 50-step chunk at nang 24
   from it (about 45 min) under `/usr/bin/time -v`.  Relabel peak
   memory, peak disk and time per step as measured; wall time stays
   estimated (measured s/step × scaled steps, basis stated).  Disk and
   other runs checked first, cases deleted after.  The issue waits for
   these numbers.  Done 2026-11-10: below.
4. The full suite is to be rerun after the encoding fix (in 0122).

## The Re 3000 measurement (2026-11-10, answer 3)

Run alone at 4 processes, Docker v2406, under `/usr/bin/time -v`; peak
memory sums the run's processes and containers every 2 s (the volunteer
tool's PeakMemory), peak disk is `du` of the run directory every 20 s.
A first attempt was stopped by Claude Code's memory guard during the
map stage (with task 0127's nang 64 meshes running); its numbers agree.

| stage | wall time | peak memory | peak disk |
|---|---|---|---|
| prepare (both meshes, coarse start) | 27 min | 2.6 GB | 1.1 GB |
| coarse solve, nang 16 (converged, 788 steps, f 0.04918) | 71 min, 5.4 s/step | 1.1 GB | 1.7 GB |
| map to nang 24 (coarse case deleted) | 1 min | 1.8 GB | 1.7 GB |
| first fine chunk, nang 24 (50 steps) | 58 min, 70 s/step | 3.6 GB | 2.4 GB |

**Caveat on 70 s/step:** this session's own test runs (`pytest -n 4`,
tasks 0125 and 0123) overlapped part of the fine chunk, against the
shared-machine rule; and a 50-step chunk carries its decompose and
reconstruct.  So it is an upper bound.  Re 2400's fine rate was 51
s/step, also partly shared.

**The card** (`validation/helical_pipe/volunteer.json`, VOLUNTEERS.md
regenerated): prepare time 0.45 h, peak memory 3.6 GB and peak disk
2.4 GB are now *measured* (only the latest result is kept, so the disk
stays there); wall time stays *estimated*, now 12 h as an upper bound
(1.2 h coarse + about 560 fine steps, scaled from Re 2400's 398/563, at
70 s/step), about 9 h at Re 2400's rate; the summary says "9 to 12
hours".  The coarse solve needed 788 steps, not the 720 the earlier
estimate assumed.  `tests/test_volunteer.py`: 25 passed.  Deleted: the
run directory.
