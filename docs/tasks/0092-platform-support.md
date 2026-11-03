# 0092 — Platform support: portable meshing, a portable Docker runner, CI on three systems

- **Status:** in progress
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

- **Absolute paths in commands** (step 1's check).
  - Only `of.convert()` puts one in a command
    (`gmshToFoam {msh.resolve()}`, with `mounts=[msh.parent]`).
  - Every validation driver (poiseuille, heated_rod, heated_pipe,
    layered_conduction, stenosis, stenosis_pulsatile, womersley,
    rect_duct) runs commands inside the case with relative names
    (`gmshToFoam {msh.name}`, solvers, `decomposePar`, …).
  - `tests/test_msh_recipe.py` passes an absolute `.msh` path with
    `mounts=[tmp_path]`.
  - `run_stage` runs `study.run["command"]` through the native runner
    only.  Decision 0039 keeps that one Linux-only, so it is unchanged.
- **Mount layout.**
  - `container_paths` mounts only the outermost directories, at
    `/work/0`, `/work/1`, …; the one holding the working directory comes
    first.
  - A directory inside a mounted one maps to its subpath.  So a case
    inside its mesh directory gets one mount, and `..` between them
    still resolves, as it did with same-path mounts.
  - `container_command` rewrites a host path only as a whole word,
    longest host first, and turns `\` into `/`.
  - `docker_argv` is the pure part, unit-tested with `PureWindowsPath`;
    `_argv` resolves the paths and adds `--user` only where
    `os.getuid` exists.
- **`other_runs`:** `psutil` first (the new `[study]` extra), then
  `/proc` (now `stages.PROC`, so tests can point it elsewhere).
  Otherwise it returns `[]` and warns once.  Any exception becomes that
  warning, so it never raises.
- **Encoding rule:** `encoding_violations` in `tests/test_architecture.py`
  found 45 sites.
  - Three weren't text opens: `rasterio.open`, `fiona.open` and
    `gmsh.open`, now in `BINARY_OPENERS`.
  - The other 42 got `encoding="utf-8"`, inserted at each call's AST end
    position.  The design session's estimate was about 46.
  - OpenFOAM-read files also got `newline="\n"`: the 7 `write_text`
    calls in `io/writers/openfoam.py` (`Allrun` included),
    `substitute_case`, and `openfoam_boundary._atomic_write` (it had
    `encoding=` but no `newline=`, so `polyMesh/boundary` and the role
    manifest would have been CRLF on Windows).
- **CI:** `.github/workflows/tests.yml` runs `python -m pytest`, not
  `python3`.
  - setup-python on Windows provides `python`; `python3` isn't
    guaranteed there.
  - The newest Python is `3.x`, setup-python's latest stable.
  - The Linux Docker job runs only `tests/test_openfoam_runner.py` and
    `tests/test_msh_recipe.py` under `-m openfoam`.  The validation
    cases take hours.

## Questions for design

## Outcome

Code done 2026-11-02.  The workflow was pushed (e54faae, with the
user's go-ahead), and its first run found Windows-only failures.  They
are fixed in the commit after it; the task stays in progress until a
second run is green.

**CI run 1** (GitHub Actions 41537461766, 2026-11-02, commit e54faae):

| job | result |
|---|---|
| ubuntu-latest, Python 3.10 / 3.x | pass |
| macos-latest, Python 3.10 / 3.x | pass |
| OpenFOAM v2406 in Docker (Linux) | pass |
| windows-latest, Python 3.10 | 97 failed, 2167 passed, 17 skipped |
| windows-latest, Python 3.x (3.15.2) | 104 failed, 2160 passed, 17 skipped |

Windows causes, all recorded in `docs/integrations/platforms.md` and
`gmsh.md`:
1. **gmsh writes ASCII `.msh` with CRLF** (C text mode).  The recipe
   stamp searched for `$EndMeshFormat\n`, so every write failed: all of
   `test_examples`, `test_msh_recipe` and the meshing `test_study` and
   `test_openfoam_*` tests (about 85).  Fix: `msh_comments.to_lf`
   rewrites gmsh's ASCII output to LF right after `gmsh.write`, in
   `Assembly.write` and `write_openfoam`.  The `.msh` is then
   byte-identical to Linux's, and `gmshToFoam` reads LF (decision 0039).
   `insert` also follows a file's own line ending.  Two new tests
   simulate Windows' gmsh (CRLF) and fail without `to_lf`.
2. **Default encoding cp1252:** tests and `docs/gallery/build.py` read
   UTF-8 sources with `read_text()` (test_architecture,
   test_convergence, test_validation_meta).  Fix: `encoding="utf-8"` at
   72 sites.  The architecture rule now also covers `tests/` and `docs/`
   (`ENCODING_TREES`), with planted cases in `tests/`.  PIL's
   `Image.open` was added to the binary openers.
3. **`\` in paths turned into text:** the architecture checker's
   messages (the planted tests) and `apply_case_template`'s
   unknown-placeholder message and changed-file list.  Fix:
   `.as_posix()`.  The same applies to `stages._tree_digest`: it hashed
   `str(relative path)`, so a template tree's digest differed between
   Windows and Linux.  No test caught that; it is the same on Linux.
4. **CRLF checkout:** no `.gitattributes`, so `docs/ascii-logo.txt` came
   out CRLF and didn't match the shipped logo.  Fix: `* text=auto
   eol=lf`.  Every committed text file was already LF (`git ls-files
   --eol`), so nothing is renormalised.

**Files.**
- `hexmesh/study/openfoam.py`: `container_paths`, `container_command` and
  `docker_argv`; `_argv` uses them; no `--user` without `os.getuid`.
- `hexmesh/study/stages.py`: `other_runs` uses psutil, then `/proc`
  (`PROC`), then warns once; never raises.
- `hexmesh/io/writers/openfoam.py`: `newline="\n"`, and `constant/` is
  created before `regionProperties` (see Surprises).
- `hexmesh/io/writers/openfoam_boundary.py`: `newline="\n"`.
- `encoding="utf-8"` at 42 sites in `io/readers/pcf.py`,
  `study/definition.py`, `study/manifest.py`, `study/openfoam.py`,
  `study/sampling.py`, `study/stages.py`, `version.py` and the two
  writers.
- `pyproject.toml`: a `[study]` extra (`psutil>=5.9`).
- `README.md`: the platform table.
- Tests:
  - `tests/test_architecture.py`: `encoding_violations`, the rule and 13
    planted cases;
  - `tests/test_openfoam_runner.py`: new mount layout, no `getuid`, a
    Windows host, whole-path rewriting; the uid assertions are
    conditional;
  - `tests/test_study.py`: `other_runs` with both back ends, without
    psutil or `/proc`, and with a failing psutil; the detached-process
    test is skipped off POSIX;
  - `tests/test_openfoam_output.py`: LF endings under simulated Windows
    text mode.
- `.github/workflows/tests.yml` (e54faae).
- After CI run 1: `hexmesh/io/writers/msh_comments.py` (`to_lf`, CRLF-aware `insert`), `hexmesh/assembly/assembler.py`, `hexmesh/study/openfoam.py` and `stages.py` (`as_posix`), `.gitattributes`, `encoding=` in 14 test files and `docs/gallery/build.py`, `tests/test_architecture.py` (`ENCODING_TREES`), `tests/test_msh_recipe.py` (2 CRLF tests), `docs/integrations/platforms.md` (new), `gmsh.md`, `README.md` there.

**Acceptance.**
- **Encoding rule:** passes on the tree.  The 13 planted cases fail and
  pass as designed, each naming the file and line.
- **Windows host:** `docker_argv` with `PureWindowsPath` and no user
  gives `-v C:\…\v0:/work/0 -v D:\meshes:/work/1 -w /work/0/case` and a
  command with only `/work/…` paths.  Unit-tested on Linux.
  `_argv` with `os.getuid` deleted gives no `--user`.
- **`other_runs()`** with `/proc` missing and psutil hidden returns `[]`
  and warns once.  With psutil raising it returns `[]` and warns.
- **No `\r`** in any of the 9 files `write_openfoam_case` writes, under
  a `Path.write_text` patched to Windows text mode.  The same check on a
  copy of the writer without `newline=` finds `\r` in all 9, so the test
  discriminates.
- **CI:** run 1 green on Linux, macOS and Docker; Windows failures listed above with their causes and fixes.
  Run 2 (41590666205, a48e360): Windows 3 failed, 2288 passed, 17 skipped; everything else green.  All three were
  in the new tests, not the library: the CRLF simulation doubled gmsh's own `\r\n` on Windows (`\r\r\n`), and
  `test_provenance_false_is_todays_file` compared with gmsh's raw CRLF file.  Both tests now normalise first.
  Run 3 waits for the push.
- **Full suite on Linux:** 2266 passed, 15 skipped (+21), no failures.
  The touched test files pass again (106) after the logo headers.
- **One Docker case unchanged:** rect_duct a/b 1, k = 1, both meshes,
  v2406 through the new `/work` mounts.  All 37 numeric fields are
  identical to task 0071's stored values (max |diff| 0.0).
  - `-m openfoam` runner and recipe tests under
    `HEXMESH_OPENFOAM=docker:…2406`: 4 passed.
  - rect_duct's coarse openfoam tests: 2 passed.

**Surprises.**
- `write_openfoam_case` crashed on any fresh directory, at HEAD too: it
  wrote `constant/regionProperties` before creating `constant/`.  It is
  exported (`hexmesh.io.write_openfoam_case`) but nothing in the repo
  calls or tests it.  The new line-ending test found it; fixed by
  creating `constant/polyMesh` first.
- `openfoam_boundary._atomic_write` already passed `encoding=`, but
  without `newline=`.  The encoding rule alone wouldn't have caught it.
  The rule checks encodings only, not line endings.

**Disk space.**  The rect_duct check used 1.9 MB of scratch, now deleted.
The suite writes under pytest's pruned `tmp_path`.  Free: 42 GB.

**Proposed follow-ups.**
- A line-ending rule in the architecture test.  For example, every write
  in `io/writers/openfoam*.py` and `study/openfoam.py` must pass
  `newline=`.  The test above covers only `write_openfoam_case`.
- `write_openfoam_case` has no other test.  Decide whether it stays
  public (the study's case stage doesn't use it).
