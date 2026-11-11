# Tasks

One file per unit of work for the coding agent.  Every task traces back to
an **accepted** decision in [`../decisions/`](../decisions/) or to a rule in
[`DESIGN.md`](../../DESIGN.md).  The process is described in
[`../decisions/README.md`](../decisions/README.md#the-loop).

## Index

Two tables.  A task is **validation** when its file carries a
`- **Category:** Vn` line (decision 0012; the gallery's coverage matrix
reads it); everything else is **development**.  Numbers are shared.

### Development

| Task | Title | Status | Decision |
|---|---|---|---|
| [0000](0000-keep-face-grading.md) | Keep face-builder grading through meshing (bug fix) | done | 0001 |
| [0001](0001-axial-grading.md) | Axial grading per fitting | done | 0001 |
| [0002](0002-first-cell-height.md) | Radial grading from first-cell height | done | 0001 |
| [0003](0003-cell-count.md) | Exact cell count before GMSH | done | 0001 |
| [0004](0004-quality-per-fitting.md) | Quality report per fitting, with hex metrics | done | 0001 |
| [0005](0005-openfoam-output.md) | OpenFOAM-compatible output | done | 0001 |
| [0006](0006-intent-serialization.md) | Save and load the network description (Intent layer) | done | 0001 |
| [0007](0007-topology-invariance-test.md) | Test that topology is unchanged across geometry variants | done | 0001 |
| [0008](0008-open-end-extensions.md) | Inlet and outlet extensions | done | 0001 |
| [0009](0009-per-fitting-wall-patches.md) | Per-fitting wall patches | done | 0001 |
| [0010](0010-equipment-nozzle-boundaries.md) | Equipment nozzles as network boundaries | done | 0002 |
| [0011](0011-assembly-independent-of-legacy.md) | Assembly independent of legacy code | done | 0004 |
| [0012](0012-miter-bend-and-elbow.md) | Miter bends and standard elbows | done | 0004 |
| [0013](0013-reducer-expander.md) | Reducer, expander and transition | done | 0004 |
| [0014](0014-spline-pipe.md) | Spline pipe | done | 0004 |
| [0015](0015-io-on-assembly.md) | PCF and bathymetry readers build an Assembly | done | 0004 |
| [0016](0016-public-api-and-examples.md) | Public API, examples and docs on the assembly | done | 0004 |
| [0017](0017-delete-legacy.md) | Delete the legacy code | done | 0004 |
| [0018](0018-layer-termination-in-sweep.md) | Layer termination in `Sweep` (insulation stops and starts) | done | 0006 |
| [0019](0019-port-face-signatures-and-classifier.md) | Port-face signatures and the topology-switch classifier | done | 0011 |
| [0021](0021-pcf-reader-spec-conformance.md) | PCF reader: conform to the PCF reference guide (bug fixes) | done | 0004 |
| [0022](0022-rename-interface-groups.md) | Rename material-interface groups to `interface_<inner>_<outer>` | done | 0013 |
| [0023](0023-boundary-role-manifest-and-retyping.md) | Boundary-role manifest and OpenFOAM patch retyping | done | 0013 |
| [0024](0024-parallel-test-suite.md) | Parallel test suite (pytest-xdist) and registered markers | done | 0014 |
| [0025](0025-ruled-straight-slabs.md) | Ruled side surfaces for straight slabs, and a wall-exactness check | done | 0015 |
| [0026](0026-assembly-refined.md) | `Assembly.refined(k)`: uniform refinement for convergence studies | done | 0015 |
| [0027](0027-grading-change-across-sweeps.md) | Grading-only changes across a sweep (wall-resolved reducers) | done | 0016 |
| [0028](0028-rectangular-cores.md) | Rectangular cores in the assembly (single-layer ducts) | done | 0009, 0010 |
| [0029](0029-transition-circle-rectangle.md) | `Transition`: circle ↔ rectangle and rectangle ↔ rectangle sweeps | done | 0009 |
| [0030](0030-wye-prototype.md) | Wye prototype: symmetric Y-junction as a block layout | done | 0017 |
| [0031](0031-profiled-reducer.md) | Profiled `Reducer`: constrictions, venturis and nozzles | done | 0008 |
| [0036](0036-linear-build-time.md) | Linear build time: fewer `synchronize` calls, and a build benchmark | done | 0020 |
| [0037](0037-pcf-branched-networks.md) | PCF reader: branched networks and junctions | done | 0023 |
| [0038](0038-pcf-insulation-and-equipment.md) | PCF reader: insulation and equipment connections | done | 0023 |
| [0039](0039-interface-degree-and-session-guard.md) | Two validation bugs: overlapping fittings on one interface, GMSH calls outside a session | done | 0024 |
| [0040](0040-port-names-orientation-angle-units.md) | Named ports, absolute orientation (`toward=`, junction roll), `rot` in degrees | done | 0024 |
| [0041](0041-assembly-axial-cell.md) | `Assembly(axial_cell=…)`: `n_layers` from a target cell size | done | 0024 |
| [0042](0042-study-runner-core.md) | Study runner: study file, sampling, preflight, mesh stage, manifest | done | 0025 |
| [0043](0043-study-openfoam-stages.md) | Study runner: OpenFOAM case and run stages, shared OpenFOAM helpers | done | 0025 |
| [0044](0044-demo-study-laminar-bend.md) | Demonstration study: laminar 90° bend, loss chart and aligned dataset | ready (after 0043) | 0025 |
| [0045](0045-layer-outlines.md) | Layer outlines: circle and rectangle in either order, and rectangle in rectangle | done | 0026 |
| [0046](0046-multi-layer-transition.md) | Multi-layer `Transition`: every outline blends along the axis | done | 0026 |
| [0047](0047-skewed-rectangle-quality-limit.md) | Quality limit for rings with skewed corner lines (aspect-ratio sweep) | done | 0026 |
| [0048](0048-layer-outline-examples.md) | Examples for layer outlines and multi-layer transitions | done | 0026 |
| [0051](0051-exact-junction-walls.md) | Exact junction walls (tee and wye) | done | 0028, 0029 |
| [0052](0052-multi-layer-tee.md) | Multi-layer tee: shells as offset levels of the junction | done | 0028 |
| [0053](0053-multi-layer-wye.md) | Multi-layer wye: shells as offset level sets | done | 0028 |
| [0054](0054-insulated-junctions-end-to-end.md) | Insulated junctions end to end: PCF, example, docs | done | 0028, 0023 |
| [0055](0055-cosine-bulge.md) | Cosine profile bulges: `("cosine", s0)` with s0 ≤ 0 | done | 0008 |
| [0056](0056-projection-limits-and-wye-axial-counts.md) | Projection follow-ups: inversion check, move warning, wye axial counts | done | 0029 |
| [0057](0057-duct-tee-rectangular-tap.md) | Duct tee: full-width rectangular tap on a rectangular duct | done | 0027 |
| [0058](0058-duct-tee-round-tap.md) | Duct tee: round tap on a rectangular duct | superseded by 0070 | 0027 |
| [0059](0059-branched-hvac-example.md) | Example: a branched HVAC supply | done | 0027 |
| [0060](0060-tee-angle-laterals.md) | General branches, stage 1: `Tee(angle=…)`, laterals | done | 0031 |
| [0061](0061-tee-offset-taps.md) | General branches, stage 2: `Tee(offset=…)`, tangential and offset taps | done | 0031, 0023 |
| [0062](0062-straight-twist.md) | General branches, stage 3: `Straight(twist=…)`, and `toward=` at any roll | done | 0031, 0029 |
| [0063](0063-duct-shoe-taps.md) | General branches, stage 4: shoe taps on ducts | done | 0031, 0027 |
| [0064](0064-pcf-reader-robustness.md) | PCF reader robustness: annotations, unknown inline components, several networks | done | 0023 |
| [0065](0065-network-model-and-builder.md) | Network interchange 1a: the network model, and the builder out of `pcf.py` | done | 0032 |
| [0066](0066-network-model-operations.md) | Network interchange 1b: select, cut, join, merge, and the public API | done | 0032 |
| [0069](0069-duct-tap-pillow-prototype.md) | Prototype: duct tap with a pillowed ring (hole on the wall) | done (Q1 answered: B adopted, decision 0033) | 0033 |
| [0070](0070-duct-tap-merge-into-tee.md) | Duct taps: the pillowed tap in `Tee` | done | 0033, 0027 |
| [0073](0073-validation-metadata-and-coverage.md) | Validation metadata (`case.json`), categories and a coverage matrix in the gallery | done (Q1, not blocking: `conduction` tag) | 0012 |
| [0076](0076-second-order-export.md) | Second-order mesh export: `Assembly.mesh(order=2)` | done | 0034, 0029 |
| [0078](0078-readme-generated-sections.md) | README: generated numbers, validation table, hero image and checks | done | — |
| [0080](0080-installable-package.md) | Installable package: extras, version, console command, install smoke test | done | — |
| [0081](0081-architecture-tests-and-contracts.md) | Architecture tests (DESIGN §3.1), and the cross-package leaks | done | 0037 |
| [0082](0082-sections-package-oh-layout.md) | `hexmesh.sections`: the O-H layout described once | done | 0037 |
| [0083](0083-shape-protocol.md) | Shapes own their behaviour: the shape protocol | done | 0037 |
| [0084](0084-h-section-layout-and-sweeps.md) | The H section: the layout, `layout=` on the spec, and every sweep | done | 0036, 0037 |
| [0085](0085-oh-h-switch-and-transition.md) | The O-H ↔ H switch, and `Transition` to an H rectangle | done | 0036, 0011 |
| [0086](0086-h-ports-on-duct-junctions-and-shells.md) | H ports on duct junctions, and shells around an H core | done | 0036, 0026 |
| [0087](0087-h-default-flip.md) | Make H the default rectangular core (version 0.4.0) | done | 0036 |
| [0088](0088-n-outer-sub-partition.md) | `n_outer = 8` as a sub-partition of the O-H face (exact core cuts) | done | 0005, 0010 |
| [0089](0089-richardson-growing-differences.md) | `richardson()`: no order when differences grow; recheck accepted cases | done | 0015 |
| [0090](0090-shared-parallel-openfoam-runs.md) | Parallel OpenFOAM runs in the shared helpers, used by every driver | done | 0012, 0025 |
| [0091](0091-msh-recipe-block.md) | The `.msh` recipe block: logo, generated by, the assembly description | done | 0038 |
| [0092](0092-platform-support.md) | Platform support: portable meshing, a portable Docker runner, CI on three systems | done | 0039 |
| [0093](0093-validation-results-json.md) | Each validation case keeps its full-precision results next to RESULTS.md | done | 0012, 0015 |
| [0094](0094-structured-errors.md) | Structured errors: a code, a location, the value and the limit | done | 0040, 0019 |
| [0095](0095-limits-and-schema.md) | Limits with units, and a JSON Schema generated from the registries | done | 0040, 0019 |
| [0096](0096-pcf-line-numbers.md) | PCF errors name the line: record `Provenance.line` | done | 0040, 0032 |
| [0097](0097-describe-and-preview.md) | `describe` and `preview`: what a network is, without GMSH | done | 0040, 0019 |
| [0098](0098-advise-and-cli.md) | `advise` (the resolution advisor) and the `hexmesh` CLI | done | 0040 |
| [0100](0100-trace-tied-rectangle-counts.md) | Trace why rectangle side counts are tied next to circles and shells | done | 0041 |
| [0101](0101-untie-rectangular-shell-counts.md) | Unequal side counts through a stack of rectangular outlines | done | 0041, 0026 |
| [0102](0102-agent-manifest.md) | `hexmesh manifest`: one machine-readable account of the suite | done | 0040 |
| [0103](0103-network-angled-tees.md) | The network builder takes angled tees | done | 0031 |
| [0104](0104-junction-nonorthogonality-prediction.md) | Junctions predict non-orthogonality in `validate()` | done | 0031 |
| [0105](0105-windows-ci-green.md) | CI green again: the Windows gmshToFoam test | done | 0039 |
| [0106](0106-error-coverage-and-hints.md) | Every user-facing error coded, and hints where they help | done | 0040 |
| [0107](0107-light-commands-without-gmsh.md) | The light commands load neither gmsh nor scipy | done | 0040 |
| [0110](0110-readme-agent-primer-checked.md) | The README's agent primer: its numbers checked | done | 0040 |
| [0111](0111-hints-equipment-study.md) | Hints for equipment and study errors; the layout errors reviewed | done | 0040 |
| [0112](0112-wye-layout-cache.md) | Cache the wye's layout, so the light commands stay light | done | 0040 |
| [0113](0113-python-floor-311.md) | Python 3.11 is the oldest supported; CI green again | done | 0039 |
| [0114](0114-pcf-sample-and-cli-insulation.md) | A committed PCF sample, and insulation from the `hexmesh` commands | done | 0032, 0040 |
| [0115](0115-release-0-5-0.md) | Release 0.5.0: the launch version, its install line and a stability statement | done | — |
| [0116](0116-wye-redesign-measurement.md) | The wye redesign, measured: the hub generalised, and the published topology's feasibility | done | 0043, 0042 |
| [0117](0117-written-junction-nodes-experiment.md) | Written nodes (route B3): one hex block placed by hexmesh, between two transfinite straights | done | 0043 |
| [0118](0118-junction-cube-probe.md) | The oriented junction cube, measured: equal tees and laterals on 6-faced blocks | done | 0043 |
| [0119](0119-volunteer-tool-and-helical-card.md) | Volunteer runs: the tool, the runners, and the helical pipe's card | done | 0044, 0012 |
| [0121](0121-idealised-aorta-example.md) | Example: an idealised aorta (arch, branches, taper and the iliac bifurcation) | done | 0018, 0043 |
| [0122](0122-equal-tee-oriented-cube.md) | Equal tees and equal laterals: the oriented junction cube behind `Tee` | done | 0043, 0031, 0046 |
| [0123](0123-report-what-hexmesh-changed.md) | Report what hexmesh changed in gmsh's mesh: corrections recorded, written elements stated | done | 0046 |
| [0124](0124-wye-written-nodes-opt-in.md) | Written nodes for `Wye`, opt-in: measure a B3 layout, and offer it only where it beats the hub | held (after 0122, 0123) | 0046, 0043 |
| [0125](0125-pcf-tee-run-length-hint.md) | PCF tees too short for their run: a hint a PCF user can act on | done | 0042 |
| [0126](0126-projection-blend-into-internal-faces.md) | Carry the wall projection's move into the internal faces: the equal tee's slide, equal laterals, second order | done | 0046, 0029, 0043 |
| [0127](0127-equal-tee-fine-nang-tier.md) | The equal tee at fine `nang`: a measured tier in `validate()`, before gmsh | done | 0043 |
| [0128](0128-units-module.md) | `hexmesh.units`: length constants, and an audit of absolute tolerances | done (2 questions for design) | 0047, 0018 |
| [0129](0129-spline-and-roll-error-hints.md) | Two error messages that say where and what to do: a too-tight spline, a roll with no straight | done | 0042 |
| [0130](0130-record-bend-arc-placement.md) | Record a bend's second-order arc placement; say what second order is verified for | done | 0046, 0034 |
| [0131](0131-branch-radial-grading.md) | A tee branch with its own radial grading (and the Reducer pattern documented) | done | 0028, 0016 |
| [0132](0132-one-density-stated-up-front.md) | One density per network: say so up front, in the docs and in the error | done | 0003, 0042 |
| [0133](0133-density-change-probe.md) | Probe: two density changes meshed by gmsh (+1 radial ring, ×2 nang slab) | ready (after 1.0) | 0003, 0046, 0018 |
| [0134](0134-remove-cube-probe-and-gallery-render-helper.md) | Housekeeping: one render helper in the gallery builder (`_cube_probe.py` stays) | done | 0043 |
| [0135](0135-library-deduplication.md) | De-duplicate four repeated blocks in the library | done | 0042 |
| [0136](0136-split-assembly-internally.md) | Split `Assembly` into internal modules behind the same class | done | 0042 |
| [0137](0137-docs-site.md) | The docs site: Essens pages, our navigation and template, GitHub Pages | in progress (design session: waits for an Essens release with folder-pages) | 0049 |
| [0138](0138-snap-tolerance-per-reader.md) | The snap tolerance: one per reader, carried by the model, and documented | done | 0128 (Q2), 0018 |
| [0139](0139-relative-plate-tolerance.md) | Interior plates' tolerance relative to the face (scale) | ready | 0128 (Q1), 0018, 0046 |
| [0140](0140-rocket-injector-manifold.md) | Example: a liquid-rocket propellant feed line and ring injector manifold | ready | — |
| [0141](0141-tee-fill-fails-at-rounding-level-direction.md) | Bug: a tee's fill fails when its direction is 1e-16 off an axis | done | — |
| [0142](0142-gallery-three-pages.md) | The gallery as three pages and a landing page, by family | done | — |
| [0143](0143-merge-warns-on-snap-tolerance-mismatch.md) | `merge` warns when the two models' snap tolerances differ | ready | — |
| [0144](0144-validation-docs-for-people.md) | Validation documentation for people: install, run, read, send back | done | — |

### Validation

| Task | Title | Category | Status | Decision |
|---|---|---|---|---|
| [0020](0020-validation-poiseuille.md) | Validation: laminar Hagen–Poiseuille pipe, three refinement levels | V1 | done | 0012, 0015 |
| [0032](0032-validation-stenosis.md) | Validation: smooth cosine constriction (Varghese et al.), Re = 500 | V2 | done | 0008, 0012 |
| [0033](0033-validation-heated-rod.md) | Validation: solid rod with uniform heat generation | V1 | done | 0012, 0015 |
| [0034](0034-validation-layered-conduction.md) | Validation: conduction through a heated multi-layer cylinder (CHT, solids) | V1 | done | 0012 |
| [0035](0035-validation-heated-pipe-cht.md) | Validation: heated multi-layer pipe with laminar flow (full CHT) | V1 | done | 0012 |
| [0049](0049-validation-turbulent-pipe.md) | Validation: fully developed turbulent pipe flow (RANS, k-ω SST) | V2 | done | 0012, 0015 |
| [0050](0050-validation-turbulent-bend.md) | Validation: turbulent flow in a 90° bend (Sudo et al. 1998) | V3 | ready (after 0049) | 0012, 0015 |
| [0067](0067-validation-womersley.md) | Validation: Womersley flow (pulsatile laminar pipe flow, exact solution) | V1 | done | 0012, 0015 |
| [0068](0068-validation-pulsatile-stenosis.md) | Validation: pulsatile flow through the cosine stenosis (Varghese et al., Part 2) | V2 | done | 0012, 0015 |
| [0071](0071-validation-rectangular-duct.md) | Validation: fully developed laminar flow in rectangular ducts | V1 | done | 0012, 0015 |
| [0072](0072-validation-laminar-square-bend.md) | Validation: laminar 90° square-duct bend (Taylor et al., Re 790) | V3 | done | 0012, 0015 |
| [0074](0074-validation-mms-conduction.md) | Verification: manufactured solutions for conduction on every fitting's mesh | V1 | done | 0012, 0015 |
| [0075](0075-validation-helical-pipe.md) | Validation: laminar flow in a helical pipe (spline pipe) | V3 | blocked (held by the user until better hardware (2026-11-08); nang 24 done at Re 1800 and 2400, Re 3000 to run) | 0012, 0015 |
| [0077](0077-validation-fenicsx-second-order.md) | Verification: FEniCSx toolchain, and second-order export checked end to end | V1 | done | 0034, 0012, 0015 |
| [0079](0079-validation-taylor-bubble.md) | Validation: a Taylor bubble rising in stagnant liquid (VOF) | V3 | ready (v2406 runner) | 0012, 0015 |
| [0099](0099-validation-graphs.md) | Validation results as graphs: convergence, layouts, the stenosis against DNS | docs | done | 0012, 0015, 0036 |
| [0120](0120-validation-vattenfall-tjunction-stage-a.md) | Validation: the Vattenfall T-junction (thermal mixing), stage (a): case, mesh, data and volunteer card | V3 | ready (after 0119) | 0012, 0044 |
| [0108](0108-gmshtofoam-inversion-audit.md) | Audit the validation cases for gmshToFoam's silent inversions | V1 | done | 0012 |
| [0109](0109-mms-wall-slope.md) | MMS: does the order track the wall slope? | V1 | done | 0012 |


### Order

**Current order (2026-11-03, design).**  It replaces the order notes of
2026-10-25 to 2026-11-02; the tasks those named are done.  Work the
first `ready` item whose prerequisites are done.  The tracks marked
*alongside* may be picked up whenever the main track waits on the user
or a long run.

0. **Public readiness** (the repository is public; the user, 2026-11-07):
   **0105 → 0106 → 0107 → 0078** (CI green on Windows; every user-facing
   error coded, with hints; the light commands without gmsh; the README
   front page).  Before other work.
   Then, before the launch post (0110, 0108 and 0112 done):
   **0113** (Python 3.11 floor; CI green) → **0114** (a PCF sample;
   `--insulation`) → **0115** (release 0.5.0, last).  After the launch
   (the user, 2026-11-08): **0103** (angled tees in networks) → **0104**
   (junction non-orthogonality) → **0116** (the wye redesign measured;
   decision 0043) → **0111** (equipment and study hints) → **0109** (MMS
   wall slope); all done, with 0061 and 0062.  Next (2026-11-09):
   **0118** (the oriented junction cube, Bošnjak et al.) and **0117**
   (route B3, feasible) measured.  The user (2026-11-10): gmsh meshes
   (decision 0046), so the cube goes behind `Tee`: **0122** → **0123**
   (the report of what hexmesh changed) → **0124** (B3 opt-in for `Wye`,
   held) and **0121** (the aorta, on today's `Wye`).
   Volunteer runs (decision 0044): **0119** (the tool; the helical
   pipe's card) → **0120** (Vattenfall stage (a)).
1. **The H section** (decision 0036; 0082, 0083, 0084 and 0090 done):
   - **0085 → 0086 → 0087**, strictly in sequence.  0085 (in progress)
     builds the capped switch (decision 0036 amendment, 2026-11-04).
     The default flips only in 0087 (version 0.4.0, a breaking change
     for `nrad` on rectangular cores).
   - **0072** (square-duct bend), ready: it runs on the H section.
2. **Alongside, no blockers:**
   - user agents (decision 0040): **0095 → 0097 → 0098** (schema,
     describe and preview, advise and the CLI).  Then **0066** and the
     network document (decision 0032 stage 2, accepted) and **0102**
     (the manifest), then the plugin.
     0094 and 0096 done;
   - validation graphs: **0099** after 0098 (it edits the same
     `results.json` files);
   - rectangle cost (decision 0041): **0101** (shells around
     rectangles; 0100 done).  C (unequal arcs on a circle) is held;
   - general branches (decision 0031): **0060 → 0061 / 0062 → 0063**;
     after 0060, **0103** (angled tees in networks) and **0104**
     (junction non-orthogonality).
     0060 carries a design note from 0081: the duct-tap front end leaves
     `Tee`;
   - network interchange: **0066**.  Its design note: the readers move
     to `interchange.importers`;
   - validation: **0049 → 0044 → 0050**; **0074 → 0075**; **0079**;
   - second order: **0076**, with **0077**'s toolchain step in
     parallel, then 0077's checks;
   - **0078** (README generated sections), small, any time.
3. **Low priority:** **0088** (`n_outer = 8`), not alongside another
   task that edits `sections/oh.py`.  No fitting needs it yet.  Do it
   before the next junction template that wants corners at 0°/90°.

Runs that write more than ~1 GB follow CLAUDE.md's disk rule.  Long
OpenFOAM runs follow its shared-machine rule (`pgrep -af pytest` first).

## Ground rules

These apply to every task.

- Read `DESIGN.md` first.  Changes must follow it and must **not** add rows
  to its "Current deviations" table.
- Work only in `hexmesh/assembly/` (and other packages where the task
  states them).  Respect the capability order and rules of DESIGN §3.1.
- Anything computable without GMSH must be computed without GMSH (DESIGN
  P3/P4): in `ports()`, `validate()` or `Assembly.validate()`, never in
  `fill()`.
- Every task adds tests.  New fittings or fill changes must still pass the
  conformance kit, `tests/test_fitting_conformance.py`.
- Run tests with `python3 -m pytest` (never `python`).  Gate: no new
  failures before and after each task.  The full suite has no known
  failures.
  - Since task 0024 (2026-10-25), this runs **in parallel** (`-n auto`,
    from `pyproject.toml`) and **skips OpenFOAM tests**.  Serial for
    debugging: `-n 0`.
    Expected time (8 cores, 2026-10-27): about 4 min in parallel,
    12 min serial.
  - OpenFOAM tests are opt-in: `python3 -m pytest -m openfoam`.  Run
    them too when a task touches OpenFOAM output (e.g. 0009, 0022, 0023).
  - Follow `CLAUDE.md`, "Both sessions, shared machine", before long
    runs.
- **Validation cases show their meshes** (since 2026-10-28).
  `validation/<case>/run.py` defines `meshes()`, returning
  `(label, caption, build)` per mesh to show; the first gets an overview
  image.  Pick a few that tell the story (e.g. the refinement levels, or
  each series).  Then `python3 docs/gallery/build.py --validation <case>`
  renders `validation/<case>/img/` and writes the README's "Mesh" section
  between `<!-- mesh:start -->` / `<!-- mesh:end -->`.  It is inserted
  after "## Case" the first time; don't edit inside the markers.  Re-run
  it when the meshes change.  See `poiseuille` and `heated_rod`.
- **Every validation case ships a `case.json`** (since 2026-10-30, task
  0073): category V1–V4, references, tags (regime, physics, features
  from decision 0012's list, toolchain), status, gates and task, valid
  against `validation/case.schema.json`.  Update its `status` with
  RESULTS'.  The gallery stops on a missing or invalid one.  A planned
  validation task carries a `- **Category:** Vn` line and a
  `- **Features:**` line (feature names in backticks), which give its
  column in the coverage matrix.  Formulas in `case.json` (references,
  gates) and in example docstrings are LaTeX math (`$…$`), so
  `docs/GALLERY.md` typesets them; module docstrings with backslashes
  are raw strings (`r"""…"""`).  (2026-10-31, the user.)
- **The logo header** (since 2026-11-02, the user).  Every `.py` file
  in `hexmesh/`, `validation/`, `tests/` and `docs/gallery/` carries
  `docs/ascii-logo.txt` as a header.  Add it to each file you create or
  edit that lacks it.  Don't sweep untouched files.
  - A block of `# ` comment lines (`# ` + the logo line, no trailing
    spaces), then one blank `#` line, at the very top.  The only lines
    above it are a `#!` shebang and a `coding:` line, which must stay
    first.
  - Never in a docstring.  Its backslashes give `SyntaxWarning` in a plain
    one, and in a raw one it would become the module docstring, which
    eleven scripts use for `--help`.
  - Not in Markdown, generated output (OpenFOAM dictionaries, `.msh`) or
    data files.
  - Copy it byte for byte from `docs/ascii-logo.txt`, so a future check
    can match it exactly.
- **Disk space** (since 2026-11-02, the user): follow CLAUDE.md's
  rule.  A task's *Outcome* states the disk space its runs used, and
  that their outputs were removed.
- Keep each task a separate, reviewable change.  Match the surrounding code
  style: dataclasses, numpy, short docstrings that cite DESIGN rules.

### Not part of any task

Don't fold these into a task: wye work beyond task 0030's symmetric
prototype (decision 0017), tee generalisation (multi-layer, laterals, offset taps, exact tee
walls), `n_outer = 8` core filling, or anything in `docs/RESEARCH.md` §8.
They are design decisions, not low-hanging fruit.  (The tee side-corner
arc split is no longer needed: the block-layout tee places its saddle
corners on the branch diagonals, DESIGN §7.1.)

## Working a task (coding agent)

1. Pick a `ready` task whose dependencies are `done`.  Set its status to
   `in progress` here and in the task file.
2. You may refine **Do** and **Accept** with what you learn from the code.
   Record what you changed and why under **Agent notes**.
3. You may not change a decision record or edit `DESIGN.md`.  If the work
   needs a design choice, or shows that a decision is wrong:
   - write the question, with options and evidence, under **Questions for
     design**;
   - set the status to `blocked`;
   - stop, or move to another task.
   You may *propose* exact DESIGN.md wording there; the design session
   applies it.
4. When finished, fill in **Outcome**: what changed (files), test results
   (counts, and any known failures), measurements, surprises, and proposed
   follow-up tasks.  Set the status to `done`.

New tasks found while working go in **Outcome** as proposals.  The design
session turns them into task files.

## Task template

```markdown
# NNNN — Title

- **Status:** ready | in progress | blocked | done
- **Decision:** [NNNN — title](../decisions/NNNN-slug.md)  (or a DESIGN.md rule)
- **Depends on:** NNNN, … | —

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  The problem, with evidence (file:line, measurements).

**Where.**  Files and functions involved.

**Do.**  Numbered steps.

**Accept.**  Tests or measurements that prove it is done.

**Out of scope.**  (optional)

## Agent notes

## Questions for design

## Outcome
```
