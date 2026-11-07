# 0105 — CI green again: the Windows gmshToFoam test

- **Status:** ready
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
