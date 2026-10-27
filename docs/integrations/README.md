# Integrations

What hexmesh depends on in third-party tools: roles, tested versions,
features used, known quirks.  Vendor manuals are background only.  The
files here, and the installed tool itself, are the source of truth.

## Tools

| Tool | Role | File | Tested version |
|---|---|---|---|
| gmsh (+ OpenCASCADE) | **Backend**: realises geometry and mesh | [gmsh.md](gmsh.md) | 4.12.1 / OCC 7.6.3 (apt) |
| OpenFOAM | **Consumer**: reads hexmesh output | [openfoam.md](openfoam.md) | v1912 (Debian `openfoam` 1912.200626) |
| PCF (Isogen piping component file) | **Input format**: plant piping data | [pcf.md](pcf.md) | Reference Guide 2016 (13.0), rev. 2018 |
| Cubit | **none: abandoned** (decision 0007, option A rejected) | — | — |

Roles:
- **Backend:** hexmesh calls it to build geometry and mesh (pipeline
  steps 4–7, DESIGN §5).
- **Consumer:** reads hexmesh output.
- **Peer:** meshes an adjacent region that hexmesh output is joined to,
  e.g. snappyHexMesh drums (decision 0003, option C).  None yet.

Rejected tools: **Cubit** (decision 0007).  Don't add integrations for it.

## File layout

Every integration file has these sections:

1. **Role**: what the tool does for hexmesh.
2. **Versions**: tested versions, and what supporting a new one requires.
3. **Features used**: the exact API calls or utilities hexmesh relies on.
4. **Known quirks**: version-specific behaviour, with evidence, each
   marked *verified* or *assumed*.
5. **Open questions**: assumptions not yet checked, each linked to the
   task or decision that will settle it.

Add a quirk the moment you find it (coding or design session), with the
version, a minimal reproduction or code reference, and the date.

## Manuals

Vendor manuals are kept in [`../manuals/`](../manuals/), which is **not in
git** (`*.pdf` is gitignored).  A fresh clone won't have them; use the
URLs below.

| Manual | Local | Upstream | Note |
|---|---|---|---|
| gmsh 4.12.1 reference manual (HTML) | `/usr/share/doc/gmsh-doc/gmsh.html` (Debian `gmsh-doc`) | https://gmsh.info/doc/texinfo/gmsh.html (latest; versioned copies in source releases) | **Use this one.** Matches the installed version. |
| gmsh 3.0 reference manual | `docs/manuals/gmsh-3.0-reference-manual.pdf` | — | **Outdated:** predates the Python API (`gmsh.model…`, added in 4.0).  Kept for history only. |
| gmsh Python API, installed version | `python3 -c "import gmsh; help(gmsh.model.mesh.setTransfiniteCurve)"` | — | Exact for whatever is installed.  Check here first. |
| Cubit 17.10 user documentation | `docs/manuals/cubit-17.10-user-documentation.pdf` (84 MB, 1,693 pages) | — | **Not used:** Cubit is abandoned (decision 0007).  Safe to delete. |
| PCF Reference Guide 2016 (13.0), rev. April 2018 | `docs/manuals/pcf-reference-guide.pdf` (388 pages) | https://pypeserverdocs.blob.core.windows.net/enterprise/content/PCFReferenceGuide.pdf | Carries a proprietary-information notice: keep local, summarise rather than copy |
| OpenFOAM v1912 user guide | `gmshToFoam -doc` (needs the OpenFOAM environment) | https://www.openfoam.com/documentation | — |
