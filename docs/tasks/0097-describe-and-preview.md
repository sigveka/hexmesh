# 0097 — `describe` and `preview`: what a network is, without GMSH

- **Status:** done
- **Decision:** [0040 — Agents for users](../decisions/0040-user-agents-network-design-and-resolution.md) (foundation C); [0019](../decisions/0019-future-agent-sdk.md) item 4
- **Depends on:** 0095, which creates `hexmesh.agent`.  Not on the
  network document: this task works on `Assembly` descriptions and on
  in-memory `NetworkModel`s.

Ground rules for all tasks: [README](README.md#ground-rules).

**Why.**  An agent, or a person, writing a network needs to see what it
wrote before meshing: where the open ends are, how long the runs are,
whether a branch points the right way.  The fittings already compute
their paths without GMSH (`path(a, b, spec)`,
`centreline_length(...)`, in `assembly/fittings.py` and
`assembly/sweep.py`), and `validate()` and `cell_counts()` are pure
Python.  Nothing yet assembles these into a summary or a picture.

**Where.**  `hexmesh/agent/describe.py`, `hexmesh/agent/preview.py`;
tests; `API.md`; `pyproject.toml` (an optional extra for the preview).

**Do.**
1. **`describe(assembly | description | network_model) → dict`**,
   JSON-safe and deterministic.  It needs no GMSH and no meshing.
   - Per fitting (or part):
     - index, label and type;
     - its inlet and outlet frames (position, direction);
     - centreline length and section (shape, sizes, layout);
     - cell count.
   - Open ends: their name (the patch name the build will use),
     position, outward direction and section.
   - Junctions: the branch directions and the angle between them.
   - Totals: bounding box, total centreline length per section, total
     cells (exact), and the warnings `validate()` gives (with codes).
   - For a `NetworkModel`: parts, ports and connections as they stand
     (inferred ones marked), the networks, and which parts the builder
     would reject, and why (`Part.reject`).
   - Units in the output (`"units": {"length": "m", "angle": "deg"}`).
2. **`preview(..., path) → path`**, a PNG with:
   - centrelines;
   - section outlines at each interface, from the frames and shapes;
   - labels at the fittings and open ends;
   - three orthographic views and an isometric one.
   - No GMSH.  matplotlib in a new optional extra, `hexmesh[preview]`.
   - Deterministic: fixed figure size and DPI, and no timestamps in the
     PNG metadata.
   - It must be cheap: under 2 s for the largest example.
3. **Python API only.**  The CLI (task 0098) wraps both.  The functions
   take what `hexmesh.agent.schema` describes.  The network-document
   input comes with decision 0032's stage 2.
4. **API.md:** a short section with one example of each output.

**Accept.**
- `describe` of every `hexmesh/examples` assembly runs without a GMSH
  session (test with gmsh not initialised), is valid JSON, and is
  byte-identical across two runs.
- Its open ends equal the patch names and positions of the real build,
  for three examples: a branched HVAC one, a PCF one and a wye.  Its
  cell totals equal `cell_count()`.
- `describe` of a PCF `NetworkModel` lists the parts the builder
  rejects, with their reasons.
- `preview` writes a PNG for every example, byte-identical across two
  runs, each under 2 s.  Commit three of them under `docs/` as
  reference images (small, under 200 kB each).
- The architecture test: `hexmesh.agent` imports only the public API,
  and nothing imports it.
- Full suite: no new failures.

**Out of scope.**  Rendering meshes (that's the gallery's), and
interactive views.

## Agent notes

- **Modules.**  The code is in `hexmesh/agent/_describe.py` and
  `_preview.py`, not `describe.py` and `preview.py` as the task says.
  The package exports the functions `describe` and `preview`.  A
  submodule of the same name would replace the function on the package
  as soon as it is imported (`hexmesh.agent.describe` became a module,
  and the tests failed with "'module' object is not callable").  The
  same was done for `schema` in 0095.
- **Units of an assembly's lengths: `"as given"`, not `"m"`.**  hexmesh
  never converts an assembly's lengths, and 0095's schema calls the
  unit `length` for that reason.  A network model is in metres, so its
  `units` say `"m"`.  If design wants `"m"` for assemblies too, it is a
  one-line change, but it would be wrong for a model built in mm.
- **Geometry.**
  - A sweep's centreline is its `path()` station positions.
    `Transition` to an H face stops short of its outlet port, because
    its built-in switch isn't in `path()`.  The centreline then joins
    the port with a straight run, which the switch is.
  - A junction's centreline runs from its centre
    (`inlet + run_length · normal`) to each port.
  - Centreline lengths come from `centreline_length()` where the fitting
    has one; otherwise they are the polyline length.
- **Validation in `describe`.**  `validate()` runs under
  `warnings.catch_warnings`, and its warnings are returned with their
  codes.  An error is returned as `HexmeshError.to_dict()`, not raised;
  `cells` is then `None`.
- **Open ends.**  The outward direction is `-normal` when the end is the
  inlet of its fitting (`ports[0]`), and `+normal` otherwise.
- **The real-build check** (`test_open_ends_match_the_real_build`)
  meshes each source and maps the `open_end` physical groups,
  `<layer>_<patch>`, back to patch names.  The centroid of each patch's
  nodes equals `describe`'s position to 10⁻⁶ of the network size.  The
  sources are `hvac_branched`, `wye`, and a PCF tee written in the test.
  No example is PCF-built.
- **`preview`** draws with `matplotlib.figure.Figure` on Agg, not
  `pyplot`: no global state and no backend choice.
  - The isometric view is a fixed 2-D projection, not a 3-D axis.
  - `savefig(metadata={"Software": None})` drops the only varying chunk,
    so the PNG is byte-identical across runs.
  - Model previews draw parts through their ports: junctions from their
    centre, bends through their corner.  Rejected parts are labelled
    "(rejected)", in red.
- **Architecture.**  `AGENT_IMPORTS` in `test_architecture.py` lists
  what `hexmesh.agent` may import, with a planted case:
  - `hexmesh`, `hexmesh.assembly`, `hexmesh.interchange` and
    `hexmesh.errors`;
  - the documented registries `assembly.intent` and `assembly.limits`
    (`FITTING_TYPES`, `LIMITS`);
  - `core.params` and `core.shape` (`UNITS`, `SHAPES`).
  0095's rule (nothing imports `hexmesh.agent`) covers the rest.
- **Extras.**  `preview = ["matplotlib>=3.5"]` is the new extra.
  matplotlib is also in `dev`, so CI runs the preview tests.  Without it
  they skip.

## Outcome

**Files.**
- New:
  - `hexmesh/agent/_describe.py` and `_preview.py`;
  - `tests/test_agent_describe.py`;
  - `docs/agent/preview_hvac_branched.png` (105 kB),
    `preview_bifurcation_tree.png` (112 kB) and `preview_pcf_tee.png`
    (60 kB).
- Changed:
  - `hexmesh/agent/__init__.py`;
  - `tests/test_architecture.py`;
  - `pyproject.toml`: the `preview` extra, and matplotlib in `dev`;
  - `API.md`: "Describe and preview";
  - `CHANGELOG.md`.

**Measurements** (all 28 examples, this machine):
- `describe`: 0.02–4.3 s per example, for building the example and two
  calls.  Most of it is `validate()`'s junction predictions; the slowest
  is `insulated_network`, with a tee and a wye.
- `preview`: 0.35–1.0 s per example, against the 2 s budget.  The PNGs
  are 60–132 kB.
- A NetworkModel needs no validation, so describing one is
  milliseconds.

**Checks.**
- 64 new tests:
  - `describe` of every example: no GMSH session before or after; valid
    JSON (`allow_nan=False`); byte-identical across two runs and between
    the assembly and its `to_dict()`; cells per fitting and in total
    equal `cell_counts()` and `cell_count()`.
  - Open ends against the real build for `hvac_branched`, `wye` and a
    PCF tee: the same patch names, and positions to 10⁻⁶ of the network
    size.
  - The wye's angles and outward directions.
  - A failing assembly is described, with its error code.
  - A PCF model with an angle valve lists it as rejected, with the
    reason and line 8.
  - `preview` of every example: a PNG, byte-identical across runs, with
    no software or time chunk, in under 2 s; and of a model.
- 2 new architecture tests: the agent imports only `AGENT_IMPORTS`, with
  a planted case.
- Full suite: 3311 passed, 15 skipped (3245 + 64 + 2).  This task
  changes no library module outside `hexmesh/agent`, so the meshes and
  messages are untouched.

**Surprises.**
- `Transition` to an H face: `path()` doesn't reach the outlet port
  (the built-in switch), so the centreline would have had a gap.
- `describe`'s cost is dominated by `validate()`.  0098's `advise` may
  want a way to skip validation when it describes repeatedly.

**Proposed follow-ups.**
- Should `describe` take a `validate=False` switch?  (A question for
  0098, not done.)
- The network document input arrives with decision 0032 stage 2.
