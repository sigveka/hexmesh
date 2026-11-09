# 0119 — Volunteer runs: the tool, the runners, and the helical pipe's card

- **Status:** ready
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
