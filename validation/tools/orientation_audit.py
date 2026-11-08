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
Audit every validation case for gmshToFoam's silent inversions (task
0108): for each level in each case's ``results.json``, and the two side
meshes that are converted too, rebuild the mesh as its driver does, write
it as ``write_openfoam`` does, and count the hexes gmshToFoam v2406's
orientation test would turn inside out
(``hexmesh.study.openfoam.would_invert``; docs/integrations/openfoam.md).
A level stored with ``keep_orientation`` was converted without that test,
so only the others' counts reach a published result
(``flipped_in_result``).  No OpenFOAM run::

    python3 -m validation.tools.orientation_audit WORK   # from the repository root

Each distinct mesh is built once, smallest first, into *WORK*, and its
``.msh`` deleted as soon as it is counted.  The rows go to
``validation/tools/orientation_audit.json`` after every mesh, so a stopped
audit resumes where it left off.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation" / "tools" / "orientation_audit.json"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def driver(case: str):
    return _load(f"{case}_run", f"validation/{case}/run.py")


#: per case, a stored level -> (the driver's builder, its arguments), or
#: None for a level that gmshToFoam never sees
BUILDS = {
    "heated_pipe": lambda d, lv: (d.assembly, (lv["k"],)),
    "heated_rod": lambda d, lv: (d.assembly, (lv["series"], lv["k"])),
    "helical_pipe": lambda d, lv: (d.assembly, (lv["nang"],)),
    "layered_conduction": lambda d, lv: (d.assembly, (lv["k"],)),
    "mms": lambda d, lv: (lambda c, k: d.assembly(c, k)[0], (_mms_mesh(d, lv["case"]), lv["k"])),
    "poiseuille": lambda d, lv: (d.assembly, (lv["factor"],)),
    "rect_duct": lambda d, lv: (None if lv["mesh"] == "cartesian"      # blockMesh
                                else (d.assembly, (lv["ratio"], lv["k"], lv["mesh"]))),
    "square_bend": lambda d, lv: (d.assembly, (lv["k"], lv["l_up"])),
    "stenosis": lambda d, lv: (d.assembly, (lv["factor"],)),
    "stenosis_pulsatile": lambda d, lv: (d.sten.assembly, (lv["factor"],)),
    "turbulent_pipe": lambda d, lv: (d.assembly, (lv["case"], lv["k"])),
    "womersley": lambda d, lv: (d.assembly, (lv["factor"],)),
}


def _mms_mesh(d, case: str) -> str:
    """The first MMS case with *case*'s mesh: the diagnostic series
    (``tee_lsq``, ``duct_tap_rect_lim``, …) differ from it in schemes only."""
    return next(c for c, build in d.CASES.items() if build is d.CASES[case])


def side_meshes(drivers: dict, stored: dict) -> list[dict]:
    """The converted meshes that aren't levels: square_bend's inlet straight
    and poiseuille's non-orthogonality trend pipes."""
    inlet = stored["square_bend"]["extra"]["inlet"]["k"]
    rows = [{"case": "square_bend", "level": f"inlet_k{inlet}", "cells_stored": None,
             "kept_orientation": False,
             "build": (drivers["square_bend"].inlet_assembly, (inlet,))}]
    rows += [{"case": "poiseuille", "level": f"trend-{t['nang']}", "cells_stored": t["cells"],
              "kept_orientation": False,
              "build": (drivers["poiseuille"].trend_assembly, (t["nang"],))}
             for t in stored["poiseuille"]["extra"]["trend"]]
    return rows


def plan() -> list[dict]:
    cases = sorted(BUILDS)
    drivers = {c: driver(c) for c in cases}
    stored = {c: json.loads((ROOT / "validation" / c / "results.json").read_text(
        encoding="utf-8")) for c in cases}
    rows = []
    for c in cases:
        for lv in stored[c]["levels"]:
            rows.append({"case": c, "level": lv["name"], "cells_stored": lv.get("cells"),
                         "kept_orientation": bool(lv.get("keep_orientation")),
                         "build": BUILDS[c](drivers[c], lv)})
    return rows + side_meshes(drivers, stored)


def _key(row: dict) -> str:
    fn, args = row["build"]
    name = fn.__name__ if fn.__name__ != "<lambda>" else "assembly"
    return f"{row['case']}:{name}{tuple(args)!r}"


def audit(work: Path) -> list[dict]:
    from hexmesh import Session
    from hexmesh.study import openfoam as of
    from hexmesh.io.writers.openfoam_boundary import roles_path
    rows = plan()
    done = json.loads(OUT.read_text(encoding="utf-8"))["meshes"] if OUT.exists() else {}
    meshes: dict[str, tuple] = {}
    for r in rows:
        if r["build"] is not None:
            meshes.setdefault(_key(r), r["build"])
    sized = sorted(((fn(*args).cell_count(), key) for key, (fn, args) in meshes.items()
                    if key not in done), key=lambda x: x[0])
    for n, key in sized:
        fn, args = meshes[key]
        t0 = time.monotonic()
        msh = work / "audit.msh"
        asm = fn(*args)
        with Session("orientation-audit"):
            asm.write_openfoam(str(msh))
            sj = asm.check_quality("scaled_jacobian").worst
        flips = of.would_invert(msh)
        msh.unlink()
        roles_path(msh).unlink()                       # write_openfoam's role manifest
        done[key] = {"cells": n, "would_invert": flips, "min_scaled_jacobian": sj,
                     "seconds": round(time.monotonic() - t0, 1)}
        print(f"{key}: {n} cells, would invert {flips}, worst SJ {sj:.3g}", flush=True)
        _write(rows, done)
    return _write(rows, done)


def _write(rows: list[dict], done: dict) -> list[dict]:
    table = []
    for r in rows:
        m = done.get(_key(r)) if r["build"] is not None else None
        table.append({"case": r["case"], "level": r["level"], "cells_stored": r["cells_stored"],
                      **({"mesh": _key(r), "cells": m["cells"],
                          "would_invert": m["would_invert"],
                          "kept_orientation": r["kept_orientation"],
                          "flipped_in_result": m["would_invert"] if not r["kept_orientation"]
                          else 0,
                          "min_scaled_jacobian": m["min_scaled_jacobian"]} if m else
                         {"mesh": None if r["build"] is None else _key(r),
                          "note": "blockMesh: not converted by gmshToFoam"
                          if r["build"] is None else "not yet audited"})})
    OUT.write_text(json.dumps({"task": "0108", "gmshToFoam": "v2406 orientation test, "
                               "reimplemented (hexmesh.study.openfoam.foam_would_invert)",
                               "levels": table, "meshes": done}, indent=1) + "\n",
                   encoding="utf-8")
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("work", type=Path, help="scratch directory for one .msh at a time")
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    table = audit(args.work)
    bad = [r for r in table if r.get("flipped_in_result")]
    off = [r for r in table if r.get("cells") is not None and r["cells_stored"] is not None
           and r["cells"] != r["cells_stored"]]
    would = [r for r in table if r.get("would_invert")]
    print(f"{len(table)} levels; {len(would)} would invert, {len(bad)} of them converted "
          f"without -keepOrientation; {len(off)} with another cell count")
    return 1 if bad or off else 0


if __name__ == "__main__":
    sys.exit(main())
