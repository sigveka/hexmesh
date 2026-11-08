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

**Parallel runs** (task 0090): ``run_solver(case, solver, n_proc=…)`` is
the one place a case is decomposed, run under ``mpirun`` and
reconstructed.  ``n_proc`` is capped at the machine's physical cores
(``physical_cores``).  It doesn't look for other sessions' runs: that is
the caller's duty on a shared machine (CLAUDE.md).
"""

from __future__ import annotations

import itertools
import os
import re
import shutil
import signal
import subprocess
import threading
from pathlib import Path, PurePath

import numpy as np

from .definition import StudyError


class FoamCommandFailed(StudyError, RuntimeError):
    """An OpenFOAM command that exited with an error: still a
    ``RuntimeError``, as it was before task 0106."""

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
        raise StudyError(f"OpenFOAM runner {spec!r}: give 'native' or 'docker:<image>'",
                         code="option_invalid", where={"field": "runner"}, value=spec,
                         limit=["native", "docker:<image>"])
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
        raise FoamCommandFailed(f"{cmd} failed in {case} (see {log}):\n{stdout[-3000:]}"
                                f"{err[-2000:]}", code="openfoam_command_failed",
                                where={"label": cmd.split()[0]}, value=proc.returncode,
                                hint=f"read {Path(case) / log}; have_openfoam() checks the "
                                     f"runner ({_runner})")
    return stdout


def openfoam_version() -> str:
    return subprocess.run(_argv("echo $WM_PROJECT_VERSION", Path.cwd()),
                          capture_output=True, text=True).stdout.strip()


# --- mesh conversion ----------------------------------------------------------

def physical_cores() -> int:
    """Physical cores of this machine: Open MPI's default slot count is
    cores, not hardware threads (``docs/integrations/openfoam.md``).
    ``psutil`` when installed, else ``/proc/cpuinfo``, else
    ``os.cpu_count()``."""
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return int(n)
    except ImportError:
        pass
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8")
    except OSError:
        return os.cpu_count() or 1
    return cpuinfo_cores(text) or os.cpu_count() or 1


def cpuinfo_cores(text: str) -> int:
    """Distinct (physical id, core id) pairs in a ``/proc/cpuinfo``; 0 if
    it lists none (some virtual machines)."""
    cores, phys = set(), "0"
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "physical id":
            phys = value
        elif key == "core id":
            cores.add((phys, value))
    return len(cores)


def _mesh_dirs(case: Path, regions) -> list[Path]:
    return [case / "constant" / r / "polyMesh" for r in regions] or [case / "constant/polyMesh"]


def long_axis(case: Path, regions=()) -> int:
    """Index (0, 1, 2) of the coordinate along which the case's mesh is
    longest: of its first region's, when it has regions."""
    pts = read_points(_mesh_dirs(case, regions)[0] / "points")
    return int(np.argmax(pts.max(axis=0) - pts.min(axis=0)))


def decompose_dict(n_proc: int, axis: int = 0) -> str:
    """``decomposeParDict``: *n_proc* slabs along coordinate *axis*,
    ``method simple`` (``scotch`` is a dummy in the native v1912 build;
    v2406's works, ``docs/integrations/openfoam.md``)."""
    n = ["1", "1", "1"]
    n[axis] = str(n_proc)
    return (header("dictionary", "decomposeParDict", "system")
            + f"numberOfSubdomains {n_proc};\nmethod          simple;\n"
            f"simpleCoeffs {{ n ({' '.join(n)}); delta 0.001; }}\n")


def start_time_option(case: Path) -> str:
    """The ``decomposePar`` time option for the time *case*'s solver
    starts from (``controlDict``'s ``startFrom``): ``-latestTime``, or
    ``-time <t>`` for ``startTime`` (OpenFOAM's default) and
    ``firstTime``.  Only that time is decomposed: the processor
    directories need no other."""
    text = _strip_header((Path(case) / "system/controlDict").read_text(encoding="utf-8"))
    start = re.search(r"^\s*startFrom\s+(\w+)\s*;", text, re.M)
    mode = start.group(1) if start else "startTime"
    if mode == "latestTime":
        return "-latestTime"
    times = [d.name for d in Path(case).iterdir()
             if d.is_dir() and re.fullmatch(r"[\d.e+-]+", d.name)]
    if mode == "firstTime":
        return f"-time {min(times, key=float)}"
    value = re.search(r"^\s*startTime\s+(" + _NUM + r")\s*;", text, re.M)
    return f"-time {value.group(1) if value else 0}"


def run_solver(case: Path, solver: str, *, n_proc: int = 1, log: str | None = None,
               regions=(), axis: int | None = None, keep: bool = False) -> str:
    """Run *solver* in *case* and return its log, as ``foam(solver, …)``.

    ``n_proc = 1`` is exactly ``foam``.  ``n_proc > 1``: write
    ``decomposeParDict`` (slabs along *axis*, by default the mesh's
    longest, ``long_axis``; also into ``system/<region>/`` for each of
    *regions*), ``decomposePar -force`` of the time the solver starts
    from (``start_time_option``), ``mpirun -np N
    <solver> -parallel``, ``reconstructPar -newTimes`` (with
    ``-allRegions`` when there are *regions*), then remove the
    ``processor*`` directories unless *keep*.  The case is serial again
    afterwards, so a driver that marches in chunks calls this per chunk:
    decomposing and reconstructing map fields exactly.

    Raises ``ValueError`` for ``n_proc`` < 1 or above ``physical_cores()``.
    Doesn't check for other runs on the machine (the caller's duty).
    """
    case = Path(case)
    log = log or f"log.{solver}"
    if n_proc < 1:
        raise StudyError(f"n_proc must be >= 1, got {n_proc!r}",
                         code="count_below_minimum", where={"field": "n_proc"}, value=n_proc,
                         limit={"min": 1})
    cores = physical_cores()
    if n_proc > cores:
        raise StudyError(f"n_proc={n_proc} is more than this machine's {cores} physical cores "
                         f"(Open MPI places one rank per core, not per hardware thread)",
                         code="cores_exceeded", where={"field": "n_proc"}, value=n_proc,
                         limit={"max": cores})
    if n_proc == 1:
        return foam(solver, case, log)
    regions = tuple(regions)
    text = decompose_dict(n_proc, long_axis(case, regions) if axis is None else axis)
    for d in [case / "system"] + [case / "system" / r for r in regions]:
        d.mkdir(parents=True, exist_ok=True)
        (d / "decomposeParDict").write_text(text, encoding="utf-8")
    every = " -allRegions" if regions else ""
    foam(f"decomposePar -force {start_time_option(case)}{every}", case, f"{log}.decomposePar")
    out = foam(f"mpirun -np {n_proc} {solver} -parallel", case, log)
    foam(f"reconstructPar -newTimes{every}", case, f"{log}.reconstructPar")
    if not keep:
        for d in case.glob("processor*"):
            shutil.rmtree(d)
    return out


def convert(case: Path, msh: Path, split_regions: bool = False,
            keep_orientation: bool = False) -> list[str]:
    """``gmshToFoam`` *msh* into *case*, then retype the patches from the
    mesh's role manifest (decision 0013).  With *split_regions*, run
    ``splitMeshRegions -cellZones -overwrite`` first and retype each
    region.  Returns the retyped patch names.

    *keep_orientation* passes ``-keepOrientation``: gmshToFoam's own
    orientation test misjudges strongly warped hexes and turns valid ones
    inside out (docs/integrations/openfoam.md, task 0074).  Pass it only
    for a mesh whose every hex is known right-handed, e.g. a positive
    worst scaled Jacobian from ``Assembly.check_quality``; the validation
    drivers do (task 0108).  :func:`would_invert` counts the hexes the
    test would flip.  Off by default."""
    from ..io.writers.openfoam_boundary import (
        apply_boundary_roles, apply_boundary_roles_to_regions, roles_path,
    )
    msh = Path(msh)
    keep = " -keepOrientation" if keep_orientation else ""
    foam(f"gmshToFoam{keep} {msh.resolve()}", case, "log.gmshToFoam",
         mounts=[msh.resolve().parent])
    if split_regions:
        foam("splitMeshRegions -cellZones -overwrite", case, "log.splitMeshRegions")
        done = apply_boundary_roles_to_regions(case, roles_path(msh))
        return sorted(f"{region}/{p}" for region, ps in done.items() for p in ps)
    return apply_boundary_roles(case, roles_path(msh))


#: OpenFOAM's hex model faces, outward (gmshToFoam keeps gmsh's vertex order)
_FOAM_HEX_FACES = ((0, 4, 7, 3), (1, 2, 6, 5), (0, 1, 5, 4), (3, 7, 6, 2), (0, 3, 2, 1),
                   (4, 5, 6, 7))


def foam_would_invert(p: np.ndarray) -> np.ndarray:
    """gmshToFoam's ``correctOrientation`` on hexes *p* (n, 8, 3), gmsh's
    vertex order: True where it would flip the hex, i.e. where for any face
    the vector from the face's first vertex to the vertex centroid is on
    the wrong side of the face's area normal (triangles about the face
    centre).  It misjudges strongly warped right-handed hexes
    (docs/integrations/openfoam.md, task 0074)."""
    p = np.asarray(p, dtype=float)
    cc = p.mean(axis=1)
    bad = np.zeros(len(p), bool)
    for f in _FOAM_HEX_FACES:
        q = p[:, f]
        fc = q.mean(axis=1)
        a = sum(np.cross(q[:, i] - fc, q[:, (i + 1) % 4] - fc) for i in range(4))
        bad |= np.einsum("ij,ij->i", q[:, 0] - cc, a) < 0
    return bad


def msh_hexes(msh: Path) -> np.ndarray:
    """The hexes of an MSH 2.2 ASCII file (``Assembly.write_openfoam``'s
    format), as their corner points (n, 8, 3) in the file's vertex order.
    Needs no GMSH."""
    from ..errors import ReaderError
    text = Path(msh).read_text(encoding="utf-8")
    if "$MeshFormat\n2.2 0 " not in text:
        raise ReaderError(f"{msh}: not MSH 2.2 ASCII, which write_openfoam writes",
                          code="msh_format_invalid", where={"source": {"file": str(msh)}},
                          hint="write it with Assembly.write_openfoam")
    nodes = text.split("$Nodes\n", 1)[1].split("$EndNodes", 1)[0].split("\n", 1)[1]
    xyz = np.array(nodes.split(), dtype=float).reshape(-1, 4)
    pos = np.full(int(xyz[:, 0].max()) + 1, -1)
    pos[xyz[:, 0].astype(int)] = np.arange(len(xyz))
    corners = []
    body = text.split("$Elements\n", 1)[1].split("$EndElements", 1)[0]
    for line in body.splitlines()[1:]:
        f = line.split()
        if f[1] == "5":                                       # 8-node hexahedron
            corners.append(f[3 + int(f[2]):])
    ids = np.array(corners, dtype=int).reshape(-1, 8)
    return xyz[pos[ids], 1:]


def would_invert(msh: Path) -> int:
    """How many hexes of *msh* (MSH 2.2 ASCII) gmshToFoam's orientation
    test would turn inside out (:func:`foam_would_invert`), counted in
    chunks.  At zero the default conversion is safe.  Otherwise the mesh
    needs ``convert(..., keep_orientation=True)``, which is right only when
    every hex is right-handed (a positive worst scaled Jacobian)."""
    p = msh_hexes(msh)
    return sum(int(foam_would_invert(p[i:i + 200_000]).sum())
               for i in range(0, len(p), 200_000))


def check_mesh(case: Path, region: str | None = None) -> dict:
    """``checkMesh`` (of *region*): Mesh OK, cells, max non-orthogonality,
    skewness and aspect ratio."""
    out = (foam(f"checkMesh -region {region}", case, f"log.checkMesh.{region}") if region
           else foam("checkMesh", case, "log.checkMesh"))
    return {
        "mesh_ok": "Mesh OK." in out,
        "cells_foam": int(re.search(r"cells:\s+(\d+)", out).group(1)),
        "max_non_orthogonality": float(
            re.search(r"non-orthogonality Max: ([\d.e+-]+)", out).group(1)),
        "max_skewness": float(re.search(r"Max skewness = ([\d.e+-]+)", out).group(1)),
        "max_aspect_ratio": float(re.search(r"Max aspect ratio = ([\d.e+-]+)", out).group(1)),
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
            raise StudyError(f"{patch}: uniform value, expected a list",
                             code="openfoam_value_uniform", where={"label": patch},
                             hint="pass n=, the patch's face count (read_patch_faces)")
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
            raise StudyError(f"{rel.as_posix()}: unknown placeholder(s) "
                             + ", ".join(f"${n}" for n in dict.fromkeys(missing)),
                             code="case_placeholder_unknown",
                             where={"source": {"file": rel.as_posix()}},
                             value=list(dict.fromkeys(missing)))
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(rel.as_posix())
    return changed


def _format(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)
