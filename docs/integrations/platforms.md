# Platforms

**Role:** the operating systems the suite and the Docker runner support
(decision 0039): Linux, macOS and Windows.  Native OpenFOAM is Linux
only.

**Versions:** GitHub Actions `ubuntu-latest`, `macos-latest` and
`windows-latest`, Python 3.10 and 3.x (`.github/workflows/tests.yml`,
task 0092).

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

### Windows: git checks out text with CRLF — *verified*
Without `.gitattributes`, the runner's git (`core.autocrlf=true`) gave
`docs/ascii-logo.txt` CRLF, so a byte comparison with the shipped logo
failed.  `.gitattributes` sets `* text=auto eol=lf`.

### gmsh on Windows: ASCII `.msh` is CRLF
See [gmsh.md](gmsh.md).

## Open questions

- The gallery's rendering on Windows is untested (task 0092, out of
  scope).
