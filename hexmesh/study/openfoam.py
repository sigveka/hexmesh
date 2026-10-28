"""
Shared OpenFOAM helpers (decision 0025 item 7, task 0043): dictionary
headers, running a utility with a log, mesh conversion, and readers for
ASCII polyMesh and field files.  Moved from the validation scripts
(``validation/poiseuille/run.py``, ``validation/heated_rod/run.py``),
which now use them, as does the study's case and run stages.

Post-processing is in Python, from the ASCII case files: function objects
(controlDict ``functions`` and ``postProcess -func``) abort on OpenFOAM
v1912 here, and coded boundary conditions fail to compile
(``docs/integrations/openfoam.md``).  Cases must be written with
``writeFormat ascii`` and ``writeCompression off`` for the readers.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

OPENFOAM_RC = Path("/usr/share/openfoam/etc/bashrc")

_NUM = r"[-+0-9.eE]+"


def header(cls: str, obj: str, location: str = "") -> str:
    """A ``FoamFile`` header for a dictionary or field file."""
    loc = f'    location    "{location}";\n' if location else ""
    return ("FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            f"    class       {cls};\n{loc}    object      {obj};\n}}\n\n")


def have_openfoam() -> bool:
    if not OPENFOAM_RC.exists():
        return False
    run = subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; "
                          "command -v gmshToFoam"], capture_output=True)
    return run.returncode == 0


def foam(cmd: str, case: Path, log: str) -> str:
    """Run *cmd* (a shell command) in *case* with the OpenFOAM environment;
    write its output to ``case/log``; raise ``RuntimeError`` on failure."""
    run = subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; {cmd}"],
                         cwd=case, capture_output=True, text=True)
    (case / log).write_text(run.stdout + run.stderr)
    if run.returncode != 0:
        raise RuntimeError(f"{cmd} failed in {case} (see {log}):\n{run.stdout[-3000:]}"
                           f"{run.stderr[-2000:]}")
    return run.stdout


def openfoam_version() -> str:
    return subprocess.run(["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; "
                           "echo $WM_PROJECT_VERSION"],
                          capture_output=True, text=True).stdout.strip()


# --- mesh conversion ----------------------------------------------------------

def convert(case: Path, msh: Path, split_regions: bool = False) -> list[str]:
    """``gmshToFoam`` *msh* into *case*, then retype the patches from the
    mesh's role manifest (decision 0013).  With *split_regions*, run
    ``splitMeshRegions -cellZones -overwrite`` first and retype each
    region.  Returns the retyped patch names."""
    from ..io.writers.openfoam_boundary import (
        apply_boundary_roles, apply_boundary_roles_to_regions, roles_path,
    )
    msh = Path(msh)
    foam(f"gmshToFoam {msh.resolve()}", case, "log.gmshToFoam")
    if split_regions:
        foam("splitMeshRegions -cellZones -overwrite", case, "log.splitMeshRegions")
        done = apply_boundary_roles_to_regions(case, roles_path(msh))
        return sorted(f"{region}/{p}" for region, ps in done.items() for p in ps)
    return apply_boundary_roles(case, roles_path(msh))


def check_mesh(case: Path) -> dict:
    """``checkMesh``: Mesh OK, cells, max non-orthogonality and skewness."""
    out = foam("checkMesh", case, "log.checkMesh")
    return {
        "mesh_ok": "Mesh OK." in out,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", out).group(1)),
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", out).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", out).group(1)),
    }


# --- readers ------------------------------------------------------------------

def _list_body(text: str, start: int = 0) -> tuple[int, str]:
    """``N ( … )`` at or after *start*: (N, body between the parentheses)."""
    m = re.compile(r"(\d+)\s*\(").search(text, start)
    n, i, depth = int(m.group(1)), m.end(), 1
    j = i
    while depth:
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        j += 1
    return n, text[i:j - 1]


def _strip_header(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    return text[text.index("}", text.index("FoamFile")) + 1:]


def read_points(path: Path):
    n, body = _list_body(_strip_header(path.read_text()))
    return np.array(re.findall(_NUM, body), float).reshape(n, 3)


def read_faces(path: Path) -> list[list[int]]:
    n, body = _list_body(_strip_header(path.read_text()))
    faces = [[int(v) for v in f.split()] for f in re.findall(r"\d+\(([^)]*)\)", body)]
    assert len(faces) == n
    return faces


def read_labels(path: Path):
    n, body = _list_body(_strip_header(path.read_text()))
    return np.array(body.split(), int)


def read_zone(path: Path, name: str):
    text = _strip_header(path.read_text())
    i = re.search(rf"^{name}\s*\{{", text, re.M).end()
    _, body = _list_body(text, text.index("faceLabels", i))
    return np.array(body.split(), int)


def read_internal(path: Path, ncomp: int):
    text = _strip_header(path.read_text())
    i = text.index("internalField")
    n, body = _list_body(text, i)
    return np.array(re.findall(_NUM, body), float).reshape(n, ncomp) if ncomp > 1 \
        else np.array(body.split(), float)


def read_patch_faces(path: Path, patch: str):
    """Face labels of *patch*, from ``constant/polyMesh/boundary``."""
    text = _strip_header(path.read_text())
    i = re.search(rf"^\s*{patch}\s*\{{", text, re.M).end()
    body = text[i:text.index("}", i)]
    n = int(re.search(r"nFaces\s+(\d+)", body).group(1))
    start = int(re.search(r"startFace\s+(\d+)", body).group(1))
    return np.arange(start, start + n)


def read_patch_values(path: Path, patch: str):
    text = _strip_header(path.read_text())
    i = re.search(rf"^\s*{patch}\s*\{{", text[text.index("boundaryField"):], re.M)
    j = text.index("boundaryField") + i.end()
    k = text.index("value", j)
    if text[k:].split(None, 2)[1] == "uniform":
        raise ValueError(f"{patch}: uniform value, expected a list")
    _, body = _list_body(text, k)
    return np.array(body.split(), float)


def latest_time(case: Path) -> Path:
    times = [d for d in case.iterdir() if d.is_dir() and re.fullmatch(r"[\d.e+-]+", d.name)]
    return max(times, key=lambda d: float(d.name))


# --- geometry of the polyMesh, as OpenFOAM computes it -------------------------

def face_geometry(pts: np.ndarray, faces: list[list[int]]):
    """Face centres and area vectors (``primitiveMeshFaceCentresAndAreas``:
    triangles about the point average, centroids weighted by area)."""
    q = pts[np.array(faces)]                       # (F, 4, 3): all quads
    est = q.mean(axis=1)
    a, b = q, np.roll(q, -1, axis=1)
    n = np.cross(b - a, est[:, None] - a)          # 2 × triangle area vectors
    mag = np.linalg.norm(n, axis=2)
    c = (a + b + est[:, None]) / 3
    centres = (mag[..., None] * c).sum(1) / mag.sum(1)[:, None]
    return centres, 0.5 * n.sum(1)


def cell_geometry(fc, sf, owner, neigh, n_cells):
    """Cell centres and volumes (``primitiveMeshCellCentresAndVols``:
    pyramids from each face to the face-centre average)."""
    nf = len(neigh)
    cnt = np.bincount(owner, minlength=n_cells) + np.bincount(neigh, minlength=n_cells)
    est = np.zeros((n_cells, 3))
    np.add.at(est, owner, fc)
    np.add.at(est, neigh, fc[:nf])
    est /= cnt[:, None]
    vol = np.zeros(n_cells)
    ctr = np.zeros((n_cells, 3))
    for cells, faces, sign in ((owner, slice(None), 1.0), (neigh, slice(0, nf), -1.0)):
        f = fc[faces]
        pyr = sign * np.einsum("ij,ij->i", sf[faces], f - est[cells])
        np.add.at(vol, cells, pyr)
        np.add.at(ctr, cells, pyr[:, None] * (0.75 * f + 0.25 * est[cells]))
    return ctr / vol[:, None], vol / 3


# --- case templates (task 0043) ------------------------------------------------

_TOKEN = re.compile(r"(?<![\w$])\$([A-Za-z_]\w*)(?!\w)")
_KEYWORD = re.compile(r"^\s*([A-Za-z_]\w*)\b", re.M)


def substitute_case(case: Path, params: dict) -> list[str]:
    """Replace ``$name`` tokens in the text files of *case* (not
    ``constant/polyMesh``, not logs) by the parameter's value; return the
    files changed (relative paths).

    Whole tokens only: ``$D`` is a placeholder, ``$Dmax`` another name, and
    ``$$`` a literal ``$``.  OpenFOAM's own references are left alone: a
    name that is a keyword on another line of the same file
    (``$internalField``, ``$inletValue``) or an environment variable
    (``$FOAM_…``, ``$WM_…``).  ``nu $nu;`` is a placeholder: an entry
    can't refer to itself.
    Any other ``$name`` without a parameter raises ``ValueError`` naming
    the file.
    """
    changed = []
    for path in sorted(p for p in case.rglob("*") if p.is_file()):
        rel = path.relative_to(case)
        if rel.parts[:2] == ("constant", "polyMesh") or rel.name.startswith("log."):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        if "$" not in text:
            continue
        work = text.replace("$$", "\0")
        lines = {}                                   # keyword → line numbers
        for k in _KEYWORD.finditer(work):
            lines.setdefault(k.group(1), set()).add(work.count("\n", 0, k.start()))
        missing = []

        def value(m):
            name = m.group(1)
            if name in params:
                return _format(params[name])
            here = work.count("\n", 0, m.start())
            if not (lines.get(name, set()) - {here}) and not name.startswith(("FOAM_", "WM_")):
                missing.append(name)
            return m.group(0)

        new = _TOKEN.sub(value, work).replace("\0", "$")
        if missing:
            raise ValueError(f"{rel}: unknown placeholder(s) "
                             + ", ".join(f"${n}" for n in dict.fromkeys(missing)))
        if new != text:
            path.write_text(new)
            changed.append(str(rel))
    return changed


def _format(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)
