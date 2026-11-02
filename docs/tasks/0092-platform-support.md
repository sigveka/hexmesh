# 0092 — Platform support: portable meshing, a portable Docker runner, CI on three systems

- **Status:** ready (after 0091)
- **Decision:** [0039 — Platform support](../decisions/0039-platform-support.md)
- **Depends on:** 0091 (it edits `io/writers`; don't run both at once)

Ground rules for all tasks: [README](README.md#ground-rules).  This task
works in `hexmesh/study/`, `hexmesh/io/`, `tests/`, `README.md`, and a
new CI config.

**Why.**  Decision 0039: meshing on Linux, macOS and Windows; studies and
validation on Linux, WSL, or through the Docker runner anywhere; the
native OpenFOAM runner on Linux only.  Today the Docker runner and
`run_stage` crash off Linux, and OpenFOAM files written on Windows get
CRLF line endings.  The decision's Context lists each site.

**Where.**  `hexmesh/study/openfoam.py`, `hexmesh/study/stages.py`,
`hexmesh/io/writers/openfoam.py`, `hexmesh/io/readers/pcf.py`, every
text I/O site in `hexmesh/`; `tests/test_architecture.py`,
`tests/test_openfoam_runner.py`, `tests/test_study.py`;
`.github/workflows/` (or the CI the user prefers); `README.md`.

**Do.**
1. **Docker runner** (`_argv`):
   - no `--user` where `os.getuid` doesn't exist (Windows Docker Desktop
     maps ownership itself);
   - mount each host directory at a fixed container path (`/work/0`,
     `/work/1`, …), set `-w` to the mapped `cwd`, and rewrite host paths
     in `cmd` to their container paths.  One mapping function, tested
     on Windows-style paths (`PureWindowsPath`) on any platform;
   - check every validation driver that passes an absolute path in a
     command, and list them in *Agent notes*.
2. **`other_runs()`:** use `psutil` when installed (an optional extra);
   on Linux keep the `/proc` reading as the fallback; elsewhere without
   `psutil`, return nothing and warn once that the check is unavailable.
   It must never raise.
3. **Line endings:** every file in `io/writers/openfoam.py` and anything
   else meant for OpenFOAM or a shell is written with `newline="\n"`.
   `Allrun`'s `chmod` stays (harmless on Windows).
4. **Encodings:** every text `open`, `read_text` and `write_text` in
   `hexmesh/` passes `encoding="utf-8"`.  Add the rule to
   `tests/test_architecture.py` (AST: a call without `encoding=` and
   without a binary mode fails, naming the rule, the file and the line),
   with a planted-violation test.
5. **Tests:** make the POSIX-only assertions conditional
   (`test_openfoam_runner.py`'s `getuid`, `test_study.py`'s
   `other_runs`).  The native-runner skip conditions stay.
6. **CI:** a workflow running `python3 -m pytest` (OpenFOAM excluded,
   as by default) on `ubuntu-latest`, `macos-latest` and
   `windows-latest`, Python 3.10 and the newest supported.  Linux also
   runs `-m openfoam` with the Docker v2406 image if the CI host allows
   it; otherwise note it.  Record anything that fails only on one
   system in `docs/integrations/gmsh.md` (or a new
   `docs/integrations/platforms.md`) with version, evidence and date.
   Don't push a workflow without asking the user first: it publishes to
   the CI service.
7. **README "Install":** the platform table from decision 0039, in two
   or three lines.

**Accept.**
- The architecture test's encoding rule passes and fails on a planted
  violation.
- `_argv` under a simulated Windows host (`PureWindowsPath` paths, no
  `getuid`) gives a valid `docker run` line: Linux container paths,
  rewritten `cmd`.  Unit-tested on Linux.
- `other_runs()` never raises with `/proc` missing (monkeypatched).
- OpenFOAM files written by `write_openfoam_case` contain no `\r`
  (tested with a monkeypatched `os.linesep`, or by reading bytes).
- CI is green on the three systems, or each failure is listed in
  *Outcome* with its cause.
- Full suite on Linux: no new failures; `-m openfoam` for one Docker
  case unchanged.

**Out of scope.**  Native OpenFOAM on Windows (MSYS2, blueCFD); the
gallery's rendering on Windows (a follow-up if CI shows it fails).

## Agent notes

## Questions for design

## Outcome
