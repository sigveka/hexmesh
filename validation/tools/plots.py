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
Graphs of every validation case, drawn from its stored ``results.json``
alone (task 0099), with no OpenFOAM and no GMSH::

    python3 -m validation.tools.plots [case …]        # from the repository root

Each case gets ``figure.png`` (the gallery's slot): the |error| of its
gated quantities against the relative cell size h/h₁ = 1/k, with order 1 and 2 reference slopes
through the finest point, the gate's tolerance as a band, and each
series' Richardson status and observed order (decision 0015; task 0089)
in the legend.  Four cases get one more graph in ``img/``: the
``rect_duct`` layouts, the ``stenosis`` centreline against the DNS, the
periodic cases' peaks, amplitudes and phases, and ``heated_rod``'s field
errors per series.

The PNGs carry no software or time chunk; a ``source-sha256`` text chunk
holds the hash of the ``results.json`` they were drawn from, which
``tests/test_validation_meta.py`` compares.  Each case's ``RESULTS.md``
embeds its graphs between ``<!-- graphs:start -->`` and
``<!-- graphs:end -->``, rewritten here.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, NullFormatter

ROOT = Path(__file__).resolve().parents[2]
CASES = ("poiseuille", "heated_rod", "layered_conduction", "heated_pipe", "womersley",
         "stenosis", "stenosis_pulsatile", "rect_duct", "mms", "turbulent_pipe", "square_bend",
         "helical_pipe",
         "fenicsx_second_order")

SIZE, DPI = (8.0, 5.0), 200          # 1600 × 1000 px
GRAPHS_START, GRAPHS_END = "<!-- graphs:start -->", "<!-- graphs:end -->"
SHA_KEY, SOURCES_KEY = "source-sha256", "sources"

# Okabe–Ito, without yellow (too faint on white); black is the reference.
SLOTS = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9")
MARKERS = ("o", "s", "^", "D", "v", "P")
REFERENCE = "#000000"
GATE = "#9a9a9a"
# Series that recur keep their colour and marker in every graph.
NAMED = {"h": 0, "cartesian": 1, "oh": 3, "hg": 5, "uniform": 0, "graded": 5}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


conv = _load("convergence", "validation/tools/convergence.py")


def style(key, index: int = 0) -> dict:
    """Colour and marker of a series: a NAMED key, else slot *index*."""
    i = NAMED.get(key, index) % len(SLOTS)
    return {"color": SLOTS[i], "marker": MARKERS[i]}


def source_sha(*cases: str) -> str:
    """The SHA-256 of the cases' ``results.json`` files, in order."""
    h = hashlib.sha256()
    for case in cases:
        h.update((ROOT / "validation" / case / "results.json").read_bytes())
    return h.hexdigest()


def text_chunks(png: Path) -> dict[str, str]:
    """The tEXt chunks of *png*."""
    data, out, i = png.read_bytes(), {}, 8
    while i < len(data):
        n = int.from_bytes(data[i:i + 4], "big")
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if kind == b"tEXt":
            key, value = body.split(b"\0", 1)
            out[key.decode("latin-1")] = value.decode("latin-1")
        i += 12 + n
    return out


def stale(png: Path) -> str | None:
    """Why *png* no longer matches the results it was drawn from, or None."""
    chunks = text_chunks(png)
    if SHA_KEY not in chunks or SOURCES_KEY not in chunks:
        return f"{png.relative_to(ROOT)} has no {SHA_KEY} chunk"
    cases = chunks[SOURCES_KEY].split(",")
    if chunks[SHA_KEY] != source_sha(*cases):
        return (f"{png.relative_to(ROOT)} is stale: validation/{{{','.join(cases)}}}/results.json "
                f"changed; regenerate with python3 -m validation.tools.plots {' '.join(cases)}")
    return None


def _figure(nrows=1, ncols=1, **kw):
    fig = Figure(figsize=SIZE, dpi=DPI, facecolor="white")
    FigureCanvasAgg(fig)
    axes = fig.subplots(nrows, ncols, squeeze=False, **kw)
    return fig, axes


def _plain(text: str) -> str:
    """case.json text for a matplotlib caption: its TeX made plain."""
    for a, b in ((r"\mathrm{", "{"), (r"\,", " "), (r"\ldots", "…"), (r"\le", "≤"),
                 (r"\ge", "≥"), (r"\times", "×"), (r"\Delta", "Δ"), ("$", "")):
        text = text.replace(a, b)
    text = re.sub(r"_\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\^\{([^}]*)\}", r"^\1", text)
    return text.replace("{", "").replace("}", "").replace("`", "")


def _finish(fig, case: str, caption: str, path: Path, sources=None) -> Path:
    meta = json.loads((ROOT / "validation" / case / "case.json").read_text(encoding="utf-8"))
    fig.suptitle(meta["title"], fontsize=10)
    fig.text(0.01, 0.01, _wrap(_plain(caption), 150), fontsize=6.5, color="0.25",
             va="bottom", ha="left")
    fig.tight_layout(rect=(0, 0.035 * (1 + caption.count("\n") + len(caption) // 150), 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    save(fig, path, sources or (case,))
    return path


def save(fig, path: Path, sources) -> None:
    """*fig* as a 256-colour PNG (a third of the RGB size; the graphs have
    a few flat colours) with two text chunks, the cases drawn from and
    their results' hash, and no software or time chunk."""
    from PIL import Image, PngImagePlugin
    fig.canvas.draw()
    rgb = Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[..., :3])
    img = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    info = PngImagePlugin.PngInfo()
    info.add_text(SOURCES_KEY, ",".join(sources))
    info.add_text(SHA_KEY, source_sha(*sources))
    img.save(path, format="PNG", pnginfo=info, optimize=True, dpi=(DPI, DPI))


def _wrap(text: str, width: int) -> str:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return "\n".join(out + [line])


# --- the convergence panel ---------------------------------------------------

def _rich(values, h) -> dict | None:
    """Richardson of the finest three *values*, at the cell sizes *h*."""
    if len(values) < 3:
        return None
    (h3, h2, h1), (f3, f2, f1) = h[-3:], values[-3:]
    return conv.richardson(f3, f2, f1, h2 / h1, h3 / h2)


def _h(levels) -> list[float]:
    """Relative cell size h/h₁ = 1/k of each level, from its refinement
    factor (``k`` or ``factor``), else its ``nang`` against the coarsest.
    Not N^(−1/3): cases that don't refine axially (layered_conduction)
    have 4×, not 8×, the cells per halving."""
    ks = [lv.get("k") or lv.get("factor") for lv in levels]
    if all(ks):
        return [1 / k for k in ks]
    base = min(lv["nang"] for lv in levels)
    return [base / lv["nang"] for lv in levels]


def _status(rich: dict | None, n: int) -> str:
    if rich is None:
        return f"{n} levels"
    if rich["status"] == "converging":
        return f"p = {rich['order']:.2f}, converging"
    return rich["status"].replace("_", " ")


def convergence(ax, series: list[dict], *, ylabel: str, band: tuple | None = None,
                slopes: bool = True, legend: str = "auto") -> None:
    """|error| (%) of each series against h/h₁, log–log.

    A series: ``label``, ``h`` (from ``_h``), ``err`` (signed or absolute, as a
    fraction), optional ``values`` (for Richardson, default ``err``) or
    ``rich`` (a stored result), and ``key`` / ``index`` for its style.
    *band*: (tolerance as a fraction, label)."""
    finest, ys, hs = None, [], set()
    for i, s in enumerate(series):
        x = np.asarray(s["h"], float)
        y = 100 * np.abs(np.asarray(s["err"], float))
        ys += list(y)
        hs |= set(x)
        rich = s.get("rich", _rich(s.get("values", s["err"]), s["h"]))
        st = style(s.get("key"), s.get("index", i))
        ax.loglog(x, y, color=st["color"], marker=st["marker"], markersize=s.get("ms", 6),
                  linewidth=1.5, markerfacecolor=s.get("face", st["color"]),
                  markeredgecolor=st["color"], markeredgewidth=1.2, zorder=3 + s.get("z", 0),
                  label=f"{s['label']} ({_status(rich, len(x))})")
        if finest is None or x[-1] < finest[0] or (x[-1] == finest[0] and y[-1] > finest[1]):
            finest = (x[-1], y[-1])
    if slopes and finest is not None:
        lo, hi = ax.get_xlim()
        xs = np.geomspace(finest[0], hi, 20)
        for p, ls in ((1, (0, (5, 3))), (2, (0, (1, 2)))):
            ax.loglog(xs, finest[1] * (xs / finest[0]) ** p, color="0.45", linewidth=1,
                      linestyle=ls, label=f"order {p}", zorder=1)
        ax.set_xlim(lo, hi)
    lo, hi = min(ys), max(ys)
    if band is not None:
        tol, text = band
        ax.axhspan(lo * 1e-3, 100 * tol, color=GATE, alpha=0.18, linewidth=0, zorder=0,
                   label=text)
        ax.axhline(100 * tol, color=GATE, linewidth=1, zorder=0)
        lo, hi = min(lo, 100 * tol), max(hi, 100 * tol)
    # the data and the gate, over every panel sharing this y axis
    ax._hexmesh_range = (lo, hi)
    shared = [a for a in ax.get_shared_y_axes().get_siblings(ax) if hasattr(a, "_hexmesh_range")]
    lo = min(a._hexmesh_range[0] for a in shared)
    hi = max(a._hexmesh_range[1] for a in shared)
    ax.set_ylim(lo / 1.8, hi * 1.8)
    _axes(ax, "relative cell size h / h₁   (finer to the left)", ylabel)
    # x ticks at the levels: 1, 1/2, 1/4, …
    ax.xaxis.set_major_locator(FixedLocator(sorted(hs)))
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: str(Fraction(v).limit_denominator(64))))
    ax.xaxis.set_minor_formatter(NullFormatter())
    _log_ticks(ax.yaxis, lambda v: f"{v:g}")
    _legend(ax, loc="upper left" if legend == "inside" else "best", inside=legend == "inside")


def _legend(ax, loc="best", inside=False):
    """In the axes for a single panel; under each one when there are several."""
    if len(ax.figure.axes) > 1 and not inside:
        ax.legend(fontsize=6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16),
                  ncol=1)
    else:
        ax.legend(fontsize=6 if inside else 6.5, frameon=False, loc=loc)


def cells_label(v: float) -> str:
    return f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}k" if v >= 1e3 else f"{v:g}"


def _cells_axis(ax):
    ax.set_xscale("log")
    _log_ticks(ax.xaxis, cells_label)


def _log_ticks(axis, fmt):
    """Log ticks at 1, 2, 5 per decade, plainly labelled."""
    axis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
    axis.set_major_formatter(FuncFormatter(lambda v, _: fmt(v)))
    axis.set_minor_formatter(NullFormatter())


def _axes(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, which="major", linewidth=0.4, color="0.85")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _levels(data, **match):
    return [lv for lv in data["levels"] if all(lv.get(k) == v for k, v in match.items())]


def _col(levels, key):
    return [lv[key] for lv in levels]


# --- the cases ---------------------------------------------------------------
# Each returns [(file relative to the case, caption, the RESULTS.md sentence)].

def poiseuille(data, out):
    lv = sorted(data["levels"], key=lambda l: l["cells"])
    fig, ax = _figure()
    convergence(ax[0, 0], [
        {"label": "Δp", "h": _h(lv), "err": _col(lv, "dp_err_signed")},
        {"label": "u_max", "h": _h(lv), "err": _col(lv, "u_max_err_signed")}],
        ylabel="|error| against the exact solution (%)", band=(0.01, "gate: fine level < 1 %"))
    gate = "Gates: extrapolated Δp and u_max within 0.1 % of exact; fine-level |error| < 1 %; " \
           "error falls monotonically; u_max order ≥ 1.5."
    return [_finish(fig, "poiseuille", gate, out / "figure.png"),
            "Δp and u_max errors fall with refinement; u_max at second order, Δp below it."]


def heated_rod(data, out):
    fig, ax = _figure()
    series = []
    for key in ("uniform", "graded"):
        lv = _levels(data, series=key)
        series.append({"label": f"ΔT₀, {key}", "key": key, "h": _h(lv),
                       "err": _col(lv, "dt0_err_signed")})
    convergence(ax[0, 0], series, ylabel="|ΔT₀ error| (% of exact)",
                band=(1e-3, "gate tolerance, on the extrapolated value: 0.1 %"))
    first = [_finish(fig, "heated_rod", "Gate: extrapolated centre excess ΔT₀ within 0.1 % "
                     "of exact (Richardson on k = 4, 8, 16).", out / "figure.png"),
             "The centre excess ΔT₀ of both series against cell size."]
    fig, ax = _figure(1, 2, sharey=True)
    for a, (field, what) in zip(ax[0], (("l2_err", "L2"), ("max_err", "max"))):
        convergence(a, [{"label": f"{what}, {key}", "key": key,
                         "h": _h(_levels(data, series=key)),
                         "err": _col(_levels(data, series=key), field)}
                        for key in ("uniform", "graded")],
                    ylabel=f"{what} error of T (% of ΔT₀ exact)")
    second = [_finish(fig, "heated_rod", "Reported, not gated: the field's L2 and maximum "
                      "errors per series.", out / "img" / "series.png"),
              "The uniform and graded series' L2 and maximum field errors."]
    return first + second


def layered_conduction(data, out):
    lv = _levels(data, variant="fixed")
    cells = _col(lv, "cells")
    h = _h(lv)
    fig, ax = _figure(1, 2, sharey=True)
    convergence(ax[0, 0], [{"label": f"T{s}", "index": i, "h": h,
                            "err": _col(lv, f"t{i}_err")}
                           for i, s in enumerate(("₀", "(r₁)", "(r₂)"))],
                ylabel="|error| (% of the temperature rise)",
                band=(1e-3, "gate tolerance, on the extrapolated value: 0.1 %"))
    convergence(ax[0, 1], [{"label": f"L2, {reg}", "index": i + 3, "h": h,
                            "err": [l["l2"][reg] for l in lv]}
                           for i, reg in enumerate(("rod", "steel", "insulation"))],
                ylabel="L2 error of T (% of the rise)")
    ax[0, 0].set_title("point temperatures (fixed outer wall)", fontsize=8)
    ax[0, 1].set_title("L2 per region (fixed outer wall)", fontsize=8)
    gate = ("Gates: extrapolated T₀, T(r₁), T(r₂) within 0.1 % of exact; L2 order per region "
            "2 ± 0.2; energy balance ≤ 1e-8; checkMesh OK.  The convection variant (not drawn) "
            "falls on the same lines.")
    return [_finish(fig, "layered_conduction", gate, out / "figure.png"),
            "Point temperatures and the L2 error per region, both at second order."]


def heated_pipe(data, out):
    lv = data["levels"]
    cells = _col(lv, "cells")
    h = _h(lv)
    fig, ax = _figure()
    convergence(ax[0, 0], [{"label": "Nu", "h": h, "err": _col(lv, "nu_err")},
                           {"label": "ΔT steel", "h": h, "err": _col(lv, "dt_steel_err")},
                           {"label": "ΔT insulation", "h": h,
                            "err": _col(lv, "dt_insulation_err")}],
                ylabel="|error| against the exact solution (%)",
                band=(5e-3, "ΔT gate tolerance, on the extrapolated value: 0.5 %"))
    gate = ("Gates: extrapolated Nu within 1 % of 48/11, solid ΔTs within 0.5 %; energy "
            "balance within 0.1 %; checkMesh OK per region.")
    return [_finish(fig, "heated_pipe", gate, out / "figure.png"),
            "The Nusselt number and the solid temperature differences against cell size."]


def womersley(data, out):
    lv = [l for l in data["levels"] if l.get("dt_factor", 1.0) == 1.0]
    cells = _col(lv, "cells")
    h = _h(lv)
    fig, ax = _figure()
    convergence(ax[0, 0], [
        {"label": "pressure-gradient amplitude", "h": h,
         "err": _col(lv, "dpdx_amplitude_err")},
        {"label": "centreline at peak, u_c", "h": h, "err": _col(lv, "u_axis_peak_err")},
        {"label": "max profile error, every phase", "h": h,
         "err": _col(lv, "profile_max_all")}],
        ylabel="|error| (% of the exact amplitude, or of u_c)",
        band=(0.01, "gate: finest level ≤ 1 %"))
    gate = ("Gates: max profile error ≤ 1 % of u_c at the finest level; amplitude within 1 % "
            "and phase within 2°; time error below space error; periodic.  The k2 level at "
            "twice the time step is not drawn.")
    return [_finish(fig, "womersley", gate, out / "figure.png"),
            "Amplitude, centreline and profile errors against cell size.",
            "../stenosis_pulsatile/img/periodic.png", "The pressure-gradient amplitude and "
            "phase per level against the exact solution, beside the pulsatile stenosis's "
            "throat peak (drawn with stenosis_pulsatile)."]


def stenosis(data, out):
    lv = data["levels"]
    ref = data["extra"]["reference"]
    cells = _col(lv, "cells")
    h = _h(lv)
    peak = max(ref["centre"].values())
    fig, ax = _figure()
    convergence(ax[0, 0], [
        {"label": "reattachment, τ_w = 0", "h": h,
         "err": [l["x_reattachment"] / ref["reattachment"] - 1 for l in lv],
         "values": _col(lv, "x_reattachment")},
        {"label": "reattachment, u(0.48 D) = 0", "h": h,
         "err": [l["x_reattachment_probe"] / ref["reattachment"] - 1 for l in lv],
         "values": _col(lv, "x_reattachment_probe")},
        {"label": "max centreline error (of the DNS peak)", "h": h,
         "err": [max(abs(e) for e in l["compare"]["centre_err_peak"] if e is not None)
                 for l in lv], "values": [l["u_peak"] for l in lv]}],
        ylabel="|difference from the DNS| (%)", slopes=False,
        band=(0.02, "centreline gate: 2 % of the DNS peak"))
    a = ax[0, 0]
    a.set_ylim(a.get_ylim()[0], max(a.get_ylim()[1], 10))
    a.axhline(5, color=GATE, linewidth=1, linestyle=(0, (4, 2)))
    a.text(a.get_xlim()[0], 5, " reattachment gate: 5 %", fontsize=6.5, ha="left", va="bottom",
           color="0.35")
    first = [_finish(fig, "stenosis", "Gates: reattachment within 5 % of the DNS's 11.03 D "
                     "(both measures); centreline x/D = −2 … 15 within 2 % of the DNS peak.  "
                     "No reference slopes: against the DNS the error has a floor, not an order; "
                     "Richardson in the legend is of the values (the centreline's: u_peak).",
                     out / "figure.png"),
             "Reattachment and centreline differences from the DNS against cell size."]

    fig, ax = _figure(1, 2, gridspec_kw={"width_ratios": (2.2, 1)})
    a = ax[0, 0]
    for i, l in enumerate(lv):
        st = style(None, i)
        xu = np.asarray(l["centreline"], float)
        a.plot(xu[:, 0], xu[:, 1], color=st["color"], linewidth=1.5,
               label=f"{l['name']} ({l['cells']:,} cells)".replace(",", " "))
    xs = sorted(float(k) for k in ref["centre"])
    a.plot(xs, [ref["centre"][_key(ref["centre"], x)] for x in xs], linestyle="none",
           marker="o", markersize=5, markerfacecolor="white", markeredgecolor=REFERENCE,
           label="DNS stations")
    a.axvline(0, color="0.6", linewidth=0.8, linestyle=(0, (2, 2)))
    a.text(0.15, peak + 0.05, "throat", fontsize=6.5, color="0.35")
    a.axvline(ref["reattachment"], color=REFERENCE, linewidth=0.8, linestyle=(0, (5, 3)))
    a.text(ref["reattachment"] + 0.15, peak, f"DNS reattachment {ref['reattachment']:.2f} D",
           fontsize=6.5, color="0.2", va="top")
    a.set_xlim(-3, 16)
    _axes(a, "x / D", "centreline u / U (U: bulk)")
    a.legend(fontsize=6.5, frameon=False, loc="lower center")
    b = ax[0, 1]
    for j, (field, what) in enumerate((("x_reattachment", "τ_w = 0"),
                                       ("x_reattachment_probe", "u(0.48 D) = 0"))):
        st = style(None, 3 + j)
        b.plot(cells, _col(lv, field), color=st["color"], marker=st["marker"], linewidth=1.5,
               label=what)
    r = ref["reattachment"]
    b.axhspan(0.95 * r, 1.05 * r, color=GATE, alpha=0.18, linewidth=0, label="DNS ± 5 % (gate)")
    b.axhline(r, color=REFERENCE, linewidth=1, label="DNS")
    _cells_axis(b)
    _axes(b, "cells", "reattachment x / D")
    b.legend(fontsize=6.5, frameon=False, loc="lower right")
    second = [_finish(fig, "stenosis", "Left: the centreline velocity of each level, with "
                      "the DNS stations; the throat at x = 0.  Right: the reattachment length "
                      "per level by both measures, against the DNS's.",
                      out / "img" / "centreline.png"),
              "The centreline velocity of each level against the DNS stations, and the "
              "reattachment length per level."]
    return first + second


def _key(d: dict, x: float) -> str:
    return next(k for k in d if float(k) == x)


def stenosis_pulsatile(data, out):
    lv = [l for l in data["levels"] if l.get("max_co") == 0.5]
    cells = _col(lv, "cells")
    h = _h(lv)
    dns = lv[0]["dns_throat_peak"]
    fig, ax = _figure()
    convergence(ax[0, 0], [{"label": "throat peak (p2, x = 0)", "h": h,
                            "err": [l["throat_peak"] / dns - 1 for l in lv],
                            "values": _col(lv, "throat_peak")}],
                ylabel="|throat peak − DNS| (% of the DNS)",
                band=(0.05, "gate: within 5 % of the DNS"))
    first = [_finish(fig, "stenosis_pulsatile", "Gates: throat centreline velocity at peak "
                     "flow within 5 % of the DNS and above 3.65 u_c; the flow features of the "
                     "paper's §3.1 present.  The time-step level (Co 0.25) is not drawn.",
                     out / "figure.png"),
             "The throat peak's difference from the DNS against cell size."]
    return first + _periodic(data, out)


def _periodic(pulsatile, out):
    """img/periodic.png in stenosis_pulsatile: its throat peak, and
    Womersley's amplitude and phase, per level against the references."""
    wom = json.loads((ROOT / "validation/womersley/results.json").read_text(encoding="utf-8"))
    fig, ax = _figure(1, 3)
    lv = [l for l in pulsatile["levels"] if l.get("max_co") == 0.5]
    dns = lv[0]["dns_throat_peak"]
    a = ax[0, 0]
    st = style(None, 0)
    a.plot(_col(lv, "cells"), _col(lv, "throat_peak"), color=st["color"], marker=st["marker"],
           linewidth=1.5, label="hexmesh")
    a.axhspan(0.95 * dns, 1.05 * dns, color=GATE, alpha=0.18, linewidth=0, label="DNS ± 5 %")
    a.axhline(dns, color=REFERENCE, linewidth=1, label=f"DNS {dns}")
    a.axhline(3.65, color=GATE, linewidth=1, linestyle=(0, (4, 2)), label="floor 3.65")
    _cells_axis(a)
    a.set_title("stenosis_pulsatile: throat peak", fontsize=8)
    _axes(a, "cells", "u / u_c at the throat, peak flow")
    a.legend(fontsize=6.5, frameon=False, loc="lower right")
    w = [l for l in wom["levels"] if l.get("dt_factor", 1.0) == 1.0]
    cells = _col(w, "cells")
    h = _h(w)
    st = style(None, 1)
    b = ax[0, 1]
    b.plot(cells, [100 * e for e in _col(w, "dpdx_amplitude_err")], color=st["color"],
           marker=st["marker"], linewidth=1.5, label="hexmesh")
    b.axhspan(-1, 1, color=GATE, alpha=0.18, linewidth=0, label="gate ± 1 %")
    b.axhline(0, color=REFERENCE, linewidth=1, label="exact")
    _cells_axis(b)
    b.set_title("womersley: ∂p/∂x amplitude", fontsize=8)
    _axes(b, "cells", "amplitude error (% of exact)")
    b.legend(fontsize=6.5, frameon=False, loc="upper right")
    c = ax[0, 2]
    c.plot(cells, _col(w, "dpdx_phase_deg"), color=st["color"], marker=st["marker"],
           linewidth=1.5, label="hexmesh")
    c.axhspan(-2, 2, color=GATE, alpha=0.18, linewidth=0, label="gate ± 2°")
    c.axhline(0, color=REFERENCE, linewidth=1, label="exact")
    _cells_axis(c)
    c.set_title("womersley: ∂p/∂x phase", fontsize=8)
    _axes(c, "cells", "phase error (°)")
    c.legend(fontsize=6.5, frameon=False, loc="upper right")
    _finish(fig, "stenosis_pulsatile", "Left: the throat peak per level against the DNS "
            "(Varghese et al.), gate within 5 % and above 3.65 u_c.  Middle and right: the "
            "Womersley case's axial pressure-gradient amplitude and phase per level against "
            "the exact solution, gates within 1 % and 2° at the finest level.",
            out / "img" / "periodic.png", sources=("stenosis_pulsatile", "womersley"))
    return ["img/periodic.png", "The pulsatile throat peak, and Womersley's pressure-gradient "
            "amplitude and phase, per level against their references."]


def rect_duct(data, out):
    fig, ax = _figure(1, 3, sharey=True)
    for a, ratio in zip(ax[0], (1, 2, 4)):
        series = []
        for key, what in (("h", "H, f·Re"), ("h", "H, u_c")):
            lv = sorted(_levels(data, mesh="h", ratio=ratio), key=lambda l: l["cells"])
            q = "fRe" if "f·Re" in what else "u_c"
            series.append({"label": what, "index": 0 if q == "fRe" else 2,
                           "h": _h(lv),
                           "err": (_col(lv, "fRe_err_signed") if q == "fRe" else
                                   [l["u_c_err_signed"] - l["u_c_sampling_err"] for l in lv])})
        convergence(a, series, ylabel="|error| against the exact series (%)" if ratio == 1
                    else "", band=(0.01, "gate: finest < 1 %"))
        a.set_title(f"a/b = {ratio}", fontsize=8)
    first = [_finish(fig, "rect_duct", "The H section (the accepted hexmesh result); u_c net of "
                     "the centre fit's bias.  Gates: extrapolated f·Re and u_c within 0.1 % of "
                     "exact, finest |error| < 1 %, observed order 2 ± 0.2, converging.",
                     out / "figure.png"),
             "The H section's f·Re and centreline errors for each aspect ratio."]
    fig, ax = _figure(1, 3, sharey=True)
    names = {"h": "H", "hg": "graded H", "oh": "O-H", "cartesian": "Cartesian control"}
    for a, ratio in zip(ax[0], (1, 2, 4)):
        series = []
        for mesh in ("cartesian", "h", "hg", "oh"):
            lv = sorted(_levels(data, mesh=mesh, ratio=ratio), key=lambda l: l["cells"])
            if not lv:
                continue
            ctrl = mesh == "cartesian"
            series.append({"label": names[mesh], "key": mesh, "h": _h(lv),
                           "err": _col(lv, "fRe_err_signed"), "ms": 10 if ctrl else 5,
                           "face": "none" if ctrl else None, "z": -1 if ctrl else 0})
        convergence(a, series, ylabel="|f·Re error| (%)" if ratio == 1 else "")
        a.set_title(f"a/b = {ratio}", fontsize=8)
    second = [_finish(fig, "rect_duct", "f·Re against cells for each layout and aspect ratio "
                      "(decision 0036).  The H section and the Cartesian control (open "
                      "markers) give the same numbers, on one second-order line; O-H converges "
                      "irregularly.  Graded H runs at a/b = 2 only.", out / "img" / "layouts.png"),
              "f·Re for the four layouts: H and the Cartesian control coincide; O-H doesn't "
              "converge regularly."]
    return first + second


MMS_GROUPS = (("straight runs", ("straight", "bend", "miter", "spline")),
              ("size and shape changes", ("reducer", "transition", "stack_change", "duct")),
              ("tees and taps", ("tee", "tee_shells", "duct_tap_rect", "duct_tap_round")),
              ("wyes", ("wye60", "wye90", "wye60_shell", "wye90_shell")))


def mms(data, out):
    fig, ax = _figure(2, 2, sharex=True, sharey=True)
    for a, (title, cases) in zip(ax.flat, MMS_GROUPS):
        series = []
        for i, c in enumerate(cases):
            lv = sorted((l for l in data["levels"] if l["case"] == c and l["k"] in (1, 2, 4)
                         and l.get("converged")), key=lambda l: l["cells"])
            series.append({"label": c, "index": i, "h": _h(lv), "ms": 4.5,
                           "err": [l["all"]["l2"] for l in lv]})
        convergence(a, series, ylabel="L2 error of T (%)", legend="inside")
        a.set_title(title, fontsize=8)
        if a not in ax[1]:
            a.set_xlabel("")
    first = [_finish(fig, "mms", "Gate: the L2 error falls with refinement, every fitting.  "
                     "Orders are reported, not gated (decision 0015 as amended); the duct taps' "
                     "k = 4 levels didn't converge and aren't drawn.", out / "figure.png"),
             "The L2 error of the manufactured solution on every fitting against cell size."]
    return first + mms_slope(data, out)


#: task 0109's reducer series: case → s0 (as ``validation/mms/run.py``'s SLOPE_S0)
MMS_SLOPE = {"reducer_s005": 0.05, "reducer_s010": 0.1, "reducer_s020": 0.2,
             "reducer_s040": 0.4}


def mms_slope(data, out):
    """Task 0109: the L2 order in the reducer (k 2 → 4) against its median
    wall non-orthogonality at k = 4, with the wall at the exact value and,
    as the control, at the exact flux."""
    by = {(l["case"], l["k"]): l for l in data["levels"] if l.get("converged")}
    if not all((c, k) in by for c in MMS_SLOPE for k in (2, 4)):
        return []
    fig, ax = _figure()
    ax = ax[0, 0]
    for i, (label, suffix) in enumerate((("wall at the exact value (fixedValue)", ""),
                                         ("control: wall at the exact flux (fixedGradient)",
                                          "_flux"))):
        st = style(None, i)
        xs, ys = [], []
        for c, s0 in MMS_SLOPE.items():
            a, b = by[(c + suffix, 2)], by[(c + suffix, 4)]
            xs.append(by[(c, 4)]["focus_wall_nonorth"]["median"])
            ys.append(np.log(a["focus"]["l2"] / b["focus"]["l2"]) / np.log(2))
            if not suffix:
                ax.annotate(f"s0 = {s0:g}", (xs[-1], ys[-1]), textcoords="offset points",
                            xytext=(6, -10), fontsize=6.5, color="0.3")
        ax.plot(xs, ys, color=st["color"], marker=st["marker"], markersize=6, linewidth=1.5,
                label=label, zorder=3)
    for p in (1, 2):
        ax.axhline(p, color="0.45", linewidth=1, linestyle=(0, (5, 3)) if p == 1 else (0, (1, 2)),
                   label=f"order {p}", zorder=1)
    if ("straight", 2) in by and ("straight", 4) in by:
        p = np.log(by[("straight", 2)]["focus"]["l2"] / by[("straight", 4)]["focus"]["l2"]) \
            / np.log(2)
        ax.axhline(p, color=GATE, linewidth=1.5, label=f"the straight pipe: {p:.2f}", zorder=1)
    ax.set_ylim(0, 2.4)
    _axes(ax, "median wall-face non-orthogonality in the reducer, k = 4 (°)",
          "observed L2 order in the reducer, k 2 → 4")
    _legend(ax, loc="lower left")
    return [_finish(fig, "mms", "Task 0109: the cosine reducer at four constrictions (s0; "
                    "the wall's largest slope atan(π s0 / 2) is 4.5°, 8.9°, 17.4°, 32.1°), "
                    "Gauss linear corrected, laplacianFoam v2406.  The control is the same mesh "
                    "with n·∇T imposed at the wall, which OpenFOAM's uncorrected boundary "
                    "snGrad then doesn't enter.", out / "img" / "slope.png"),
            "The reducer's order against its wall non-orthogonality, with the exact-flux "
            "control."]


def turbulent_pipe(data, out):
    lv = sorted(_levels(data, case="lowre_550"), key=lambda l: l["cells"])
    rich = data["extra"]["richardson_lowre_550"]
    cells = _col(lv, "cells")
    h = _h(lv)
    fig, ax = _figure()
    convergence(ax[0, 0], [
        {"label": "f, from the extrapolated", "h": h, "rich": rich["f"],
         "err": [l["f"] / rich["f"]["extrapolated"] - 1 for l in lv]},
        {"label": "U_c/U_b, from the extrapolated", "h": h, "rich": rich["uc_over_ub"],
         "err": [l["uc_over_ub"] / rich["uc_over_ub"]["extrapolated"] - 1 for l in lv]},
        {"label": "f, from McKeon eq. 3.5", "index": 3, "h": h,
         "err": _col(lv, "f_err_mckeon"), "rich": rich["f"]}],
        ylabel="|difference| (%)", band=(0.03, "f gate, finest level: 3 % of McKeon"))
    return [_finish(fig, "turbulent_pipe", "Wall-resolved, Re_τ 550, k = 1, 2, 4.  Gates: "
                    "Richardson status converging for f and U_c/U_b; f within 3 % of McKeon et "
                    "al. at the finest level (and 5 % with Spalding wall functions, not drawn).  "
                    "The first two series are distances from their own extrapolated values.",
                    out / "figure.png"),
            "f and U_c/U_b at Re_τ 550 against cell size, from their extrapolated values and "
            "from McKeon et al."]


def square_bend(data, out):
    rich = data["extra"]["richardson_peak_u"]["matched"]
    lv = sorted(_levels(data, inlet="matched"), key=lambda l: l["cells"])
    cells = _col(lv, "cells")
    h = _h(lv)
    fig, ax = _figure()
    series = []
    for i, st in enumerate(sorted(rich)):
        r = rich[st]
        if r["extrapolated"] is None:
            continue
        series.append({"label": f"peak U/V_c, {st.replace('theta=', 'θ = ')}°", "index": i,
                       "h": h, "rich": r,
                       "err": [l["stations"][st]["peak_u_symmetry"] / r["extrapolated"] - 1
                               for l in lv]})
    convergence(ax[0, 0], series, ylabel="|peak − extrapolated| (% of the extrapolated)")
    return [_finish(fig, "square_bend", "Matched inlet, symmetry plane.  Gate: the peak's "
                    "Richardson status converging (GCI reported); the peak's gapwise position "
                    "at the measured point (not drawn).", out / "figure.png"),
            "The peak velocity at θ = 60° and 77.5° against cell size, from its extrapolated "
            "value."]


def helical_pipe(data, out):
    fig, ax = _figure()
    series = []
    for i, re_ in enumerate(sorted({l["re"] for l in data["levels"] if "re" in l})):
        lv = sorted((l for l in data["levels"] if l.get("re") == re_ and l.get("f") is not None),
                    key=lambda l: l["cells"])
        series.append({"label": f"Re {re_}: f", "index": i, "h": _h(lv),
                       "err": _col(lv, "f_err_ito")})
    convergence(ax[0, 0], series, ylabel="|f − Ito| (% of Ito)", slopes=False,
                band=(0.05, "gate: within 5 % of Ito"))
    return [_finish(fig, "helical_pipe", "In progress: nang 24 not yet run.  Gate: f within "
                    "5 % of Ito's correlation at nang 16.  No reference slopes: a correlation "
                    "is not an exact solution.", out / "figure.png"),
            "The friction factor's difference from Ito's correlation per level."]


def fenicsx_second_order(data, out):
    rows = (("Hex8", 1, "Q1 on Hex8"), ("Hex8", 2, "Q2 on Hex8"), ("Hex27", 2, "Q2 on Hex27"))
    fig, ax = _figure(1, 3, sharey=True)
    for a, case in zip(ax.flat, ("straight", "bend", "tee")):
        series = []
        for i, (geometry, degree, label) in enumerate(rows):
            lv = sorted(_levels(data, case=case, geometry=geometry), key=lambda l: l["k"])
            err = [next(s["l2"] / s["l2_norm"] for s in l["solves"]
                        if s["degree"] == degree and s["variant"] == "neumann") for l in lv]
            series.append({"label": label, "index": i, "h": _h(lv), "err": err, "rich": None})
        convergence(a, series, ylabel="relative L2 error of u (%)", slopes=False)
        h = np.array(sorted({x for s in series for x in s["h"]}))
        y0 = 100 * series[-1]["err"][-1]
        for p_, ls in ((2, (0, (1, 2))), (3, (0, (5, 3)))):
            a.plot(h, y0 * (h / h.min()) ** p_, color="0.45", linewidth=1, linestyle=ls,
                     label=f"order {p_}", zorder=1)
        _legend(a)
        a.set_title(case, fontsize=8)
        if a is not ax.flat[0]:
            a.set_ylabel("")
    return [_finish(fig, "fenicsx_second_order",
                    "Neumann data from the exact wall (its normal, not the mesh's).  Gate: Q2 on "
                    "the Hex27 mesh converges at order >= 2.7 (pairwise orders in RESULTS.md); Q2 "
                    "on the linear mesh is lower, pulled towards 2 by the straight-sided wall.",
                    out / "figure.png"),
            "The relative L2 error of the manufactured solution against cell size, per mesh "
            "and element."]


# --- the driver --------------------------------------------------------------

def draw(case: str) -> list[tuple[str, str]]:
    """Draw *case*'s graphs; returns [(path relative to the case, sentence)]."""
    here = ROOT / "validation" / case
    data = json.loads((here / "results.json").read_text(encoding="utf-8"))
    flat = globals()[case](data, here)
    out = []
    for path, sentence in zip(flat[::2], flat[1::2]):
        rel = Path(path).relative_to(here) if Path(path).is_absolute() else Path(path)
        if not (here / rel).exists():
            raise FileNotFoundError(f"validation/{case}/{rel}: draw its case first")
        out.append((rel.as_posix(), sentence))
    return out


def graphs_md(graphs) -> str:
    lines = [GRAPHS_START, "## Graphs", "",
             "_Drawn from `results.json` by `python3 -m validation.tools.plots`; don't edit "
             "between the markers._", ""]
    for rel, sentence in graphs:
        lines += [f'<img src="{rel}" width="100%" alt="{sentence}">', "", sentence, ""]
    return "\n".join(lines + [GRAPHS_END])


def embed(case: str, graphs) -> None:
    """Rewrite the graphs section of *case*'s RESULTS.md, or put it before
    the first ``## `` heading."""
    path = ROOT / "validation" / case / "RESULTS.md"
    text = path.read_text(encoding="utf-8")
    block = graphs_md(graphs)
    if GRAPHS_START in text:
        a, b = text.index(GRAPHS_START), text.index(GRAPHS_END) + len(GRAPHS_END)
        text = text[:a] + block + text[b:]
    else:
        m = re.search(r"^## ", text, flags=re.M)
        at = m.start() if m else len(text)
        text = text[:at] + block + "\n\n" + text[at:]
    path.write_text(text, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases", nargs="*", metavar="case", help=f"default: all of {', '.join(CASES)}")
    args = ap.parse_args(argv)
    unknown = sorted(set(args.cases) - set(CASES))
    if unknown:
        ap.error(f"unknown case(s) {', '.join(unknown)}; known: {', '.join(CASES)}")
    # stenosis_pulsatile draws the periodic graph womersley embeds
    cases = sorted(args.cases or CASES, key=lambda c: c == "womersley")
    for case in cases:
        graphs = draw(case)
        embed(case, graphs)
        for rel, _ in graphs:
            p = ROOT / "validation" / case / rel
            print(f"validation/{case}/{rel}  {p.stat().st_size // 1024} kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
