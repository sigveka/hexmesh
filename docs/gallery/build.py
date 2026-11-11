#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
Example gallery: meshes every example, renders it, measures it, and writes
the gallery's pages.  Not part of the test suite.

    python3 docs/gallery/build.py                   # every example, one at a time
    python3 docs/gallery/build.py --jobs 4          # four examples at once
    python3 docs/gallery/build.py --only tee wye    # re-run some, keep the rest
    python3 docs/gallery/build.py --markdown-only   # rewrite the pages and the README's blocks
    python3 docs/gallery/build.py --hero            # render img/hero.png only
    python3 docs/gallery/build.py --validation      # validation meshes, all cases
    python3 docs/gallery/build.py --validation poiseuille

**The pages** (decision 0050, task 0142): ``docs/GALLERY.md``, the landing
page; ``docs/gallery/FEATURES.md``, the feature examples by family
(``hexmesh.examples.FAMILIES``: title, introduction, fittings, validation
tags), each family with its API sections and the validation cases whose
tags it collects (status and last run, from ``results.json``);
``docs/gallery/APPLICATIONS.md``, each application with the fittings it
uses, linked to their family; ``docs/gallery/VALIDATION.md``, the cases
and the coverage matrix.  Every example is one block
(:func:`example_md`), so a later stage can write it into
``docs/features/<family>.md``.

The prose comes from the examples' docstrings, ``FAMILIES``' introductions
and the ``applications`` package's docstring, so edit it there.  Validation cases come from
``validation/<case>/`` (README.md, RESULTS.md with a ``**Status:**`` line,
optional ``figure.png``, and ``case.json`` checked against
``validation/case.schema.json``: a missing or invalid one stops the build)
and planned ones from ``docs/tasks/*validation*`` (their ``Category`` and
``Features`` lines).  The validation section groups cases by category and
ends with a coverage matrix, hexmesh features × cases (task 0073).

**Validation meshes.**  A case whose ``run.py`` defines ``meshes()``,
returning ``(label, caption, build)`` per mesh, gets
``validation/<case>/img/<label>_section.png`` for each mesh (and
``<label>.png``, an overview, for the first) and a "Mesh" section in its
README.md, between ``<!-- mesh:start -->`` and ``<!-- mesh:end -->``
markers (inserted after the "## Case" section the first time).

Needs ``vtk`` for rendering.  Each example runs in its own process (one
GMSH session each).  Follow the shared-machine rules in CLAUDE.md before a
full run; build times measured with ``--jobs`` > 1, or while other runs
are active, are contended.

Writes ``docs/gallery/img/<name>.png`` (overview), ``<name>_section.png``
(inlet cross-section), ``docs/gallery/metrics.json`` and the pages.
A full run also renders ``img/hero.png``, the README's cut-away of
``insulated_network``.

**Cut-aways.**  An example that defines ``gallery_cutaway()`` also gets
``img/<name>_cutaway.png``: its mesh with whole cells removed, to show
the blocks inside.  The function returns a dict: ``keep`` (cell centres,
an (n, 3) array → a boolean mask of the cells drawn), ``direction`` (from
the focus towards the camera), ``up``, and optionally ``focus`` and
``colours`` (``wall``, ``cut``, ``ends``: each a (face, edge) pair of hex
strings; :data:`CUTAWAY` otherwise).  Faces are drawn by what they are:
the wall, the open ends, and every other exposed face as cut.

**README.md** (task 0078): every run, ``--markdown-only`` included,
rewrites two marked blocks, ``readme:metrics`` (``insulated_tee``'s
numbers from ``metrics.json``) and ``readme:validation`` (one row per
``case.json``, its ``headline`` as the result, and the planned tasks in
one row), and nothing else.  ``readme:features`` is hand-written.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMG = HERE / "img"
METRICS = HERE / "metrics.json"
GALLERY = ROOT / "docs" / "GALLERY.md"           # the landing page
#: the three generated pages beside this script (decision 0050, task 0142)
FEATURES = HERE / "FEATURES.md"
APPLICATIONS = HERE / "APPLICATIONS.md"
VALIDATION = HERE / "VALIDATION.md"
API = ROOT / "API.md"

sys.path.insert(0, str(ROOT))

# Open ends and section faces are coloured by material, in the order the
# assembly lists its materials; walls are neutral.
PALETTE = ["#3b7dd8", "#d9822b", "#5aa469", "#a361c7", "#c9b037"]
COLOUR_NAMES = ["blue", "orange", "green", "purple", "yellow"]
WALL = "#d5d9df"
EDGE = "#55606e"
# Cut-away images: (face, edge) per kind of face.
CUTAWAY = {"wall": ("#b3202a", "#5a0d12"), "cut": ("#f2b8a2", "#8c3b2e"),
           "ends": ("#2a6f97", "#123a52")}
# VTK's hexahedron faces, outward for gmsh's (= VTK's) node order.
HEX_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


# --------------------------------------------------------------------------
# Rendering helpers, shared by every image
# --------------------------------------------------------------------------

def rgb(h: str) -> tuple[float, float, float]:
    """``"#rrggbb"`` as VTK's 0–1 floats."""
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def vtk_points(xyz):
    """A ``vtkPoints`` of the mesh's nodes, in their order."""
    import vtk
    points = vtk.vtkPoints()
    for p in xyz:
        points.InsertNextPoint(*p)
    return points


def poly_actor(points, polys, face: str, edge: str, width: float):
    """An actor drawing *polys* (node-index lists into *points*) with face
    colour *face*, edges *edge* of line *width*; returns it (its property
    is the caller's to adjust further)."""
    import vtk
    cells = vtk.vtkCellArray()
    for poly in polys:
        cells.InsertNextCell(len(poly), poly)
    data = vtk.vtkPolyData()
    data.SetPoints(points)
    data.SetPolys(cells)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(data)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*rgb(face))
    prop.EdgeVisibilityOn()
    prop.SetEdgeColor(*rgb(edge))
    prop.SetLineWidth(width)
    return actor


def snapshot(ren, path: Path, size) -> None:
    """Render *ren* off screen at *size* (8× multisampling) to a PNG."""
    import vtk
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetMultiSamples(8)
    win.AddRenderer(ren)
    win.SetSize(*size)
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(grab.GetOutputPort())
    writer.Write()


def crop_to_content(path: Path, width: int, pad: float) -> None:
    """Crop the PNG at *path* to its non-white content plus a margin of
    *pad* × its larger side, then scale it to *width*, in place."""
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
    if box:
        m = int(pad * max(box[2] - box[0], box[3] - box[1]))
        im = im.crop((max(box[0] - m, 0), max(box[1] - m, 0),
                      min(box[2] + m, im.width), min(box[3] + m, im.height)))
        im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
    im.save(path)


# --------------------------------------------------------------------------
# Worker: one example, in its own process
# --------------------------------------------------------------------------

def measure(asm) -> dict:
    """Mesh statistics of the meshed assembly (GMSH model still open)."""
    import gmsh

    sicn = asm.check_quality()
    sj = asm.check_quality("scaled_jacobian", by="fitting")
    aspect = asm.check_quality("aspect_ratio")
    worst = min(sj.regions, key=lambda r: r.min_quality)
    n = sum(r.n_elements for r in sicn.regions)
    roles = asm.group_roles()
    return {
        "fittings": len(asm.edges),
        "fitting_types": dict(Counter(type(e.fitting).__name__ for e in asm.edges)),
        "volumes": len(gmsh.model.getEntities(3)),
        "materials": list(asm.volumes),
        "min_sicn": sicn.min_quality,
        "mean_sicn": sum(r.mean_quality * r.n_elements for r in sicn.regions) / n,
        "min_sj": worst.min_quality,
        "min_sj_fitting": worst.name,
        "max_aspect": max(r.max_quality for r in aspect.regions),
        "groups": {role: sorted(g for g, r in roles.items() if r == role)
                   for role in ("open_end", "wall", "interface", "volume")},
    }


def material_of(group: str, materials: list[str]) -> str | None:
    """The material a ``<material>_<rest>`` group belongs to."""
    hits = [m for m in materials if group.startswith(m + "_")]
    return max(hits, key=len) if hits else None


def faces(asm) -> tuple[dict, dict]:
    """Boundary polygons for the overview, and the inlet section's."""
    import gmsh
    import numpy as np

    tags, xyz, _ = gmsh.model.mesh.getNodes()
    xyz = xyz.reshape(-1, 3)
    index = {int(t): i for i, t in enumerate(tags)}

    def polys(surfaces):
        out = []
        for s in surfaces:
            types, _, nodes = gmsh.model.mesh.getElements(2, s)
            for t, conn in zip(types, nodes):
                k = gmsh.model.mesh.getElementProperties(t)[3]
                for e in np.asarray(conn).reshape(-1, k):
                    out.append([index[int(v)] for v in e])
        return out

    materials = list(asm.volumes)
    roles = asm.group_roles()
    overview: dict[str, list] = {}
    for dim, tag in gmsh.model.getPhysicalGroups(2):
        name = gmsh.model.getPhysicalName(dim, tag)
        role = roles.get(name)
        if role not in ("wall", "open_end"):
            continue
        key = "wall" if role == "wall" else material_of(name, materials)
        overview.setdefault(key, []).extend(
            polys(gmsh.model.getEntitiesForPhysicalGroup(dim, tag)))
    section = {name: polys(cs.surfaces) for name, cs in asm.inlet.face.layers}
    frame = asm.inlet.frame
    return ({"xyz": xyz, "polys": overview, "materials": materials},
            {"xyz": xyz, "polys": section, "materials": materials,
             "normal": np.asarray(frame.normal), "up": np.asarray(frame.up),
             "position": np.asarray(frame.position)})


def render(scene: dict, path: Path, size, view: str, fit: bool = False) -> None:
    """Render polygons with VTK, off screen, to a PNG.

    With *fit*, the image is rendered at twice the size and cropped to the
    mesh (plus a margin), then scaled to *size*'s width, so long, thin
    meshes fill the frame instead of a mostly empty one."""
    import numpy as np
    import vtk

    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    xyz = scene["xyz"]
    points = vtk_points(xyz)
    used = []
    for key, polys in scene["polys"].items():
        if not polys:
            continue
        for poly in polys:
            used.extend(poly)
        colour = WALL if key == "wall" or key is None else \
            PALETTE[scene["materials"].index(key) % len(PALETTE)]
        actor = poly_actor(points, polys, colour, EDGE, 0.6 if view == "overview" else 1.0)
        if view == "section":
            actor.GetProperty().LightingOff()
        ren.AddActor(actor)

    pts = xyz[sorted(set(used))]
    centre = pts.mean(axis=0)
    cam = ren.GetActiveCamera()
    if view == "overview":
        # Look mostly along the network's thinnest direction, tilted so
        # out-of-plane fittings read as 3-D; keep z up where possible.
        _, vecs = np.linalg.eigh(np.cov((pts - centre).T))
        small, mid, large = vecs[:, 0], vecs[:, 1], vecs[:, 2]
        if small[2] < 0:
            small = -small
        d = 0.8 * small + 0.45 * mid + 0.4 * large
        d /= np.linalg.norm(d)
        up = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([0, 1.0, 0])
        cam.SetPosition(*(centre + d))
    else:
        cam.ParallelProjectionOn()
        up = scene["up"]
        cam.SetPosition(*(centre - scene["normal"]))
    cam.SetFocalPoint(*centre)
    cam.SetViewUp(*up)
    ren.ResetCamera()
    cam.Zoom(1.15 if view == "overview" else 1.05)
    snapshot(ren, path, (2 * size[0], 2 * size[1]) if fit else size)
    if fit:
        crop_to_content(path, size[0], 0.04)


def cutaway_scene(asm, spec: dict) -> dict:
    """Faces of the cells *spec*'s ``keep`` draws, sorted into wall, open
    ends and cut (every other face exposed by the cut)."""
    import gmsh
    import numpy as np

    tags, xyz, _ = gmsh.model.mesh.getNodes()
    xyz = xyz.reshape(-1, 3)
    index = {int(t): i for i, t in enumerate(tags)}
    roles = asm.group_roles()
    hexes, kind = [], {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        role = roles.get(gmsh.model.getPhysicalName(dim, tag))
        if dim not in (2, 3) or (dim == 2 and role not in ("wall", "open_end")):
            continue
        for e in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            for typ, conn in zip(*gmsh.model.mesh.getElements(dim, e)[::2]):
                if dim == 3 and typ == 5:                   # 8-node hexahedron
                    hexes.append(np.asarray(conn, np.int64).reshape(-1, 8))
                elif dim == 2 and typ == 3:                 # 4-node quadrangle
                    for q in np.asarray(conn, np.int64).reshape(-1, 4):
                        kind[frozenset(index[int(v)] for v in q)] = \
                            "wall" if role == "wall" else "ends"
    hexes = np.vectorize(index.get)(np.vstack(hexes))
    keep = hexes[np.asarray(spec["keep"](xyz[hexes].mean(axis=1)), bool)]
    seen: dict = {}
    for h in keep:
        for f in HEX_FACES:
            q = tuple(int(h[i]) for i in f)
            k = frozenset(q)
            seen[k] = None if k in seen else q
    polys: dict[str, list] = {"wall": [], "ends": [], "cut": []}
    for k, q in seen.items():
        if q is not None:
            polys[kind.get(k, "cut")].append(q)
    pts = xyz[np.unique(keep)]
    return {"xyz": xyz, "polys": polys, "colours": {**CUTAWAY, **spec.get("colours", {})},
            "direction": np.asarray(spec["direction"], float), "up": spec["up"],
            "focus": np.asarray(spec.get("focus", pts.mean(axis=0)), float)}


def render_cutaway(scene: dict, path: Path, width: int = 1000) -> None:
    """Render :func:`cutaway_scene`'s faces, lit, cropped to the mesh."""
    import numpy as np
    import vtk

    points = vtk_points(scene["xyz"])
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    for key, polys in scene["polys"].items():
        if not polys:
            continue
        actor = poly_actor(points, polys, *scene["colours"][key], 0.7)
        actor.GetProperty().SetSpecular(0.25)
        actor.GetProperty().SetSpecularPower(20)
        ren.AddActor(actor)
    cam = ren.GetActiveCamera()
    d = scene["direction"] / np.linalg.norm(scene["direction"])
    cam.SetPosition(*(scene["focus"] + d))
    cam.SetFocalPoint(*scene["focus"])
    cam.SetViewUp(*scene["up"])
    ren.ResetCamera()
    snapshot(ren, path, (2 * width, 2 * width))
    crop_to_content(path, width, 0.03)


def worker(qualname: str, out: Path) -> None:
    module = importlib.import_module(f"hexmesh.examples.{qualname}")
    name = qualname.split(".")[-1]
    captured: dict = {}
    spent = [0.0]

    def inspect(asm):
        t = time.perf_counter()
        captured["metrics"] = measure(asm)
        captured["overview"], captured["section"] = faces(asm)
        if hasattr(module, "gallery_cutaway"):
            captured["cutaway"] = cutaway_scene(asm, module.gallery_cutaway())
        spent[0] = time.perf_counter() - t

    with tempfile.TemporaryDirectory() as tmp:
        t = time.perf_counter()
        result = module.main(os.path.join(tmp, f"{name}.msh"), inspect=inspect)
        build = time.perf_counter() - t - spent[0]

    IMG.mkdir(parents=True, exist_ok=True)
    render(captured["overview"], IMG / f"{name}.png", (1000, 560), "overview")
    render(captured["section"], IMG / f"{name}_section.png", (420, 420), "section")
    m = captured["metrics"]
    if "cutaway" in captured:
        render_cutaway(captured["cutaway"], IMG / f"{name}_cutaway.png")
        m["cutaway"] = True
    m.update(predicted=result.predicted, meshed=result.meshed,
             build_s=round(build, 2))
    out.write_text(json.dumps(m, indent=1), encoding="utf-8")


HERO = "sections.insulated_network"


def hero_worker(out: Path) -> None:
    """``img/hero.png``: :data:`HERO` with the quarter towards the viewer
    (y < 0, z > 0) cut away, whole cells, so the O-H core, the steel and
    the insulation show through the header, the tee and the wye; faces
    coloured by material as in the section images (task 0078)."""
    import gmsh
    import numpy as np
    import vtk
    from hexmesh import Session

    module = importlib.import_module(f"hexmesh.examples.{HERO}")
    with Session("hero"):
        asm = module.build()
        asm.mesh()
        materials = list(asm.volumes)
        roles = asm.group_roles()
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        xyz = xyz.reshape(-1, 3)
        index = {int(t): i for i, t in enumerate(tags)}
        cells: dict[str, np.ndarray] = {}
        for dim, tag in gmsh.model.getPhysicalGroups(3):
            name = gmsh.model.getPhysicalName(dim, tag)
            if roles.get(name) != "volume" or name not in materials:
                continue
            hexes = []
            for v in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
                types, _, nodes = gmsh.model.mesh.getElements(3, v)
                for typ, conn in zip(types, nodes):
                    if typ == 5:                              # 8-node hexahedron
                        hexes.append(np.asarray(conn, dtype=np.int64).reshape(-1, 8))
            cells[name] = np.vectorize(index.get)(np.vstack(hexes))

    points = vtk_points(xyz)
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    kept = []
    for name, conn in cells.items():
        c = xyz[conn].mean(axis=1)
        conn = conn[~((c[:, 1] < 0) & (c[:, 2] > 0))]      # the quarter cut away
        kept.append(conn)
        grid = vtk.vtkUnstructuredGrid()
        grid.SetPoints(points)
        for h in conn:                    # gmsh's hex node order is VTK's
            grid.InsertNextCell(vtk.VTK_HEXAHEDRON, 8, [int(i) for i in h])
        surface = vtk.vtkDataSetSurfaceFilter()
        surface.SetInputData(grid)
        mapper = vtk.vtkDataSetMapper()
        mapper.SetInputConnection(surface.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*rgb(PALETTE[materials.index(name) % len(PALETTE)]))
        prop.EdgeVisibilityOn()
        prop.SetEdgeColor(*rgb(EDGE))
        prop.SetLineWidth(0.5)
        ren.AddActor(actor)

    pts = xyz[np.unique(np.vstack(kept))]
    centre = pts.mean(axis=0)
    cam = ren.GetActiveCamera()
    d = np.array([-0.35, -1.0, 0.75])
    cam.SetPosition(*(centre + d / np.linalg.norm(d)))
    cam.SetFocalPoint(*centre)
    cam.SetViewUp(0, 0, 1)
    ren.ResetCamera()
    cam.Zoom(1.2)
    size = (1000, 560)
    snapshot(ren, out, (2 * size[0], 2 * size[1]))
    crop_to_content(out, size[0], 0.03)


def run_hero() -> None:
    """Render ``img/hero.png`` in its own process (one GMSH session)."""
    IMG.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    p = subprocess.run([sys.executable, __file__, "--hworker", str(IMG / "hero.png")],
                       env=env, capture_output=True, text=True)
    if p.returncode:
        raise SystemExit(f"hero: FAILED\n{p.stderr[-2000:]}")
    print(f"wrote {(IMG / 'hero.png').relative_to(ROOT)}", flush=True)


def load_case(case: str):
    """``validation/<case>/run.py`` as a module (not run)."""
    import importlib.util
    path = ROOT / "validation" / case / "run.py"
    spec = importlib.util.spec_from_file_location(f"validation_{case}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validation_worker(case: str, label: str, out: Path) -> None:
    import gmsh
    from hexmesh import Session

    entries = load_case(case).meshes()
    first = entries[0][0] == label
    build = next(b for l, _, b in entries if l == label)
    img = ROOT / "validation" / case / "img"
    img.mkdir(parents=True, exist_ok=True)
    with Session(f"{case}-{label}"):
        asm = build()
        asm.validate()
        predicted = asm.cell_count()
        asm.mesh()
        meshed = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
        m = measure(asm)
        overview, section = faces(asm)
    if first:
        render(overview, img / f"{label}.png", (1000, 600), "overview", fit=True)
    render(section, img / f"{label}_section.png", (420, 420), "section")
    m.update(predicted=predicted, meshed=meshed)
    out.write_text(json.dumps(m, indent=1), encoding="utf-8")


def validation_cases() -> list[str]:
    """Cases whose run.py defines meshes()."""
    found = []
    for run in sorted((ROOT / "validation").glob("*/run.py")):
        if re.search(r"^def meshes\(", run.read_text(encoding="utf-8"), re.M):
            found.append(run.parent.name)
    return found


def run_validation(cases: list[str], jobs: int) -> dict:
    """Render every case's meshes, one subprocess per mesh; return
    case → label → metrics."""
    todo = [(c, label) for c in cases for label, _, _ in load_case(c).meshes()]

    def one(item):
        case, label = item
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m.json"
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            p = subprocess.run([sys.executable, __file__, "--vworker", case, label,
                                str(out)], env=env, capture_output=True, text=True)
            if p.returncode:
                print(f"{case}/{label}: FAILED\n{p.stderr[-2000:]}", flush=True)
                return item, {"error": p.stderr.strip().splitlines()[-1]}
            m = json.loads(out.read_text(encoding="utf-8"))
            print(f"{case}/{label}: {m['meshed']} cells, min SICN {m['min_sicn']:.3f}",
                  flush=True)
            return item, m

    results: dict = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for (case, label), m in pool.map(one, todo):
            results.setdefault(case, {})[label] = m
    return results


MESH_START, MESH_END = "<!-- mesh:start -->", "<!-- mesh:end -->"


def mesh_md(case: str, metrics: dict) -> str:
    """The README "Mesh" section of a validation case."""
    entries = load_case(case).meshes()
    first = entries[0][0]
    lines = [MESH_START, "## Mesh", "",
             "_Generated by `python3 docs/gallery/build.py --validation "
             f"{case}`; don't edit between the markers._", "",
             f'<img src="img/{first}.png" width="{overview_width(case, first)}" '
             f'alt="{case}, {first} mesh">', "",
             "<p>" + " ".join(f'<img src="img/{l}_section.png" width="{96 // len(entries)}%" '
                              f'alt="{c}">' for l, c, _ in entries) + "</p>", "",
             "Inlet cross-sections, left to right: "
             + "; ".join(c for _, c, _ in entries) + ".", "",
             "| Mesh | Cells | min SICN | min SJ (where) | max aspect |",
             "|---|---|---|---|---|"]
    for label, _, _ in entries:
        m = metrics.get(label)
        if not m or "error" in m:
            lines.append(f"| {label} | — | — | — | — |")
            continue
        cells = fmt_int(m["meshed"]) + ("" if m["meshed"] == m["predicted"] else " ✗")
        lines.append(f"| {label} | {cells} | {m['min_sicn']:.3f} | {m['min_sj']:.3f} "
                     f"({m['min_sj_fitting']}) | {m['max_aspect']:.1f} |")
    lines += ["", MESH_END]
    return "\n".join(lines)


def overview_width(case: str, label: str) -> str:
    """Full width for a wide overview, narrower for a tall one."""
    from PIL import Image
    path = ROOT / "validation" / case / "img" / f"{label}.png"
    if not path.exists():
        return "100%"
    w, h = Image.open(path).size
    return "100%" if h <= 0.6 * w else "60%"


def update_readme(case: str, block: str) -> None:
    """Replace the marked block, or insert it after the "## Case" section."""
    path = ROOT / "validation" / case / "README.md"
    text = path.read_text(encoding="utf-8")
    if MESH_START in text and MESH_END in text:
        a, b = text.index(MESH_START), text.index(MESH_END) + len(MESH_END)
        text = text[:a] + block + text[b:]
    else:
        m = re.search(r"^## Case\b.*?(?=^## )", text, re.M | re.S)
        at = m.end() if m else len(text)
        text = text[:at] + block + "\n\n" + text[at:]
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def run_examples(names: list[str], jobs: int) -> dict:
    """Run each example in a subprocess; return name → metrics."""
    def one(qualname):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m.json"
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            p = subprocess.run([sys.executable, __file__, "--worker", qualname,
                                str(out)], env=env, capture_output=True, text=True)
            if p.returncode:
                print(f"{qualname}: FAILED\n{p.stderr[-2000:]}", flush=True)
                return qualname, {"error": p.stderr.strip().splitlines()[-1]}
            m = json.loads(out.read_text(encoding="utf-8"))
            print(f"{qualname}: {m['meshed']} cells, min SICN {m['min_sicn']:.3f}, "
                  f"{m['build_s']} s", flush=True)
            return qualname, m

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return dict(pool.map(one, names))


def git_describe() -> str:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()
    rev = git("rev-parse", "--short", "HEAD")
    return rev + (" + uncommitted changes" if git("status", "--porcelain") else "")


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def md_doc(doc: str) -> tuple[str, str]:
    """Docstring → (summary, body) in Markdown."""
    doc = re.sub(r"``(.+?)``", r"`\1`", doc.strip())
    paras = [p for p in re.split(r"\n\s*\n", doc)
             if not p.strip().startswith("python3 -m")]
    summary = " ".join(paras[0].split())
    return summary, "\n\n".join(paras[1:])


def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def fittings_text(types: dict) -> str:
    return ", ".join(t if n == 1 else f"{t} ×{n}" for t, n in types.items())


def slug(heading: str) -> str:
    """GitHub's (and Essens's) anchor for a Markdown heading."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def api_anchors() -> dict[str, str]:
    """``{"Bend": "API.md#bendradius-angle-…"}``: each class's or
    function's first ``###`` section in API.md."""
    out: dict[str, str] = {}
    for line in API.read_text(encoding="utf-8").splitlines():
        m = re.match(r"### `(?:Assembly\.)?(\w+)\(", line)
        if m and m.group(1) not in out:
            out[m.group(1)] = slug(line[4:])
    return out


def api_link(name: str, anchors: dict[str, str], up: str = "../../") -> str:
    """``[`Bend`](../../API.md#…)``, or the bare name if API.md has no section."""
    return f"[`{name}`]({up}API.md#{anchors[name]})" if name in anchors else f"`{name}`"


def example_md(qualname: str, m: dict | None, img: str = "img/",
               anchors: dict[str, str] | None = None, level: int = 3) -> str:
    """One example's self-contained block (decision 0050): heading, images,
    what it shows, the command, the numbers, the names, and the API
    sections of the fittings it uses.  *img* is the image folder relative
    to the page; *level* the heading level."""
    module = importlib.import_module(f"hexmesh.examples.{qualname}")
    name = qualname.split(".")[-1]
    summary, body = md_doc(module.__doc__)
    out = [f"{'#' * level} {name}", "", f"**{summary}**", ""]
    if m and "error" not in m:
        out += [f'<p><img src="{img}{name}.png" width="68%" alt="{name}"> '
                f'<img src="{img}{name}_section.png" width="29%" '
                f'alt="{name}, inlet section"></p>', ""]
        if m.get("cutaway"):
            out += [f'<p><img src="{img}{name}_cutaway.png" width="60%" '
                    f'alt="{name}, cut away"></p>', ""]
    out += [body, "", "```bash", f"python3 -m hexmesh.examples.{qualname}", "```", ""]
    if not m:
        out += ["_Not measured yet._", ""]
        return "\n".join(out)
    if "error" in m:
        out += [f"**Failed:** `{m['error']}`", ""]
        return "\n".join(out)
    cells = fmt_int(m["meshed"]) + ("" if m["meshed"] == m["predicted"]
                                    else f" ✗ (predicted {fmt_int(m['predicted'])})")
    colours = ", ".join(f"{mat} {COLOUR_NAMES[i % len(COLOUR_NAMES)]}"
                        for i, mat in enumerate(m["materials"]))
    g = m["groups"]
    out += [
        "| Fittings | Volumes | Cells | min SICN | mean SICN | min SJ (where) | max aspect | Build |",
        "|---|---|---|---|---|---|---|---|",
        f"| {m['fittings']}: {fittings_text(m['fitting_types'])} | {m['volumes']} "
        f"| {cells} | {m['min_sicn']:.3f} | {m['mean_sicn']:.3f} "
        f"| {m['min_sj']:.3f} ({m['min_sj_fitting']}) | {m['max_aspect']:.1f} "
        f"| {m['build_s']:.1f} s |",
        "",
        f"- **Open ends:** {', '.join(f'`{x}`' for x in g['open_end'])}",
        f"- **Walls:** {', '.join(f'`{x}`' for x in g['wall'])}",
    ]
    if g["interface"]:
        out.append(f"- **Interfaces:** {', '.join(f'`{x}`' for x in g['interface'])}")
    out += [f"- **Colours:** {colours}; walls grey."]
    if anchors is not None:
        out.append("- **Parameters:** " + ", ".join(api_link(t, anchors)
                                                    for t in m["fitting_types"]))
    out.append("")
    return "\n".join(out)


def status_of(text: str) -> str:
    """The ``**Status:** …`` paragraph or list item of a Markdown file."""
    m = re.search(r"\*\*Status:?\*?\*?:?\s*(.+?)(?:\n\s*\n|\n- )", text + "\n\n", re.S)
    if not m:
        return "—"
    status = " ".join(m.group(1).replace("**", "").split())
    return status.split(". ")[0].rstrip(".")


CATEGORIES_V = {
    "V1": "exact solution (code verification)",
    "V2": "high-fidelity simulation",
    "V3": "experiment",
    "V4": "correlation or standard",
}
STATUS_MARK = {"accepted": "●", "in progress": "◐", "planned": "○", "rejected": "✗"}


def case_schema() -> dict:
    return json.loads((ROOT / "validation" / "case.schema.json").read_text(encoding="utf-8"))


def case_meta(case: str) -> dict:
    """``validation/<case>/case.json``, checked against the schema; a
    missing or invalid file raises, naming it (task 0073)."""
    import jsonschema
    path = ROOT / "validation" / case / "case.json"
    if not path.exists():
        raise SystemExit(f"{path.relative_to(ROOT)}: missing (every validation case "
                         f"ships a case.json, docs/tasks/README.md)")
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.validate(meta, case_schema())
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        msg = e.message if isinstance(e, jsonschema.ValidationError) else str(e)
        raise SystemExit(f"{path.relative_to(ROOT)}: invalid: {msg}") from None
    return meta


def case_dirs() -> list[str]:
    """Every validation case: a directory with a ``run.py``."""
    return sorted(p.parent.name for p in (ROOT / "validation").glob("*/run.py"))


def planned_cases(done_tasks: set[str]) -> list[dict]:
    """Validation tasks without a case yet that carry a ``Category`` line:
    {task, title, file, category, features, status}."""
    features = case_schema()["properties"]["tags"]["properties"]["features"]["items"]["enum"]
    out = []
    for t in sorted((ROOT / "docs" / "tasks").glob("*validation*.md")):
        task = t.name[:4]
        if task in done_tasks:
            continue
        text = t.read_text(encoding="utf-8")
        cat = re.search(r"^- \*\*Category:\*\* (V[1-4])", text, re.M)
        if not cat:
            continue
        feat = re.search(r"^- \*\*Features:\*\* (.+)$", text, re.M)
        tags = re.findall(r"`([^`]+)`", feat.group(1)) if feat else []
        unknown = set(tags) - set(features)
        if unknown:
            raise SystemExit(f"docs/tasks/{t.name}: unknown features {sorted(unknown)}")
        out.append({"task": task, "title": text.splitlines()[0].lstrip("# ").split(" — ", 1)[-1],
                    "file": t.name, "category": cat.group(1), "features": tags,
                    "status": status_of(text)})
    return out


def coverage_md(cases: list[tuple[str, dict]], planned: list[dict],
                level: int = 3) -> list[str]:
    """Features down, cases across (existing, then planned); a mark per
    feature a case exercises, by status.  Empty rows are what isn't
    validated yet."""
    features = case_schema()["properties"]["tags"]["properties"]["features"]["items"]["enum"]
    cols = [(c, m["category"], m["status"], set(m["tags"]["features"])) for c, m in cases]
    cols += [(f"{p['task']}", p["category"], "planned", set(p["features"])) for p in planned]
    head = "| Feature | " + " | ".join(f"{name}<br>{cat}" for name, cat, _, _ in cols) + " |"
    rows = [head, "|---|" + "---|" * len(cols)]
    for f in features:
        marks = [STATUS_MARK[st] if f in fs else "" for _, _, st, fs in cols]
        label = f"`{f}`" if any(marks) else f"`{f}` (none)"
        rows.append(f"| {label} | " + " | ".join(marks) + " |")
    legend = ", ".join(f"{m} {s}" for s, m in STATUS_MARK.items())
    return [f"{'#' * level} Coverage", "",
            "Which hexmesh features each case exercises (decision 0012's list, "
            "extended by decision 0050). "
            f"Marks: {legend}; planned cases are named by task.  Rows marked "
            "*(none)* have no validation case, existing or planned.", "",
            *rows, ""]


def last_run(case: str) -> dict | None:
    """The latest-dated level's ``environment`` in ``validation/<case>/results.json``
    (date, hexmesh commit, …), or None."""
    path = ROOT / "validation" / case / "results.json"
    if not path.exists():
        return None
    envs = [lv["environment"] for lv in json.loads(path.read_text(encoding="utf-8"))["levels"]
            if lv.get("environment") and lv["environment"].get("date")]
    return max(envs, key=lambda e: e["date"]) if envs else None


def validation_md(val: str = "../../validation/", tasks: str = "../tasks/") -> str:
    """The Validation page's body; *val* and *tasks* are the paths from the
    page to ``validation/`` and ``docs/tasks/``."""
    out = [
        "Meshes from hexmesh solved with OpenFOAM and compared with a reference "
        "(decision 0012); each case is judged by grid convergence against gates "
        "set in advance (decision 0015).  Cases are grouped by their reference: "
        "V1 exact solutions (code verification), V2 high-fidelity simulations, "
        "V3 experiments, V4 correlations and standards.",
        "",
        "Each case lives in `validation/<case>/`: `case.json` gives its category, "
        "references, tags, status and gates; `README.md` describes it; "
        "`RESULTS.md` holds the measurements; an optional `figure.png` is "
        "shown here.",
        "",
    ]
    cases = [(c, case_meta(c)) for c in case_dirs()]
    planned = planned_cases({m["task"] for _, m in cases})
    for cat, what in CATEGORIES_V.items():
        mine = [(c, m) for c, m in cases if m["category"] == cat]
        later = [p for p in planned if p["category"] == cat]
        out += [f"## {cat}: {what}", ""]
        if not mine and not later:
            out += ["_No cases yet._", ""]
        for name, m in mine:
            case = ROOT / "validation" / name
            tags = m["tags"]
            tag_list = [*tags["regime"], *tags["physics"], *tags["features"],
                        (f"OpenFOAM {tags['toolchain']['openfoam']}" if "openfoam" in tags["toolchain"]
                         else f"FEniCSx {tags['toolchain']['fenicsx']}")
                        + f" ({tags['toolchain']['runner']})"]
            refs = "; ".join((f"{r['source']} [`{r['key']}`]" if "key" in r else r["source"])
                             + ("" if r["role"] == "primary" else " (secondary)")
                             for r in m["references"])
            run = last_run(name)
            stamp = (f"  **Last run:** {run['date']}, hexmesh {run.get('hexmesh', '?')}."
                     if run else "")
            out += [f"### {m['title']}", "",
                    f"**Status:** {m['status']} (task {m['task']}).  **Reference:** {refs}."
                    + stamp, "",
                    "Tags: " + ", ".join(f"`{t}`" for t in tag_list) + ".", ""]
            if m["gates"]:
                out += ["Gates: " + "; ".join(f"{g['quantity']}: {g['limit']}"
                                              for g in m["gates"]) + ".", ""]
            if m.get("notes"):
                out += [f"**Note:** {m['notes']}", ""]
            if name in validation_cases():
                first = load_case(name).meshes()[0][0]
                if (case / "img" / f"{first}.png").exists():
                    out += [f'<p><img src="{val}{name}/img/{first}.png" width="68%"> '
                            f'<img src="{val}{name}/img/{first}_section.png" '
                            f'width="29%"></p>', ""]
            if (case / "figure.png").exists():
                out += [f'<img src="{val}{name}/figure.png" width="70%">', ""]
            links = [f"[{f}]({val}{name}/{f})" for f in ("README.md", "RESULTS.md")
                     if (case / f).exists()]
            links.append(f"[case.json]({val}{name}/case.json)")
            out += [f"Case: `validation/{name}/`: " + ", ".join(links) + ".", ""]
        if later:
            out += ["Planned:", "", "| Task | Status |", "|---|---|",
                    *(f"| [{p['task']}: {p['title']}]({tasks}{p['file']}) | {p['status']} |"
                      for p in later), ""]
    out += coverage_md(cases, planned, level=2)
    return "\n".join(out)


# --------------------------------------------------------------------------
# README.md: the generated blocks (task 0078)
# --------------------------------------------------------------------------

README = ROOT / "README.md"
BIB = ROOT / "docs" / "references.bib"
#: the example whose numbers the README quotes, beside its code block
README_EXAMPLE = "sections.insulated_tee"
#: a reference's kind when its source doesn't start with one
KIND_V = {"V1": "exact", "V2": "simulation", "V3": "experiment", "V4": "correlation"}
STATUS_ICON = {"accepted": "✅", "in progress": "🔄", "planned": "📋", "rejected": "❌"}


def readme_block(text: str, name: str, body: str) -> str:
    """*text* with the ``readme:<name>`` block's content replaced by *body*."""
    start, end = f"<!-- readme:{name}:start -->", f"<!-- readme:{name}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"README.md: needs exactly one {start} … {end}")
    a, b = text.index(start) + len(start), text.index(end)
    return text[:a] + "\n" + body.strip("\n") + "\n" + text[b:]


def cite(key: str) -> str | None:
    """"Varghese et al. 2007" for a docs/references.bib key, or None."""
    m = re.search(r"@\w+\{" + re.escape(key) + r",(.*?)\n\}", BIB.read_text(encoding="utf-8"),
                  re.S)
    if not m:
        return None
    author = re.search(r"^\s*author\s*=\s*\{(.+)\},?\s*$", m.group(1), re.M)
    year = re.search(r"^\s*year\s*=\s*\{?(\d{4})", m.group(1), re.M)
    if not author or not year:
        return None
    last = [a.split(",")[0].strip().strip("{}") for a in author.group(1).split(" and ")]
    who = last[0] if len(last) == 1 else (f"{last[0]} and {last[1]}" if len(last) == 2
                                         else f"{last[0]} et al.")
    return f"{who} {year.group(1)}"


def reference_md(meta: dict) -> str:
    """"DNS (V2), Varghese et al. 2007": the primary reference's kind (its
    source's first word or two, else the category's), category, citation."""
    ref = next(r for r in meta["references"] if r["role"] == "primary")
    head = re.split(r"[:,(]", ref["source"], maxsplit=1)[0].strip()
    kind = head if 0 < len(head.split()) <= 2 and "_" not in head \
        and (head.islower() or head.isupper()) else KIND_V[meta["category"]]
    key = ref.get("key") or ref["source"].split()[0]
    who = cite(key)
    return f"{kind} ({meta['category']})" + (f", {who}" if who else "")


def readme_metrics_md(metrics: dict, meta: dict) -> str:
    m = metrics[README_EXAMPLE]
    where = re.sub(r"^#\d+ ", "", m["min_sj_fitting"]).lower()
    cells = f"{fmt_int(m['predicted'])} = {fmt_int(m['meshed'])}"
    cores = "one core" if meta["jobs"] == 1 else f"{meta['jobs']} examples at once"
    return "\n".join([
        f"What it gives (the gallery's `hexmesh.examples.{README_EXAMPLE}`):", "",
        "| cells (predicted = meshed) | regions | min scaled Jacobian (where) | min SICN | build |",
        "|---|---|---|---|---|",
        f"| {cells} | {' · '.join(m['materials'])} | {m['min_sj']:.2f} (the {where}) "
        f"| {m['min_sicn']:.2f} | {m['build_s']:.1f} s |", "",
        f"<sub>gmsh {meta['gmsh']}, {cores}, {meta['date']}.  Every example's numbers: "
        f"[GALLERY.md](docs/GALLERY.md).</sub>"])


def readme_validation_md() -> str:
    cases = [(c, case_meta(c)) for c in case_dirs()]
    order = list(CATEGORIES_V)
    cases.sort(key=lambda cm: (order.index(cm[1]["category"]), cm[1]["task"]))
    lines = ["Each case is meshed by hexmesh, solved with OpenFOAM, and judged by grid",
             "convergence against gates set in advance.", "",
             "| Case | Reference | Result | Status |", "|---|---|---|---|"]
    for _, m in cases:
        lines.append(f"| {m['title']} | {reference_md(m)} | {m.get('headline', '')} "
                     f"| {STATUS_ICON[m['status']]} {m['status']} |")
    planned = planned_cases({m["task"] for _, m in cases})
    if planned:
        short = [re.sub(r"^(Validation|Verification)( \(V\d\))?: ", "", p["title"])
                 for p in planned]
        titles = "; ".join(s[:1].lower() + s[1:] if s[1:2].islower() else s
                           for s in short)                  # "FEniCSx" stays
        titles = titles[:1].upper() + titles[1:]
        cats = sorted({p["category"] for p in planned})
        kinds = ", ".join(f"{KIND_V[c]} ({c})" for c in cats)
        lines.append(f"| {titles} | {kinds} | | {STATUS_ICON['planned']} planned |")
    return "\n".join(lines)


def write_readme(metrics: dict, meta: dict) -> bool:
    """Rewrite README.md's ``metrics`` and ``validation`` blocks; True if
    that changed the file."""
    text = README.read_text(encoding="utf-8")
    new = text
    if metrics.get(README_EXAMPLE) and "error" not in metrics[README_EXAMPLE] and meta:
        new = readme_block(new, "metrics", readme_metrics_md(metrics, meta))
    new = readme_block(new, "validation", readme_validation_md())
    if new != text:
        README.write_text(new, encoding="utf-8", newline="\n")
    return new != text


READING_NUMBERS = [
    "- **Cells:** hexahedra in the written mesh.  hexmesh predicts the count "
    "before GMSH runs (`Assembly.cell_count()`); a ✗ marks a mismatch.",
    "- **SICN:** GMSH's signed inverse condition number, per cell: 1 for a "
    "cube, 0 or below for an inverted cell.  Examples must have none at or "
    "below 0.",
    "- **SJ:** the minimum scaled Jacobian over a hex's corners (1 for a "
    "cube), with the fitting holding the worst cell.  Junctions (tee, wye) "
    "are where it is lowest.",
    "- **Aspect:** the largest ratio of a cell's longest to shortest edge.  "
    "Wall grading and long axial cells raise it deliberately.",
    "- **Build:** wall time of `main()` (build, mesh, write, quality check) on "
    "the machine in the page's footer.  Compare within one run only.",
    "- **Images:** the network from outside (walls grey, open ends coloured "
    "by material), and the inlet cross-section seen from upstream.",
]

#: a fitting type's family when more than one family lists it
FITTING_HOME = {"Straight": "networks", "PipeSpec": "sections", "Assembly": "networks"}


def fitting_family() -> dict[str, str]:
    """Fitting type → the family that explains it (the first listing it,
    unless :data:`FITTING_HOME` says otherwise)."""
    from hexmesh.examples import FAMILIES
    out: dict[str, str] = {}
    for fam, f in FAMILIES.items():
        for t in f["fittings"]:
            out.setdefault(t, fam)
    return {**out, **FITTING_HOME}


def footer(meta: dict) -> list[str]:
    if not meta:
        return ["---", "", "_Examples not measured yet: run `python3 docs/gallery/build.py`._", ""]
    return ["---", "",
            f"Generated {meta['date']} from hexmesh {meta['commit']}, gmsh {meta['gmsh']}, "
            f"Python {meta['python']}, {meta['cpus']} CPUs, {meta['jobs']} job(s).", ""]


def validated_by(tags: list[str], cases: list[tuple[str, dict]], planned: list[dict],
                 val: str = "../../validation/", tasks: str = "../tasks/") -> str:
    """The family's "Validated by" line: every case carrying one of *tags*,
    with its status and last run, or "none"."""
    if not tags:
        return "**Validated by:** no validation tag covers this family yet."
    items = []
    for name, m in cases:
        hit = [t for t in m["tags"]["features"] if t in tags]
        if not hit:
            continue
        run = last_run(name)
        when = f"; last run {run['date']}, hexmesh {run.get('hexmesh', '?')}" if run else ""
        items.append(f"{STATUS_MARK[m['status']]} [{m['title']}]({val}{name}/README.md) "
                     f"({m['category']}, {m['status']}{when}; "
                     + ", ".join(f"`{t}`" for t in hit) + ")")
    for p in planned:
        hit = [t for t in p["features"] if t in tags]
        if hit:
            items.append(f"{STATUS_MARK['planned']} [task {p['task']}]({tasks}{p['file']}) "
                         f"({p['category']}, planned; " + ", ".join(f"`{t}`" for t in hit) + ")")
    tag_text = ", ".join(f"`{t}`" for t in tags)
    if not items:
        return f"**Validated by:** none yet (tags {tag_text})."
    return "\n".join([f"**Validated by** (tags {tag_text}):", "", *(f"- {i}" for i in items)])


def numbers_cells(m: dict | None) -> str:
    if m and "error" not in m:
        return (f"{fmt_int(m['meshed'])} | {m['min_sicn']:.3f} | "
                f"{m['min_sj']:.3f} | {m['build_s']:.1f} s")
    return "— | — | — | —"


def features_md(metrics: dict, meta: dict, anchors: dict[str, str],
                cases: list[tuple[str, dict]], planned: list[dict]) -> str:
    from hexmesh.examples import FAMILIES
    lines = ["# Features", "",
             "The building blocks of a hexmesh network, by family: what each looks "
             "like, how good its cells are, the API sections that explain its "
             "parameters, and the validation cases that cover it.  "
             "[The gallery](../GALLERY.md) explains the numbers.", "",
             "| Family | Examples |", "|---|---|"]
    for fam, f in FAMILIES.items():
        names = ", ".join(f"[{q.split('.')[-1]}](#{q.split('.')[-1]})" for q in f["examples"])
        lines.append(f"| [{f['title']}](#{slug(f['title'])}) | {names} |")
    lines.append("")
    for fam, f in FAMILIES.items():
        lines += [f"## {f['title']}", "", f["intro"], "",
                  "**Fittings:** " + ", ".join(api_link(t, anchors) for t in f["fittings"])
                  + ".", "",
                  validated_by(f["tags"], cases, planned), "",
                  "| Example | Shows | Cells | min SICN | min SJ | Build |",
                  "|---|---|---|---|---|---|"]
        for q in f["examples"]:
            name = q.split(".")[-1]
            summary, _ = md_doc(importlib.import_module(f"hexmesh.examples.{q}").__doc__)
            lines.append(f"| [{name}](#{name}) | {summary} | {numbers_cells(metrics.get(q))} |")
        lines.append("")
        for q in f["examples"]:
            lines.append(example_md(q, metrics.get(q), anchors=anchors))
    return "\n".join(lines + footer(meta))


def applications_md(metrics: dict, meta: dict, anchors: dict[str, str]) -> str:
    from hexmesh.examples import CATEGORIES, FAMILIES
    home = fitting_family()
    pkg = importlib.import_module("hexmesh.examples.applications")
    _, intro = md_doc(pkg.__doc__)
    lines = ["# Applications", "",
             "Networks closer to a real model, built from the [features](FEATURES.md).  "
             "Each lists the fittings it uses, linked to their family.  "
             "[The gallery](../GALLERY.md) explains the numbers.", "", intro, "",
             "| Example | Shows | Cells | min SICN | min SJ | Build |",
             "|---|---|---|---|---|---|"]
    names = CATEGORIES["applications"]
    for name in names:
        q = f"applications.{name}"
        summary, _ = md_doc(importlib.import_module(f"hexmesh.examples.{q}").__doc__)
        lines.append(f"| [{name}](#{name}) | {summary} | {numbers_cells(metrics.get(q))} |")
    lines.append("")
    for name in names:
        q = f"applications.{name}"
        m = metrics.get(q)
        block = example_md(q, m, anchors=anchors, level=2)
        if m and "error" not in m:
            used = []
            for t, n in m["fitting_types"].items():
                fam = home.get(t)
                label = f"{t} ×{n}" if n > 1 else t
                used.append(f"{label} ([{FAMILIES[fam]['title'].lower()}]"
                            f"(FEATURES.md#{slug(FAMILIES[fam]['title'])}))" if fam else label)
            block = block.rstrip("\n") + "\n- **Fittings used:** " + ", ".join(used) + "\n"
        lines.append(block)
    return "\n".join(lines + footer(meta))


def validation_page_md(meta: dict) -> str:
    return "\n".join(["# Validation cases", "", validation_md()] + footer(meta))


def landing_md(metrics: dict, meta: dict, cases: list[tuple[str, dict]]) -> str:
    from hexmesh.examples import CATEGORIES, FAMILIES
    n_feat = sum(len(f["examples"]) for f in FAMILIES.values())
    lines = ["# hexmesh gallery", "",
             "What hexmesh's meshes look like and how good their cells are, on "
             "three pages.  Every example is a runnable module; the pages are "
             "generated by `docs/gallery/build.py` (prose from the examples' "
             "docstrings, numbers and images from meshing them).", "",
             f"- **[Features](gallery/FEATURES.md):** the building blocks, by family "
             f"({len(FAMILIES)} families, {n_feat} examples): bends, reducers, "
             "junctions, sections, layers, grading, and how networks are built.",
             f"- **[Applications](gallery/APPLICATIONS.md):** {len(CATEGORIES['applications'])} "
             "networks closer to a real model, and which fittings they use.",
             f"- **[Validation](gallery/VALIDATION.md):** {len(cases)} cases solved "
             "and compared with a reference, judged by grid convergence.", "",
             "## Features", "", "| | Family | Examples |", "|---|---|---|"]
    for fam, f in FAMILIES.items():
        first = f["examples"][0].split(".")[-1]
        thumb = (f'<img src="gallery/img/{first}.png" width="160" alt="{first}">'
                 if (IMG / f"{first}.png").exists() else "")
        names = ", ".join(f"[{q.split('.')[-1]}](gallery/FEATURES.md#{q.split('.')[-1]})"
                          for q in f["examples"])
        lines.append(f"| {thumb} | [{f['title']}](gallery/FEATURES.md#{slug(f['title'])}) "
                     f"| {names} |")
    lines += ["", "## Applications", "", "| | Example | Shows |", "|---|---|---|"]
    for name in CATEGORIES["applications"]:
        q = f"applications.{name}"
        summary, _ = md_doc(importlib.import_module(f"hexmesh.examples.{q}").__doc__)
        thumb = (f'<img src="gallery/img/{name}.png" width="160" alt="{name}">'
                 if (IMG / f"{name}.png").exists() else "")
        lines.append(f"| {thumb} | [{name}](gallery/APPLICATIONS.md#{name}) | {summary} |")
    by_status = Counter(m["status"] for _, m in cases)
    lines += ["", "## Validation", "",
              "Cases by status: " + ", ".join(f"{STATUS_MARK[s]} {n} {s}"
                                               for s, n in by_status.items()) + ".  "
              "[The Validation page](gallery/VALIDATION.md) has each case and the "
              "coverage matrix (which features each case exercises).", "",
              "## Reading the numbers", "", *READING_NUMBERS, ""]
    return "\n".join(lines + footer(meta))


def write_markdown(metrics: dict, meta: dict) -> None:
    """The landing page and the three pages (decision 0050, task 0142)."""
    anchors = api_anchors()
    cases = [(c, case_meta(c)) for c in case_dirs()]
    planned = planned_cases({m["task"] for _, m in cases})
    pages = {GALLERY: landing_md(metrics, meta, cases),
             FEATURES: features_md(metrics, meta, anchors, cases, planned),
             APPLICATIONS: applications_md(metrics, meta, anchors),
             VALIDATION: validation_page_md(meta)}
    for path, text in pages.items():
        path.write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="+", metavar="NAME",
                    help="examples to re-run (name or category.name)")
    ap.add_argument("--jobs", type=int, default=1, help="examples at once")
    ap.add_argument("--markdown-only", action="store_true",
                    help="rewrite GALLERY.md from metrics.json, no meshing")
    ap.add_argument("--validation", nargs="*", metavar="CASE",
                    help="render validation meshes into their READMEs "
                         "(all cases with meshes() if none named)")
    ap.add_argument("--hero", action="store_true",
                    help="render only img/hero.png (a full run renders it too)")
    ap.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    ap.add_argument("--hworker", nargs=1, help=argparse.SUPPRESS)
    ap.add_argument("--vworker", nargs=3, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.worker:
        worker(args.worker[0], Path(args.worker[1]))
        return
    if args.vworker:
        validation_worker(args.vworker[0], args.vworker[1], Path(args.vworker[2]))
        return
    if args.hworker:
        hero_worker(Path(args.hworker[0]))
        return
    if args.hero:
        run_hero()
        return

    from hexmesh.examples import ALL
    saved = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    metrics = saved.get("examples", {})
    meta = saved.get("meta", {})
    if args.validation is not None:
        cases = args.validation or validation_cases()
        vmetrics = saved.get("validation", {})
        vmetrics.update(run_validation(cases, args.jobs))
        for case in cases:
            update_readme(case, mesh_md(case, vmetrics.get(case, {})))
            print(f"wrote validation/{case}/README.md")
        saved["validation"] = vmetrics
        METRICS.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        write_markdown(metrics, meta)
        print("wrote the gallery pages")
        return
    if not args.markdown_only:
        names = ALL
        if args.only:
            names = [q for q in ALL if q in args.only or q.split(".")[-1] in args.only]
        metrics.update(run_examples(names, args.jobs))
        import gmsh
        meta = {"date": datetime.date.today().isoformat(), "commit": git_describe(),
                "gmsh": gmsh.__version__, "python": sys.version.split()[0],
                "cpus": os.cpu_count(), "jobs": args.jobs}
        METRICS.write_text(json.dumps({**saved, "meta": meta, "examples": metrics},
                                      indent=1), encoding="utf-8")
        if not args.only:
            run_hero()
    write_markdown(metrics, meta)
    print("wrote the gallery pages")
    print("wrote README.md" if write_readme(metrics, meta) else "README.md unchanged")


if __name__ == "__main__":
    main()
