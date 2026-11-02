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

**Runner** (decision 0012's toolchain amendment): ``native`` sources
``OPENFOAM_RC``; ``docker:<image>`` (e.g. ``docker:opencfd/openfoam-
default:2406``) runs each command in a fresh container (as the calling
user where the host has user ids), with the case and any extra
directories mounted at ``/work/0``, ``/work/1``, … and host paths in the
command rewritten to match, so it runs from Windows too (decision 0039,
task 0092).  Pick it with
``set_runner`` or the ``HEXMESH_OPENFOAM`` environment variable; record
``runner()`` and ``openfoam_version()`` with every result.  One
toolchain per case: conversion and solvers in the same runner.
``foam()`` writes each command's output to its log as it runs, and stops
the command (its container) if the caller is interrupted.
"""

from __future__ import annotations

import itertools
import os
import re
import signal
import subprocess
import threading
from pathlib import Path, PurePath

import numpy as np

OPENFOAM_RC = Path("/usr/share/openfoam/etc/bashrc")
#: The image's environment, whatever its version directory.
_DOCKER_RC = "for f in /usr/lib/openfoam/openfoam*/etc/bashrc; do source $f; done"
#: The default for new validation cases (decision 0012, toolchain).
V2406 = "docker:opencfd/openfoam-default:2406"

_runner = os.environ.get("HEXMESH_OPENFOAM", "native")


def set_runner(spec: str) -> None:
    """``"native"`` or ``"docker:<image>"``."""
    global _runner
    if spec != "native" and not (spec.startswith("docker:") and len(spec) > 7):
        raise ValueError(f"OpenFOAM runner {spec!r}: give 'native' or 'docker:<image>'")
    _runner = spec


def runner() -> str:
    return _runner


_names = itertools.count()


def _argv(cmd: str, cwd: Path, mounts=(), name: str | None = None) -> list[str]:
    """The command line that runs *cmd* in *cwd* with the runner's
    OpenFOAM environment (Docker: :func:`docker_argv`); *name* names the
    container."""
    if _runner == "native":
        return ["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; {cmd}"]
    user = (os.getuid(), os.getgid()) if hasattr(os, "getuid") else None
    return docker_argv(cmd, Path(cwd).resolve(), [Path(m).resolve() for m in mounts],
                       image=_runner[len("docker:"):], name=name, user=user)


#: where the Docker runner mounts host directories
CONTAINER_ROOT = "/work"


def container_paths(dirs) -> list[tuple[PurePath, str, bool]]:
    """(host, container path, mounted) for each absolute host directory in
    *dirs* (duplicates collapse; the first is the working directory).
    Directories not inside another one are mounted at ``/work/0``,
    ``/work/1``, …: the one holding the working directory first, then the
    rest in order.  One inside a mounted directory maps to its subpath, so
    ``..`` between them still resolves.  Works on ``PureWindowsPath`` as
    well as ``Path``."""
    dirs = list(dict.fromkeys(dirs))
    roots = [d for d in dirs if not any(o != d and d.is_relative_to(o) for o in dirs)]
    roots.sort(key=lambda r: not dirs[0].is_relative_to(r))          # stable
    out = []
    for d in dirs:
        i, root = next((i, r) for i, r in enumerate(roots) if d.is_relative_to(r))
        rel = d.relative_to(root).as_posix()
        out.append((d, f"{CONTAINER_ROOT}/{i}" + ("" if rel == "." else f"/{rel}"), d == root))
    return out


#: what may end a path in a shell command
_PATH_END = r"""(?=$|[\s;&|<>()"'])"""


def container_command(cmd: str, mapping) -> str:
    """*cmd* with every host path under a mapped directory rewritten to its
    container path (Windows separators become ``/``).  A path matches only
    as a whole word: after the start, a space, ``=`` or a quote."""
    for host, cont, _ in sorted(mapping, key=lambda m: -len(str(m[0]))):
        pattern = (r"""(?<![^\s="'])""" + re.escape(str(host))
                   + r"""(?P<rest>(?:[\\/][^\s;&|<>()"']*)?)""" + _PATH_END)
        cmd = re.sub(pattern, lambda m: cont + m["rest"].replace("\\", "/"), cmd)
    return cmd


def docker_argv(cmd: str, cwd: PurePath, mounts=(), *, image: str, name: str | None = None,
                user: tuple[int, int] | None = None) -> list[str]:
    """``docker run`` for *cmd* in *cwd* (absolute host paths): *cwd* and
    *mounts* mounted under ``/work`` (:func:`container_paths`), ``-w`` the
    container path of *cwd*, host paths in *cmd* rewritten
    (:func:`container_command`).  ``--user`` only with *user* (uid, gid):
    Windows has none, and Docker Desktop maps file ownership itself."""
    mapping = container_paths([cwd, *mounts])
    mounted = sorted((m for m in mapping if m[2]), key=lambda m: int(m[1].split("/")[2]))
    vols = [a for host, cont, _ in mounted for a in ("-v", f"{host}:{cont}")]
    return ["docker", "run", "--rm", *(["--name", name] if name else []),
            *(["--user", f"{user[0]}:{user[1]}"] if user else []),
            "-e", "HOME=/tmp", *vols, "-w", mapping[0][1], "--entrypoint", "bash",
            image, "-c", f"{_DOCKER_RC} >/dev/null 2>&1; {container_command(cmd, mapping)}"]

_NUM = r"[-+0-9.eE]+"


def header(cls: str, obj: str, location: str = "") -> str:
    """A ``FoamFile`` header for a dictionary or field file."""
    loc = f'    location    "{location}";\n' if location else ""
    return ("FoamFile\n{\n    version     2.0;\n    format      ascii;\n"
            f"    class       {cls};\n{loc}    object      {obj};\n}}\n\n")


def have_openfoam() -> bool:
    """Whether the selected runner has OpenFOAM (``gmshToFoam``)."""
    if _runner == "native" and not OPENFOAM_RC.exists():
        return False
    try:
        run = subprocess.run(_argv("command -v gmshToFoam", Path.cwd()), capture_output=True)
    except FileNotFoundError:          # no docker
        return False
    return run.returncode == 0


def foam(cmd: str, case: Path, log: str, mounts=()) -> str:
    """Run *cmd* (a shell command) in *case* with the runner's OpenFOAM
    environment; raise ``RuntimeError`` on failure; return its standard
    output.  The output goes to ``case/log`` as it runs (standard error
    appended at the end).  *mounts*: further directories a Docker runner
    needs.

    If the caller is interrupted (``KeyboardInterrupt``, ``SystemExit``,
    or SIGTERM, e.g. from ``timeout``), the command is stopped too: a
    Docker container would otherwise outlive its client (task 0035)."""
    name = None if _runner == "native" else f"hexmesh-{os.getpid()}-{next(_names)}"
    path = Path(case) / log
    main = threading.current_thread() is threading.main_thread()
    if main:
        def _term(signum, frame):
            raise SystemExit(128 + signum)
        old = signal.signal(signal.SIGTERM, _term)
    try:
        with open(path, "w", encoding="utf-8") as out:
            proc = subprocess.Popen(_argv(cmd, case, mounts, name), cwd=case, stdout=out,
                                    stderr=subprocess.PIPE, text=True)
            try:
                _, err = proc.communicate()
            except BaseException:
                if name:
                    subprocess.run(["docker", "stop", "-t", "2", name], capture_output=True)
                proc.terminate()
                proc.wait()
                raise
        stdout = path.read_text(encoding="utf-8")
        if err:
            with open(path, "a", encoding="utf-8") as out:
                out.write(err)
    finally:
        if main:
            signal.signal(signal.SIGTERM, old)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd} failed in {case} (see {log}):\n{stdout[-3000:]}"
                           f"{err[-2000:]}")
    return stdout


def openfoam_version() -> str:
    return subprocess.run(_argv("echo $WM_PROJECT_VERSION", Path.cwd()),
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
    foam(f"gmshToFoam {msh.resolve()}", case, "log.gmshToFoam", mounts=[msh.resolve().parent])
    if split_regions:
        foam("splitMeshRegions -cellZones -overwrite", case, "log.splitMeshRegions")
        done = apply_boundary_roles_to_regions(case, roles_path(msh))
        return sorted(f"{region}/{p}" for region, ps in done.items() for p in ps)
    return apply_boundary_roles(case, roles_path(msh))


def check_mesh(case: Path, region: str | None = None) -> dict:
    """``checkMesh`` (of *region*): Mesh OK, cells, max non-orthogonality
    and skewness."""
    out = (foam(f"checkMesh -region {region}", case, f"log.checkMesh.{region}") if region
           else foam("checkMesh", case, "log.checkMesh"))
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
    n, body = _list_body(_strip_header(path.read_text(encoding="utf-8")))
    return np.array(re.findall(_NUM, body), float).reshape(n, 3)


def read_faces(path: Path) -> list[list[int]]:
    n, body = _list_body(_strip_header(path.read_text(encoding="utf-8")))
    faces = [[int(v) for v in f.split()] for f in re.findall(r"\d+\(([^)]*)\)", body)]
    assert len(faces) == n
    return faces


def read_labels(path: Path):
    n, body = _list_body(_strip_header(path.read_text(encoding="utf-8")))
    return np.array(body.split(), int)


def read_zone(path: Path, name: str):
    text = _strip_header(path.read_text(encoding="utf-8"))
    # v1912 puts each name on its own line; v2406 opens the list on the
    # first one, "(planeA"
    i = re.search(rf"^\(?{name}\s*\{{", text, re.M).end()
    _, body = _list_body(text, text.index("faceLabels", i))
    return np.array(body.split(), int)


def read_internal(path: Path, ncomp: int):
    text = _strip_header(path.read_text(encoding="utf-8"))
    i = text.index("internalField")
    n, body = _list_body(text, i)
    return np.array(re.findall(_NUM, body), float).reshape(n, ncomp) if ncomp > 1 \
        else np.array(body.split(), float)


def read_patch_faces(path: Path, patch: str):
    """Face labels of *patch*, from ``constant/polyMesh/boundary``."""
    text = _strip_header(path.read_text(encoding="utf-8"))
    i = re.search(rf"^\s*{patch}\s*\{{", text, re.M).end()
    body = text[i:text.index("}", i)]
    n = int(re.search(r"nFaces\s+(\d+)", body).group(1))
    start = int(re.search(r"startFace\s+(\d+)", body).group(1))
    return np.arange(start, start + n)


def read_patch_values(path: Path, patch: str, n: int | None = None):
    """A patch's ``value`` list (scalars).  A ``uniform`` value is returned
    as *n* copies, or raises ``ValueError`` without *n*."""
    text = _strip_header(path.read_text(encoding="utf-8"))
    i = re.search(rf"^\s*{patch}\s*\{{", text[text.index("boundaryField"):], re.M)
    j = text.index("boundaryField") + i.end()
    k = re.compile(r"(?<!\w)value\s").search(text, j).start()   # not valueFraction
    words = text[k:].split(None, 3)
    if words[1] == "uniform":
        if n is None:
            raise ValueError(f"{patch}: uniform value, expected a list")
        return np.full(n, float(words[2].rstrip(";")))
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
            text = path.read_text(encoding="utf-8")
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
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(str(rel))
    return changed


def _format(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)
