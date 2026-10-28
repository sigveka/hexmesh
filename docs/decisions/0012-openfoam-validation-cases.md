# 0012 — OpenFOAM verification and validation cases

- **Status:** accepted
- **Date:** 2026-10-25 (accepted 2026-10-25: the user asked for the
  first case as a task)
- **Tasks:** 0020

## Context

hexmesh claims structured all-hex meshes give better CFD for pipe
networks (README, DESIGN §1).  Nothing yet shows a hexmesh mesh running
in OpenFOAM, let alone converging to a known answer.  Task 0005 covers
format conversion, but not a solved case.  RESEARCH §7 lists reference
cases: analytic laminar pipe flow, Dean flow, heated pipe flow, the
stenosis (§7.3), the Štigler tee (§7.2), turbulent pipe DNS, and the
Vattenfall mixing tee.

OpenFOAM v1912 is installed locally
(`docs/integrations/openfoam.md`), along with its tutorials under
`/usr/share/doc/openfoam-examples/examples/`.

## Options

### A. Validation cases as scripts in the repository, run on demand
Each case is a directory with a script that builds the mesh with
hexmesh, sets up the OpenFOAM case, runs it, compares against reference
data, and writes a results summary.  They are not part of the default
`pytest` run (they need OpenFOAM and take minutes).  A pytest marker
lets them run when OpenFOAM is available.

### B. Validation only as documentation (manual instructions)
Cheaper, but not repeatable, and results go stale as the code changes.

## Decision

**A**, accepted 2026-10-25.

- Location: `validation/<case>/` at the repository root.  Each case has
  a script, a short `README.md` (physics, reference, how to run), and a
  committed `RESULTS.md` written by the script (numbers, date, hexmesh
  and OpenFOAM versions).
- Generated meshes and case directories go to a work directory that is
  git-ignored.
- Tests: `tests/test_validation.py` runs the cases with a pytest marker
  (`@pytest.mark.openfoam`), skipped when `gmshToFoam` is not on PATH,
  and excluded from the default run.
- Reference cases are added one at a time, simplest first:
  Hagen–Poiseuille (task 0020), then T-junction, Dean bend, heated pipe
  with CHT, and stenosis/tee once their fittings exist.
- Findings about OpenFOAM conversion go to
  `docs/integrations/openfoam.md`, and results that bear on design go to
  RESEARCH §7.

## Consequences

- A new top-level `validation/` directory.  `.gitignore` gets its work
  directory.
- The project gets its first evidence that meshes are solver-correct.
- Analytic cases tasked 2026-10-26: 0033 (heated rod), 0034 (layered
  conduction, solids), 0035 (heated multi-layer pipe, CHT).  More are
  planned in RESEARCH §7.5.
- Turbulent cases tasked 2026-10-28: 0049 (fully developed pipe, k-ω
  SST, against [`mckeon_and_zagarola_etal_2005`] and
  [`el_khoury_and_schlatter_etal_2013`]) and 0050 (90° bend, against
  [`sudo_and_sumida_etal_1998`]).  Gates follow the RANS literature
  (RESEARCH §10.2): per cent level, not the 0.1 % of the laminar cases.
- Validation cases use only existing fittings and APIs.  A missing
  capability (for example a global refinement factor) is reported as a
  finding, not built inside the validation task.

## Verified vs. assumed

- Verified: OpenFOAM v1912 and its tutorials are installed; `gmshToFoam`
  runs once the OpenFOAM environment is sourced.
- Assumed: run times of minutes per case on this machine.
