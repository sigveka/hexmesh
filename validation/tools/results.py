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
Each validation case's stored results, ``validation/<case>/results.json``
(task 0093): every level's numbers at full precision, so a recheck or a
change of gate never needs an OpenFOAM rerun.

    results = _load("results", "validation/tools/results.py")   # validation/ is no package
    store = results.Store(HERE / "results.json", "heated_rod")
    row = results.run_level(store, "uniform-4", lambda: run_level(...), case_dir, keep_work)

The file::

    {"format": "hexmesh.validation.results", "version": 1, "case": "heated_rod",
     "levels": [{"name": "uniform-4", "precision": "full",
                 "environment": {"hexmesh": "…", "gmsh": "…", "openfoam": "v1912",
                                 "runner": "native", "python": "…", "date": "…"},
                 …the driver's values…}, …],
     "extra": {…case-wide values that belong to no level…}}

- ``precision`` is ``"full"`` (written by a driver) or ``"rounded from
  RESULTS.md"`` (filled from the tables, task 0093 step 4).  A driver
  reuses full levels and reruns rounded ones.
- No fields, nothing per cell: small profiles only.  20 MB per case at
  most (:data:`MAX_BYTES`; the user, 2026-11-03: 1 MB was too tight for
  the pulsatile stenosis's sampled profiles, 4.5 MB).
- Written deterministically: sorted keys, ``indent=1``, a trailing
  newline, UTF-8, ``\\n`` line endings (decision 0039).
- ``validation/results.schema.json`` describes it.
- A hexmesh level records its section counts (:func:`counts`), which
  ``hexmesh.agent``'s calibration reads (task 0098).
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import shutil
from pathlib import Path
from typing import Callable

FORMAT = "hexmesh.validation.results"
VERSION = 1
FULL = "full"
ROUNDED = "rounded from RESULTS.md"
MAX_BYTES = 20_000_000


def add_arguments(ap: argparse.ArgumentParser, here: Path) -> None:
    """``--json`` (default: the case's committed ``results.json``) and
    ``--keep-work``."""
    ap.add_argument("--json", type=Path, default=here / "results.json",
                    help="results file; levels already in it are reused "
                         "(default: the case's results.json)")
    ap.add_argument("--keep-work", action="store_true",
                    help="keep each level's case directory (deleted once its results are stored)")


def environment() -> dict:
    """hexmesh commit, gmsh, Python, the OpenFOAM version and runner, and
    today's date."""
    from hexmesh.study import openfoam as of
    from hexmesh.study.manifest import versions
    return {**versions(), "openfoam": of.openfoam_version(), "runner": of.runner(),
            "date": datetime.date.today().isoformat()}


def _finite(value):
    """NaN and ±inf are not JSON: stored as strings.  Keys become strings
    first, so they sort as they will when read back."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if hasattr(value, "tolist"):                     # numpy scalars and arrays
        return _finite(value.tolist())
    return value


def dumps(data: dict) -> str:
    return json.dumps(_finite(data), sort_keys=True, indent=1, ensure_ascii=False,
                      allow_nan=False) + "\n"


def write(path: Path, data: dict) -> None:
    """*data* with ``format`` and ``version``, deterministically; refuses
    more than :data:`MAX_BYTES`."""
    text = dumps({**data, "format": FORMAT, "version": VERSION})
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"{path}: {len(text.encode('utf-8'))} bytes, over the "
                         f"{MAX_BYTES}-byte cap (task 0093): store less")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    tmp.replace(path)


def load(path: Path) -> dict | None:
    if not Path(path).exists():
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path}: not a {FORMAT} file (format={data.get('format')!r})")
    if data.get("version") != VERSION:
        raise ValueError(f"{path}: unsupported version {data.get('version')!r}")
    return data


class Store:
    """One case's ``results.json``: levels by name, written after every
    level (fine levels take hours)."""

    def __init__(self, path: Path, case: str):
        self.path = Path(path)
        self.data = load(self.path) or {"case": case, "levels": [], "extra": {}}
        if self.data["case"] != case:
            raise ValueError(f"{path}: results of {self.data['case']!r}, not {case!r}")
        self.data.setdefault("extra", {})

    def level(self, name: str) -> dict | None:
        return next((lv for lv in self.data["levels"] if lv["name"] == name), None)

    def levels(self) -> list[dict]:
        return list(self.data["levels"])

    def put(self, name: str, values: dict, *, precision: str = FULL,
            env: dict | None = None) -> dict:
        """Store (or replace) level *name* and write the file."""
        row = {**_finite(values), "name": name, "precision": precision,
               "environment": env if env is not None else environment()}
        old = [i for i, lv in enumerate(self.data["levels"]) if lv["name"] == name]
        if old:
            self.data["levels"][old[0]] = row
        else:
            self.data["levels"].append(row)
        self.write()
        return row

    def put_extra(self, key: str, value) -> None:
        self.data["extra"][key] = _finite(value)
        self.write()

    def write(self) -> None:
        write(self.path, self.data)


COUNTS = ("nang", "nrad", "nang_w", "nang_h")


def counts(asm) -> dict:
    """The inlet section's counts of *asm* (an ``Assembly``), for a level
    of ``results.json``: ``nang``, the core's ``nrad`` (0 on an H core),
    ``nang_w`` and ``nang_h`` (None where the section has none; task 0098)."""
    spec = asm.to_dict()["inlet"]["spec"]
    return {"nang": spec["nang"], "nrad": spec["core"]["nrad"],
            "nang_w": spec["nang_w"], "nang_h": spec["nang_h"]}


def run_level(store: Store, name: str, run: Callable[[], dict], case_dir: Path | None,
              keep_work: bool = False) -> dict:
    """Level *name* from *store* if it holds it at full precision, else
    ``run()``, stored.  The level's *case_dir* is then deleted unless
    *keep_work*; a failed level keeps it and says where it is."""
    got = store.level(name)
    if got is not None and got["precision"] == FULL:
        print(f"[{name}] reused from {store.path}", flush=True)
        return got
    try:
        values = run()
    except BaseException:
        if case_dir is not None and Path(case_dir).exists():
            print(f"[{name}] failed; its case is kept in {case_dir}", flush=True)
        raise
    row = store.put(name, values)
    if case_dir is not None and not keep_work:
        remove_work(case_dir)
    return row


def remove_work(case_dir: Path) -> None:
    """Delete one level's case directory, and its parent ``work/`` once
    empty."""
    case_dir = Path(case_dir)
    if case_dir.exists():
        shutil.rmtree(case_dir)
    parent = case_dir.parent
    if parent.name == "work" and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()


# --- recheck rows (validation/tools/recheck.py) ------------------------------

def row(quantity: str, *, rich: dict | None = None, gate: str | None = None,
        ok: bool | None = None, value: str = "", note: str = "") -> dict:
    """One line of a case's recheck: a Richardson series (*rich*, from
    ``convergence.richardson``) and/or a gate (*gate* text, *ok*), with
    the gated *value* as displayed."""
    out = {"quantity": quantity, "gate": gate, "verdict": None if ok is None else
           ("pass" if ok else "fail"), "value": value, "note": note,
           "status": None, "order": None, "extrapolated": None}
    if rich is not None:
        out.update(status=rich["status"], order=rich["order"], extrapolated=rich["extrapolated"])
    return out


def series(data: dict, **match) -> list[dict]:
    """The levels whose fields equal *match*, in stored order."""
    return [lv for lv in data["levels"] if all(lv.get(k) == v for k, v in match.items())]
