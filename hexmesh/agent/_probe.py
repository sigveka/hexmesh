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
"""The support matrix of ``hexmesh.agent.manifest()`` (task 0102), probed,
not declared: each fitting type is built after a short ``Straight`` on a
fixed set of small specs and run through the library's own checks
(``Assembly.validate``), without a GMSH session.  Each entry is
"supported" or what the library raised: its code, class and message.

The probe takes over a second (a wye's layout), so its result is package
data, written by::

    python3 -m hexmesh.agent._probe

``tests/test_agent_manifest.py`` probes again and fails, naming this
command, when the library and ``support.json`` disagree.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

from hexmesh import (Assembly, Bend, Elbow, HexmeshError, MiterBend, PipeSpec, Reducer,
                     SplinePipe, Straight, Switch, Tee, Transition, Wye)
from hexmesh.assembly.intent import FITTING_TYPES
from hexmesh.core.shape import RectShape

SUPPORT = Path(__file__).with_name("support.json")

# --- the support probe ------------------------------------------------------
# The specs a fitting is probed on: (shape, layout, stack) and a builder of
# the spec at a radial scale (a Reducer's outlet is the same spec, smaller).

PROBE_SPECS = {
    "circle": ("circle", "oh", "single layer",
               lambda s: PipeSpec(nang=4).core("fluid", radius=0.05 * s, nrad=2)),
    "circle_shells": ("circle", "oh", "circular shells",
                      lambda s: PipeSpec(nang=4).core("fluid", radius=0.05 * s, nrad=2)
                      .shell("wall", dR=0.005 * s, nrad=1)),
    "rect_h": ("rect", "h", "single layer",
               lambda s: PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=0.05 * s,
                                                           half_h=0.03 * s)),
    "rect_oh": ("rect", "oh", "single layer",
                lambda s: PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=0.05 * s,
                                                            half_h=0.03 * s, nrad=2,
                                                            layout="oh")),
    "rect_shells": ("rect", "h", "rectangular shells",
                    lambda s: PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=0.05 * s,
                                                                half_h=0.03 * s)
                    .shell("wall", dR=0.005 * s, nrad=1)),
    "circle_in_rect": ("circle", "oh", "a circle in a rectangle",
                       lambda s: PipeSpec(nang=4).core("fluid", radius=0.05 * s, nrad=2)
                       .shell("box", nrad=2, outer=RectShape(0.07 * s, 0.07 * s, 4, 4))),
    "circle_n_outer_8": ("circle", "oh", "single layer, n_outer = 8",
                         lambda s: PipeSpec(nang=8, n_outer=8)
                         .core("fluid", radius=0.05 * s, nrad=2)),
}


def _other_shape(key: str) -> PipeSpec:
    """A Transition's outlet: a rectangle from a circle, a circle from a rectangle."""
    if PROBE_SPECS[key][0] == "circle":
        return PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=0.04, half_h=0.04)
    return PipeSpec(nang=4).core("fluid", radius=0.05, nrad=2)


def _switched(key: str) -> PipeSpec | None:
    """A Switch's outlet: given from an H inlet (it carries the O-H ring),
    with the inlet's shells (a Switch keeps them); the default otherwise."""
    if PROBE_SPECS[key][1] != "h":
        return None
    out = PROBE_SPECS["rect_oh"][3](1.0)
    for sh in PROBE_SPECS[key][3](1.0).shells:
        out = out.shell(sh.name, dR=sh.dR, nrad=sh.nrad, mprg=sh.mprg, outer=sh.outer)
    return out


# Each fitting, as built for a probe: f(spec key, spec builder) -> fitting.
PROBES = {
    "Straight": lambda k, mk: Straight(0.2, n_layers=2),
    "Bend": lambda k, mk: Bend(0.3, 90.0, n_layers=4),
    "MiterBend": lambda k, mk: MiterBend(0.3, 90.0),
    "Elbow": lambda k, mk: Elbow(90.0),
    "Reducer": lambda k, mk: Reducer(mk(0.8), 0.2, n_layers=2),
    "Transition": lambda k, mk: Transition(_other_shape(k), 0.2, n_layers=2),
    "SplinePipe": lambda k, mk: SplinePipe(((0.1, 0.0, 0.0), (0.6, 0.0, 0.0), (1.1, 0.1, 0.0),
                                            (1.6, 0.3, 0.0)), n_layers=8),
    "Tee": lambda k, mk: (Tee(branch_length=0.15, branch_radius=0.02)
                          if PROBE_SPECS[k][0] == "circle" else
                          Tee(branch_length=0.15, branch=RectShape(0.02, 0.02, 4, 4))),
    "Wye": lambda k, mk: Wye(60.0, 0.3, 0.3),
    "Switch": lambda k, mk: Switch(0.2, n_layers=2, outlet=_switched(k)),
}
# Fittings a lone probe can't build, and why.
UNPROBED = {"Closure": "joins two existing interfaces of a loop (Assembly.close); "
                       "checked there"}


def _probe(fitting: str, key: str) -> dict:
    make = PROBE_SPECS[key][3]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spec = make(1.0)
            asm = Assembly(spec)
            asm.add(Straight(0.1, n_layers=1))
            asm.add(PROBES[fitting](key, make))
            asm.validate()
    except HexmeshError as e:
        return {"supported": False, "code": e.code, "error": type(e).__name__,
                "message": str(e)}
    except Exception as e:                                    # noqa: BLE001
        return {"supported": False, "code": None, "error": type(e).__name__,
                "message": str(e)}
    return {"supported": True}


def probe() -> dict:
    """Per fitting type, per probe spec: supported, or what the library
    raised (its code, class and message)."""
    specs = {k: {"shape": shape, "layout": layout, "stack": stack,
                 "spec": make(1.0).to_dict()}
             for k, (shape, layout, stack, make) in PROBE_SPECS.items()}
    fittings = {}
    for name in FITTING_TYPES:
        if name in UNPROBED:
            fittings[name] = {"probed": False, "why": UNPROBED[name]}
        else:
            fittings[name] = {"probed": True,
                              "specs": {k: _probe(name, k) for k in PROBE_SPECS}}
    return {"method": "each fitting after a short Straight on each spec, through "
                      "Assembly.validate() (no GMSH session); 'supported' or what it raised",
            "specs": specs, "fittings": fittings}


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False,
                      allow_nan=False) + "\n"


def main() -> int:
    """Write ``support.json`` from a fresh probe."""
    SUPPORT.write_text(dumps(probe()), encoding="utf-8", newline="\n")
    print(f"wrote {SUPPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
