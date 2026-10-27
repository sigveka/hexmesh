"""
Example gallery: meshes every example, renders it, measures it, and writes
``docs/GALLERY.md``.  Not part of the test suite.

    python3 docs/gallery/build.py                   # every example, one at a time
    python3 docs/gallery/build.py --jobs 4          # four examples at once
    python3 docs/gallery/build.py --only tee wye    # re-run some, keep the rest
    python3 docs/gallery/build.py --markdown-only   # rewrite GALLERY.md only

The prose comes from the examples' docstrings and the category packages'
docstrings, so edit it there.  Validation cases come from
``validation/<case>/`` (README.md, RESULTS.md with a ``**Status:**`` line,
optional ``figure.png``) and planned ones from ``docs/tasks/*validation*``.

Needs ``vtk`` for rendering.  Each example runs in its own process (one
GMSH session each).  Follow the shared-machine rules in CLAUDE.md before a
full run; build times measured with ``--jobs`` > 1, or while other runs
are active, are contended.

Writes ``docs/gallery/img/<name>.png`` (overview), ``<name>_section.png``
(inlet cross-section), ``docs/gallery/metrics.json`` and ``docs/GALLERY.md``.
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
GALLERY = ROOT / "docs" / "GALLERY.md"

sys.path.insert(0, str(ROOT))

# Open ends and section faces are coloured by material, in the order the
# assembly lists its materials; walls are neutral.
PALETTE = ["#3b7dd8", "#d9822b", "#5aa469", "#a361c7", "#c9b037"]
COLOUR_NAMES = ["blue", "orange", "green", "purple", "yellow"]
WALL = "#d5d9df"
EDGE = "#55606e"


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


def render(scene: dict, path: Path, size, view: str) -> None:
    """Render polygons with VTK, off screen, to a PNG."""
    import numpy as np
    import vtk

    def rgb(h):
        return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    points = vtk.vtkPoints()
    xyz = scene["xyz"]
    for p in xyz:
        points.InsertNextPoint(*p)
    used = []
    for key, polys in scene["polys"].items():
        if not polys:
            continue
        cells = vtk.vtkCellArray()
        for poly in polys:
            cells.InsertNextCell(len(poly), poly)
            used.extend(poly)
        data = vtk.vtkPolyData()
        data.SetPoints(points)
        data.SetPolys(cells)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(data)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        colour = WALL if key == "wall" or key is None else \
            PALETTE[scene["materials"].index(key) % len(PALETTE)]
        prop.SetColor(*rgb(colour))
        prop.EdgeVisibilityOn()
        prop.SetEdgeColor(*rgb(EDGE))
        prop.SetLineWidth(0.6 if view == "overview" else 1.0)
        if view == "section":
            prop.LightingOff()
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


def worker(qualname: str, out: Path) -> None:
    module = importlib.import_module(f"hexmesh.examples.{qualname}")
    name = qualname.split(".")[-1]
    captured: dict = {}
    spent = [0.0]

    def inspect(asm):
        t = time.perf_counter()
        captured["metrics"] = measure(asm)
        captured["overview"], captured["section"] = faces(asm)
        spent[0] = time.perf_counter() - t

    with tempfile.TemporaryDirectory() as tmp:
        t = time.perf_counter()
        result = module.main(os.path.join(tmp, f"{name}.msh"), inspect=inspect)
        build = time.perf_counter() - t - spent[0]

    IMG.mkdir(parents=True, exist_ok=True)
    render(captured["overview"], IMG / f"{name}.png", (1000, 560), "overview")
    render(captured["section"], IMG / f"{name}_section.png", (420, 420), "section")
    m = captured["metrics"]
    m.update(predicted=result.predicted, meshed=result.meshed,
             build_s=round(build, 2))
    out.write_text(json.dumps(m, indent=1))


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
            m = json.loads(out.read_text())
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


def example_md(qualname: str, m: dict | None) -> str:
    module = importlib.import_module(f"hexmesh.examples.{qualname}")
    name = qualname.split(".")[-1]
    summary, body = md_doc(module.__doc__)
    out = [f"### {name}", "", f"**{summary}**", ""]
    if m and "error" not in m:
        out += [f'<p><img src="gallery/img/{name}.png" width="68%" alt="{name}"> '
                f'<img src="gallery/img/{name}_section.png" width="29%" '
                f'alt="{name}, inlet section"></p>', ""]
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
    out += [f"- **Colours:** {colours}; walls grey.", ""]
    return "\n".join(out)


def status_of(text: str) -> str:
    """The ``**Status:** …`` paragraph or list item of a Markdown file."""
    m = re.search(r"\*\*Status:?\*?\*?:?\s*(.+?)(?:\n\s*\n|\n- )", text + "\n\n", re.S)
    if not m:
        return "—"
    status = " ".join(m.group(1).replace("**", "").split())
    return status.split(". ")[0].rstrip(".")


def validation_md() -> str:
    out = [
        "## Validation",
        "",
        "Meshes from hexmesh solved with OpenFOAM and compared with analytic or "
        "published solutions (decision 0012); each case is judged by grid "
        "convergence against gates set in advance (decision 0015).",
        "",
        "Each case lives in `validation/<case>/`: `README.md` describes it, "
        "`RESULTS.md` holds the measurements and opens with a `**Status:**` "
        "line, and an optional `figure.png` is shown here.",
        "",
    ]
    cases = sorted(p for p in (ROOT / "validation").glob("*/RESULTS.md"))
    for res in cases:
        case = res.parent
        title = next((re.sub(r"^Results:\s*", "", l[2:].strip()) for l in res.read_text().splitlines()
                      if l.startswith("# ")), case.name)
        out += [f"### {title}", "",
                f"**Status:** {status_of(res.read_text())}", ""]
        if (case / "figure.png").exists():
            out += [f'<img src="../validation/{case.name}/figure.png" width="70%">', ""]
        out += [f"Case: [validation/{case.name}/README.md](../validation/{case.name}/README.md); "
                f"results: [RESULTS.md](../validation/{case.name}/RESULTS.md).", ""]
    planned = []
    for t in sorted((ROOT / "docs" / "tasks").glob("*validation*.md")):
        if any(r.parent.name in t.stem for r in cases):
            continue
        text = t.read_text()
        title = text.splitlines()[0].lstrip("# ").strip()
        planned.append(f"| [{title}](tasks/{t.name}) | {status_of(text)} |")
    if planned:
        out += ["### Planned", "", "| Task | Status |", "|---|---|", *planned, ""]
    return "\n".join(out)


def write_markdown(metrics: dict, meta: dict) -> None:
    from hexmesh.examples import CATEGORIES

    jobs = meta.get("jobs", 1)
    lines = [
        "# hexmesh examples",
        "",
        "What each example shows, what its mesh looks like, and how good the "
        "cells are.  Every example is a runnable module; this page is "
        "generated by `docs/gallery/build.py` (prose from the examples' "
        "docstrings, numbers and images from meshing them).",
        "",
        "## Reading the numbers",
        "",
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
        f"the machine below{' with ' + str(jobs) + ' examples at once' if jobs > 1 else ''}.  "
        "Compare within one run only.",
        "- **Images:** the network from outside (walls grey, open ends coloured "
        "by material), and the inlet cross-section seen from upstream.",
        "",
        "## Contents",
        "",
        "| Example | Shows | Cells | min SICN | min SJ | Build |",
        "|---|---|---|---|---|---|",
    ]
    body = []
    for cat, names in CATEGORIES.items():
        pkg = importlib.import_module(f"hexmesh.examples.{cat}")
        title, intro = md_doc(pkg.__doc__)
        lines.append(f"| **{title.rstrip('.')}** | | | | | |")
        body += [f"## {title.rstrip('.')}", "", intro, ""]
        for name in names:
            qual = f"{cat}.{name}"
            m = metrics.get(qual)
            summary, _ = md_doc(importlib.import_module(f"hexmesh.examples.{qual}").__doc__)
            if m and "error" not in m:
                nums = (f"{fmt_int(m['meshed'])} | {m['min_sicn']:.3f} | "
                        f"{m['min_sj']:.3f} | {m['build_s']:.1f} s")
            else:
                nums = "— | — | — | —"
            lines.append(f"| [{name}](#{name}) | {summary} | {nums} |")
            body.append(example_md(qual, m))
    lines += ["", *body, validation_md(), "---", ""]
    if meta:
        lines += [f"Generated {meta['date']} from hexmesh {meta['commit']}, "
                  f"gmsh {meta['gmsh']}, Python {meta['python']}, "
                  f"{meta['cpus']} CPUs, {meta['jobs']} job(s).", ""]
    else:
        lines += ["_Examples not measured yet: run `python3 docs/gallery/build.py`._", ""]
    GALLERY.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="+", metavar="NAME",
                    help="examples to re-run (name or category.name)")
    ap.add_argument("--jobs", type=int, default=1, help="examples at once")
    ap.add_argument("--markdown-only", action="store_true",
                    help="rewrite GALLERY.md from metrics.json, no meshing")
    ap.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.worker:
        worker(args.worker[0], Path(args.worker[1]))
        return

    from hexmesh.examples import ALL
    saved = json.loads(METRICS.read_text()) if METRICS.exists() else {}
    metrics = saved.get("examples", {})
    meta = saved.get("meta", {})
    if not args.markdown_only:
        names = ALL
        if args.only:
            names = [q for q in ALL if q in args.only or q.split(".")[-1] in args.only]
        metrics.update(run_examples(names, args.jobs))
        import gmsh
        meta = {"date": datetime.date.today().isoformat(), "commit": git_describe(),
                "gmsh": gmsh.__version__, "python": sys.version.split()[0],
                "cpus": os.cpu_count(), "jobs": args.jobs}
        METRICS.write_text(json.dumps({"meta": meta, "examples": metrics}, indent=1))
    write_markdown(metrics, meta)
    print(f"wrote {GALLERY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
