# 0195 — A local-check test leaves an empty temporary directory on every run

- **Status:** done (2026-11-24)
- **Decision:** none needed (test hygiene).
- **Depends on:** none.
- **Blocks:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Found in 0194 (its *Outcome*):
`test_no_runner_skips_the_openfoam_steps[True-1]` leaves an empty
`/tmp/hexmesh-local-check-*` on every run.  On a shared machine with
limited disk (CLAUDE.md), tests write only to `tmp_path`.

**Do.**
1. Find what creates the directory: `tools/local_check.py`'s own
   `mkdtemp`, or the test.  Make the test pass `tmp_path`, or a
   monkeypatched base, so nothing lands in the system's temporary
   directory.
2. If `local_check.py` itself leaves the directory behind when it skips
   its OpenFOAM steps, clean it up there too: a `TemporaryDirectory`
   context, or removal in `finally`.
3. A test: the system temporary directory has no new
   `hexmesh-local-check-*` after the test runs.
4. Remove the stray directories this test made, by exact path, only
   the empty ones it created.

**Accept.**  No new directory after the suite; the test above passes.

## Agent notes

- **The cause** was `tools/local_check.py`, not the test: a failed run
  keeps its temporary directory for the logs, and `--require` without a
  runner fails every OpenFOAM step before any writes one, so the kept
  directory was empty.  Now a failed (or `--keep`) run keeps it only if
  something is in it.
- **The tests:** an autouse fixture in `tests/test_local_check.py` points
  `tempfile.tempdir` at `tmp_path`, so the check's `mkdtemp` never lands
  in the system's temporary directory.  A new test runs the `--require`
  case and finds no directory left, and a failing step that writes a log
  keeps it, named in "logs kept in".
- **Checked:** the system's `hexmesh-local-check-*` listing before and
  after `tests/test_local_check.py` is the same (25 passed).
- **Strays removed** by exact path with `rmdir` (empty only): three
  from 2026-11-24 08:10, 08:15 and 15:17, empty, so from runs without a
  log (this test's `--require` case).

## Questions for design

## Outcome

- **Files:** `tools/local_check.py` (no empty directory kept),
  `tests/test_local_check.py` (the fixture, one test).
- **Tests:** `tests/test_local_check.py`, 25 passed; no new directory in
  the system's temporary directory.
