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
Predicted cross-section quality, without GMSH (DESIGN P3; task 0047,
decision 0026 item 4).

A sweep fitting's hexes are its face's quads carried along the axis.  On a
straight, every hex is a quad extruded at right angles, so:

* its corner scaled Jacobian (``quality_hex.scaled_jacobian``, Knupp) is the
  quad's smallest corner sine;
* OpenFOAM's non-orthogonality of a face between two hexes is the angle,
  in the section plane, between the shared edge's normal and the line
  joining the two quads' centroids (the extruded prisms' cell centres).

Bends change both by at most about 0.02 in SJ (task 0047's sweep).  So the
face alone predicts the quality, and ``section_quality`` builds the face's
quads the way the face builders and GMSH's transfinite meshing do:

* boundary nodes at the side fractions of a ``Bump`` spacing (``mbmp``),
  along each side as its outline draws it (``Shape.side``; the core's O-H
  curves from ``shape.outline``);
* radial nodes at a ``Progression`` spacing (``mprg``) along straight
  corner lines;
* interior nodes by transfinite interpolation: a ring's patch is the linear
  blend of its two boundaries, exactly (its other two sides are straight);
  the core's centre patch is a Coons patch on chord-length fractions.

Checked against meshed straights for every case of
``benchmarks/outline_quality.py`` (task 0047): within 0.01 SJ and 1°.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .errors import AssemblyError
from ..core.grading import bump, progression      # noqa: F401 (re-exported)
from ..sections import layout_of
from ..core.spec import PipeSpec
from .limits import OUTLINE_NONORTH_MAX, OUTLINE_NONORTH_WARN, PREDICTED_SJ_MIN, PREDICTED_SJ_WARN


@dataclass(frozen=True)
class LayerQuality:
    """Predicted quality of one layer of a section (straight extrusion)."""

    name:          str
    min_sj:        float   # smallest corner scaled Jacobian
    max_non_ortho: float   # largest non-orthogonality, degrees, of its faces

    def __str__(self) -> str:
        return (f"`{self.name}`: corner SJ {self.min_sj:.3f}, "
                f"non-orthogonality {self.max_non_ortho:.1f}°")


# ---------------------------------------------------------------------------
# Node spacing along a transfinite curve (GMSH 4.12, meshGEdge.cpp)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# The section's quads
# ---------------------------------------------------------------------------

def _quads(grid: np.ndarray) -> np.ndarray:
    """(n, 4, 2) quads of a node grid, counter-clockwise."""
    q = np.stack([grid[:-1, :-1], grid[1:, :-1], grid[1:, 1:], grid[:-1, 1:]], axis=2)
    q = q.reshape(-1, 4, 2)
    area = _signed_area(q)
    return q if area.sum() > 0 else q[:, ::-1]


def _signed_area(q: np.ndarray) -> np.ndarray:
    x, y = q[..., 0], q[..., 1]
    return 0.5 * (x * np.roll(y, -1, axis=1) - np.roll(x, -1, axis=1) * y).sum(axis=1)


def _corner_sines(q: np.ndarray) -> np.ndarray:
    """Smallest corner sine of each (counter-clockwise) quad; < 0 if folded."""
    e1 = np.roll(q, -1, axis=1) - q
    e2 = np.roll(q, 1, axis=1) - q
    cross = e1[..., 0] * e2[..., 1] - e1[..., 1] * e2[..., 0]
    return (cross / (np.linalg.norm(e1, axis=2) * np.linalg.norm(e2, axis=2))).min(axis=1)


def _centroids(q: np.ndarray) -> np.ndarray:
    x, y = q[..., 0], q[..., 1]
    xn, yn = np.roll(x, -1, axis=1), np.roll(y, -1, axis=1)
    c = x * yn - xn * y
    a = 3.0 * c.sum(axis=1)
    return np.stack([((x + xn) * c).sum(axis=1) / a, ((y + yn) * c).sum(axis=1) / a], axis=1)


def section_quality(spec: PipeSpec) -> list[LayerQuality]:
    """Predicted min corner scaled Jacobian and max non-orthogonality of
    each layer of *spec*'s section, core first (pure Python).

    A layer's non-orthogonality includes the faces it shares with the
    layer inside it.  Needs circle and rectangle outlines and
    ``n_outer = 4``, as ``check_supported``.
    """
    if spec.n_outer != 4 or any(o.is_station for o in spec.outlines):
        raise AssemblyError("section_quality needs circle and rectangle "
                            "outlines and n_outer = 4",
                            code="section_not_supported",
                            hint="use circle or rectangle layers and n_outer=4")
    quads, layer = [], []
    for i, grid in layout_of(spec).node_grids(spec):
        q = _quads(grid)
        quads.append(q)
        layer.append(np.full(len(q), i))
    q, layer = np.concatenate(quads), np.concatenate(layer)
    sj = _corner_sines(q)
    centre = _centroids(q)

    # interior edges: shared by two quads (keys from rounded coordinates;
    # neighbouring patches compute their shared nodes the same way)
    scale = spec.outlines[-1].max_extent
    a, b = q, np.roll(q, -1, axis=1)
    ka = np.round(a / scale, 9).reshape(-1, 2)
    kb = np.round(b / scale, 9).reshape(-1, 2)
    keys = np.where((ka[:, :1] < kb[:, :1]) | ((ka[:, :1] == kb[:, :1]) & (ka[:, 1:] < kb[:, 1:])),
                    np.hstack([ka, kb]), np.hstack([kb, ka]))
    _, inv, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    order = np.argsort(inv, kind="stable")
    pairs = order[counts[inv[order]] == 2].reshape(-1, 2)     # edge slots
    owner, neigh = pairs[:, 0] // 4, pairs[:, 1] // 4
    edge = (b - a).reshape(-1, 2)[pairs[:, 0]]
    normal = np.stack([edge[:, 1], -edge[:, 0]], axis=1)
    d = centre[neigh] - centre[owner]
    cos = np.abs((normal * d).sum(axis=1)) / (np.linalg.norm(normal, axis=1)
                                              * np.linalg.norm(d, axis=1))
    angle = np.degrees(np.arccos(np.clip(cos, 0.0, 1.0)))

    out = []
    for i, name in enumerate(spec.layer_names):
        mine = (layer[owner] == i) | (layer[neigh] == i)
        out.append(LayerQuality(name, float(sj[layer == i].min()),
                                float(angle[mine].max()) if mine.any() else 0.0))
    return out


# ---------------------------------------------------------------------------
# A twisted straight (task 0062)
# ---------------------------------------------------------------------------

_HEX_FACES = np.array([[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
                       [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def face_warp(verts: np.ndarray) -> np.ndarray:
    """Per hex of *verts* (n, 8, 3), its largest face warp in degrees: the
    angle between the two triangles of a quad face, the larger of its two
    diagonal splits (0 for a flat face)."""
    p = verts[:, _HEX_FACES]                                   # (n, 6, 4, 3)

    def unit_normal(a, b, c):
        n = np.cross(b - a, c - a)
        return n / np.linalg.norm(n, axis=-1, keepdims=True)
    out = np.zeros(p.shape[:2])
    for i in range(2):
        a, b, c, d = (p[:, :, (i + k) % 4] for k in range(4))
        cos = np.clip((unit_normal(a, b, c) * unit_normal(a, c, d)).sum(-1), -1.0, 1.0)
        out = np.maximum(out, np.degrees(np.arccos(cos)))
    return out.max(axis=1)


def twist_quality(spec: PipeSpec, dtheta: float, dz: float) -> tuple[float, float, float]:
    """Predicted (min corner SJ, max non-orthogonality, max face warp in
    degrees) of a straight whose section rolls by *dtheta* degrees over a
    layer of length *dz* (pure numpy).

    Two layers of the section's quads (``section_quality``) at three
    rolled stations: every node of a twisted ``Straight`` is on a station
    face, so these are its cells.  The SJ and non-orthogonality follow the
    wall shear, atan(R dθ / dz); the warp follows dθ (task 0062: equal to
    the meshed values to 1e-9).
    """
    from ..quality_hex import min_scaled_jacobians, shared_face_angles
    quads = np.concatenate([_quads(g) for _, g in layout_of(spec).node_grids(spec)])
    scale = spec.outlines[-1].max_extent
    _, first, inv = np.unique(np.round(quads.reshape(-1, 2) / scale, 9), axis=0,
                              return_index=True, return_inverse=True)
    pts, q = quads.reshape(-1, 2)[first], inv.reshape(-1, 4)
    n = len(pts)
    stations = []
    for k in range(3):
        a = math.radians(dtheta * k)
        c, s = math.cos(a), math.sin(a)
        stations.append(np.column_stack([pts @ np.array([[c, s], [-s, c]]),
                                         np.full(n, k * dz)]))
    X = np.concatenate(stations)
    conn = np.concatenate([np.hstack([q + k * n, q + (k + 1) * n]) for k in range(2)])
    verts = X[conn]
    angles, _, _ = shared_face_angles(verts, conn)
    return (float(min_scaled_jacobians(verts).min()), float(angles.max()),
            float(face_warp(verts).max()))


# ---------------------------------------------------------------------------
# The limits (task 0047)
# ---------------------------------------------------------------------------

def changes_shape(spec: PipeSpec, i: int) -> bool:
    """Whether shell *i* (1 = the first shell) changes outline shape: not a
    ``dR`` shell (the inner outline grown) and not a circle round a
    circle.  Only these rings have skewed corner lines or unequal sides."""
    inner, outer = spec.outlines[i - 1], spec.outlines[i]
    if spec.shells[i - 1].dR is not None:
        return False
    return not (inner.is_round and outer.is_round)


def check_section_quality(spec: PipeSpec) -> list[str]:
    """Apply the outline quality limits to every shell that changes shape.

    Raises ``ValueError`` past a hard limit (``PREDICTED_SJ_MIN``,
    ``OUTLINE_NONORTH_MAX``); returns one message per soft limit passed
    (``PREDICTED_SJ_WARN``, ``OUTLINE_NONORTH_WARN``).  Each names the
    layer, the metric, the predicted value and the limit.
    """
    shells = [i for i in range(1, len(spec.outlines)) if changes_shape(spec, i)]
    if not shells:
        return []
    quality = section_quality(spec)
    warn = []
    for i in shells:
        q = quality[i]
        what = (f"layer `{q.name}` ({spec.outlines[i - 1].label} in a "
                f"{spec.outlines[i].label})")
        if q.min_sj < PREDICTED_SJ_MIN:
            raise AssemblyError(f"{what}: predicted corner scaled Jacobian {q.min_sj:.3f} "
                                f"is below PREDICTED_SJ_MIN {PREDICTED_SJ_MIN:g}",
                                code="section_predicted_sj_below_minimum", where={"label": q.name},
                                value=float(q.min_sj), limit="PREDICTED_SJ_MIN")
        if q.max_non_ortho > OUTLINE_NONORTH_MAX:
            raise AssemblyError(f"{what}: predicted non-orthogonality {q.max_non_ortho:.1f}° "
                                f"is above OUTLINE_NONORTH_MAX {OUTLINE_NONORTH_MAX:g}°",
                                code="section_nonorth_above_maximum", where={"label": q.name},
                                value=float(q.max_non_ortho), limit="OUTLINE_NONORTH_MAX")
        if q.min_sj < PREDICTED_SJ_WARN:
            warn.append(f"{what}: predicted corner scaled Jacobian {q.min_sj:.3f} "
                        f"is below PREDICTED_SJ_WARN {PREDICTED_SJ_WARN:g}")
        if q.max_non_ortho > OUTLINE_NONORTH_WARN:
            warn.append(f"{what}: predicted non-orthogonality {q.max_non_ortho:.1f}° "
                        f"is above OUTLINE_NONORTH_WARN {OUTLINE_NONORTH_WARN:g}°")
    return warn
