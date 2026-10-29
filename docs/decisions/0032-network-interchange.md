# 0032 — Network interchange: importers, a network model, a network document, one builder

- **Status:** proposed (**work in progress**: a living plan.  Settled
  parts and open questions are kept side by side and revised as they
  settle; stages become tasks when accepted)
- **Date:** 2026-10-29 (started at the user's request: "we should make a
  plan (work in progress) where design decisions are justified")
- **Tasks:** stage 1 accepted 2026-10-29 (the user): tasks 0065 (network
  model and builder extraction) and 0066 (model operations and public
  API).  Later stages: none yet.

## Purpose

hexmesh takes networks from several sources: PCF (plant piping; decision
0023), bathymetry routes, and soon IFC (building-services ducts and
pipes) and VMTK centrelines (vascular, decision 0018).  This plan
defines the capability that turns any of them into an `Assembly`, and
the format in which an ingested network is saved, versioned and
exchanged.

## Names

The pattern is a compiler's (front-ends → intermediate representation
→ back-end), or CAD's neutral model and translators.

| Name | What it is | Compiler analogue |
|---|---|---|
| **network interchange** (`hexmesh.interchange`) | the capability as a whole | the toolchain |
| **importer** | reads one source format into the network model (PCF, IFC, bathymetry, VMTK) | front-end |
| **network model** | the format-neutral description of a physical network: points, parts, sections, attributes, provenance | intermediate representation |
| **network document** | the network model saved as versioned JSON-LD | the IR's text form |
| **builder** | network model → `Assembly` | back-end |
| **exporter** (later) | network model → a source format | the reverse direction |

## Where we start from (verified 2026-10-29)

- `hexmesh/io/readers/pcf.py` (1600 lines) mixes **PCF parsing** (units,
  records, SKEYs, keypoints) with a **generic builder**: the connection
  graph within a tolerance, joint absorption, the tree check, root
  choice, junction entry, insulation planning, equipment ends, and
  placement into an `Assembly`.
- `bathymetry.py` already reuses that builder by importing
  `NetworkSpec` / `ComponentSpec` from `pcf.py`.
- So a de facto IR exists, but it is PCF-shaped: `ComponentSpec` carries
  `skey`, `record_type` and `raw` PCF attributes, and a section is a
  nominal bore.  The spec callable is `spec(bore)`.

## Design choices

Each with the alternatives and why.  "Settled" means proposed as
settled within this plan; the plan is accepted stage by stage.

### 1. A shared network model and one builder (settled)

- **Chosen:** every importer emits the network model, and one builder
  turns it into an `Assembly`.
- **Alternatives:**
  - each importer builds its own `Assembly` (today's PCF;
    bathymetry borrows PCF's internals);
  - a base-class builder with per-format overrides.
- **Why:** the hard, valuable part is format-independent: connectivity
  within a tolerance, tree checks, root choice, junction entry,
  insulation placement, equipment ends, error format.  Written once, it
  is tested once, and every format gets every improvement: PCF's 0037,
  0038 and 0064 work becomes IFC's and VMTK's for free.

### 2. Composition over inheritance; inheritance only where it is natural (settled)

- **Chosen:** the shared contract is the data (the network model).
  Inheritance appears in two small places:
  - a closed hierarchy of **part types** the builder dispatches on;
  - a thin **`Importer` base**: `read(path) → NetworkModel`, plus a hook
    that formats a part's provenance for messages.
- **Alternative:** a builder base class that each format subclasses.
- **Why:** the formats describe networks too differently.  PCF has
  components with end points; IFC has elements joined by ports, with
  profiles; bathymetry has a polyline; VMTK a centreline with radii.  A
  base class shaped around one format forces the others into it, and its
  hooks multiply.  A data contract keeps importers independent.

### 3. The network model: ports and connections are first class (settled 2026-10-29)

The user asked for documents that hold several networks, and ports that
can be referenced, "so one can break and reconstruct networks as
needed".  That makes the model a graph of three node kinds:

- **Ports** (first class, each with a stable id):
  - position and direction;
  - **flow direction** when the source gives it (IFC ports do; PCF
    doesn't), otherwise unknown;
  - section;
  - optional equipment tag (item 7).
- **Parts** (closed set of types), each referencing its ports **in
  order**:
  - `Straight`;
  - `Bend` (by corner, or by centre and radius);
  - `Reducer` / `Transition` (size or shape change);
  - `Junction` (n ports);
  - `Joint` (absorbed);
  - `InlineEquipment` (valves, silencers: meshed as straights);
  - `Terminal` (an open end with a name);
  - `Polyline` (bathymetry routes, centrelines).
- **Connections** (first class): port ↔ port, recording **how they were
  established**: *declared* by the source (IFC `IfcRelConnectsPorts`,
  PCF `END-CONNECTION-PIPELINE`) or *inferred* within a tolerance (PCF
  end points), with the distance.  Inferred connections can then be
  reviewed, and declared ones trusted.
- **Networks:** named collections that reference parts.  A model (and a
  document) holds any number of them, and they may share ports.

Plus, on every node:
- **Sections:** circle (nominal and/or actual size) or rectangle
  (width × height), so ducts fit (decisions 0009/0026).
- **Attributes:** insulation status per part and port, names and labels,
  system membership.
- **Provenance:** source file, format, record id, line, and a source GUID
  where one exists (IFC).  Every error names "PCF component 5 (TEE,
  SKEY TEBW, line 64)" or "IFC #1234 IfcDuctFitting".  Users and agents
  need to find a problem's source (decision 0019, constraint 3), and for
  IFC it links mesh regions back to BIM elements.

**Operations** (public API, item 6):
- **select:** a sub-network, from a set of parts, a network name, or
  everything reachable from a port;
- **cut:** remove a connection, or split at a port; both sides become
  open ends with names;
- **join:** connect two open ports;
- **merge:** combine models or documents (ids are kept, clashes
  reported).

**Operation log** (settled 2026-10-29, the user):
- `cut`, `join` and `merge` change the model in place and **append to an
  operation log** on it: the operation, its arguments by id, the time,
  the hexmesh version.  The import itself is the log's first entry (the
  importer, its source and options).
- The model then carries its own edit history ("imported from PCF, cut
  at V-101, joined to iso 2"), the way `Assembly.to_dict()` records how
  an assembly was built.
- The network document saves the log (stage 2), so an edited network is
  **reproducible** (replay the log on the source) and **reviewable**.
- It also gives undo (replay all but the last), and a ready mapping for
  any later agent tools or service (decision 0019).
- **Selections** don't change the model and aren't logged; a build
  records the selection it used in its own provenance.

**Not REST (settled 2026-10-29):** the public API is a Python library
API.  REST would be a service layer, which nothing planned needs.  The
model is designed so a service or the agent tools (decision 0019, MCP)
could sit on it as a thin wrapper, with no change:
- stable ids (the would-be resources);
- the network document as the one representation (`application/ld+json`);
- structured errors;
- long operations as jobs.

The builder takes a model plus a selection.  This is also how IFC
models networks (ports and port connections), so the IFC importer is
close to a direct mapping.

**Why this shape:** importing only produces a model; what to mesh is a
separate choice.  A plant model can be cut at an isolation valve, a
duct system split per floor, or two PCF isometrics joined at their
shared end, without re-importing.

### 4. `spec(section)` instead of `spec(bore)` (settled; compatible)

- **Chosen:** the spec callable receives a `Section` (shape, nominal
  size, actual dimensions); `section.bore` stays for PCF users, and a
  callable of one float keeps working (detected and adapted).
- **Why:** IFC gives actual rectangle sizes that must drive `RectShape`.
  A bore can't express a duct.

### 5. The network document: versioned JSON-LD (proposed; details open)

- **Chosen:** the network model saves to and loads from **JSON-LD**: plain
  JSON plus an `@context` mapping keys to vocabulary terms.
- **Alternatives:** plain JSON with a schema; a binary format; RDF
  Turtle.
- **Why:**
  - it is still plain JSON, for tools and agents that ignore the
    context;
  - it links to existing vocabularies where the meaning matches:
    - Flow System Ontology (W3C Linked Building Data): segments,
      fittings, terminals, connections;
    - ifcOWL / IFC GUIDs: traceability to the BIM element;
    - QUDT: units;
    - PROV-O: provenance;
  - our own `hm:` vocabulary covers the rest.
- **Graph, not tree:** a document is a `@graph` of ports, parts,
  connections and networks, any number of each, with references by
  `@id`.  Several networks per document, shared ports, and cut and join
  are all expressed directly.
- **Vocabulary mapping is shallow in v1** (settled 2026-10-29).
  "Depth" means how much of our model is mapped to external terms.
  - **Mapped:** the main classes and relations only: segment, fitting,
    terminal, port, connection, "feeds fluid to" (FSO), and the source
    GUID (IFC).
  - **Not mapped:** everything else (sections, insulation, provenance
    details) stays in `hm:`.
  - **Why:** every mapping claims our term means exactly theirs, and a
    wrong one is worse than none.  Deepen (QUDT units, PROV-O) when a
    real consumer needs it.
- **Rules:**
  - **Ordered arrays** (coordinates, a part's port list, polyline
    points) are declared `@list`: JSON-LD arrays are unordered sets
    otherwise.  A network's parts are a set (correct as is).
  - **Stable `@id`s**, the same names agents use (decision 0019,
    constraint 4).
  - **The context ships inside the package** and is versioned; loading
    never fetches from the network (offline use, reproducibility).
  - **Reading our own documents** needs only `json`; `pyld` (an
    optional extra) only to normalise foreign JSON-LD.
  - **One self-contained document in v1.**  References across documents
    work in principle (ids are IRIs), but resolving them is deferred
    (open question).
- **Versioning:**
  - a JSON Schema per version of the compacted form
    (`schemas/network-vN.json`), validated on load;
  - `schemaVersion` in the document;
  - upgrade functions between versions, as `intent.upgrade` does for the
    `Assembly` file.
- **Not for the `Assembly` save file:** that is a construction recipe,
  hexmesh-internal.  It stays plain versioned JSON with a schema (it may
  carry an `@context` for consistency, without semantic modelling).

### 6. The network model is a public API (settled 2026-10-29, the user)

Users and agents build, inspect and edit models in Python (and as
documents) before building.  It gets the same care as `Assembly`:
documented in `API.md`, stable names, structured errors, versioned with
the document schema.  Its part types, the operations of item 3, and the
builder entry point (`build(model, selection, spec, …) → Assembly`) are
the public surface; importer internals are not.

### 7. Equipment as a tag for now (settled 2026-10-29, the user)

A terminal (or an inline-equipment part's port) carries an equipment
tag: `{"tag": "P-101", "nozzle": "N1"}`, with an optional `kind` ("fan",
"vessel", "air terminal").  No geometry and no link to an equipment
description yet; the tag names the open end's patch (decision 0002's
rule) and survives round trips.  A richer reference can come later
without breaking documents (the tag stays).

### 8. Readers in the generator layer (settled; decision 0030)

Importers, the network model, the document and the builder live in
hexmesh (the generator), not in the study engine.  The network document
schema is one of the suite's versioned contracts (decision 0030,
constraint 3).

## Stages

1. **Refactor** (no behaviour change) — **accepted 2026-10-29**, tasks
   0065 and 0066:
   - move the generic builder out of `pcf.py` into
     `hexmesh.interchange`;
   - introduce the network model (ports, parts, connections, networks,
     sections, provenance) and its operations (select, cut, join,
     merge), as a public API;
   - port PCF and bathymetry to it;
   - `spec(section)` with the one-float adapter.
   - **Accept:** every reader test unchanged, and identical
     `to_dict()` / meshes for every fixture.
   - Task 0064 (PCF robustness) goes before it or folds into it.
2. **Network document v1:** JSON-LD write/read, the JSON Schema, the
   shipped context, `@list` and `@id` rules, round trips on every
   fixture (model → document → model identical).  Vocabulary: `hm:`
   first, mappings to FSO / QUDT / PROV-O where clean.
3. **IFC importer** (ducts first): IfcOpenShell as an optional extra
   (`hexmesh[ifc]`, LGPL-3.0).
   - Map segments to `Straight` with their profile, and fittings by
     ports: 2 ports → bend or reducer/transition; 3 → junction.
   - Equipment becomes `Terminal` or `InlineEquipment`.
   - Fixtures (licences checked 2026-10-29, `docs/integrations/`):
     EnEff-BIM air-handling unit (MIT), ConMan2 HVAC (MIT), buildingSMART
     `Building-Hvac.ifc` via BIMvoice (CC-BY-4.0), committed with their
     notices.
   - IFC port flow directions are kept, and the builder prefers them
     for the root.
   - Needs the duct tees (tasks 0057–0059) for branched networks.
4. **IFC pipes** (`IfcPipeSegment`, `IfcPipeFitting`): the same importer,
   pipe sections.
5. **VMTK centrelines** (decision 0018): `Polyline` parts with radii;
   needs the vascular work.
6. **Exporters** (later): network model → PCF / IFC, for round trips
   with the source tools.

## Open questions

Settled 2026-10-29 (now items 3, 5, 6, 7): public API; shallow
vocabulary mapping; flow direction kept when given; several networks
and port references per document; equipment as a tag.

Still open:
- **References across documents** (imports): when, and how ids
  resolve.
- **Which FSO terms exactly** (check the ontology before stage 2:
  `fso:connectedWith`, `fso:feedsFluidTo`, segment / fitting / terminal
  classes).
- **Inferred connections:** the default tolerance rule (today's PCF
  rule), and whether a document stores inferred connections or
  re-infers them on load.  Leaning: store them, marked *inferred*,
  so a document is reproducible.
- **Flow direction conflicts:** a selection whose declared flow
  directions disagree (two sources feeding one pipe): an error, or a
  warning with the builder choosing?

## Constraints for decisions going forward

1. **Format-specific code stays in importers.**  The builder never
   branches on the source format.
2. **Every part carries provenance**, and every error names it.
3. **The network document is versioned with a schema**, and loading
   never needs the network.
4. **Importers are optional extras when they need third-party libraries**
   (IfcOpenShell, pyld); core hexmesh stays numpy-only.

## Effect on future expansions

- **0018 (vascular):** a VMTK importer onto `Polyline` parts (stage 5);
  constraint 1 keeps it independent of PCF.
- **0019 (agent SDK):** the network document is a natural agent input
  ("edit the network, then build"); provenance gives structured errors
  their location.
- **0021 (flow restrictions):** PCF instruments and orifice flanges stay
  `InlineEquipment` until stage-1 restriction fittings exist; the record
  type is kept, so a later mapping can find them.
- **0030 (suite):** the network document is one of the suite's versioned
  contracts; importers sit in the generator layer.

## Verified vs. assumed

- **Verified (2026-10-29):**
  - the structure of `pcf.py` and bathymetry's reuse of it;
  - the IFC fixtures' licences and contents (counts of segments,
    fittings, ports and connections; `docs/integrations/ifc.md`);
  - the PCF fixture sources (`docs/integrations/pcf.md`).
- **Assumed:**
  - that the PCF builder separates cleanly from the parser (stage 1
    tests it);
  - that FSO's terms match our parts closely enough to map;
  - that IfcOpenShell exposes ports and profiles as needed.
