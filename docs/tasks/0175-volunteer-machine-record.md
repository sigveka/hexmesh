# 0175 — Volunteer runs record the machine and the solver time

- **Status:** ready
- **Decision:** [0044](../decisions/0044-volunteer-runs.md), its note of
  2026-11-18 (the machine recorded automatically)
- **Depends on:** none.  It touches `PeakMemory`'s neighbour in
  `validation/volunteer.py`, as task 0174 does: do them one after the
  other, not in parallel.
- **Blocks:** the next volunteer tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The first volunteer run (task 0173) recorded its machine as
free text typed afterwards.  Its `wall_s` (12 730 s) counted sleep and
restarts, against about 4 190 s of solving.  Times from different
volunteers can't be compared that way (decision 0044's note).

**Where.**  `validation/volunteer.py` (`cmd_run`, `cmd_collect`,
`check`, the state file in the run directory);
`validation/contrib.schema.json`; the credit in RESULTS.md and the
`VOLUNTEERS.md` generator if they show the machine;
`tests/test_volunteer.py`.

**Do.**
1. **`machine()`:** one self-contained function in `validation/`, with
   no new dependency.  It returns the allow-listed record, and nothing
   else:
   - `os`: name, version and release as `platform` gives them (e.g.
     "Windows 11 10.0.26100"), and `arch` (`platform.machine()`);
   - `cpu`: the model string.  Linux: `/proc/cpuinfo`'s `model name`.
     macOS: `sysctl -n machdep.cpu.brand_string`.  Windows: the
     registry's `ProcessorNameString` (`winreg`).  `null` when none of
     them works;
   - `logical_cpus` (`os.cpu_count()`), and `memory_gb`.  Linux:
     `/proc/meminfo`.  macOS: `sysctl hw.memsize`.  Windows:
     `GlobalMemoryStatusEx` through `ctypes`;
   - `engine`, for `docker:` runners only, from `docker info --format
     '{{json .}}'`: `NCPU`, `MemTotal` in GB, `OperatingSystem` (e.g.
     "Docker Desktop", "Rancher Desktop WSL Distribution") and
     `ServerVersion`.  `null` for the other runners, or when
     `docker info` fails;
   - `scheduler`: `{"nodes": …, "tasks": …}` from
     `SLURM_JOB_NUM_NODES` and `SLURM_NTASKS` when set, else `null`;
   - every probe has a short timeout.  A failing probe gives `null` for
     its field, never an error.  Start programs the PATH-safe way
     (task 0173).
2. **`run` records it** in the run directory's state at each start, so
   on a cluster it is the compute node.  Keep the distinct records: a
   run resumed on another node adds one.
3. **Solver time:** `solve_s`, the sum over the run's solver chunks of
   each log's last `ClockTime`.  Say which logs, and how a chunk that
   was stopped counts (its last `ClockTime` line).  `wall_s` is
   unchanged.  If a driver's logs don't allow it (other drivers than the
   helical pipe's), `solve_s` is `null`; list which under *Agent notes*.
4. **`collect`** prints the machine record(s) and `solve_s` before it
   writes the file, then writes them under `run` (`machine`: a list of
   records; `solve_s`).  `--no-machine` leaves the records out.
   `--machine` stays as the label in `contributor`.
5. **Schema:** both fields optional, the file format still version 1.
   `additionalProperties: false` inside the machine record, so a field
   not on the allow-list fails the schema.  Strings have length limits.
6. **`check` and `--merge`:** a missing record is a note in the report,
   not a rejection.  The merge stores the record(s) and `solve_s` with
   the level.  The RESULTS.md credit line uses the label if there is one,
   else a short form from the record ("Intel Core Ultra 7 265HX, 20
   CPUs, 64 GB; Docker Desktop VM 20 CPUs, 31 GB; Windows 11").
7. **Re-collect nothing.**  The stored Re 3000 n_arc 24 level keeps its
   label.  Don't add a record after the fact.
8. **Tests:**
   - `machine()` with each probe faked absent gives `null`s, not errors;
   - its keys equal the allow-list exactly;
   - a fake `docker info` gives the engine fields;
   - the Slurm variables are read;
   - `collect --no-machine` writes no record;
   - an old-format contribution (no record) passes `check` with the note;
   - the schema rejects a record with an extra key such as `hostname`.
   - Run `machine()` once for real on Linux and record its output under
     *Agent notes*.  The user's Windows session can add a Windows one,
     or say it wasn't run.
9. VOLUNTEERS.md (through its generator) and CHANGELOG: one line each
   saying what is recorded, what isn't, and `--no-machine`.

**Accept.**
- A volunteer file from `collect` carries the record and `solve_s`, and
  `check` and `--merge` store them.
- Old-format files still pass `check`.
- No field outside the allow-list can reach the file (the schema test).
- The full suite passes.

**Out of scope.**  Benchmarks or normalised speeds across machines;
recording the GPU; the 0030 suite's use of the record (decision 0044's
note: a 1.x addition if asked).

## Agent notes

## Questions for design

## Outcome
