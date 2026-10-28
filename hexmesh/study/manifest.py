"""
Study manifest and aligned export (decision 0025, items 4 and 5).

``<output>/study.csv``: one row per variant (hash, every parameter,
status, cells, quality, times, topology key, error).  ``study.json``: the
same rows, the study file, and versions (hexmesh commit, gmsh, Python).

``export``: for each topology key with meshed variants,
``<output>/aligned/<key>.npz`` with ``coords`` (variants × nodes × 3,
nodes in tag order), ``hexes`` (the shared connectivity, as node
indices), ``node_tags`` and ``variants`` (the hashes).  Each variant's
mesh is read back and its connectivity checked against the first.
"""

from __future__ import annotations

import csv
import json
import platform
import subprocess
from pathlib import Path

import numpy as np

from .definition import Study, StudyError, canonical
from .stages import variant_dir

COLUMNS = ["hash", "status", "cells", "cells_meshed", "min_sicn", "min_sj",
           "min_sj_fitting", "preflight_time", "mesh_time", "run_exit", "run_time", "run_log",
           "topology", "warnings", "error"]


def versions() -> dict:
    import gmsh
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "hexmesh"], cwd=root,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        commit = (commit + ("+local" if dirty else "")) or None
    except (OSError, subprocess.SubprocessError):
        commit = None
    return {"hexmesh": commit, "gmsh": gmsh.__version__, "python": platform.python_version()}


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in ("network", "traceback", "group_roles")}


def write_manifest(study: Study, rows: list[dict]) -> None:
    study.output.mkdir(parents=True, exist_ok=True)
    names = list(dict.fromkeys(k for r in rows for k in r["params"]))
    results = list(dict.fromkeys(k for r in rows for k in (r.get("result") or {})))
    with open(study.output / "study.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS[:2] + names + [f"result.{k}" for k in results] + COLUMNS[2:])
        for r in rows:
            vals = {k: r.get(k) for k in COLUMNS}
            vals["warnings"] = "; ".join(r.get("warnings") or [])
            res = r.get("result") or {}
            w.writerow([vals["hash"], vals["status"]]
                       + [canonical(r["params"].get(n)) for n in names]
                       + ["" if res.get(k) is None else res[k] for k in results]
                       + ["" if vals[k] is None else vals[k] for k in COLUMNS[2:]])
    (study.output / "study.json").write_text(json.dumps({
        "study": study.raw, "versions": versions(),
        "variants": [_public(r) for r in rows]}, indent=1, default=str))


def read_manifest(study: Study) -> dict:
    path = study.output / "study.json"
    if not path.exists():
        raise StudyError(f"no manifest at {path}: run the study first")
    return json.loads(path.read_text())


def read_mesh(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(node tags, coords in tag order, hex connectivity as node indices)."""
    import gmsh
    from .. import Session
    with Session("study-export"):
        gmsh.open(str(path))
        tags, x, _ = gmsh.model.mesh.getNodes()
        order = np.argsort(tags)
        tags, x = tags[order], x.reshape(-1, 3)[order]
        hexes = []
        for etype, _, nodes in zip(*gmsh.model.mesh.getElements(3)):
            if int(etype) != 5:
                raise StudyError(f"{path}: not all-hex (element type {int(etype)})")
            hexes.append(nodes.reshape(-1, 8))
        hexes = np.searchsorted(tags, np.concatenate(hexes))
    return tags, x, hexes


def export(study: Study) -> dict[str, Path]:
    meshed = {"meshed", "case_ready", "case_failed", "done", "run_failed"}
    rows = [r for r in read_manifest(study)["variants"] if r["status"] in meshed]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["topology"], []).append(r)
    out_dir = study.output / "aligned"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for key, members in groups.items():
        tags0 = hexes0 = None
        coords = []
        for r in members:
            tags, x, hexes = read_mesh(variant_dir(study, r["hash"]) / study.mesh_name)
            if tags0 is None:
                tags0, hexes0 = tags, hexes
            elif not (np.array_equal(tags, tags0) and np.array_equal(hexes, hexes0)):
                raise StudyError(f"topology key {key}: variant {r['hash']} has a different "
                                 f"connectivity from {members[0]['hash']}")
            coords.append(x)
        path = out_dir / f"{key}.npz"
        np.savez(path, coords=np.stack(coords), hexes=hexes0, node_tags=tags0,
                 variants=np.array([r["hash"] for r in members]))
        written[key] = path
    return written
