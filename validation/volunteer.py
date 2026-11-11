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
Volunteer runs (decision 0044; task 0119): heavy validation levels that
someone with cluster time runs, sending back one small file that is
checked mechanically.  From the repository root::

    python3 -m validation.volunteer list
    python3 -m validation.volunteer prepare <case> <level> --dir run/
    sbatch run/job.sh        # or: bash run/job.sh   (resumable)
    python3 -m validation.volunteer collect run/
    python3 -m validation.volunteer check <case>-<level>.contrib.json [--merge]
    python3 -m validation.volunteer docs     # regenerate validation/VOLUNTEERS.md

A case offers levels with a card, ``validation/<case>/volunteer.json``:
its requirements, each labelled measured or estimated.  Its driver,
``validation/<case>/run.py``, exposes the hooks ``prepare(level, d,
mesh_only)``, ``run(level, d, n_proc)``, ``collect(level, d)`` and
``recompute(values)``; this tool adds the runner, the mesh hash, the job
script, the memory and wall-time records, the contribution file and the
check.

**The mesh hash** is SHA-256 over a canonical form of the ``.msh``
(MSH 2.2 ASCII, as ``write_openfoam`` writes it): its physical names, its
node tags with coordinates rounded to 1e-12, and its elements.  Not the
bytes: the ``$Comments`` block names the hexmesh and gmsh versions, a
Windows file has CRLF line endings, and gmsh 4.15.2 writes a few
coordinates one unit in the last place away from 4.12.1's (task 0119).

**check** treats the contribution as data: it reads JSON, never runs
anything from it.  Accepted only if the file is valid against
``validation/contrib.schema.json``, the mesh hash matches a local
``prepare --mesh-only``, every number the driver's ``recompute`` derives
matches, and, where ``results.json`` already holds the level, its gated
quantity agrees within the card's tolerance.  A level that misses a gate
is accepted and reported as a miss.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
SCHEMA = VALIDATION / "contrib.schema.json"
DOC = VALIDATION / "VOLUNTEERS.md"
CARD_FORMAT = "hexmesh.validation.volunteer-card"
CONTRIB_FORMAT = "hexmesh.validation.contribution"
HASH_METHOD = ("sha256 over the MSH 2.2 physical names, node tags with coordinates rounded "
               "to 1e-12, and elements")
STATE = "volunteer-run.json"            # a run directory's record
MAX_CONTRIB_BYTES = 1_000_000
LOG_LINES = 200
BASES = ("measured", "estimated")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def results_module():
    return _load("stored", VALIDATION / "tools" / "results.py")


def driver(case: str):
    return _load(f"{case}_run", VALIDATION / case / "run.py")


# --- cards --------------------------------------------------------------------

def cards() -> dict[str, dict]:
    """Every case's card, by case name."""
    out = {}
    for path in sorted(VALIDATION.glob("*/volunteer.json")):
        card = json.loads(path.read_text(encoding="utf-8"))
        if card.get("format") != CARD_FORMAT:
            raise ValueError(f"{path}: not a {CARD_FORMAT} file")
        out[path.parent.name] = card
    return out


def card(case: str) -> dict:
    all_ = cards()
    if case not in all_:
        raise SystemExit(f"no volunteer card for {case!r}; cases: {', '.join(all_) or 'none'}")
    return all_[case]


def gates(case: str) -> list[dict]:
    """The case's gates, quoted from its ``case.json``."""
    meta = json.loads((VALIDATION / case / "case.json").read_text(encoding="utf-8"))
    return meta["gates"]


def _value(req: dict) -> str:
    v = req["value"]
    num = f"{v:,}" if isinstance(v, int) else f"{v:g}" if isinstance(v, float) else f"{v}"
    return f"{num} {req['unit']}".strip()


def requirements_table(level: dict) -> list[str]:
    lines = ["| requirement | value | basis | where it comes from |", "|---|---|---|---|"]
    for name, req in level["requirements"].items():
        lines.append(f"| {req['label']} | {_value(req)} | {req['basis']} | {req['how']} |")
    return lines


# --- runners ------------------------------------------------------------------

def pick_runner(c: dict, given: str | None) -> str:
    """*given*, else ``HEXMESH_OPENFOAM``, else the first that is there:
    OpenFOAM on PATH, the native bashrc, Apptainer with the card's image,
    Docker with it."""
    from hexmesh.study import openfoam as of
    if given:
        return given
    if os.environ.get("HEXMESH_OPENFOAM"):
        return os.environ["HEXMESH_OPENFOAM"]
    if shutil.which("gmshToFoam"):
        return "path"
    if of.OPENFOAM_RC.exists():
        return "native"
    image = c["openfoam"]["image"]
    if shutil.which("apptainer") or shutil.which("singularity"):
        return f"apptainer:docker://{image}"
    if shutil.which("docker"):
        return f"docker:{image}"
    raise SystemExit("no OpenFOAM found: load it (module load …), set HEXMESH_OPENFOAM_RC to "
                     "its bashrc, or install Apptainer or Docker; see validation/VOLUNTEERS.md")


def use_runner(spec: str, required: str, allow_version: bool) -> str:
    from hexmesh.study import openfoam as of
    of.set_runner(spec)
    return of.require_version(required, allow_other=allow_version)


# --- the mesh hash --------------------------------------------------------------

def mesh_hash(msh: Path) -> str:
    """SHA-256 over *msh*'s canonical form (:data:`HASH_METHOD`): the
    whitespace-separated tokens of ``$PhysicalNames`` and ``$Elements``,
    and ``$Nodes`` as little-endian int64 tags and float64 coordinates
    rounded to 1e-12 (``-0.0`` as ``0.0``)."""
    import numpy as np
    text = Path(msh).read_text(encoding="utf-8")
    fmt = re.search(r"\$MeshFormat\s+(\S+)\s+(\d)", text)
    if not fmt or fmt[1] != "2.2" or fmt[2] != "0":
        raise ValueError(f"{msh}: not an MSH 2.2 ASCII file")
    sec = {m[1]: m[2] for m in re.finditer(r"\$(\w+)\s*\n(.*?)\$End\1", text, re.S)}
    h = hashlib.sha256()
    for name in ("PhysicalNames", "Elements"):
        h.update(f"{name}\n{' '.join(sec.get(name, '').split())}\n".encode())
    nodes = np.array(sec["Nodes"].split()[1:], dtype=float).reshape(-1, 4)
    h.update(b"Nodes\n" + nodes[:, 0].astype("<i8").tobytes()
             + (np.round(nodes[:, 1:], 12) + 0.0).astype("<f8").tobytes())
    return h.hexdigest()


def _drop_mesh(msh: Path) -> None:
    msh = Path(msh)
    msh.unlink(missing_ok=True)
    msh.with_suffix(".roles.json").unlink(missing_ok=True)


def local_mesh_hash(case: str, level: str) -> str:
    """The hash of *level*'s mesh made here (``prepare --mesh-only``)."""
    with tempfile.TemporaryDirectory(prefix="hexmesh-volunteer-") as tmp:
        msh = driver(case).prepare(level, Path(tmp), mesh_only=True)["msh"]
        return mesh_hash(msh)


# --- memory --------------------------------------------------------------------

class PeakMemory:
    """The run's peak resident memory, sampled every *every* seconds: the
    sum over this process's descendants (Linux ``/proc``), plus the
    memory of this process's Docker containers (``docker stats``), whose
    processes aren't descendants."""

    def __init__(self, every: float = 2.0):
        self.every, self.peak, self._stop = every, 0, threading.Event()
        self.how = ("sum of the resident memory of the run's processes (/proc) and of "
                    f"its Docker containers (docker stats), sampled every {every:g} s")
        self.available = Path("/proc/self/status").exists()

    def __enter__(self):
        if self.available:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self.available:
            self._thread.join(timeout=10)

    def _loop(self):
        while not self._stop.wait(self.every):
            try:
                self.peak = max(self.peak, self.sample())
            except Exception:                       # a vanished process; sample again
                pass

    @staticmethod
    def sample() -> int:
        parent = {}
        for d in Path("/proc").iterdir():
            if d.name.isdigit():
                try:
                    parent[int(d.name)] = int((d / "stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()[1])
                except (OSError, IndexError, ValueError):
                    pass
        mine, grew = {os.getpid()}, True
        while grew:
            add = {p for p, pp in parent.items() if pp in mine and p not in mine}
            grew = bool(add)
            mine |= add
        total = 0
        for p in mine - {os.getpid()}:
            try:
                m = re.search(r"^VmRSS:\s+(\d+) kB", Path(f"/proc/{p}/status").read_text(encoding="utf-8"), re.M)
                total += int(m[1]) * 1024 if m else 0
            except OSError:
                pass
        return total + PeakMemory._docker()

    @staticmethod
    def _docker() -> int:
        if not shutil.which("docker"):
            return 0
        out = subprocess.run(["docker", "stats", "--no-stream", "--format",
                              "{{.Name}} {{.MemUsage}}"], capture_output=True, text=True,
                             timeout=30).stdout
        units = {"B": 1, "KiB": 2 ** 10, "MiB": 2 ** 20, "GiB": 2 ** 30, "kB": 1e3, "MB": 1e6,
                 "GB": 1e9}
        total = 0
        for line in out.splitlines():
            name, _, use = line.partition(" ")
            m = re.match(r"([\d.]+)\s*([A-Za-z]+)", use)
            if name.startswith(f"hexmesh-{os.getpid()}-") and m and m[2] in units:
                total += int(float(m[1]) * units[m[2]])
        return total


# --- prepare ------------------------------------------------------------------------

def _hours(h: float) -> str:
    s = int(math.ceil(h * 3600))
    return f"{s // 3600}:{s % 3600 // 60:02d}:00"


def job_script(case: str, level: str, d: Path, req: dict | None, n_proc: int) -> str:
    """``job.sh``: Slurm directives from the card (comments to bash), then
    the run with this Python."""
    lines = ["#!/bin/bash",
             f"# hexmesh volunteer run: {case}, level {level}.",
             "# Submit with  sbatch job.sh  or run with  bash job.sh .  It resumes from the",
             "# last saved step: after a stop (a time limit, a failed node), run it again.",
             f"#SBATCH --job-name=hexmesh-{case}-{level}",
             f"#SBATCH --ntasks={n_proc}",
             "#SBATCH --nodes=1"]
    if req:
        lines.append(f"#SBATCH --time={_hours(1.5 * req['wall_time']['value'])}"
                     "            # 1.5 x the stated wall time")
        lines.append(f"#SBATCH --mem={math.ceil(1.5 * req['peak_memory']['value'])}G"
                     "                 # 1.5 x the stated peak memory")
    lines += [f"#SBATCH --output={d}/slurm-%j.out", "set -e",
              f"cd {shlex.quote(str(ROOT))}",
              f"exec {shlex.quote(sys.executable)} -m validation.volunteer run "
              f"{shlex.quote(str(d))}", ""]
    return "\n".join(lines)


def cmd_prepare(args) -> int:
    from hexmesh.study.manifest import versions
    c = card(args.case)
    offered = c["levels"].get(args.level)
    if offered is None:
        print(f"note: {args.case} doesn't offer {args.level!r} (offered: "
              f"{', '.join(c['levels'])}); it has no stated requirements", file=sys.stderr)
    d = args.dir.resolve()
    drv = driver(args.case)
    if args.mesh_only:
        out = drv.prepare(args.level, d, mesh_only=True)
        h = mesh_hash(out["msh"])
        _drop_mesh(out["msh"])
        print(h)
        return 0
    if (d / STATE).exists():
        raise SystemExit(f"{d} is already prepared; run {d / 'job.sh'}, or use a new --dir")
    req = offered["requirements"] if offered else None
    if req:
        free = shutil.disk_usage(d if d.exists() else d.parent).free / 1e9
        if free < req["peak_disk"]["value"]:
            print(f"warning: {free:.1f} GB free, the run needs about "
                  f"{req['peak_disk']['value']:g} GB", file=sys.stderr)
    runner = pick_runner(c, args.runner)
    version = use_runner(runner, c["openfoam"]["version"], args.allow_version)
    print(f"OpenFOAM {version} ({runner})", flush=True)
    out = drv.prepare(args.level, d)
    h = mesh_hash(out["msh"])
    _drop_mesh(out["msh"])
    n_proc = args.np or (offered["requirements"]["cores"]["value"] if offered else 1)
    state = {"case": args.case, "level": args.level, "runner": runner, "openfoam": version,
             "allow_version": args.allow_version, "n_proc": n_proc,
             "mesh": {"sha256": h, "method": HASH_METHOD, "check": out["check"]},
             "prepared": {**versions(), "date": datetime.date.today().isoformat()},
             "wall_s": 0.0, "peak_memory_bytes": None, "runs": 0}
    (d / STATE).write_text(json.dumps(state, indent=1), encoding="utf-8")
    (d / "job.sh").write_text(job_script(args.case, args.level, d, req, n_proc), encoding="utf-8")
    (d / "job.sh").chmod(0o755)
    print(f"prepared {args.case} {args.level} in {d}\nmesh sha256 {h}\n"
          f"next: sbatch {d / 'job.sh'}   (or: bash {d / 'job.sh'})")
    return 0


# --- run -------------------------------------------------------------------------------

def _state(d: Path) -> dict:
    path = Path(d) / STATE
    if not path.exists():
        raise SystemExit(f"{d} isn't a prepared run directory (no {STATE}): run prepare first")
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_run(args) -> int:
    d = args.dir.resolve()
    state = _state(d)
    c = card(state["case"])
    use_runner(state["runner"], c["openfoam"]["version"], state["allow_version"])
    n_proc = args.np or int(os.environ.get("SLURM_NTASKS", 0)) or state["n_proc"]
    state["n_proc_used"] = sorted(set(state.get("n_proc_used", [])) | {n_proc})
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(128 + s))   # Slurm's time limit
    t0 = time.monotonic()
    meter = PeakMemory()
    try:
        with meter:
            driver(state["case"]).run(state["level"], d, n_proc)
    finally:
        state["wall_s"] += time.monotonic() - t0
        state["runs"] += 1
        if meter.available:
            state["peak_memory_bytes"] = max(state["peak_memory_bytes"] or 0, meter.peak)
            state["peak_memory_how"] = meter.how
        (d / STATE).write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(f"finished; next: python3 -m validation.volunteer collect {d}")
    return 0


# --- collect --------------------------------------------------------------------------

def _log_tail(d: Path) -> list[str]:
    logs = sorted(Path(d).glob("case/log.simpleFoam.all")) or sorted(Path(d).glob("case/log.*"))
    if not logs:
        return []
    return logs[0].read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:]


def cmd_collect(args) -> int:
    stored = results_module()
    d = args.dir.resolve()
    state = _state(d)
    c = card(state["case"])
    use_runner(state["runner"], c["openfoam"]["version"], state["allow_version"])
    got = driver(state["case"]).collect(state["level"], d)
    contrib = {
        "format": CONTRIB_FORMAT, "version": 1, "case": state["case"], "level": state["level"],
        "results": stored._finite(got["values"]), "extra": stored._finite(got["extra"]),
        "environment": stored.environment(),
        "mesh": state["mesh"],
        "run": {"cores": state.get("n_proc_used", [state["n_proc"]])[-1],
                "runs": state["runs"], "wall_s": state["wall_s"],
                "peak_memory_gb": None if state["peak_memory_bytes"] is None
                else state["peak_memory_bytes"] / 1e9,
                "peak_memory_how": state.get("peak_memory_how", "not measured"),
                "allow_version": state["allow_version"]},
        "log_tail": _log_tail(d)}
    if args.name or args.machine:
        contrib["contributor"] = {k: v for k, v in (("name", args.name),
                                                    ("machine", args.machine)) if v}
    out = (args.out or Path.cwd()) / f"{state['case']}-{state['level']}.contrib.json"
    text = stored.dumps(contrib)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text.encode('utf-8')) / 1e3:.0f} kB): send this file back")
    if args.delete or (sys.stdin.isatty() and
                       input(f"delete the run directory {d}? [y/N] ").strip().lower() == "y"):
        shutil.rmtree(d)
        print(f"deleted {d}")
    else:
        print(f"kept {d}; delete it when the file is accepted")
    return 0


# --- check ---------------------------------------------------------------------------

def _close(a, b, rel: float = 1e-9) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
                and all(_close(x, y, rel) for x, y in zip(a, b)))
    if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) \
            or not isinstance(b, (int, float)):
        return a == b
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-300)


def check(path: Path, *, results: Path | None = None, merge: bool = False,
          hasher=local_mesh_hash) -> tuple[bool, list[str]]:
    """Check the contribution at *path* (decision 0044).  Returns
    (accepted, report lines); with *merge*, an accepted level is stored in
    *results* (default: the case's ``results.json``).  *hasher(case,
    level)* gives the local mesh hash."""
    import jsonschema
    stored = results_module()
    report, problems = [], []
    raw = Path(path).read_bytes()
    if len(raw) > MAX_CONTRIB_BYTES:
        return False, [f"rejected: {len(raw)} bytes, over the {MAX_CONTRIB_BYTES}-byte limit"]
    try:
        contrib = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return False, [f"rejected: not UTF-8 JSON ({e})"]
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(contrib),
                    key=lambda e: list(e.absolute_path))
    if errors:
        return False, ["rejected: the file doesn't match validation/contrib.schema.json:"] + [
            f"  {'/'.join(map(str, e.absolute_path)) or '(top level)'}: {e.message}"
            for e in errors]
    case, level, values = contrib["case"], contrib["level"], contrib["results"]
    if case not in cards():
        return False, [f"rejected: no volunteer card for case {case!r}"]
    c = cards()[case]
    drv = driver(case)
    report.append(f"{case} {level}: OpenFOAM {contrib['environment']['openfoam']} "
                  f"({contrib['environment']['runner']}), hexmesh "
                  f"{contrib['environment']['hexmesh']}, gmsh {contrib['environment']['gmsh']}")
    if contrib["environment"]["openfoam"].lstrip("vV") != c["openfoam"]["version"].lstrip("vV"):
        report.append(f"note: OpenFOAM {contrib['environment']['openfoam']}, not the card's "
                      f"{c['openfoam']['version']} (run with --allow-version)")
    if contrib["mesh"]["method"] != HASH_METHOD:
        problems.append(f"mesh hash method {contrib['mesh']['method']!r}, not {HASH_METHOD!r}")
    try:
        here = hasher(case, level)
    except ValueError as e:
        return False, report + [f"rejected: {e}"]
    if contrib["mesh"]["sha256"] != here:
        problems.append(f"mesh hash {contrib['mesh']['sha256'][:16]}… differs from the mesh "
                        f"made here, {here[:16]}…: not the same mesh (check the hexmesh tag "
                        "and gmsh version)")
    else:
        report.append(f"mesh hash matches ({here[:16]}…)")
    for key, want in drv.recompute(values).items():
        if key not in values:
            problems.append(f"results: {key} is missing")
        elif not _close(values[key], want):
            problems.append(f"results: {key} is {values[key]!r}, but the level's own numbers "
                            f"give {want!r}")
    rec = c.get("reproduce")
    store = stored.Store(results or VALIDATION / case / "results.json", case)
    old = store.level(level)
    if rec and old is not None and old["precision"] == stored.FULL:
        q, tol = rec["quantity"], rec["rel_tol"]
        dev = values[q] / old[q] - 1
        line = f"{q} {values[q]!r} vs the stored level's {old[q]!r}: {dev:+.2e} (tolerance {tol:g})"
        (report if abs(dev) <= tol else problems).append(
            line if abs(dev) <= tol else f"{line}: doesn't reproduce the stored level")
    if problems:
        return False, report + ["rejected:"] + [f"  {p}" for p in problems]
    data = json.loads(json.dumps(store.data))
    data["levels"] = [lv for lv in data["levels"] if lv["name"] != level] + [
        {**values, "name": level, "precision": stored.FULL}]
    rows = drv.recheck(data)
    report.append("gates with this level:")
    report += [f"  {r['quantity']}: {r['value'] or r['status']} "
               f"({r['verdict'] or 'reported'})" for r in rows]
    report.append("accepted")
    if merge:
        env = {**contrib["environment"], "contributed": {
            **contrib.get("contributor", {}), "cores": contrib["run"]["cores"],
            "wall_s": contrib["run"]["wall_s"], "peak_memory_gb": contrib["run"]["peak_memory_gb"],
            "mesh_sha256": contrib["mesh"]["sha256"]}}
        store.put(level, values, env=env)
        for key, val in contrib.get("extra", {}).items():
            merged = store.data["extra"].get(key)
            store.put_extra(key, {**merged, **val} if isinstance(merged, dict)
                            and isinstance(val, dict) else val)
        report.append(f"merged into {store.path}")
    return True, report


def cmd_check(args) -> int:
    ok, lines = check(args.file, results=args.results, merge=args.merge)
    print("\n".join(lines))
    return 0 if ok else 1


# --- list and VOLUNTEERS.md --------------------------------------------------------------

def cmd_list(args) -> int:
    for case, c in cards().items():
        print(f"{case}: {c['title']}")
        for name, lv in c["levels"].items():
            print(f"\n  level {name}: {lv['title']}")
            print("\n".join("  " + line for line in requirements_table(lv)))
        print()
    return 0


def render() -> str:
    """``validation/VOLUNTEERS.md``, from the cards."""
    out = ["# Volunteer runs", "",
           "<!-- generated by `python3 -m validation.volunteer docs`: edit the cards "
           "(validation/<case>/volunteer.json), not this file -->", "",
           "Some validation cases need more computer than we have.  If you have cluster "
           "time, you can run one of them with five commands, knowing beforehand what it "
           "costs, and send back one small file.  We check that file mechanically: the mesh "
           "must be ours and the numbers must agree with each other.  The result is then "
           "judged against the case's pass/fail limits, fixed before any run, and reported "
           "whether it passes or not.  Contributed results are under the project's BSD-3 "
           "licence, and you are credited in the case's results.", "",
           "**This is a trial.**  The volunteer framework is new: a test of whether people "
           "with more computing power can take the validation cases beyond what the "
           "maintainer can run on one desktop.  Expect rough edges, and tell us what went "
           "wrong (an issue) as well as what worked.", "",
           "## The five commands", "",
           "```bash",
           "git clone --branch <tag> https://github.com/sigveka/hexmesh && cd hexmesh",
           "pip install -e .",
           "python3 -m validation.volunteer list                      # cases and their "
           "requirements",
           "python3 -m validation.volunteer prepare <case> <level> --dir run/   # mesh, case, "
           "job script",
           "sbatch run/job.sh        # or: bash run/job.sh  (resumable: run it again after a "
           "stop)",
           "python3 -m validation.volunteer collect run/              # writes one "
           ".contrib.json",
           "```", "",
           "Send the `.contrib.json` file back: in a pull request, attached to the case's "
           "issue (label `volunteer-run`), or by e-mail.  Nothing else is needed.  "
           "`collect --name \"Your Name\" --machine \"cluster, node type\"` puts your credit "
           "in the file.", "",
           "- **`<tag>`** is the release named in the card below: the mesh check needs the "
           "same hexmesh and gmsh versions.",
           "- **OpenFOAM:** `prepare` uses the first of these it finds: `HEXMESH_OPENFOAM` "
           "if set; OpenFOAM already loaded (`module load …`, the `path` runner); the "
           "bashrc in `HEXMESH_OPENFOAM_RC`; Apptainer or Singularity with the card's "
           "image; Docker.  Choose one with `--runner path`, `--runner "
           "apptainer:docker://<image>` and so on.  It refuses another OpenFOAM version "
           "than the card's, unless you pass `--allow-version` (the version is recorded "
           "either way).",
           "- **Cores:** `job.sh` asks for the card's recommended cores; `prepare --np N` "
           "changes that.  Under Slurm the run uses `SLURM_NTASKS`.",
           "- **Stopping and resuming:** the run saves its state every 50 solver steps.  "
           "Run `job.sh` again after a stop; it continues from the last save.",
           "- **What is sent back:** the level's numbers, the versions used, the mesh's "
           "fingerprint and check, cores, wall time and peak memory, and the last 200 lines "
           "of the solver log.  No fields, no mesh: well under 1 MB.", ""]
    for case, c in cards().items():
        out += [f"## {c['title']} (`{case}`)", "", c["summary"], "",
                f"- **OpenFOAM:** {c['openfoam']['version']} (image "
                f"`{c['openfoam']['image']}`)",
                f"- **hexmesh:** {c['hexmesh']['tag'] or 'the first release with this tool'} "
                f"({c['hexmesh']['note']})",
                f"- **gmsh:** {c['gmsh']['version']} ({c['gmsh']['note']})", ""]
        for name, lv in c["levels"].items():
            out += [f"### Level `{name}`: {lv['title']}", "", lv["what"], "",
                    f"```bash\npython3 -m validation.volunteer prepare {case} {name} "
                    f"--dir run/\n```", "", *requirements_table(lv), ""]
        out += ["**Pass/fail limits** (fixed before any run; a result is reported "
                "whether it passes or not):", ""]
        out += [f"- {g['quantity']}: {g['limit']}" for g in gates(case)]
        out += ["", f"**Sent back:** {c['returns']}", ""]
    text = "\n".join(out)
    raw = _raw_placeholders(text)
    if raw:
        raise ValueError(f"VOLUNTEERS.md would show raw {raw}: GitHub strips them as HTML; "
                         f"quote them in a code span in the card (task 0137)")
    return text


def _raw_placeholders(md: str) -> list[str]:
    """``<word>`` outside code spans and fences: GitHub hides it as an HTML tag."""
    import re
    md = re.sub(r"```.*?```|<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"`[^`\n]*`", "", md)
    return sorted(set(re.findall(r"<[a-z][\w -]*>", md)))


def cmd_docs(args) -> int:
    DOC.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {DOC.relative_to(ROOT)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m validation.volunteer",
                                 description=__doc__.strip().split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="cases and their requirements")
    p = sub.add_parser("prepare", help="mesh, case and job script for a level")
    p.add_argument("case")
    p.add_argument("level")
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--mesh-only", action="store_true", help="only the mesh; print its hash")
    p.add_argument("--runner", help="native, path, docker:IMAGE or apptainer:IMAGE "
                                    "(default: found; see VOLUNTEERS.md)")
    p.add_argument("--np", type=int, help="MPI processes (default: the card's)")
    p.add_argument("--allow-version", action="store_true",
                   help="run with another OpenFOAM version than the card's (recorded)")
    p = sub.add_parser("run", help="solve a prepared level (job.sh calls this); resumable")
    p.add_argument("dir", type=Path)
    p.add_argument("--np", type=int)
    p = sub.add_parser("collect", help="write the .contrib.json")
    p.add_argument("dir", type=Path)
    p.add_argument("--name", help="your name, for the credit")
    p.add_argument("--machine", help="the machine, e.g. 'cluster X, 2x EPYC 7763'")
    p.add_argument("--out", type=Path, help="directory for the file (default: here)")
    p.add_argument("--delete", action="store_true", help="delete the run directory after")
    p = sub.add_parser("check", help="check a contribution (maintainers)")
    p.add_argument("file", type=Path)
    p.add_argument("--merge", action="store_true", help="store an accepted level")
    p.add_argument("--results", type=Path, help="results.json to compare and merge into "
                                                "(default: the case's)")
    sub.add_parser("docs", help="regenerate validation/VOLUNTEERS.md")
    args = ap.parse_args(argv)
    return {"list": cmd_list, "prepare": cmd_prepare, "run": cmd_run, "collect": cmd_collect,
            "check": cmd_check, "docs": cmd_docs}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
