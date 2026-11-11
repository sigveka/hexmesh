# 0144 — Validation documentation for people: install, run, read, send back

- **Status:** done (the design session, at the user's request, 2026-11-11)
- **Decision:** none new; [0050](../decisions/0050-documents-as-units.md)
  (documentation for reading).  The user, 2026-11-11: "Check the
  validation and volunteer documentation, is it human-oriented…" then
  "yes" to the proposed fixes.
- **Depends on:** none.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The user's three questions about the validation and volunteer
documentation:
1. Does it say what software is needed?
2. Does it say how to run a case, and do the drivers explain their
   arguments?
3. Does it say how to analyse and send back results?

The review (2026-11-11) found:
- `VOLUNTEERS.md` mostly fine.
- `validation/README.md` (18 lines) said nothing about OpenFOAM, Docker,
  cost or sending results back.
- 12 of 13 case READMEs never said how OpenFOAM is chosen.
- 47 driver options had no help text.
- Two things in the code didn't match what the docs implied:
  - eight drivers' `--openfoam` default **ignored `HEXMESH_OPENFOAM`**,
    while four had no option and used it;
  - CONTRIBUTING said the `-m openfoam` tests run with
    `HEXMESH_OPENFOAM=docker:…`, though most of them skip without a
    native install.

**Done.**
1. **`validation/README.md` rewritten as a guide:**
   - what you need: hexmesh; OpenFOAM v2406 by Docker, Apptainer or an
     install, with links; FEniCSx; disk;
   - a table of the 13 cases with their default runner and cost (quick
     and full);
   - running a case, and the shared options;
   - the quick checks in the test suite and their native-only catch;
   - reading `recheck`'s table in plain words (status, order, gate,
     Richardson, GCI);
   - sending results back (the volunteer route, or a pull request with
     `results.json`, the graphs and the gallery text; gates unchanged);
   - the tools.
2. **One `--openfoam` for every OpenFOAM driver:**
   `validation/tools/results.py` gains `add_openfoam_argument(ap,
   default)`.  `HEXMESH_OPENFOAM` replaces the case's default, and the
   option replaces both.
   - The 8 Docker-default drivers use it.
   - The 4 native-default drivers (poiseuille, heated_rod,
     layered_conduction, stenosis) gain it.
   - Without the variable, every driver's default is what it was.
3. **Help text on every option:** 47 driver options and the volunteer
   tool's 7.  Level names are explained (k multiplies the cells per
   direction; poiseuille's coarse/medium/fine are k = 1, 2, 4), as are
   `--end-time` (the iteration cap; steady solves stop on convergence),
   the turbulent cases' names and the square bend's two inlets.
4. **The volunteer page:**
   - a *Before you start* section: Python, OpenFOAM by any of four
     routes with install links, the image sizes, resources;
   - a link to the guide;
   - "run `check` yourself before sending".

   The `check` command's help no longer says "(maintainers)".
5. **CONTRIBUTING:** the `-m openfoam` line corrected; the validation
   section points to the guide.

## Agent notes

- **Times:** from the case READMEs and the stored results (`exec_time`,
  `wall_s`).  Measured 2026-11-11 for the five cases that had none,
  coarsest level, results to a scratch file:
  - mms: 397 s, 16 fittings at k = 1;
  - turbulent_pipe: 44 s, `lowre_550` at k = 1;
  - square_bend: 763 s, matched inlet at k = 1;
  - fenicsx_second_order: 252 s, k = 1;
  - heated_rod: 152 s, every level.

  The coding session's tests ran at least during the last, so the guide
  marks them as upper bounds.  The full runs of mms, turbulent_pipe,
  square_bend and the FEniCSx case aren't recorded anywhere: "not
  recorded" in the table.
- **The FEniCSx case** chooses no OpenFOAM runner; it has its own
  Docker image and `--memory`.

## Outcome

- **Files:**
  - `validation/README.md`;
  - `validation/tools/results.py` (`add_openfoam_argument`);
  - 13 `validation/*/run.py` (help texts; the shared option in 12);
  - `validation/volunteer.py` and the regenerated
    `validation/VOLUNTEERS.md`;
  - `CONTRIBUTING.md`;
  - `tests/test_validation_meta.py`;
  - CHANGELOG.
- **Tests:**
  - new in `test_validation_meta.py`, 30: every `add_argument` in the
    validation drivers, tools and volunteer tool has help (one per
    file); every OpenFOAM driver uses the shared option and
    `set_runner`; `HEXMESH_OPENFOAM` sets the default and the option
    overrides it;
  - `test_validation_meta`, `test_volunteer` and `test_readme`: 150
    passed, 1 skipped;
  - every driver's `--help` runs;
  - the site build checks every link and anchor (247 pages).
- **Follow-ups:**
  - **Proposed: make `tests/test_validation.py` honour
    `HEXMESH_OPENFOAM`**, so the quick checks run with Docker too.
    Today they skip without a native install.  Most other `openfoam`
    tests do the same.
  - Record full-run times for mms, turbulent_pipe, square_bend and the
    FEniCSx case at the next release run.
  - Each case README's first lines could say its runner and cost; today
    the table holds them.
