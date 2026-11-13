# Platforms

**Role:** the operating systems the suite and the Docker runner support
(decision 0039): Linux, macOS and Windows.  Native OpenFOAM is Linux
only.

**Versions:** GitHub Actions `ubuntu-latest`, `macos-latest` and
`windows-latest`, Python 3.11 and 3.x (`.github/workflows/tests.yml`;
task 0092, and task 0113 for 3.11).

**Features used:** `pathlib`, `subprocess`, Docker Desktop's `-v`
mounts (`hexmesh.study.openfoam.docker_argv`).

## Known quirks

Found by task 0092's first CI run (GitHub Actions run 41537461766,
2026-11-02).  Linux and macOS were green; both Windows jobs failed.

### Windows: the default text encoding is cp1252 — *verified*
`Path.read_text()` and `open()` without `encoding=` decode with the
locale's code page, cp1252 on the runners (Python 3.10 and 3.15).  A
UTF-8 source with `–` or `≈` then fails: `UnicodeDecodeError: 'charmap'
codec can't decode byte 0x81`.  The architecture test's encoding rule
(`tests/test_architecture.py`, `ENCODING_TREES`) covers `hexmesh/`,
`tests/` and `docs/`.

### Windows: `str(path)` uses `\` — *verified*
Text built from `str(relative_path)` differs from Linux's.  It broke
messages that tests match (`0\U: unknown placeholder(s)`) and would have
changed a content digest across systems (`study.stages._tree_digest`).
Use `.as_posix()` wherever a path becomes text that is compared, hashed
or stored.
**Rule:** `tests/test_architecture.py::test_no_bare_path_in_compared_text`
(task 0157): an `assert` comparing text with an f-string that holds a
bare `tmp_path` or `*path`/`*dir` name.

### Windows: git checks out text with CRLF — *verified*
Without `.gitattributes`, the runner's git (`core.autocrlf=true`) gave
`docs/ascii-logo.txt` CRLF, so a byte comparison with the shipped logo
failed.  `.gitattributes` sets `* text=auto eol=lf`.

### gmsh on Windows: ASCII `.msh` is CRLF
See [gmsh.md](gmsh.md).

### CI: `setup-python` fails on a 504 from the Python download — *verified*
Two `windows-latest, Python 3.10` jobs failed in `actions/setup-python@v5`
before any test ran (runs 42466812439 and 42468603272, 2026-11-08; task
0113).
- 3.10 wasn't in the runner's tool cache, so the action downloaded
  `python-3.10.11-win32-x64.zip` from `actions/python-versions`
  releases.  It got `Unexpected HTTP response: 504` three times and gave
  up.
- **The version was available**, only the download timed out.  Every
  other job of those runs, macOS and Linux at 3.10 included, set up
  Python and passed.
- A version that isn't cached depends on that download.  Rerunning the
  job is the fix for a one-off 504.  Since task 0113, CI tests 3.11 and
  3.x.

### NumPy 2 is what CI installs; this machine has 1.26 — *verified*
`repr` of a NumPy scalar is `0.0` on NumPy 1 but `np.float64(0.0)` on
NumPy 2.  A test that wrote coordinates with `{x!r}` passed here and
failed on every CI job (runs 42476909094 and 42478255352, 2026-11-08;
fixed in task 0113).  Format `float(x)`, or `x.tolist()` values, in
text that's parsed back.

### Windows: `subprocess.run(["bash", …])` starts WSL's launcher, not Git's bash — *verified*
`subprocess.run(["bash", "-n", r"C:\…\job.sh"])` exited 1 on both
`windows-latest` jobs (run 43185960002, 2026-11-12, commit c1c7c9f;
`tests/test_volunteer.py`).  Task 0157's CI step (run 43428690797,
2026-11-13, `windows-latest`, Python 3.x) showed why:
- **On the PATH, Git's bash is first:** `where.exe bash` lists
  `C:\Program Files\Git\bin\bash.exe`, then
  `C:\Windows\System32\bash.exe`, then Git's `usr\bin\bash.exe`;
  `shutil.which("bash")` gives Git's.
- **`subprocess` starts System32's:** Windows' process search
  (`CreateProcess`) looks in System32 before the PATH.  WSL's launcher,
  with no distribution installed, exits 1 and prints "Windows Subsystem
  for Linux has no installed distributions." to **stdout**, in UTF-16
  (stderr empty).
So `bash` from Python on a Windows runner never reaches Git's bash
unless its full path is given (`shutil.which("bash")`).  The earlier
inference (WSL's launcher ahead on the PATH) had the launcher right and
the reason wrong.
A test that runs `bash` (or any POSIX tool) is POSIX-only.
**Rule:** `tests/test_architecture.py::test_posix_tools_are_marked`
(task 0157): a test running `bash`, `sh`, `timeout` or an OpenFOAM
utility carries `@pytest.mark.posix_only` (or `openfoam`), which
`tests/conftest.py` skips on Windows.  It replaced c7a64b9's inline
skip.

### Windows: `shlex.quote` quotes a Windows path — *verified*
`shlex.quote(str(path))` wraps `C:\Users\…` in single quotes (it holds
`\` and `:`), so text that embeds the quoted path doesn't end with the
plain path (CI on 61894b1, 2026-11-12).  Compare with the
same quoting the code applies.
**Rule:** `test_no_bare_path_in_compared_text` (task 0157), as for
`str(path)` above: the failing assert, `endswith(f"… run {tmp_path}")`,
is one of its planted examples.

## Open questions

- The gallery's rendering on Windows is untested (task 0092, out of
  scope).
