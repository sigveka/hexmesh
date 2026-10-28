"""
The study file (decision 0025, task 0042).

A study file is JSON::

    {
      "template":   {"python": "module:function"}      # build(params) -> Assembly
                  | {"json": "network.json"},          # to_dict() with "$name"s
      "parameters": {"D": 0.1},                        # fixed, in every variant
      "sampling":   {"grid":  {"radius": [0.2, 0.3], "angle": [45, 90]}}
                  | {"table": {"rows": [{...}, ...]} | {"csv": "rows.csv"}}
                  | {"lhs":   {"ranges": {"radius": [0.2, 0.4]}, "n": 8, "seed": 1}},
      "budget":     {"max_cells_variant": 100000, "max_cells_total": 1000000},
      "output":     "out",                             # default "study"
      "jobs":       1,                                 # mesh processes at once
      "format":     "msh" | "openfoam",                # default "msh"
      "walls_by_fitting": false,
      "case": {"template": "case", "split_regions": false},
      "run":  {"command": "./Allrun", "cores_per_job": 1,
               "post": "module:function", "timeout": 3600}
    }

Every key but ``template`` is optional; paths are relative to the study
file.  A variant's parameters are ``parameters`` updated by one sample.

**Python template**: ``module:function`` is imported with the study
file's directory first on ``sys.path``, and called with the variant's
parameters as one dict; it returns an ``Assembly``.

**JSON template**: an ``Assembly.to_dict()`` description in which any
value may be the string ``"$name"``: the whole value is replaced by the
parameter ``name``.  There are no expressions; ``"$$x"`` is the literal
string ``"$x"``.  A placeholder without a parameter, or a parameter no
placeholder uses, is an error.

**case** (task 0043; needs ``"format": "openfoam"``): ``template`` is an
OpenFOAM case directory without a mesh.  Each meshed variant gets a copy
in ``variants/<hash>/case``: the mesh converted (``gmshToFoam``, and
``splitMeshRegions -cellZones`` with ``split_regions``), its patches
retyped from the role manifest, and ``$name`` tokens in its dictionaries
replaced by the variant's parameters
(``hexmesh.study.openfoam.substitute_case``).

**run**: ``command`` runs in each case directory (with the OpenFOAM
environment), at most ``jobs`` at once, and ``jobs × cores_per_job``
must not exceed the machine's cores.  Then ``post`` (``module:function``,
imported like a Python template) is called as ``post(case_path,
params)`` and returns a dict: the variant's result.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

KEYS = {"template", "parameters", "sampling", "budget", "output", "jobs", "format",
        "walls_by_fitting", "case", "run"}
CASE_KEYS = {"template", "split_regions"}
RUN_KEYS = {"command", "cores_per_job", "post", "timeout"}
BUDGET_KEYS = {"max_cells_variant", "max_cells_total"}
FORMATS = ("msh", "openfoam")
_PLACEHOLDER = re.compile(r"^\$([A-Za-z_]\w*)$")


class StudyError(ValueError):
    """A study file that can't be used, with what is wrong."""


@dataclass
class Study:
    path:       Path
    template:   dict
    parameters: dict = field(default_factory=dict)
    sampling:   dict | None = None
    budget:     dict = field(default_factory=dict)
    output:     Path = Path("study")
    jobs:       int = 1
    format:     str = "msh"
    walls_by_fitting: bool = False
    case:       dict | None = None
    run:        dict | None = None
    raw:        dict = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def mesh_name(self) -> str:
        return "mesh.msh"

    def resolve(self, p) -> Path:
        p = Path(p)
        return p if p.is_absolute() else self.root / p

    # -- templates -----------------------------------------------------------

    def function(self, target: str, what: str):
        """Import ``module:function``, the study file's directory first on
        ``sys.path``."""
        if not isinstance(target, str) or target.count(":") != 1:
            raise StudyError(f"{what} must be 'module:function', got {target!r}")
        mod, fn = target.split(":")
        root = str(self.root)
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            return getattr(importlib.import_module(mod), fn)
        except (ImportError, AttributeError) as e:
            raise StudyError(f"{what} {target!r}: {e}") from None

    def builder(self):
        """``params -> Assembly`` for this study's template."""
        if "python" in self.template:
            return self.function(self.template["python"], "template.python")
        from ..assembly import Assembly
        text = self.resolve(self.template["json"]).read_text()
        network = json.loads(text)
        return lambda params: Assembly.from_dict(substitute(network, params))

    def check_placeholders(self, names: set[str]) -> None:
        """For a JSON template: every placeholder has a parameter and every
        parameter has a placeholder."""
        if "json" not in self.template:
            return
        used = placeholders(json.loads(self.resolve(self.template["json"]).read_text()))
        unknown, unused = sorted(used - names), sorted(names - used)
        if unknown or unused:
            raise StudyError("; ".join(
                ([f"unknown placeholder(s): {', '.join('$' + u for u in unknown)}"]
                 if unknown else [])
                + ([f"unused parameter(s): {', '.join(unused)}"] if unused else [])))


def load_study(path) -> Study:
    path = Path(path).resolve()
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise StudyError(f"{path}: not JSON ({e})") from None
    if not isinstance(raw, dict):
        raise StudyError(f"{path}: a study file is a JSON object")
    unknown = set(raw) - KEYS
    if unknown:
        raise StudyError(f"unknown study key(s): {', '.join(sorted(unknown))}; "
                         f"known: {', '.join(sorted(KEYS))}")
    tpl = raw.get("template")
    if not isinstance(tpl, dict) or len(tpl) != 1 or next(iter(tpl)) not in ("python", "json"):
        raise StudyError('template must be {"python": "module:function"} or {"json": "path"}')
    budget = raw.get("budget", {})
    if set(budget) - BUDGET_KEYS:
        raise StudyError(f"unknown budget key(s): {', '.join(sorted(set(budget) - BUDGET_KEYS))}")
    fmt = raw.get("format", "msh")
    if fmt not in FORMATS:
        raise StudyError(f"format must be one of {FORMATS}, got {fmt!r}")
    jobs = raw.get("jobs", 1)
    if not isinstance(jobs, int) or jobs < 1:
        raise StudyError(f"jobs must be a positive integer, got {jobs!r}")
    case, run = raw.get("case"), raw.get("run")
    for name, block, keys, required in (("case", case, CASE_KEYS, "template"),
                                        ("run", run, RUN_KEYS, "command")):
        if block is None:
            continue
        if not isinstance(block, dict) or required not in block:
            raise StudyError(f"{name} must be an object with {required!r}")
        if set(block) - keys:
            raise StudyError(f"unknown {name} key(s): {', '.join(sorted(set(block) - keys))}")
    if case is not None and fmt != "openfoam":
        raise StudyError('a case stage needs "format": "openfoam" (the role manifest)')
    if run is not None and case is None:
        raise StudyError("a run stage needs a case stage")
    if run is not None:
        cores = run.get("cores_per_job", 1)
        if not isinstance(cores, int) or cores < 1:
            raise StudyError(f"run.cores_per_job must be a positive integer, got {cores!r}")
    study = Study(path=path, template=tpl, parameters=dict(raw.get("parameters", {})),
                  sampling=raw.get("sampling"), budget=budget, jobs=jobs, format=fmt,
                  walls_by_fitting=bool(raw.get("walls_by_fitting", False)),
                  case=case, run=run, raw=raw)
    study.output = study.resolve(raw.get("output", "study"))
    return study


# --- placeholders ------------------------------------------------------------

def placeholders(obj) -> set[str]:
    if isinstance(obj, dict):
        return set().union(*(placeholders(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(placeholders(v) for v in obj)) if obj else set()
    if isinstance(obj, str):
        m = _PLACEHOLDER.match(obj)
        return {m.group(1)} if m else set()
    return set()


def substitute(obj, params: dict):
    """*obj* with every ``"$name"`` value replaced by ``params[name]``."""
    if isinstance(obj, dict):
        return {k: substitute(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, params) for v in obj]
    if isinstance(obj, str):
        if obj.startswith("$$"):
            return obj[1:]
        m = _PLACEHOLDER.match(obj)
        if m:
            if m.group(1) not in params:
                raise StudyError(f"unknown placeholder ${m.group(1)}")
            return params[m.group(1)]
    return obj


# --- variant identity --------------------------------------------------------

def canonical(obj):
    """JSON-ready *obj* with floats in a canonical form: integral floats as
    ints (``90.0`` → ``90``), others by their shortest repr; NaN rejected."""
    if isinstance(obj, dict):
        return {str(k): canonical(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [canonical(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return int(obj)
    if isinstance(obj, float) or hasattr(obj, "__float__"):
        f = float(obj)
        if not math.isfinite(f):
            raise StudyError(f"parameter value {obj!r} is not finite")
        return int(f) if f.is_integer() and abs(f) < 2**53 else float(repr(f))
    raise StudyError(f"parameter value {obj!r} ({type(obj).__name__}) is not JSON data")


def variant_hash(params: dict, length: int = 12) -> str:
    """A short stable name for a variant's resolved parameters."""
    text = json.dumps(canonical(params), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:length]
