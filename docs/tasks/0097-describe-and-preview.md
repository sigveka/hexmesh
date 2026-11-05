# 0097 — `describe` and `preview`: what a network is, without GMSH

- **Status:** ready (after 0095)
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
