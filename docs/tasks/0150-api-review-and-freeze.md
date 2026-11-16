# 0150 — The API review, then the freeze (0.8)

- **Status:** in progress (step 2's table waits for the design session's review)
- **Decision:** [0042](../decisions/0042-road-to-1-0.md) exit criterion 5
  ("the stable surface reviewed once, then frozen"), milestone 0.8 (the
  release candidate).
- **Depends on:**
  - 0147 (per-arc counts: a schema field to review);
  - 0148 (`io.readers` deprecated, to remove here);
  - 0149 (wheels);
  - 0151 (the shape-site cap to 0;
    [decision 0051](../decisions/0051-design-9-remaining-rows.md)).
  After these, DESIGN §9 holds only the `io.readers` row, which this
  task removes.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  1.0 promises that nothing breaks until 2.0: no removal or
rename in the Python API, the saved-description format, the CLI's JSON,
the manifest's format or the error codes.  Anything to rename or remove
must happen once, here, before the freeze.

**Do.**
1. **The inventory**, generated, not hand-written: every public name
   (`__all__` of each public package), every argument and default, the
   description schema, the CLI commands and their JSON `result`s, the
   manifest's format, the error and warning codes.  It becomes a
   committed file, say `docs/api-1.0.json`, that a test compares with
   the code from then on: a change to the frozen surface fails CI unless
   the file is updated on purpose.
2. **The review**, as a table under *Agent notes*: per item, keep,
   rename (with the old name deprecated), make internal, or remove.
   Criteria: one name per concept (DESIGN §3.1); names a user would
   guess; no internal type in a public signature; units in metres and
   degrees everywhere (decision 0047).  The design session reviews the
   table before any change.
3. **Known items** (decision 0042's 2026-11-11 note):
   - `interchange/build.py` calls `Assembly._twist_for_toward`, a
     private method, across packages: make it public or route it
     through `add(toward=…)`;
   - `validation/tools/wye_redesign.py` patches
     `hexmesh.assembly._checks.min_scaled_jacobians`;
   - the network document (decision 0032 stage 2): in the surface, or
     explicitly internal;
   - `hexmesh.io.readers`: removed (0148 deprecated it), and its
     DESIGN §9 row with it;
   - **branch shells** (decision 0051, option B, still open): ask the
     user whether to plan them for 1.x; if yes, reserve the `Tee`
     argument name (`branch_shells=` or better).
   - **an output `scale=` on the writers** (decision 0047's note of
     2026-11-11, from task 0139): ask the user; add or reserve it.
   - **`hexmesh.agent.schema` is both a function and a submodule**
     (`agent/schema.py`, the `python3 -m hexmesh.agent.schema`
     command).  Importing the submodule replaces the package's function
     with the module, for the rest of the process: CI run 43599497895
     failed on it (a test imported the submodule; fixed in 5fce743).  A
     user can hit it the same way.  Check every package for a public
     function named like a submodule; rename one side (for example the
     command module `_schema_cli`, keeping `python3 -m` working through
     a documented entry point), or document it.  Found by the design
     session, 2026-11-14.
   - **Classes of a circle's arc ratio and a rectangle's side ratio:**
     both class 2 since decision 0041's correction (2026-11-14); check
     the signature docs say so.
4. **Apply the table:** renames with deprecated aliases; removals of
   things deprecated for at least one release; each with a CHANGELOG
   line.
5. **README *Stability*:** rewritten for 1.x (decision 0042,
   *Consequences*), effective at 1.0.

**Accept.**
- The inventory file and its test.
- The review table, approved by the design session.
- Applied changes with deprecations.
- Full suite and CI green.
- 0.8.0 released by `docs/RELEASING.md`.

**Out of scope.**  New features.  After the freeze, 0.8 → 1.0 is fixes
only (the soak).

## Agent notes

- **2026-11-16, step 1 done:**
  - **The generator:** `tools/api_inventory.py` writes
    `docs/api-1.0.json`; `--check` prints the diff and exits 1 on a
    change.  `tests/test_api_inventory.py` runs `--check` in a fresh
    process, plus 3 unit tests.
  - **What it holds:**
    - 15 public modules: every module with an `__all__` whose path has no
      `_` part.  163 exports, each with its signature (argument kinds and
      defaults; a dataclass's `default_factory` by its product) and, for
      a class, its public methods and properties.
    - The description schema (`agent.schema()`), the 9 CLI commands, the
      envelope and exit codes, the manifest's format, version and keys,
      and the 322 codes.
    - The hexmesh version is left out, so a release doesn't change the
      file.  Paths are recorded in POSIX form, the same on Windows.
  - **Import order matters, a finding for step 3:** the first version
    imported every module to look for `__all__`.  Importing
    `hexmesh.agent.schema` (the submodule) replaced the package's
    `schema` function, and the generator then failed calling it.  The
    generator now finds `__all__` from the source and describes each
    package before its submodules are imported.

- **2026-11-16, step 2, the review table** (for the design session; no
  change made yet).  Found by scanning the inventory: names bound to
  different objects; package names that are also submodules; argument
  and member names hinting at units; annotations naming a type no
  public module exports.

  | # | item | finding | proposed |
  |---|---|---|---|
  | 1 | `hexmesh.agent.schema` | a function and a submodule (`agent/schema.py`, `python3 -m hexmesh.agent.schema`).  Importing the submodule replaces the function for the rest of the process. | Rename the submodule to `_schema_cli`.  `hexmesh schema` (the CLI command, which exists) becomes the documented command; `python3 -m hexmesh.agent.schema` goes, with a CHANGELOG **Breaking** line.  It can't be deprecated in place: the shadowing is the module's existence. |
  | 2 | `hexmesh.agent.advise` | the same pattern: function and public submodule (`agent/advise.py`, which also holds `AdviceError`).  `import hexmesh.agent.advise as m` gives the function, not the module. | Rename the submodule `_advise`; `AdviceError` stays exported from `hexmesh.agent`. |
  | 3 | `hexmesh.interchange.build` | the same: function and submodule `interchange/build.py`. | Rename the submodule `_build`. |
  | 4 | `hexmesh.sections` (15 names: `oh`, `h`, `build_face`, `build_oh_*`, `build_ring`, `add_physical_group`, …) | builder-level: `build_face` takes a `LayeredCrossSection`, which no public module exports; `oh` and `h` are modules. | Internal: not promised in 1.0 (drop `__all__` or rename `_sections`).  Users reach layouts through `PipeSpec(layout=…)`. |
  | 5 | `Straight`, `Bend`, `Reducer`, `Transition` in `hexmesh.interchange` | network-model part types with the same names as the fittings in `hexmesh` (different classes).  One name per concept (DESIGN §3.1): here, two concepts with one name. | Keep: the namespace separates them, and a part becomes the fitting of the same name.  Document it in API.md.  The alternative, `StraightPart` etc., touches every PCF user. |
  | 6 | `describe` in `hexmesh.agent` and `hexmesh.interchange` | two functions: the agent's describes an assembly or a model as JSON; the interchange's prints a model. | Keep both; say in each docstring which is which.  Or rename the interchange's to `summary`. |
  | 7 | `hexmesh.io` and `hexmesh.io.writers` | the same two functions exported twice. | Keep `hexmesh.io` as the promised path; `io.writers` stays importable but isn't promised (no `__all__`). |
  | 8 | `hexmesh.io.readers` | deprecated in 0148. | Remove, with its DESIGN §9 row (step 3's known item). |
  | 9 | `hexmesh.assembly.fittings` | a subset of `hexmesh.assembly` (9 names), a second path to the same classes. | Not promised (no `__all__`); `hexmesh` and `hexmesh.assembly` are the paths. |
  | 10 | radians in public members | `PipeSpec.rot_rad`; `PipeSpec.period` and each shape's `period(n)` in radians; the outline protocol's `ring_corner(d)` and `extent(a)` take radians.  Decision 0047: degrees everywhere. | `rot_rad` internal (`_rot_rad`).  `period`: degrees, under a new name (`period_deg`) with `period` deprecated, or internal.  The outline protocol (`corner`, `ring_corner`, `corners_from`, `side`, `extent`, `distance`, `grown`, `lerp`, …) is for the face builders: internal, with item 4. |
  | 11 | internal types in public signatures | `NetworkSpec` (returned by `read_pcf`); `Cut`, `Selection` (`NetworkModel.cut`, `.select`); `BlockLayout` (`Tee.layout`, `Wye.layout`, `Switch.layout`); `Skeleton`, `TubeUnion` (`Wye.skeleton`, `Wye.wall`); `CurveMesh` (`FillResult`); `LayeredCrossSection` (`Interface.__init__`). | Export `NetworkSpec`, `Cut` and `Selection` from `hexmesh.interchange` (users get them back).  `layout`, `skeleton`, `wall`: internal (underscore).  `FillResult` and `Interface.__init__`: users get them but never build them; promise their attributes, not the constructors. |
  | 12 | `interchange/build.py` calls `Assembly._twist_for_toward` | a private method across packages (known item). | Route it through `add(toward=…)` if the builder's case fits; otherwise a public `Assembly` method.  To settle by reading the call in step 4. |
  | 13 | `validation/tools/wye_redesign.py` patches `hexmesh.assembly._checks.min_scaled_jacobians` | a validation tool, not the library (known item). | Keep: tools may use internals; the inventory doesn't cover `validation/`.  A note in the tool. |
  | 14 | the network document (decision 0032 stage 2) | not implemented: no JSON-LD writer or reader in `hexmesh/interchange`. | Explicitly not in the 1.0 surface (README *Stability*); additive later. |
  | 15 | circle arc ratio and rectangle side ratio | API.md's per-arc section says the arcs are density like `nang_w`/`nang_h` (decision 0041's correction).  The docs never name a class number for either. | Nothing to change. |
  | 16 | branch shells (decision 0051 option B) | open. | **A question for the user** (task step 3): plan them for 1.x?  If yes, reserve the `Tee` argument name. |
  | 17 | an output `scale=` on the writers (decision 0047's note) | open. | **A question for the user:** add or reserve it. |

  The 15 modules otherwise keep their names; no units-in-name problem
  in the arguments (the scan found only `unit_scale` on the readers,
  documented as a factor).

- **2026-11-16, the design session's review of the table** (step 2's
  approval; apply in step 4):
  - **Approved as proposed:** rows 1, 2, 3, 5, 7, 8, 9, 11, 12, 13, 14
    and 15.
    - Row 1: `hexmesh schema` becomes the documented command, with a
      CHANGELOG **Breaking** line; update every doc that shows
      `python3 -m hexmesh.agent.schema`.  Add an architecture test: no
      public package exports a name that is also one of its submodules
      (the three clashes, and any later one).
    - Row 5: document it in API.md, one sentence each way.
  - **Row 4, `hexmesh.sections`: not promised, by removing its
    `__all__`,** not by renaming the package (no churn in the freeze
    window).  README *Stability* lists the modules that are importable
    but not promised (rows 4, 7, 9).  If a doc or example imports from
    it, change that to the promised path.
  - **Row 6: keep both `describe`s**; each docstring names the other.
    Renaming one would need a deprecation that outlives 0.8.
  - **Row 10:** `rot_rad` and the outline protocol internal, as
    proposed.  `period`: internal (`_period`) unless a doc, example or
    test outside the package uses it; if one does, `period_deg` with
    `period` deprecated.  Units stay degrees in every public member
    (decision 0047).
  - **Row 16, branch shells: the user, 2026-11-16, "Plan for 1.x,
    reserve name".**  Reserve `branch_shells=` on `Tee`: accepted as a
    keyword whose only allowed value is `None` (the default).  Any
    other value raises a coded error that says it is planned for 1.x.
    The inventory records it, so adding it later is additive.  Decision
    0051's note of today.
  - **Row 17, writer `scale=`: the user, 2026-11-16, "Add it in 0.8".**
    Every public writer takes `scale: float = 1.0`, applied once to the
    node coordinates as written; nothing else changes (the assembly,
    the cell count, the checks run on the unscaled mesh).
    `scale <= 0` raises a coded error.  Tests: a tee written at
    `scale=1e-3` has the full-size nodes × 1e-3 within 1e-15 relative,
    for each writer; the OpenFOAM writer's `checkMesh`, if it runs, is
    unchanged apart from size.  API.md and GUIDE: build at a reference
    size and scale at output for small parts, quoting task 0139's
    drift.  Decision 0047's note of today.
  - **Order of step 4:** the renames and internals first (one commit
    per row group), then `scale=`, then `branch_shells=`, then the
    inventory regenerated, the CHANGELOG, README *Stability*.  The full
    suite before the push.

## Questions for design

## Outcome
