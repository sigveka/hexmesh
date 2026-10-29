# IFC (Industry Foundation Classes)

## Role

**Planned input format** for building-services networks: ducts first,
then pipes (decision 0032, stages 3–4).  Not read by hexmesh yet.

## Entities that matter (IFC4)

- `IfcDuctSegment`, `IfcPipeSegment`: geometry usually an
  `IfcExtrudedAreaSolid` of an `IfcRectangleProfileDef`,
  `IfcCircleProfileDef` or `IfcArbitraryClosedProfileDef`.
- `IfcDuctFitting`, `IfcPipeFitting`: `PredefinedType` BEND, TRANSITION,
  JUNCTION, …, often `NOTDEFINED` in exports, so recognise them from
  their ports and geometry.
- `IfcDistributionPort` (location and flow direction), nested in their
  element (`IfcRelNests`, or `IfcRelConnectsPortToElement` in older
  exports), joined by `IfcRelConnectsPorts`: the connectivity.
- Equipment: `IfcFan`, `IfcDuctSilencer`, `IfcAirTerminal`, dampers.
- Systems: `IfcDistributionSystem` / `IfcSystem`.
- Specification: [IfcDuctFitting, IFC4](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifchvacdomain/lexical/ifcductfitting.htm).
  The IFC standard is CC BY-ND 4.0; that covers the specification, not
  sample models.

## Sample files (surveyed 2026-10-29, design session)

Found with GitHub code search (`IFCDUCTSEGMENT`, `IFCDUCTFITTING`,
extension `ifc`); licences from the GitHub API; contents inventoried
from the STEP text (no IfcOpenShell installed).

| File | Source, licence | Tool | Contents |
|---|---|---|---|
| `BIM/4.2 AHUcooling_VDI6020/IFC/4.2 AHUcooling.ifc` | `EnEff-BIM/EnEffBIM_UseCases`, **MIT** (research project, 2015) | Revit 2015 exporter | 15 duct segments (33 rectangle profiles, 2 circle), 3 fittings, 4 silencers, 2 fans, 4 air terminals, 64 ports, 32 `IfcRelConnectsPorts`, 5 systems.  **The best: a connected network.** |
| `src/00_sampleData/IFC_stepP21/DepMod2025/2025-DepMod2HVAC-Model-v1.ifc` | `seb-esser/ConMan2`, **MIT** | Revit 2024 (ODA SDAI) | 3 segments, 3 fittings (`NOTDEFINED`), 12 ports, 5 connections, arbitrary-profile extrusions.  Small and connected. |
| `IFC4/buildingSMART-Certification-datasets/Simple-Scene/Building-Hvac.ifc` | `BIMvoice/ifcsamples`, **CC-BY-4.0** (copy of buildingSMART's certification dataset) | SketchUp IFC manager | 1 segment, 2 air terminals, no fittings or ports.  Smoke test only. |
| `fixtures/showcase/bimcraft-mep-plant-room.ifc` | `getcadcraft/bimcraft`, Apache-2.0 | — | not inspected |

All are IFC4.  Licensed for copying with their notices (MIT,
CC-BY-4.0, Apache-2.0).  Copies are in the design session's scratchpad
(`ifc_dl/`) until stage 3 commits them as fixtures.

**Not usable (no licence):** `IfcOpenShell/files` (public test files, no
licence file), `Perceptron04/Nemetschek_ifc`, `Moult/bcf-test-cases`,
`buildingSMART/Standards-builds` (spec annex files, CC BY-ND via the
standard), and student repositories.

## Library

**IfcOpenShell** (Python bindings, LGPL-3.0): the reader to use, as an
optional extra (`hexmesh[ifc]`).  Not installed here; check the version
and record behaviour when stage 3 starts.
