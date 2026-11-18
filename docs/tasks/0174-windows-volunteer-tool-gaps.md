# 0174 — Volunteer tool off Linux: peak memory measured, generated files written with LF

- **Status:** ready
- **Decision:** [0039 — Platform support](../decisions/0039-platform-support.md);
  [0044](../decisions/0044-volunteer-runs.md) (what a contribution records)
- **Depends on:** none.
- **Blocks:** none.  It isn't needed for 1.0, but it should land before
  the next volunteer tag.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  Two follow-ups from task 0173's volunteer run on Windows
(2026-11-18):
1. **Peak memory wasn't measured** (`peak_memory_how: "not measured"`).
   The cause, from the code (the design session): `PeakMemory.available`
   is `Path("/proc/self/status").exists()`.  So on Windows *and macOS*
   the meter doesn't start at all, and the `docker stats` part is
   skipped too.  With the Docker runner, the solver's memory is
   in the containers, and `docker stats` sees it on every platform.
2. **`validation.tools.plots` wrote RESULTS.md with CRLF on Windows.**
   `path.write_text(text, encoding="utf-8")` uses text mode, which
   writes `os.linesep`.  About 60 `write_text` calls under `validation/`
   and `docs/gallery/build.py` have no `newline=`.  Any of them that
   writes a tracked file makes a whole-file diff on Windows.

**Do.**
1. **Peak memory:**
   - sample `docker stats` whenever `docker` is found, with or without
     `/proc`;
   - sum the descendants through `/proc` where it exists, and skip that
     part elsewhere (no new dependency: `psutil` is not in the
     requirements);
   - say which parts were measured in `how` (e.g. "Docker containers
     only (docker stats)"), so a contribution doesn't claim the host
     processes when it didn't measure them;
   - "not measured" only when neither part is available;
   - the `docker stats` call goes through the same `PATH`-safe start as
     `openfoam.py` (task 0173's `_spawnable`) or relies on
     `_gmsh.initialize()`.  Say which.
2. **LF everywhere:** every write of a tracked text file under
   `validation/`, `docs/gallery/`, `tools/` and `hexmesh/` (generated
   JSON, Markdown, `.msh` comments excepted where 0039's rule already
   says what to do) passes `newline="\n"` (`write_text` takes it from
   Python 3.10, and hexmesh needs 3.11).  List the files changed in *Agent notes*.
3. **A test** in task 0157's architecture tests: a text check that
   `write_text(` and `open(…, "w"…)` calls in those directories pass
   `newline=`, with an allow-list for the deliberate exceptions.
   Test `PeakMemory` with `/proc` faked absent and a fake `docker stats`
   output: the peak and `how` are as above.
4. **Why `test_posix_tools_are_marked` missed `true`** (task 0173,
   follow-up 2).  The design session read it (2026-11-18):
   `posix_tool_violations` looks only at direct
   `subprocess.run/Popen/…` calls whose first argument is a list
   literal.  `test_only_docker_names_containers` never calls
   `subprocess`.  It monkeypatches `of._argv` with a lambda that
   returns `["true"]`, and hexmesh's own `foam()` starts it.  So the argv
   reaches `Popen` through library code, which the scanner can't see.
   - Widen the scan: in a test function (or a module-level helper in
     `tests/`), any list or tuple literal whose first item is a
     `POSIX_TOOLS` or `OPENFOAM_TOOLS` name counts, not only one passed
     straight to `subprocess`.  Strings that are commands for a runner
     (`foam("true", …)`, `"bash -c …"` text) stay out: the rule is
     about argv lists.
   - Run it and handle every new hit.  Mark the test `posix_only`, use
     `[sys.executable, "-c", "pass"]` so it runs everywhere (the fix
     `c7a64b9` used, and the one 0173's follow-up 2 proposed in place
     of its `posix_only`), or put it on `POSIX_ALLOWED` with the reason.  Record the
     count of hits under *Agent notes*.
   - A test of the scanner itself: the monkeypatched-`_argv` shape is
     flagged.
5. CHANGELOG *Unreleased* (or the release in preparation).

**Accept.**
- On a host without `/proc` (a test, and the macOS CI job), a run with
  the Docker runner records a non-zero peak and an honest `how`.
- The architecture test passes; regenerating the gallery and plots on
  Windows leaves `git status` clean (the user's Windows session can
  confirm, or say it wasn't checked).

**Out of scope.**  Holding the machine awake during `volunteer run`,
and OneDrive's delete failures.  Both are handled as docs notes in task
0170 (step 4).  Measuring native (non-Docker) runs on Windows.

## Agent notes

## Questions for design

## Outcome
