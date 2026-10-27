# 0021 — Future expansion: flow restrictions (orifices, nozzles, venturis, and beyond)

- **Status:** proposed (future expansion; staged plan, no tasks beyond
  those already written)
- **Date:** 2026-10-27 (recorded at the user's request: "we should have
  a future plan for these different kinds of flow restrictions")
- **Tasks:** none new.  Stage 0 is tasks 0031 and 0032 (decision 0008).

## Context

Flow restrictions are common in pipe networks: flow meters (orifice
plates, nozzles, venturis), restriction orifices, bellmouths, flow
conditioners, valves.  hexmesh can reach many of them with two
mechanisms it already has, plus a few planned ones.

**Experiment (2026-10-26, design session).**  A concentric sharp-edged
orifice built from existing parts: the fluid split into a core of
radius d/2 and a fluid ring d/2 → D/2 (two layers both named `fluid`),
and the plate as the ring stopping for one cell
(`Straight(…, stack_changes=…)`, task 0018).  D = 0.1, d = 0.05, plate
2 mm:
- all-hex, 5 604 cells = predicted; one `fluid` volume; plate faces come
  out as walls (`fluid_end`, 192 faces);
- min SICN 0.39 in the plate section (cells meet the plate square-on);
  0.13–0.18 in the plain pipe either side;
- **broken:** the two same-named layers collide in group naming: the
  ring's inlet and outlet faces end up in *unnamed* groups;
- **wrong:** the core/ring boundary is written as
  `interface_fluid_fluid`.

So the layer stack needs a distinction between a layer's **name**
(identity, used by stack changes) and its **material** (volumes,
regions, patches, interfaces).

## The plan, by kind of restriction

| Kind | Approach | Mechanism | Stage |
|---|---|---|---|
| Smooth constrictions, venturis (ISO 5167-4), ISA 1932 and long-radius nozzles (ISO 5167-3), cosine stenosis | profiled sweep | profiled `Reducer` | **0** (tasks 0031, 0032) |
| Concentric sharp-edged orifice plate (ISO 5167-2), single-hole restriction orifice | fluid core + fluid ring; the ring stops for the plate thickness | layer termination (0006) + name/material split | 1 |
| Plate as solid cells (heat transfer) | the ring changes material to the plate's instead of stopping | new stack change: material change | 1 |
| Thin plate as a zero-thickness baffle | ring faces at one station as an internal group → OpenFOAM `createBaffles` | internal face group with a new role | 1 |
| Downstream bevel (ISO 5167-2 thick plates) | the core widens conically inside the plate section | profile inside a stack-changed section | 2 |
| Quarter-circle and conical-entrance orifices (ISO/TR 15377) | the core follows the rounded or conical entry inside the plate | as above | 2 |
| Multi-stage restriction orifices | repeated plates | stage 1, repeated | 2 |
| Bellmouth inlets | a profile at an open end | profiled `Reducer` | 2 |
| Eccentric orifice | the hole is off-centre: an eccentric core inside the ring | section geometry ("shape is geometry", 0009) | 3 |
| Segmental orifice | the hole is a circular segment | a contour section shape (0018, item 7) | 3 |
| Cone meters (V-cone), central bodies | the **core** stops (a solid body on the axis), flow in the ring | inner-layer termination: an annulus-only section, switch class 3 | 3 |
| Multi-hole and perforated plates, flow conditioners (tube bundles, Zanker, NOVA), valves with internals (gate, globe, butterfly, part-open ball) | not a swept section | non-conformal coupling or an external mesher (decision 0003, option C) | 4 (outside the swept model) |

**Connecting a restriction to ordinary pipe.**  A one-layer and a
two-layer fluid section have different connectivity (switch class 3).
Until a switch exists, a metering run uses the two-layer fluid spec
throughout, and a `Reducer` moves the core radius between d/2 and its
normal proportion (a radius-only change, class 0).  ISO 5167 requires
long straight runs on both sides of a meter anyway.

## Prerequisites per stage

- **Stage 1:** a decision on layer name vs material (layers keep unique
  names; volumes, open-end patches, regions grouped by material;
  interface groups only between different materials).  Then an
  `Orifice(d, thickness, …)` fitting generating the stack changes and a
  plate wall patch (`fluid_wall_<label>`), and an `orifice` example.
  Material-change stack changes and the baffle role follow.
- **Stage 2:** profiles and stack changes composed in one fitting
  (per-station specs in the shared sweep machinery; decision 0018,
  constraint 2).
- **Stage 3:** eccentric section geometry; contour sections; inner-layer
  termination and annulus-only sections (a class-3 switch strategy,
  decision 0003).
- **Stage 4:** decision 0003, option C.

## Validation references (to check when each stage is tasked)

Literature survey: RESEARCH §10 (2026-10-27).

- Stage 0: Varghese et al. stenosis DNS (task 0032).
- **Stage 1, laminar first:** low-Re orifice data from
  [`johansen_1930`], [`hollingshead_and_johnson_etal_2011`] (the
  orifice coefficient rises to a maximum, then drops, as Re falls) and a
  2023 laminar β = 0.5 study.  This reuses the laminar pipeline (tasks
  0020, 0033–0035), with no turbulence model.
- **Stages 1–2, turbulent:** the ISO 5167-2 Reader–Harris/Gallagher
  equation (Re_D ≳ 5 000), with a RANS model (SST k-ω did best in the
  literature).  RANS typically lands 2–6 % from the coefficient, so gates
  come from that, judged with GCI.  Background: [`reader_harris_2015`],
  [`shah_and_joshi_etal_2012`] (OpenFOAM, against Morrison et al. LDA
  data).
- **Showcase:** two out-of-plane elbows upstream of an orifice
  (installation effects, RESEARCH §10.4).  It's where a conformal network
  mesh adds value over the 2-D axisymmetric baseline used for isolated
  devices.
- Nozzles and venturis: ISO 5167-3 and -4 coefficients (check the
  Venturi Re limit in the edition used).
- Stage 4: perforated-plate loss coefficients
  ([`malavasi_and_messa_etal_2012`]); conditioner criteria from ISO 5167.

## Constraints for decisions going forward

1. **Stack changes stay general in the data model.**  Decision 0006
   allows only outermost layers to stop; keep that as a `validate()`
   rule, not a data-model assumption, so inner layers (cone meters) and
   material changes (solid plates) can be added.
2. **Profiles and stack changes must compose** in one sweep (bevels,
   rounded entries): per-station specs belong to the shared sweep
   machinery (same as decision 0018, constraint 2).
3. **Don't key new groups or regions by layer name.**  The layer
   name/material split is planned; new code that writes groups, regions
   or roles should take the material from one place.
4. **Section geometry stays behind one abstraction**, so an eccentric
   core or a contour shape can join (decisions 0009, 0018).
5. **Boundary roles stay extensible** (decision 0013): a `baffle` role
   for internal face groups is expected.
6. **Validation is not laminar-only** (decision 0012): meters need
   turbulent RANS cases.

## Verified vs. assumed

- **Verified:** the orifice experiment above (cell count, groups,
  quality, the two group-naming faults); that a two-layer spec with equal
  names is accepted by `PipeSpec` and validates.
- **Checked 2026-10-27** (RESEARCH §10): the references above exist,
  with bibliographic details; findings mostly from abstracts and
  repository records.
- **Assumed:** the stage assignments (no prototype beyond the plain
  orifice); the standards' exact limits (sources disagree on the Venturi
  Re limit); installation-effect figures from industry and vendor
  sources.
