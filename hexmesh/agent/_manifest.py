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
"""One machine-readable account of the suite for agents (task 0102;
decision 0040, amendment 2026-11-07): ``manifest() -> dict``.

Built from the registries, not copies: the CLI's parser and
:data:`_commands.RESULTS`, ``FITTING_TYPES``, ``LIMITS``, ``CODES``, the
advisor's calibration and the validation summary (package data from
``python3 -m validation.tools.summary``), and the support matrix, probed
from the library's own checks and stored (``_probe``, ``support.json``).

JSON-safe, deterministic, and no GMSH session.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hexmesh import __version__
from hexmesh.assembly import limits
from hexmesh.assembly.intent import FORMAT as DESCRIPTION_FORMAT
from hexmesh.assembly.intent import VERSION as DESCRIPTION_VERSION
from hexmesh.errors import CODES

from . import _commands
from . import advise as _advise

FORMAT, VERSION = "hexmesh.agent.manifest", 1
VALIDATION = Path(__file__).with_name("validation.json")
SUPPORT = Path(__file__).with_name("support.json")

# --- the other sections -----------------------------------------------------

def commands() -> dict:
    """Each subcommand: its arguments (from the parser), and its result."""
    sub = next(a for a in _commands.parser()._actions if isinstance(a, argparse._SubParsersAction))
    out = {}
    for name in _commands.COMMANDS:
        args = []
        for a in sub.choices[name]._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            args.append({"name": a.dest if not a.option_strings else a.option_strings[0],
                         "positional": not a.option_strings,
                         "required": bool(a.required) or not a.option_strings,
                         "help": a.help, "choices": list(a.choices) if a.choices else None,
                         "default": a.default if a.option_strings else None})
        out[name] = {"arguments": args, "result": _commands.RESULTS[name],
                     "needs_gmsh": name in _commands.NEEDS_GMSH}
    return out


WORKFLOW = [
    {"step": "read what a description may hold", "command": "schema",
     "hands": "the JSON Schema of an Assembly description"},
    {"step": "write the network", "command": None,
     "hands": "an Assembly description (.json), or a PCF file with --spec"},
    {"step": "check it", "command": "validate",
     "hands": "errors (stops at the first) and warnings, each with a code"},
    {"step": "count it exactly, before meshing", "command": "estimate",
     "hands": "the cell count, per fitting"},
    {"step": "see what it is", "command": "describe",
     "hands": "fittings, ports, materials, bounds; preview draws it (PNG)"},
    {"step": "choose the resolution", "command": "advise",
     "hands": "a resolution table for an accuracy class, or a cell budget"},
    {"step": "write the resolution in", "command": "apply",
     "hands": "the description with the table's counts; validate it again"},
    {"step": "mesh it", "command": "build",
     "hands": "a .msh (order 1 or 2) carrying its recipe; the only step with GMSH"},
]

CONVENTIONS = [
    "Lengths are in metres (hexmesh.units has mm, cm, inch, …); a PCF's own units are read from it.",
    "Angles are in degrees (PipeSpec.rot, bend and wye angles, roll).",
    "Doubling every density parameter gives 8x the cells in 3-D, not 2x.",
    "Topology (n_outer, rot, layout, the layer stack) fixes where interfaces land and can't "
    "change without rebuilding; density (nang, nrad, n_layers) is resolution only.",
    "Cell counts are exact before meshing (estimate; Assembly.cell_count).",
    "Convergence orders come from the refinement factor k of the directions that refine, "
    "never from the cell count (docs/RESEARCH.md §7.12).",
    "Errors and warnings carry a stable code (errors section) and the fields where, value, "
    "limit, hint.",
]


def _limits() -> dict:
    return {name: {"value": _plain(l.value), "unit": l.unit, "kind": l.kind, "doc": l.doc}
            for name, l in sorted(limits.LIMITS.items())}


def _plain(v):
    if isinstance(v, (tuple, list)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    return v


def _advice() -> dict:
    cal = _advise.calibration()
    return {"format": _advise.FORMAT, "version": _advise.VERSION,
            "calibration": {"format": cal["format"], "version": cal["version"]},
            "regime": cal["regime"], "rule": cal["rule"], "scope": cal["scope"],
            "classes": {name: {"max_error": c["max_error"],
                               "basis": {where: {"basis": d["classes"][name]["basis"],
                                                 "validated": d["classes"][name]["validated"],
                                                 "case": d["case"]}
                                         for where, d in _calibrated(cal)}}
                        for name, c in sorted(cal["classes"].items())}}


def _calibrated(cal: dict):
    """(where, entry) of each calibrated series: the circle, and each
    measured aspect ratio of a rectangle."""
    shapes = cal["shapes"]
    yield "circle", shapes["circle"]
    for ratio, d in sorted(shapes["rect"]["aspect"].items(), key=lambda kv: float(kv[0])):
        yield f"rect, a/b {ratio}", d


def support() -> dict:
    """The probed support matrix (``support.json``, from ``_probe``)."""
    return json.loads(SUPPORT.read_text(encoding="utf-8"))


def validation() -> dict:
    return json.loads(VALIDATION.read_text(encoding="utf-8"))


def manifest() -> dict:
    """The manifest: what hexmesh does, how its commands chain, and what it
    accepts.  An agent reads it first (``hexmesh manifest``)."""
    return {
        "format": FORMAT, "manifest_version": VERSION, "version": __version__,
        "schema": {"format": DESCRIPTION_FORMAT, "version": DESCRIPTION_VERSION},
        "invocation": ["hexmesh <command>", "python3 -m hexmesh.agent.cli <command>"],
        "envelope": {"keys": ["command", "ok", "result", "version"],
                     "on_error": ["command", "ok", "error", "version"],
                     "exit_codes": {str(_commands.EXIT_OK): "ok",
                                    str(_commands.EXIT_INVALID): "invalid input",
                                    str(_commands.EXIT_FAILURE): "a failure (an unreachable budget, "
                                                           "a mesh that fails)"}},
        "commands": commands(),
        "workflow": WORKFLOW,
        "support": support(),
        "limits": _limits(),
        "errors": dict(sorted(CODES.items())),
        "advise": _advice(),
        "validation": validation(),
        "conventions": CONVENTIONS,
    }
