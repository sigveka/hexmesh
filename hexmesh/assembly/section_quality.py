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

from ..core.shape import CircleShape, RectShape, outline
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

def progression(n: int, ratio: float) -> np.ndarray:
    """Fractions of the n + 1 nodes of a ``Progression`` curve: each cell
    *ratio* times the previous."""
    i = np.arange(n + 1)
    if abs(ratio - 1.0) < 1e-12:
        return i / n
    return (ratio ** i - 1.0) / (ratio ** n - 1.0)


def bump(n: int, coef: float) -> np.ndarray:
    """Fractions of the n + 1 nodes of a ``Bump`` curve.  GMSH places them
    at equal steps of the integral of a node density ∝ 1 / (K ∓ x²),
    x = t − ½: K = 1/(4(1 − coef)) refines toward both ends (coef < 1),
    K = 1/(4(coef − 1)) toward the middle (coef > 1)."""
    if abs(coef - 1.0) < 1e-12:
        return np.arange(n + 1) / n
    if coef < 1.0:
        k = math.sqrt(1.0 / (4.0 * (1.0 - coef)))
        F, Finv = (lambda x: np.arctanh(x / k)), (lambda y: k * np.tanh(y))
    else:
        k = math.sqrt(1.0 / (4.0 * (coef - 1.0)))
        F, Finv = (lambda x: np.arctan(x / k)), (lambda y: k * np.tan(y))
    lo, hi = F(-0.5), F(0.5)
    return 0.5 + Finv(lo + (hi - lo) * np.arange(n + 1) / n)


# ---------------------------------------------------------------------------
# The section's quads
# ---------------------------------------------------------------------------

def _ring(inner: np.ndarray, outer: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Patch nodes (len(inner), len(t), 2): the two boundaries' linear blend."""
    return inner[:, None, :] * (1 - t)[None, :, None] + outer[:, None, :] * t[None, :, None]


def _chord_fractions(p: np.ndarray) -> np.ndarray:
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    return d / d[-1]


def _coons(bottom, top, left, right) -> np.ndarray:
    """Transfinite patch nodes from four boundary node rows; *bottom* and
    *top* run along u (left → right), *left* and *right* along v."""
    u = _chord_fractions(bottom)[:, None, None]
    v = _chord_fractions(left)[None, :, None]
    B, T = bottom[:, None, :], top[:, None, :]
    L, R = left[None, :, :], right[None, :, :]
    return ((1 - v) * B + v * T + (1 - u) * L + u * R
            - ((1 - u) * (1 - v) * bottom[0] + u * (1 - v) * bottom[-1]
               + (1 - u) * v * top[0] + u * v * top[-1]))


def _patches(spec: PipeSpec) -> list[tuple[int, np.ndarray]]:
    """(layer index, node grid) of every patch of *spec*'s face, unrotated."""
    outlines = spec.outlines
    corners = spec.corners()
    core = outlines[0]
    mb = spec.mbmp
    counts = [core.side_count(k, 4) for k in range(4)]
    s = [bump(c, mb) for c in counts]

    # core: centre patch from the inner curves, then the four ring patches
    inner = [outline(core, k, s[k], inner=True) for k in range(4)]
    out = [(0, _coons(bottom=inner[2], top=inner[0][::-1],
                      left=inner[1][::-1], right=inner[3]))]
    t = progression(spec._core_nrad, spec._core_mprg)
    prev = [outline(core, k, s[k]) for k in range(4)]
    out += [(0, _ring(inner[k], prev[k], t)) for k in range(4)]

    for i, (sh, o) in enumerate(zip(spec.shells, outlines[1:]), start=1):
        t = progression(sh.nrad, sh.mprg)
        c = corners[i]
        cur = [o.side(c[k], c[(k + 1) % 4], s[k]) for k in range(4)]
        out += [(i, _ring(prev[k], cur[k], t)) for k in range(4)]
        prev = cur
    return out


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
    if spec.n_outer != 4 or not all(isinstance(o, (CircleShape, RectShape))
                                    for o in spec.outlines):
        raise NotImplementedError("section_quality needs circle and rectangle "
                                  "outlines and n_outer = 4")
    quads, layer = [], []
    for i, grid in _patches(spec):
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
# The limits (task 0047)
# ---------------------------------------------------------------------------

def changes_shape(spec: PipeSpec, i: int) -> bool:
    """Whether shell *i* (1 = the first shell) changes outline shape: not a
    ``dR`` shell (the inner outline grown) and not a circle round a
    circle.  Only these rings have skewed corner lines or unequal sides."""
    inner, outer = spec.outlines[i - 1], spec.outlines[i]
    if spec.shells[i - 1].dR is not None:
        return False
    return not (isinstance(inner, CircleShape) and isinstance(outer, CircleShape))


def _describe(shape) -> str:
    if isinstance(shape, CircleShape):
        return "circle"
    w, h = shape.half_w, shape.half_h
    return f"{max(w, h) / min(w, h):.3g}:1 rectangle"


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
        what = (f"layer `{q.name}` ({_describe(spec.outlines[i - 1])} in a "
                f"{_describe(spec.outlines[i])})")
        if q.min_sj < PREDICTED_SJ_MIN:
            raise ValueError(f"{what}: predicted corner scaled Jacobian {q.min_sj:.3f} "
                             f"is below PREDICTED_SJ_MIN {PREDICTED_SJ_MIN:g}")
        if q.max_non_ortho > OUTLINE_NONORTH_MAX:
            raise ValueError(f"{what}: predicted non-orthogonality {q.max_non_ortho:.1f}° "
                             f"is above OUTLINE_NONORTH_MAX {OUTLINE_NONORTH_MAX:g}°")
        if q.min_sj < PREDICTED_SJ_WARN:
            warn.append(f"{what}: predicted corner scaled Jacobian {q.min_sj:.3f} "
                        f"is below PREDICTED_SJ_WARN {PREDICTED_SJ_WARN:g}")
        if q.max_non_ortho > OUTLINE_NONORTH_WARN:
            warn.append(f"{what}: predicted non-orthogonality {q.max_non_ortho:.1f}° "
                        f"is above OUTLINE_NONORTH_WARN {OUTLINE_NONORTH_WARN:g}°")
    return warn
