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

## Amendment (2026-10-30): toolchain

- **Evidence (task 0035):** v1912's buoyant and CHT solvers (Ubuntu
  package 1912.200626) fail on any non-orthogonal mesh, OpenFOAM's own
  `buoyantCavity` tutorial sheared by 1° included.  `blockMesh` O-grids
  and sheared ducts fail the same way, so hexmesh is cleared.  v2406
  (`opencfd/openfoam-default:2406`, Docker) runs all of them, and the
  full CHT case.
- **Decision:**
  - new validation cases run on **v2406 in Docker**, conversion and
    solvers in the same version (one toolchain per case);
  - the runner is selectable in `hexmesh.study.openfoam`, and recorded
    with every result;
  - finished v1912 cases keep their results, with a one-off v2406
    cross-check at the coarsest level; re-validation only if a result
    moves beyond its GCI.
- **Users:** README states the v2406+ requirement for buoyant/CHT
  solvers on hexmesh meshes.

## Amendment (2026-10-30, the user): how cases are categorised

**Vocabulary** (Roache; ASME V&V 20; AIAA G-077):
- **code verification:** the equations are solved correctly; checked
  against exact solutions;
- **solution verification:** the discretisation error is estimated
  (Richardson / GCI, decision 0015).  It happens *in every case*, so it
  isn't a category;
- **validation:** the model is right for the physics; checked against
  measurements or a trusted stand-in.

**Primary category: the reference** (exactly one per case):

| Category | Reference | Examples |
|---|---|---|
| **V1, exact solution** (code verification) | analytic or series solution | Poiseuille, heated rod, layered conduction, heated pipe, Womersley, laminar rectangular duct |
| **V2, high-fidelity simulation** | DNS / LES data | stenosis steady and pulsatile, square-duct DNS |
| **V3, experiment** | measurements | Sudo bend, Taylor square bend, Davis transition, Štigler tee |
| **V4, correlation or standard** (comparison) | empirical fits, standards, handbooks | McKeon friction factor, ISO 5167, Idelchik / ASHRAE |

A case with several references takes the strongest as its category and
lists the rest (e.g. 0049: V2 for profiles, V4 for the friction
factor).

**Tags** (any number):
- **regime:** `laminar`, `transient`, `transitional`, `rans:<model>`;
- **physics:** `flow`, `cht`;
- **features:** the hexmesh features a case exercises, from a fixed
  list: `section:circle`, `section:rect`, `layers`, `straight`, `bend`,
  `miter`, `spline`, `profiled-reducer`, `transition`, `tee`,
  `duct-tap`, `wye`, `stack-changes`, `projection`;
- **toolchain:** OpenFOAM version and runner.

**Machine-readable:**
- each `validation/<case>/` has a `case.json`: category, reference
  (citation key and data source), tags, status, gates, task;
- the gallery generates the validation page from these files: cases
  grouped by category, and a **coverage matrix** (features × cases)
  showing what is validated and what isn't.

## Verified vs. assumed

- Verified: OpenFOAM v1912 and its tutorials are installed; `gmshToFoam`
  runs once the OpenFOAM environment is sourced.
- Assumed: run times of minutes per case on this machine.
