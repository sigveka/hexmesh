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
"""A picture of a network before meshing: ``preview()`` (task 0097).

``preview(x, path)`` draws an ``Assembly``, its saved description or a
``NetworkModel`` to a PNG:
- the centrelines;
- each interface's outer section outline, from its frame and shape;
- labels at the fittings and the open ends (their patch names);
- three orthographic views (top, front, side) and an isometric one.

No GMSH: the geometry is ``describe``'s (the fittings' paths).  It
needs matplotlib, the ``hexmesh[preview]`` extra.  The PNG is
deterministic: a fixed size and DPI, no timestamp or software tag.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from hexmesh import Assembly
from hexmesh.interchange import NetworkModel

from ._describe import centreline

SIZE = (12.0, 9.0)        # inches
DPI = 100
#: (title, the two world axes drawn as x and y): top, front, side
VIEWS = (("top (x, y)", (0, 1)), ("front (x, z)", (0, 2)), ("side (y, z)", (1, 2)))
#: the isometric view's screen axes: x and y unit vectors in world space
_ISO_X = np.array([1.0, -1.0, 0.0]) / math.sqrt(2)
_ISO_Y = np.array([-1.0, -1.0, 2.0]) / math.sqrt(6)
_SEGMENTS = 48            # points per circle outline


def preview(x, path) -> Path:
    """Draw *x* (an ``Assembly``, its ``to_dict()`` description or a
    ``NetworkModel``) to the PNG *path*; returns the path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib.figure import Figure
    except ImportError as e:            # pragma: no cover - the extra is missing
        raise ImportError("preview() needs matplotlib: pip install 'hexmesh[preview]'") from e
    if isinstance(x, dict):
        x = Assembly.from_dict(x)
    if isinstance(x, NetworkModel):
        lines, outlines, labels = _model_geometry(x)
    elif isinstance(x, Assembly):
        lines, outlines, labels = _assembly_geometry(x)
    else:
        raise TypeError(f"preview() takes an Assembly, its to_dict() description or a "
                        f"NetworkModel, not {type(x).__name__}")
    fig = Figure(figsize=SIZE, dpi=DPI)
    axes = fig.subplots(2, 2)
    projections = [(t, (lambda p, ij=ij: p[..., list(ij)])) for t, ij in VIEWS]
    projections.append(("isometric", lambda p: np.stack([p @ _ISO_X, p @ _ISO_Y], axis=-1)))
    for ax, (title, project) in zip(axes.flat, projections):
        for c in outlines:
            q = project(c)
            ax.plot(q[:, 0], q[:, 1], color="0.6", linewidth=0.6)
        for c in lines:
            q = project(c)
            ax.plot(q[:, 0], q[:, 1], color="C0", linewidth=1.4)
        for text, p, kind in labels:
            q = project(p)
            ax.annotate(text, q, fontsize=7, color="0.15" if kind == "fitting" else "C3",
                        xytext=(3, 3), textcoords="offset points")
            if kind == "end":
                ax.plot([q[0]], [q[1]], "o", color="C3", markersize=3)
        ax.set_title(title, fontsize=9)
        ax.set_aspect("equal", adjustable="datalim")
        ax.tick_params(labelsize=7)
        ax.grid(True, linewidth=0.3)
    fig.tight_layout()
    path = Path(path)
    fig.savefig(path, format="png", dpi=DPI, metadata={"Software": None})
    return path


def outline(frame, shape, rot: float) -> np.ndarray:
    """*shape*'s outline in *frame*'s plane: a closed polyline.  A rectangle
    has ``half_w`` along ``frame.right`` and ``half_h`` along ``frame.up``,
    rotated by *rot* degrees."""
    d = shape.to_dict()
    if d["type"] == "circle":
        t = np.linspace(0, 2 * math.pi, _SEGMENTS + 1)
        uv = d["radius"] * np.stack([np.cos(t), np.sin(t)], axis=1)
    else:
        w, h = d["half_w"], d["half_h"]
        uv = np.array([[w, h], [-w, h], [-w, -h], [w, -h], [w, h]])
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    uv = uv @ np.array([[c, s], [-s, c]])
    return frame.position + uv[:, :1] * frame.right + uv[:, 1:] * frame.up


def _assembly_geometry(asm: Assembly):
    lines, labels = [], []
    for e in asm.edges:
        cs = centreline(e)
        lines += cs
        mid = _midpoint(cs[0]) if len(cs) == 1 else cs[0][-1]      # a junction: its centre
        labels.append((e.name, mid, "fitting"))
    outlines = [outline(i.frame, i.spec.outlines[-1], i.spec.rot) for i in asm.interfaces]
    labels += [(asm.patch_name(i), i.frame.position, "end") for i in asm.open_interfaces()]
    return lines, outlines, labels


def _model_geometry(m: NetworkModel):
    lines, labels = [], []
    for p in m.parts.values():
        pts = [q for q in m.positions(p) if q is not None]
        centre = getattr(p, "centre", None)
        if centre is not None and len(pts) > 2:        # a junction: runs from its centre
            lines += [np.array([centre, q], dtype=float) for q in pts]
        elif getattr(p, "corner", None) is not None and len(pts) == 2:
            lines.append(np.array([pts[0], p.corner, pts[1]], dtype=float))
        elif len(pts) >= 2:
            lines.append(np.array(pts, dtype=float))
        if pts:
            labels.append((f"{p.name or p.id} (rejected)" if p.reject else p.name or p.id,
                           np.mean(pts, axis=0), "rejected" if p.reject else "fitting"))
    return lines, [], labels


def _midpoint(c: np.ndarray) -> np.ndarray:
    """The point halfway along polyline *c*, by arc length."""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))])
    return np.array([np.interp(s[-1] / 2, s, c[:, k]) for k in range(3)])
