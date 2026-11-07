# 0105 — CI green again: the Windows gmshToFoam test

- **Status:** in progress
- **Decision:** [0039 — Platform support](../decisions/0039-platform-support.md)
- **Depends on:** none.  First of the public-readiness tasks (0105, 0106,
  0078).

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The `tests` workflow has failed on every push since
2026-11-06 (the last success was 2026-11-05 22:41 UTC).  Linux, macOS
and the OpenFOAM Docker job pass.  On Windows, at both Python 3.10 and
3.x, two tests fail (run 42376137627):

```
FAILED tests/test_openfoam_runner.py::test_convert_keep_orientation_flag[False-gmshToFoam /]
FAILED tests/test_openfoam_runner.py::test_convert_keep_orientation_flag[True-gmshToFoam -keepOrientation /]
2 failed, 3587 passed, 17 skipped
```

`tests/test_openfoam_runner.py:224` asserts that the command starts with
`gmshToFoam /`.  On Windows the path in the command is presumably built
with a backslash, or as a Windows path.  The repository is public, so a
red badge is the first thing a visitor sees.

**Do.**
1. Find what the command holds on Windows (log it in the test's
   failure message).
2. Decide which is wrong:
   - **the test:** it should compare the command's arguments, not a
     POSIX string;
   - **the code:** the command reaches OpenFOAM, which runs in Linux
     (Docker or WSL), so its paths must be POSIX on every host.  If
     `convert` builds a Windows path, that is a real bug for Windows
     users with Docker.  Fix the code, and say so in CHANGELOG.
3. Record the finding in `docs/integrations/openfoam.md` if it is tool
   behaviour, and in decision 0039's Windows notes if it concerns
   platform support (write it under *Agent notes*; design moves it).

**Accept.**
- The `tests` workflow passes on all six jobs, plus OpenFOAM Docker, on
  main.
- The test checks the path form OpenFOAM receives, on every platform.
- Full suite: no new failures.

## Agent notes

- **What the command held** (run 42376137627, windows-latest, Python
  3.10): `gmshToFoam C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\popen-gw1\test_convert_keep_orientation_0\mesh.msh`.
- **Verdict: the test was wrong, the code is right.**  `convert` names
  the mesh by its host path, and `foam` passes it to the runner.  On
  Windows the only runner is Docker: the native runner is Linux-only, and
  under WSL Python itself runs in Linux, so its paths are POSIX (decision
  0039).  `docker_argv` mounts the host directory at `/work/N` and
  `container_command` rewrites every host path under it to the container
  path, with `\` turned into `/`.  The test faked `foam`, so it saw the
  command *before* that rewrite.  On the CI path above, the rewrite gives
  `gmshToFoam -keepOrientation /work/0/mesh.msh`, with
  `C:\Users\…\test_convert_keep_orientation_0` mounted at `/work/0`
  (checked with `PureWindowsPath` on Linux).  The existing
  `test_container_paths_on_windows` (drive-letter paths) already covered
  the rewrite itself.
- **The test now** checks that the host command is exactly
  `gmshToFoam[ -keepOrientation] <resolved host path>`.  It then passes
  that command through `docker_argv` and checks that the container
  command ends with `gmshToFoam[ -keepOrientation] /work/0/mesh.msh`: the
  form OpenFOAM receives, the same on every host.  A failure prints both
  commands.
- **For decision 0039's Windows notes** (design moves it): Windows with
  the Docker runner hands OpenFOAM POSIX paths; confirmed on the
  `convert` path, task 0105.  Nothing new for
  `docs/integrations/openfoam.md`: no tool behaviour was involved.
- No code change, so no CHANGELOG entry.

## Questions for design

_None._

## Outcome

- **Files:** `tests/test_openfoam_runner.py` (one test rewritten, both
  parameters kept).
- **Local:** `tests/test_openfoam_runner.py` 22 passed.  The last full
  suite (task 0060, today) had 3664 passed and 0 failed, and this change
  touches only this test.
- **CI:** pending the push.  Acceptance is all six `tests` jobs plus
  OpenFOAM Docker green on main.  The status stays *in progress* until
  that run is seen.
