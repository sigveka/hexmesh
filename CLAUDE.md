# hexmesh — Claude context

## Project overview

Structured all-hex mesh generator for CFD pipe networks using GMSH. Pipes are built as transfinite hex blocks using an OH (O-grid + H-block) cross-section topology. Designed for OpenFOAM simulations; tet elements in junction zones are not acceptable.

**Read `DESIGN.md` first.** It defines the design principles and assembly rules (interfaces first-class, fittings are fills, conformal by construction). New code must follow it and must not add to its "Current deviations" table.

For fitting mathematics (frames, bend/miter geometry, tee/lateral intersection
curves, published bifurcation block topologies) see `docs/RESEARCH.md`;
citations in `docs/references.bib`, papers in `docs/papers/`.

## Design ↔ coding workflow

Design discussion and coding happen in separate sessions, handed over
through files:

- `docs/decisions/NNNN-*.md`: why (options, choice, consequences).  The
  only route by which `DESIGN.md` changes.  Process and template in
  `docs/decisions/README.md`.
- `docs/tasks/NNNN-*.md`: what (steps, acceptance, findings).  Index,
  ground rules and template in `docs/tasks/README.md`.

**Coding session:** work only `ready` tasks, and keep the status current in
the task file and the index.  You may refine a task's steps (record it under
*Agent notes*).  Never edit `DESIGN.md` or a decision record.  For design
questions, or proposed DESIGN wording, write under *Questions for design*,
set the task to `blocked`, and stop or switch task.  Finish with *Outcome*:
files, test counts, measurements, surprises, proposed follow-ups.

**Both sessions:** record version-specific tool behaviour (gmsh/OCC,
OpenFOAM) in `docs/integrations/<tool>.md` as soon as it is found, with
version, evidence and date.  Check those files, and the installed
`help(gmsh…)` docstrings, before the vendor manuals in `docs/manuals/`.
The gmsh 3.0 PDF there is outdated.

**Both sessions, shared machine:** the design and coding sessions may run
at the same time on this machine.
- Stop only processes you started, by their task or process ID.
  **Never kill by name pattern** (`pkill -f pytest`, `killall python3`):
  it hits the other session's test runs.
- Before a long or CPU-heavy run (the full suite, OpenFOAM cases,
  benchmarks), check for another session's run (`pgrep -af pytest`).
  Don't start timing measurements while one is active.
- Write scratch output to your own session's scratchpad or a
  `tmp_path`, never to shared fixed paths.

**Design session:** start by reading tasks that are `blocked` or newly
`done`.  Move measurements into `RESEARCH.md` and answer questions.
Record settled questions as decisions, then write tasks; unsettled ones
stay `proposed`, with no tasks.  Check every new decision against the
constraints of the future expansions listed in
`docs/decisions/README.md` (vascular networks, decision 0018; agent SDK, decision 0019; flow
restrictions, decision 0021; simulation suite, decision 0030).

---

## Cross-section topology: `n_outer`

### Parameter separation

Two kinds of parameters govern a `PipeSpec` cross-section.

**Topology** fixes where conformal interfaces land.  It can't change
without rebuilding geometry:
- `n_outer`: number of outer structural corners;
- `rot`: rotation of the outer corner frame;
- the layer stack: which materials, in what order.

**Density** is resolution only, and can be scaled without changing
topology:
- `nang`: divisions per 90° arc, shared by every layer;
- `nrad`: cells across each radial layer;
- `n_layers`: axial cells, per fitting.

`Reducer` relies on this split: its outlet may differ from its inlet in
radii only.  Topology and density must match.

### `n_outer`

| `n_outer` | outer arc angle | assembly support |
|-----------|-----------------|------------------|
| 4         | 90°             | yes: the 5-patch O-H face |
| 8         | 45°             | no: `check_supported` rejects it |

- **Constraint:** `nang % (n_outer // 4) == 0`, so each outer arc gets a
  whole number of divisions.  `n_outer` is a multiple of 4.  Both are
  enforced in `PipeSpec`.
- **Why `n_outer = 8` is rejected:** today's `build_oh_circle8` makes one
  8-sided centre patch, which can't bound a transfinite hex block
  (DESIGN §9).
- **Open question:** whether `n_outer = 8` should instead be a
  sub-partition of the 4-corner grid is decision 0005 (proposed).
- **Junction relevance:** junctions need corners at 0°/90°/180°/270°
  (DESIGN §7).  The wye's background is in `docs/RESEARCH.md` §4.

### Resolution and cell count

The assembly has no global `refinement` multiplier.  Density is set
explicitly on `PipeSpec` and on each fitting.  The cell count is exact
before meshing: `Assembly.cell_count()`, and
`Assembly.validate(max_cells=…)` for a budget.

Doubling every density parameter doubles the nodes in each direction,
which gives **8× the cells** in 3-D.  Users from unstructured meshing
expect a linear relationship, so keep this prominent in user docs.
