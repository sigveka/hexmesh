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
"""The resolution advisor: ``advise()`` and ``apply()`` (task 0098, decision 0040).

``advise(x, inputs)`` takes an ``Assembly`` or its ``to_dict()``
description, and the flow (``inputs``, below).  It returns a JSON-safe
report: per section the Re, the regime and the first cell; per fitting
its axial counts; the exact cell total against the budget; and a
**resolution table**.  ``apply(description, table)`` writes the table
into the description, which is then built as usual.  Every choice
records its rule and inputs under ``reasons``, so an agent can explain
it and a user can override one value and re-run.

**Inputs** (one dict, SI units except lengths):

- ``length_unit``: the geometry's unit, ``"m"`` (default) or ``"mm"``.
  hexmesh doesn't convert lengths; the advisor needs metres for Re and
  y⁺.  Reported lengths are in this unit.
- ``fluid``: ``"water"`` or ``"air"`` (20 °C, :data:`FLUIDS`), or
  ``{"density": kg/m³, "viscosity": Pa·s}`` (dynamic viscosity).
- ``flow``: ``{"velocity": m/s}`` or ``{"flow_rate": m³/s}``, at the
  assembly's inlet.  At a junction it splits in proportion to the open
  area downstream of each outlet.
- ``wall``: ``"wall-resolved"`` (default), or ``{"treatment":
  "wall-resolved", "y_plus": 1}``.  ``"wall-function"`` is an error
  until task 0049 validates it.
- ``accuracy``: ``"coarse"``, ``"medium"`` (default) or ``"fine"``:
  ≤ 1 %, 0.3 % and 0.1 % in the validation cases' gated quantities
  (``calibration.json``, from ``_calibrate``).
- ``budget``: the maximum cells, optional.

**Counts.**  Density is shared by every section of an assembly
(DESIGN: a reducer may change radii only), so the table has one
``density`` and per-fitting axial counts.  Circles: ``nang`` and the
core's ``nrad`` from the calibrated cells along a diameter.  Rectangles
(the H layout): ``nang_w`` and ``nang_h`` from the cells across D_h,
square cells.  A transition ties a circle's ``nang`` to a rectangle's
counts: the largest wins.  Laminar flow keeps the calibrated runs'
uniform grading; turbulent wall-resolved flow grades the wall to the
y⁺ target, which no validated case covers yet (``"validated": false``).

**Budget.**  Over it, the resolution is lowered in a fixed order: the
straights' axial counts, then the accuracy class one step at a time,
then the fittings' axial counts to their minima.  The first cell never
moves off the y⁺ target.  Cells are counted with ``cell_count()``
inside the loop; ``validate()`` runs once, on the result.

Doubling every count gives 8× the cells: every report says so.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
from functools import lru_cache
from pathlib import Path

from hexmesh import Assembly, HexmeshError, HexmeshWarning, __version__
from hexmesh.assembly import limits
from hexmesh.core.grading import (bump, bump_for_first_cell, first_cell_height,
                                  progression_for_first_cell)
from hexmesh.core.shape import core_wall_span

from ._describe import _checks, _jsonable, _length, section

FORMAT = "hexmesh.agent.advice"
VERSION = 1
CALIBRATION = Path(__file__).with_name("calibration.json")

#: named fluids at 20 °C and 1 atm [white_2011, tables A.1 and A.2]
FLUIDS = {
    "water": {"density": 998.0, "viscosity": 1.00e-3,
              "source": "water at 20 °C [white_2011, table A.1]"},
    "air": {"density": 1.205, "viscosity": 1.80e-5,
            "source": "air at 20 °C, 1 atm [white_2011, table A.2]"},
}
ACCURACY = ("coarse", "medium", "fine")
LENGTH_UNITS = {"m": 1.0, "mm": 1e-3}
RE_LAMINAR, RE_TURBULENT = 2300.0, 4000.0
RE_BLASIUS_MAX = 1e5
EIGHT_X = ("doubling every count (nang, nrad, n_layers) doubles the cells in each "
           "direction: 8× the cells")
#: fittings whose own rules set their counts (``advise`` keeps them)
OWN_RULES = {"Wye": "its n_split, n_run and n_branch rules", "Switch": "its length rule"}


class AdviceError(HexmeshError):
    """Inputs ``advise`` can't use, or a budget it can't meet."""


# --- inputs -------------------------------------------------------------------------

def _bad(message, field, value=None, **kw):
    return AdviceError(message, code="advice_input_invalid", where={"field": field},
                       value=value, **kw)


def _positive(d, key, field):
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0:
        raise _bad(f"{field} must be a positive number, got {v!r}", field, v)
    return float(v)


def _inputs(inputs: dict) -> dict:
    """*inputs* checked and normalised (module docstring)."""
    if not isinstance(inputs, dict):
        raise _bad(f"inputs must be a dict, got {type(inputs).__name__}", "inputs")
    known = {"length_unit", "fluid", "flow", "wall", "accuracy", "budget"}
    extra = sorted(set(inputs) - known)
    if extra:
        raise _bad(f"unknown input(s) {extra}; known: {sorted(known)}", extra[0])
    unit = inputs.get("length_unit", "m")
    if unit not in LENGTH_UNITS:
        raise _bad(f"length_unit must be one of {sorted(LENGTH_UNITS)}, got {unit!r}",
                   "length_unit", unit, limit=sorted(LENGTH_UNITS))
    fluid = inputs.get("fluid")
    if isinstance(fluid, str):
        if fluid not in FLUIDS:
            raise AdviceError(f"unknown fluid {fluid!r}; named fluids: {sorted(FLUIDS)}, or "
                              "give {density, viscosity}", code="advice_fluid_unknown",
                              where={"field": "fluid"}, value=fluid, limit=sorted(FLUIDS))
        fluid = {"name": fluid, **FLUIDS[fluid]}
    elif isinstance(fluid, dict):
        fluid = {"density": _positive(fluid, "density", "fluid.density"),
                 "viscosity": _positive(fluid, "viscosity", "fluid.viscosity"),
                 "source": "given"}
    else:
        raise _bad("fluid is required: a name or {density, viscosity}", "fluid", fluid)
    flow = inputs.get("flow")
    if not isinstance(flow, dict) or len(flow) != 1 or \
            next(iter(flow)) not in ("velocity", "flow_rate"):
        raise _bad("flow must be {\"velocity\": m/s} or {\"flow_rate\": m³/s}", "flow", flow)
    key = next(iter(flow))
    flow = {key: _positive(flow, key, f"flow.{key}")}
    wall = inputs.get("wall", "wall-resolved")
    if isinstance(wall, str):
        wall = {"treatment": wall}
    if not isinstance(wall, dict):
        raise _bad(f"wall must be a string or a dict, got {wall!r}", "wall", wall)
    treatment = wall.get("treatment", "wall-resolved")
    if treatment == "wall-function":
        raise AdviceError("wall functions are not supported yet: they wait for task 0049's "
                          "validation (decision 0040)", code="advice_wall_function_unsupported",
                          where={"field": "wall.treatment"}, value=treatment,
                          hint="use \"wall-resolved\"")
    if treatment != "wall-resolved":
        raise _bad(f"wall.treatment must be \"wall-resolved\", got {treatment!r}",
                   "wall.treatment", treatment, limit=["wall-resolved", "wall-function"])
    wall = {"treatment": treatment,
            "y_plus": _positive({"y": wall.get("y_plus", 1.0)}, "y", "wall.y_plus")}
    accuracy = inputs.get("accuracy", "medium")
    if accuracy not in ACCURACY:
        raise _bad(f"accuracy must be one of {list(ACCURACY)}, got {accuracy!r}",
                   "accuracy", accuracy, limit=list(ACCURACY))
    budget = inputs.get("budget")
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int)
                               or budget < 1):
        raise _bad(f"budget must be a positive integer number of cells, got {budget!r}",
                   "budget", budget)
    return {"length_unit": unit, "fluid": fluid, "flow": flow, "wall": wall,
            "accuracy": accuracy, "budget": budget}


# --- physics ------------------------------------------------------------------------

def friction_factor(re: float) -> tuple[float, str]:
    """Darcy friction factor of a smooth pipe in turbulent flow, and its
    source: Blasius below Re 10⁵ [blasius_1913], Haaland's explicit form
    above [haaland_1983]."""
    if re < RE_BLASIUS_MAX:
        return 0.3164 * re ** -0.25, "Blasius, f = 0.3164 Re^-1/4 [blasius_1913]"
    return (-1.8 * math.log10(6.9 / re)) ** -2, \
        "Haaland, smooth, 1/√f = -1.8 log10(6.9/Re) [haaland_1983]"


def first_cell_for_y_plus(y_plus: float, velocity: float, d_h: float, nu: float) -> dict:
    """The wall cell height (m) for *y_plus*: y = y⁺ ν / u_τ with
    u_τ = U √(f/8)."""
    re = velocity * d_h / nu
    f, source = friction_factor(re)
    u_tau = velocity * math.sqrt(f / 8)
    return {"first_cell": y_plus * nu / u_tau, "re": re, "friction_factor": f,
            "u_tau": u_tau, "source": source}


def _regime(re: float) -> str:
    return "laminar" if re < RE_LAMINAR else "transitional" if re < RE_TURBULENT \
        else "turbulent"


# --- the network's sections ---------------------------------------------------------

def _core(sec: dict) -> dict:
    """The fluid core of a ``describe`` section: shape, area, D_h (in the
    geometry's unit)."""
    o = sec["layers"][0]["outline"]
    if o["type"] == "circle":
        r = o["radius"]
        return {"shape": "circle", "radius": r, "area": math.pi * r * r, "d_h": 2 * r,
                "layout": sec["layout"]}
    a, b = o["half_w"], o["half_h"]
    return {"shape": "rect", "half_w": a, "half_h": b, "area": 4 * a * b,
            "d_h": 4 * a * b / (a + b), "aspect": max(a, b) / min(a, b),
            "layout": sec["layout"]}


def _flows(asm: Assembly, q0: float) -> dict[int, float]:
    """Flow rate into each interface: the inlet's *q0*, split at each
    junction in proportion to the open area downstream of each outlet."""
    starts = {e.ports[0].index: e for e in asm.edges if e.kind != "close"}
    area: dict[int, float] = {}

    def downstream(i, seen=()):
        if i.index in area:
            return area[i.index]
        e = starts.get(i.index)
        if e is None or i.index in seen:
            a = _core(section(i.spec))["area"]
        else:
            a = sum(downstream(o, seen + (i.index,)) for o in e.ports[1:])
        area[i.index] = a
        return a

    q = {asm.interfaces[0].index: q0}
    for e in asm.edges:
        if e.kind == "close" or e.ports[0].index not in q:
            continue
        outs = e.ports[1:]
        total = sum(downstream(o) for o in outs)
        for o in outs:
            q.setdefault(o.index, q[e.ports[0].index] * downstream(o) / total)
    return q


def _sections(asm: Assembly, inp: dict) -> list[dict]:
    """Every place a section carries flow: each fitting's inlet, and its
    outlets where their section differs.  Re in metres, whatever the unit."""
    scale = LENGTH_UNITS[inp["length_unit"]]
    fluid = inp["fluid"]
    nu = fluid["viscosity"] / fluid["density"]
    flow = inp["flow"]
    inlet_area = _core(section(asm.interfaces[0].spec))["area"] * scale ** 2
    q0 = flow.get("flow_rate", flow.get("velocity", 0) * inlet_area)
    q = _flows(asm, q0)
    out = []
    for e in asm.edges:
        for j, port in enumerate(e.ports):
            if j > 0 and section(port.spec) == section(e.ports[0].spec):
                continue
            if port.index not in q:
                continue
            core = _core(section(port.spec))
            u = q[port.index] / (core["area"] * scale ** 2)
            re = u * core["d_h"] * scale / nu
            out.append({"fitting": e.index, "name": e.name, "port": j,
                        "interface": port.index, **core, "flow_rate": q[port.index],
                        "velocity": u, "re": re, "regime": _regime(re)})
    return out


# --- density ------------------------------------------------------------------------

@lru_cache(maxsize=1)
def calibration() -> dict:
    """``calibration.json``, read once."""
    with open(CALIBRATION, encoding="utf-8") as f:
        return json.load(f)


def _class(shape: str, aspect: float | None, accuracy: str, reasons: list) -> dict:
    """The calibrated class for *shape*, falling back to the best class in
    range; a rectangle takes the worse of the measured aspect ratios
    around it (design answer Q3)."""
    cal = calibration()["shapes"]
    order = ACCURACY[:ACCURACY.index(accuracy) + 1][::-1]
    if shape == "circle":
        entries = [("circle", cal["circle"])]
    else:
        measured = sorted(int(r) for r in cal["rect"]["aspect"])
        if aspect > measured[-1]:
            entries = [(f"a/b {measured[-1]}", cal["rect"]["aspect"][str(measured[-1])])]
        else:
            lo = max(r for r in measured if r <= aspect + 1e-9)
            hi = min(r for r in measured if r >= aspect - 1e-9)
            entries = [(f"a/b {r}", cal["rect"]["aspect"][str(r)]) for r in sorted({lo, hi})]
    for cls in order:
        found = [(name, e["classes"][cls]) for name, e in entries]
        if all(not c.get("out_of_range") for _, c in found):
            name, c = max(found, key=lambda x: x[1]["n"])
            c = {**c, "class": cls, "series": name,
                 "case": dict(entries)[name]["case"]}
            if shape == "rect" and aspect > float(measured[-1]) + 1e-9:
                c.update(validated=False, basis=c["basis"] + f"; a/b {aspect:.3g} is past "
                         f"the largest measured a/b {measured[-1]}, whose class is used")
            if cls != accuracy:
                reasons.append(f"{accuracy} is out of the calibrated range ("
                               f"{found[0][1].get('basis', '')}); using {cls}")
            return c
    raise AssertionError("coarse is always in range")          # pragma: no cover


def _rect_counts(core: dict, n: float) -> tuple[int, int]:
    """(nang_w, nang_h) for *n* cells across D_h, square cells."""
    a, b = core["half_w"], core["half_h"]
    short, long_ = min(a, b), max(a, b)
    n_short = max(1, math.ceil(n * 2 * short / core["d_h"] - 1e-9))
    n_long = max(1, round(n_short * long_ / short))
    return (n_long, n_short) if a >= b else (n_short, n_long)


def _density(sections: list[dict], inp: dict, tied: str | None) -> dict:
    """One density for the assembly: the largest count any section needs."""
    reasons: list[str] = []
    classes = {}
    nang = nrad = nang_w = nang_h = None
    for s in sections:
        if s["shape"] == "rect" and s["layout"] != "h":
            raise AdviceError(f"{s['name']}: a rectangle with layout {s['layout']!r} has no "
                              "calibration; the H layout (the default) has",
                              code="advice_layout_unsupported",
                              where={"fitting": s["fitting"]}, value=s["layout"],
                              hint="use layout='h' for rectangles")
        c = _class(s["shape"], s.get("aspect"), inp["accuracy"], reasons)
        s["class"] = c
        key = s["shape"] if s["shape"] == "circle" else f"rect {c['series']}"
        classes[key] = c
        if s["shape"] == "circle":
            na = math.ceil(c["n"] / 2 - 1e-9)
            na += na % 2                    # even: a node mid-arc, as calibrated
            nang = max(nang or 0, na)
            nrad = max(nrad or 0, math.ceil(na * calibration()["shapes"]["circle"]
                                            ["nrad_per_nang"] - 1e-9))
        else:
            w, h = _rect_counts(s, c["n"])
            nang_w, nang_h = max(nang_w or 0, w), max(nang_h or 0, h)
    if nang is not None:
        reasons.append(f"circles: nang {nang} and nrad {nrad} (nrad = nang/2, as calibrated) "
                       f"give nang + 2 nrad ≥ the class's cells along a diameter; nang "
                       f"even, so a node sits mid-arc, where the first cell is measured")
    if nang_w is not None:
        reasons.append(f"rectangles (H): nang_w {nang_w}, nang_h {nang_h}: square cells, "
                       "at least the class's cells across D_h")
    if tied and (nang_w is not None or nang is not None):
        m = max(x for x in (nang, nang_w, nang_h) if x is not None)
        reasons.append(f"{tied}, which needs nang = nang_w = nang_h: all {m}")
        nang = nang_w = nang_h = m
        nrad = max(nrad or 0, math.ceil(m / 2 - 1e-9))
    return {"nang": nang, "nrad": nrad, "nang_w": nang_w, "nang_h": nang_h,
            "mprg": 1.0, "wall_bump": None, "classes": classes, "reasons": reasons}


def _bump_growth(n: int, coef: float) -> float:
    x = bump(n, coef)
    d = [x[i + 1] - x[i] for i in range(n)]
    return max(max(d[i + 1] / d[i], d[i] / d[i + 1]) for i in range(n - 1)) if n > 1 else 1.0


def _wall(density: dict, sections: list[dict], inp: dict) -> list[str]:
    """Grade the wall to the y⁺ target where a section is turbulent or
    transitional: ``mprg`` (circles) or ``wall_bump`` (H), with more cells
    where the growth would pass ``MAX_WALL_GROWTH``.  Laminar: the
    calibrated runs' uniform grading (design answer Q3).  Fills each
    section's ``first_cell`` (in the geometry's unit) and reasons."""
    scale = LENGTH_UNITS[inp["length_unit"]]
    nu = inp["fluid"]["viscosity"] / inp["fluid"]["density"]
    y_plus = inp["wall"]["y_plus"]
    reasons = []
    growth = limits.MAX_WALL_GROWTH
    turbulent = [s for s in sections if s["regime"] != "laminar"]
    for s in turbulent:
        w = first_cell_for_y_plus(y_plus, s["velocity"], s["d_h"] * scale, nu)
        s["wall"] = {**w, "first_cell": w["first_cell"] / scale}
    circles = [s for s in turbulent if s["shape"] == "circle"]
    if circles:
        # mprg is shared, so the section with the smallest first cell
        # against its ring sets it; the others' first cells follow
        def need(n):
            return max(progression_for_first_cell(core_wall_span(s["radius"]), n,
                                                  s["wall"]["first_cell"]) for s in circles)
        n = density["nrad"]
        while need(n) > growth:
            n += 1
        if n != density["nrad"]:
            reasons.append(f"nrad {density['nrad']} → {n}: the ring's growth from the "
                           f"first cell stays within MAX_WALL_GROWTH {growth:g}")
            density["nrad"] = n
        q = need(n)
        density["mprg"] = 1.0 / q
        reasons.append(f"circles: mprg {1 / q:.6g} (growth {q:.4g} per cell) puts the "
                       f"y⁺ = {y_plus:g} first cell at the governing section's wall")
    rects = [s for s in turbulent if s["shape"] == "rect"]
    if rects:
        # wall_bump is per side: the smallest first cell over the sections
        h = min(s["wall"]["first_cell"] for s in rects)
        while True:
            coefs = []
            for s in [x for x in sections if x["shape"] == "rect"]:
                coefs.append((bump_for_first_cell(2 * s["half_w"], density["nang_w"], h),
                              bump_for_first_cell(2 * s["half_h"], density["nang_h"], h)))
            cw, ch = coefs[0]
            g = max(_bump_growth(density["nang_w"], cw), _bump_growth(density["nang_h"], ch))
            if g <= growth:
                break
            density["nang_w"] = math.ceil(density["nang_w"] * 1.25)
            density["nang_h"] = math.ceil(density["nang_h"] * 1.25)
        density["wall_bump"] = [cw, ch]
        density["first_cell"] = h
        reasons.append(f"rectangles: wall_bump puts a first cell of {h:.4g} at every wall "
                       f"(growth {g:.4g} ≤ MAX_WALL_GROWTH {growth:g})")
    for s in sections:
        s["first_cell"] = _first_cell(s, density)
        if s.get("wall"):
            s["y_plus"] = s["first_cell"] * scale * s["wall"]["u_tau"] / nu
    if turbulent:
        reasons.append("turbulent wall-resolved grading has no validated case "
                       "(\"validated\": false)")
    return reasons


def _first_cell(s: dict, density: dict) -> float:
    """The meshed wall cell of section *s* under *density*: the largest
    (mid-arc on a circle; on an H rectangle the larger of the two sides'
    end cells, which ``wall_bump`` makes equal).
    A circle's radial cells grow outward by ``mprg``, so its wall cell is
    the first of the ring read inward, growing by 1/mprg."""
    if s["shape"] == "circle":
        return first_cell_height(core_wall_span(s["radius"]), density["nrad"],
                                 1.0 / density["mprg"])
    if density.get("wall_bump"):
        return density["first_cell"]
    return max(2 * s["half_w"] / density["nang_w"], 2 * s["half_h"] / density["nang_h"])


# --- axial counts -------------------------------------------------------------------

def _h_core(core: dict, density: dict) -> float:
    """The core cell size of a section under *density* (geometry's unit)."""
    if core["shape"] == "circle":
        return core["d_h"] / (density["nang"] + 2 * density["nrad"])
    # the larger in-plane cell, where tied counts make them unequal
    return max(2 * core["half_w"] / density["nang_w"], 2 * core["half_h"] / density["nang_h"])


def _minimum(e, field: str) -> int:
    """The fewest layers *field* of edge *e* may have: the field's
    ``minimum``, and for ``n_layers`` what the fitting's ``layers_ok``
    accepts (a bend's turn per slab)."""
    f = e.fitting
    meta = {x.name: x.metadata for x in dataclasses.fields(f)}
    n = int(meta.get(field, {}).get("minimum", 1))
    if field == "n_layers" and hasattr(f, "layers_ok"):
        out = e.ports[1].frame if len(e.ports) == 2 else None
        while not f.layers_ok(n, e.ports[0].frame, e.ports[0].spec, out) and n < 10_000:
            n += 1
    return n


def _axial(asm: Assembly, density: dict, ar_straight: float, ar_fitting: float,
           minimal: bool = False) -> dict[int, dict]:
    """Per fitting, its axial counts and why: the core cell × the aspect
    limit along its length (straights and the rest have their own limit),
    never below the fitting's minimum; *minimal*: the minimum, for every
    fitting but the straights (the budget's last step)."""
    out = {}
    for e in asm.edges:
        f, name = e.fitting, type(e.fitting).__name__
        if name in OWN_RULES:
            out[e.index] = {"counts": {}, "reasons": [f"{name}: kept, {OWN_RULES[name]}"]}
            continue
        straight = name == "Straight"
        ar = ar_straight if straight else ar_fitting
        h = _h_core(_core(section(e.ports[0].spec)), density)
        if name == "Tee":
            hb = _h_core(_core(section(e.ports[-1].spec)), density)
            plan = [("n_run", f.run_length, h, 1), ("n_branch", f.branch_length, hb, 1)]
        else:                                       # every other fitting has n_layers
            div = 2 * f.n_cuts if name == "MiterBend" else 1
            plan = [("n_layers", _length(e), h, div)]
        counts, reasons = {}, []
        for field, length, cell, div in plan:
            lo = _minimum(e, field)
            if minimal and not straight:
                n = lo
                reasons.append(f"{field} {n}: the fitting's minimum (budget)")
            else:
                n = max(lo, math.ceil(length / (div * ar * cell) - 1e-9))
                why = (f"{field} {n}: length {length:.4g} / ({'2 n_cuts × ' if div > 1 else ''}"
                       f"aspect {ar:g} × core cell {cell:.4g})")
                if n == lo and lo > 1:
                    why += f", raised to the fitting's minimum {lo}"
                reasons.append(why)
            counts[field] = n
        if name == "Tee":
            reasons.append(f"n_turn {f.n_turn}: kept, the junction's own count")
        out[e.index] = {"counts": counts, "reasons": reasons}
    return out


# --- the table and apply ------------------------------------------------------------

TABLE_FORMAT = "hexmesh.agent.resolution"
DENSITY_KEYS = ("nang", "nrad", "nang_w", "nang_h", "mprg", "wall_bump")


def _table(density: dict, axial: dict) -> dict:
    return {"format": TABLE_FORMAT, "version": 1,
            "density": {k: density.get(k) for k in DENSITY_KEYS},
            "fittings": {str(i): a["counts"] for i, a in sorted(axial.items()) if a["counts"]}}


def _shape_with(shape: dict, dens: dict) -> dict:
    shape = dict(shape)
    if shape["type"] == "circle" and dens.get("nang"):
        shape["nang"] = dens["nang"]
    for key in ("nang_w", "nang_h"):
        if key in shape and dens.get(key):
            shape[key] = dens[key]
    return shape


def _spec_with(spec: dict, dens: dict) -> dict:
    """A ``PipeSpec.to_dict()`` with the table's density."""
    spec = copy.deepcopy(spec)
    for key in ("nang", "nang_w", "nang_h"):
        if spec.get(key) is not None and dens.get(key):
            spec[key] = dens[key]
    core = spec["core"]
    core["shape"] = _shape_with(core["shape"], dens)
    if core["layout"] == "oh" and core["shape"]["type"] == "circle":
        core["nrad"] = dens["nrad"]
        core["mprg"] = dens.get("mprg") or 1.0
    elif core["layout"] == "h":
        core["mprg"] = 1.0
        core["wall_bump"] = list(dens.get("wall_bump") or [1.0, 1.0])
    for shell in spec["shells"]:
        if "outer" in shell:
            shell["outer"] = _shape_with(shell["outer"], dens)
    return spec


def apply(description: dict, table: dict) -> dict:
    """*description* (``Assembly.to_dict()``) with the resolution
    *table*'s density in every spec and its axial counts per fitting.
    Build it with ``Assembly.from_dict``."""
    if not isinstance(table, dict) or table.get("format") != TABLE_FORMAT:
        raise _bad(f"not a resolution table (format {TABLE_FORMAT!r})", "table",
                   table.get("format") if isinstance(table, dict) else table)
    d = Assembly.from_dict(description).to_dict()       # validated and upgraded
    dens = table["density"]
    d["inlet"]["spec"] = _spec_with(d["inlet"]["spec"], dens)
    for n in d["inlet"].get("nozzle", {}).get("drum", {}).get("nozzles", []):
        n["spec"] = _spec_with(n["spec"], dens)
    for i, e in enumerate(d["edges"]):
        f = e["fitting"]
        counts = table["fittings"].get(str(i), {})
        unknown = sorted(set(counts) - set(f))
        if unknown:
            raise _bad(f"fitting {i} ({f['type']}) has no field(s) {unknown}",
                       f"fittings.{i}", unknown)
        if f.get("stack_changes") and "n_layers" in counts:   # cell indices scale
            old = f["n_layers"]
            f["stack_changes"] = [[min(max(1, round(j * counts["n_layers"] / old)),
                                       counts["n_layers"] - 1), s]
                                  for j, s in f["stack_changes"]]
        f.update(counts)
        if isinstance(f.get("outlet"), dict) and "core" in f["outlet"]:
            f["outlet"] = _spec_with(f["outlet"], dens)
        if f.get("stack_changes"):
            f["stack_changes"] = [[j, _spec_with(s, dens)] for j, s in f["stack_changes"]]
        if isinstance(f.get("branch"), dict):              # a duct tap's branch shape
            f["branch"] = _shape_with(f["branch"], dens)
        if f["type"] == "Tee":                              # re-derived for the new counts
            for key in ("n_wall", "nrad", "mprg"):
                if f.get(key) is not None:
                    f[key] = None
    return d


# --- advise -------------------------------------------------------------------------

def _round(shape) -> bool:
    return type(shape).side_curve == "arc"


def _tied(asm: Assembly) -> str | None:
    """Why the assembly's counts are tied (nang = nang_w = nang_h), or None
    (decision 0041, task 0100): a circle carries one count, so it ties a
    rectangle it meets.  That is a Transition joining a circle to a
    rectangle, a round duct tap on a rectangle, or a stack with a circle
    and a rectangle.  A stack of rectangles takes the core's (nang_w,
    nang_h) and ties nothing."""
    for e in asm.edges:
        shapes = [o for port in e.ports for o in port.spec.outlines]
        if type(e.fitting).__name__ == "Transition" and \
                any(map(_round, shapes)) and not all(map(_round, shapes)):
            return f"{e.name} (a Transition) joins a circle to a rectangle"
        branch = getattr(e.fitting, "branch", None)
        if type(e.fitting).__name__ == "Tee" and not _round(e.ports[0].spec.core_shape) and \
                (getattr(e.fitting, "branch_radius", None) is not None or
                 branch is not None and _round(branch)):
            return f"{e.name} is a round tap on a duct"
    for i in asm.interfaces:
        outlines = i.spec.outlines
        if any(map(_round, outlines)) and not all(map(_round, outlines)):
            return f"layer {i.spec.layer_names[0]!r}'s stack has a circle and a rectangle"
    return None


def _solve(asm, d, sections, inp, accuracy, ar_straight, minimal, tied):
    secs = copy.deepcopy(sections)
    run = {**inp, "accuracy": accuracy}
    density = _density(secs, run, tied)
    density["reasons"] += _wall(density, secs, run)
    axial = _axial(asm, density, ar_straight, limits.MAX_AXIAL_ASPECT_FITTING, minimal)
    table = _table(density, axial)
    built = Assembly.from_dict(apply(d, table))
    return {"accuracy": accuracy, "ar_straight": ar_straight, "minimal": minimal,
            "sections": secs, "density": density, "axial": axial, "table": table,
            "assembly": built, "cells": built.cell_count()}


def advise(x, inputs: dict) -> dict:
    """The resolution report for *x* (an ``Assembly`` or its ``to_dict()``)
    under *inputs* (module docstring).  Needs no GMSH session."""
    inp = _inputs(inputs)
    if isinstance(x, Assembly):
        d = x.to_dict()
    elif isinstance(x, dict):
        d = Assembly.from_dict(x).to_dict()
    else:
        raise TypeError(f"advise() takes an Assembly or its to_dict() description, "
                        f"not {type(x).__name__}")
    asm = Assembly.from_dict(d)
    sections = _sections(asm, inp)
    scale = LENGTH_UNITS[inp["length_unit"]]
    notes = [HexmeshWarning(calibration()["scope"], code="advice_calibration_scope").to_dict(),
             HexmeshWarning(EIGHT_X, code="advice_eight_x").to_dict()]
    big = max(s["d_h"] for s in sections)
    if big * scale > 5:
        notes.append(HexmeshWarning(f"the largest diameter is {big:g} {inp['length_unit']}: "
                                    "millimetres read as metres?  Set length_unit",
                                    code="advice_length_unit_suspect",
                                    where={"field": "length_unit"}, value=big,
                                    limit={"max": 5}).to_dict())
    for s in sections:
        if s["regime"] == "transitional":
            notes.append(HexmeshWarning(f"{s['name']}: Re {s['re']:.4g} is transitional "
                                        f"({RE_LAMINAR:g}–{RE_TURBULENT:g}); graded as "
                                        "turbulent", code="advice_regime_transitional",
                                        where={"fitting": s["fitting"]}, value=s["re"],
                                        limit=[RE_LAMINAR, RE_TURBULENT]).to_dict())
    tied = _tied(asm)
    acc = inp["accuracy"]
    best = _solve(asm, d, sections, inp, acc, limits.MAX_AXIAL_ASPECT_STRAIGHT, False,
                  tied)
    steps, error = [], None
    budget = inp["budget"]
    if budget is not None and best["cells"] > budget:
        def step(what, r):
            steps.append({"step": what, "cells_before": steps[-1]["cells_after"] if steps
                          else best["cells"], "cells_after": r["cells"]})
            return r
        r = step(f"straights' axial aspect {limits.MAX_AXIAL_ASPECT_STRAIGHT:g} → "
                 f"{limits.MAX_AXIAL_ASPECT_BUDGET:g}",
                 _solve(asm, d, sections, inp, acc, limits.MAX_AXIAL_ASPECT_BUDGET, False,
                        tied))
        while r["cells"] > budget and ACCURACY.index(r["accuracy"]) > 0:
            lower = ACCURACY[ACCURACY.index(r["accuracy"]) - 1]
            r = step(f"accuracy {r['accuracy']} → {lower}",
                     _solve(asm, d, sections, inp, lower, limits.MAX_AXIAL_ASPECT_BUDGET,
                            False, tied))
        if r["cells"] > budget:
            r = step("fittings' axial counts → their minima",
                     _solve(asm, d, sections, inp, r["accuracy"],
                            limits.MAX_AXIAL_ASPECT_BUDGET, True, tied))
        best = r
        if r["cells"] > budget:
            error = AdviceError(
                f"the budget of {budget} cells can't be met: the smallest result has "
                f"{r['cells']} ({r['cells'] / budget - 1:.1%} over)",
                code="advice_budget_unreachable", where={"field": "budget"},
                value=r["cells"], limit={"max": budget},
                hint="raise the budget, or shorten the network").to_dict()
    warned, verror, _ = _checks(best["assembly"])
    return _report(inp, best, steps, notes, error, warned, verror, scale)


def _report(inp, r, steps, notes, error, warned, verror, scale):
    density = r["density"]
    classes = {k: {key: c.get(key) for key in ("class", "case", "series", "n", "validated",
                                                "basis", "errors", "nearest") if key in c}
               for k, c in sorted(density["classes"].items())}
    if not all(c["validated"] for c in classes.values()):
        notes.append(HexmeshWarning("part of this advice rests on no validated case: see "
                                    "calibration[...].validated and basis",
                                    code="advice_not_validated").to_dict())
    if any(s["regime"] != "laminar" for s in r["sections"]):
        notes.append(HexmeshWarning("turbulent wall-resolved resolution: no validated case "
                                    "yet; the core counts reuse the laminar calibration",
                                    code="advice_not_validated").to_dict())
    sections = []
    for s in r["sections"]:
        row = {"fitting": s["fitting"], "name": s["name"], "port": s["port"],
               "interface": s["interface"], "shape": s["shape"],
               "d_h": s["d_h"], "flow_rate": s["flow_rate"], "velocity": s["velocity"],
               "re": s["re"], "regime": s["regime"], "first_cell": s["first_cell"],
               "class": s["class"]["class"], "expected_errors": s["class"].get("errors"),
               "reasons": [f"Re = U D_h / ν = {s['velocity']:.4g} × {s['d_h'] * scale:.4g} m"
                           f" / {inp['fluid']['viscosity'] / inp['fluid']['density']:.4g}"
                           f" = {s['re']:.4g}: {s['regime']} (laminar < {RE_LAMINAR:g}, "
                           f"turbulent > {RE_TURBULENT:g})"]}
        if s.get("wall"):
            w = s["wall"]
            row["y_plus"] = s["y_plus"]
            row["reasons"].append(
                f"first cell for y⁺ {inp['wall']['y_plus']:g}: y = y⁺ ν / u_τ, u_τ = U √(f/8)"
                f" = {w['u_tau']:.4g} m/s, f = {w['friction_factor']:.4g} ({w['source']}); "
                f"meshed {s['first_cell']:.4g} {inp['length_unit']} gives y⁺ {s['y_plus']:.3g}")
        else:
            row["reasons"].append("laminar: the calibrated runs' uniform wall grading; the "
                                  "first cell follows from the class's counts")
        sections.append(row)
    fittings = [{"index": e.index, "name": e.name, "type": type(e.fitting).__name__,
                 "counts": r["axial"][e.index]["counts"],
                 "reasons": r["axial"][e.index]["reasons"]} for e in r["assembly"].edges]
    budget = inp["budget"]
    return _jsonable({
        "format": FORMAT, "version": VERSION, "hexmesh": __version__,
        "ok": error is None and verror is None,
        "inputs": inp,
        "units": {"length": inp["length_unit"], "re": "1", "velocity": "m/s",
                  "flow_rate": "m³/s"},
        "sections": sections,
        "density": {k: density.get(k) for k in DENSITY_KEYS},
        "density_reasons": density["reasons"],
        "fittings": fittings,
        "totals": {"cells": r["cells"], "exact": True, "budget": budget,
                   "within_budget": None if budget is None else r["cells"] <= budget,
                   "accuracy": r["accuracy"]},
        "budget_steps": steps,
        "calibration": classes,
        "table": r["table"],
        "notes": notes,
        "error": error,
        "validation": {"warnings": warned, "error": verror},
    })
