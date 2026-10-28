"""
Study stages (decision 0025, task 0042): preflight and mesh.

**preflight** builds every variant in this process, without GMSH:
``validate()`` (with ``max_cells_variant``), ``cell_count()``, the
topology key, and the total budget.  Failures name the variant, its
parameters and the error (whose text names the fitting).

**mesh** runs one subprocess per variant (one GMSH session each), at most
``jobs`` at once.  The worker rebuilds the variant from its
``network.json`` and writes the mesh and ``result.json``.  A variant whose
mesh and result exist, and whose ``network.json`` is unchanged, is
skipped.  A crash is recorded in the variant's row, not raised.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .definition import Study, StudyError, canonical, variant_hash
from .sampling import variants

STATUS = ("checked", "preflight_failed", "meshed", "mesh_failed")


# --- topology key ------------------------------------------------------------

def _spec_key(spec) -> list:
    """A spec's connectivity: its port signature without the grading floats
    (``mprg``, ``mbmp``), which move nodes but don't renumber them."""
    from ..assembly.signature import signature
    sig = signature(spec)
    return [sig.n_outer, sig.nang_w, sig.nang_h,
            [[layer.name, layer.kind, layer.nrad] for layer in sig.layers]]


def _counts(fitting) -> dict:
    """A fitting's integer-typed fields (``n_layers``, ``n_cuts``, a tee's
    ``n_run`` …), as resolved, and its stack changes' cells and specs."""
    out = {}
    if dataclasses.is_dataclass(fitting):
        for f in dataclasses.fields(fitting):
            kind = str(f.type)
            if "int" in kind and "float" not in kind:
                out[f.name] = getattr(fitting, f.name)
    for i, spec in getattr(fitting, "stack_changes", None) or ():
        out.setdefault("stack_changes", []).append([int(i), _spec_key(spec)])
    return out


def topology_key(asm, length: int = 12) -> str:
    """Hash over every interface's connectivity and every fitting's type,
    ports and counts, in creation order.  Variants with equal keys are
    node-aligned: the same node tags and hex connectivity (decision 0025,
    item 4)."""
    data = {
        "interfaces": [_spec_key(i.spec) for i in asm.interfaces],
        "fittings": [[type(e.fitting).__name__, e.kind, [p.index for p in e.ports],
                      _counts(e.fitting)] for e in asm.edges],
    }
    text = json.dumps(canonical(data), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:length]


# --- preflight ---------------------------------------------------------------

def preflight(study: Study) -> list[dict]:
    """One row per variant: ``hash``, ``params``, ``status`` ("checked" or
    "preflight_failed"), ``cells``, ``topology``, ``warnings``, ``error``,
    ``preflight_time``, and ``network`` (the variant's ``to_dict``)."""
    from ..assembly import AssemblyError
    params_list = variants(study)
    names = set().union(*(p.keys() for p in params_list))
    study.check_placeholders(names)
    build = study.builder()
    rows, seen = [], {}
    for params in params_list:
        h = variant_hash(params)
        if h in seen:
            raise StudyError(f"variants {seen[h]} and {len(rows)} have the same "
                             f"parameters {params}")
        seen[h] = len(rows)
        row = {"hash": h, "params": params, "status": "checked", "cells": None,
               "topology": None, "warnings": [], "error": None, "network": None}
        t0 = time.perf_counter()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)    # recorded below
                asm = build(dict(params))
                asm.validate(max_cells=study.budget.get("max_cells_variant"))
            row["cells"] = asm.cell_count()
            row["topology"] = topology_key(asm)
            row["warnings"] = list(getattr(asm, "warnings", []))
            row["network"] = asm.to_dict()
        except (AssemblyError, StudyError, ValueError, TypeError, KeyError,
                NotImplementedError) as e:
            row["status"] = "preflight_failed"
            row["error"] = f"{type(e).__name__}: {e}"
        row["preflight_time"] = time.perf_counter() - t0
        rows.append(row)
    total = study.budget.get("max_cells_total")
    cells = sum(r["cells"] or 0 for r in rows)
    if total is not None and cells > total:
        raise StudyError(f"the study has {cells} cells, over max_cells_total {total}")
    return rows


def failure_table(rows: list[dict]) -> str:
    failed = [r for r in rows if r["status"] == "preflight_failed"]
    if not failed:
        return ""
    lines = ["| variant | parameters | error |", "|---|---|---|"]
    lines += [f"| {r['hash']} | {json.dumps(canonical(r['params']), sort_keys=True)} "
              f"| {r['error']} |" for r in failed]
    return "\n".join(lines)


# --- mesh --------------------------------------------------------------------

def variant_dir(study: Study, h: str) -> Path:
    return study.output / "variants" / h


def _network_text(network: dict) -> str:
    return json.dumps(network, indent=1, sort_keys=True)


def up_to_date(study: Study, row: dict) -> bool:
    d = variant_dir(study, row["hash"])
    try:
        result = json.loads((d / "result.json").read_text())
        same = (d / "network.json").read_text() == _network_text(row["network"])
    except (OSError, json.JSONDecodeError):
        return False
    return same and result.get("status") == "meshed" and (d / study.mesh_name).exists()


def mesh(study: Study, rows: list[dict], jobs: int | None = None) -> list[str]:
    """Mesh every "checked" row that isn't up to date; fills each row's
    mesh fields from its ``result.json``.  Returns the hashes meshed."""
    jobs = jobs or study.jobs
    todo = [r for r in rows if r["status"] == "checked" and not up_to_date(study, r)]
    for r in todo:
        d = variant_dir(study, r["hash"])
        d.mkdir(parents=True, exist_ok=True)
        (d / "result.json").unlink(missing_ok=True)
        (d / "network.json").write_text(_network_text(r["network"]))
        (d / "params.json").write_text(json.dumps(canonical(r["params"]), indent=1))

    def run(row):
        d = variant_dir(study, row["hash"])
        cmd = [sys.executable, "-m", "hexmesh.study", "_mesh", str(d), study.format,
               "1" if study.walls_by_fitting else "0"]
        env = dict(os.environ)
        root = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if not (d / "result.json").exists():
            (d / "result.json").write_text(json.dumps({
                "status": "mesh_failed",
                "error": f"worker exited {proc.returncode}: "
                         + (proc.stderr.strip().splitlines() or ["(no output)"])[-1]}))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(run, todo))
    load_results(study, rows)
    return [r["hash"] for r in todo]


def load_results(study: Study, rows: list[dict]) -> None:
    """Fill each "checked" row from its ``result.json``, if that result is
    for the variant's current ``network.json``."""
    for r in rows:
        if r["status"] != "checked":
            continue
        d = variant_dir(study, r["hash"])
        try:
            if (d / "network.json").read_text() != _network_text(r["network"]):
                continue
            result = json.loads((d / "result.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue                       # not meshed yet
        r.update({k: v for k, v in result.items() if k not in ("status", "traceback")})
        r["status"] = result["status"]


def mesh_worker(d: Path, fmt: str, walls_by_fitting: bool) -> int:
    """Run in the subprocess: mesh the variant in *d*, write result.json."""
    from .. import Assembly, Session
    out = {"status": "mesh_failed"}
    t0 = time.perf_counter()
    try:
        import gmsh
        with Session(f"study-{d.name}"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                asm = Assembly.load(d / "network.json")
            out["cells"] = asm.cell_count()
            path = d / "mesh.msh"
            if fmt == "openfoam":
                asm.write_openfoam(str(path), walls_by_fitting=walls_by_fitting)
            else:
                asm.write(str(path), walls_by_fitting=walls_by_fitting)
            types, tags, _ = gmsh.model.mesh.getElements(3)
            out["cells_meshed"] = int(sum(len(t) for t in tags))
            out["all_hex"] = all(int(t) == 5 for t in types)
            out["min_sicn"] = asm.check_quality().min_quality
            sj = asm.check_quality("scaled_jacobian", by="fitting")
            worst = min(sj.regions, key=lambda r: r.min_quality)
            out["min_sj"], out["min_sj_fitting"] = worst.min_quality, worst.name
            out["group_roles"] = asm.group_roles()
        out["status"] = "meshed"
    except Exception as e:                                   # recorded, not raised
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc()[-4000:]
    out["mesh_time"] = time.perf_counter() - t0
    (d / "result.json").write_text(json.dumps(out, indent=1))
    return 0 if out["status"] == "meshed" else 1
