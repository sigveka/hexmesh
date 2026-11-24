# 0195 — A local-check test leaves an empty temporary directory on every run

- **Status:** ready
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

## Questions for design

## Outcome
