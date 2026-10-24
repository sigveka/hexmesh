"""
Corner identity — corners are named by the frame, never found by distance
(DESIGN.md §6.1).

Face builders record corners in a fixed order: corner ``k`` lies at
``corner_angles[k]`` from ``h_axis``; ``outer_curves[k]`` / ``inner_curves[k]``
run from corner ``k`` to ``k+1``; ``radial_curves[k]`` runs inner → outer at
corner ``k``; quadrant surface ``k`` lies between corners ``k`` and ``k+1``.

``canonical_geom`` reads that order and fixes curve signs by comparing
endpoint *tags* (OCC may store an arc reversed).  ``frame_offset`` gives the
index correspondence between two faces from their frames alone, in pure
numpy, so it is checked during validation and reused unchanged in ``fill``.
"""

from __future__ import annotations
import math

import numpy as np

from ..core.cross_section import CrossSection
from ..core.spec import PipeSpec
from ..connectors.fittings import _connect_layer_aligned, _curve_endpoints
from .interface import Frame


def _oriented(curve: int, start: int, end: int) -> int:
    """Signed *curve* tag running from point *start* to point *end*."""
    t0, t1 = _curve_endpoints(abs(curve))
    if (t0, t1) == (start, end):
        return abs(curve)
    if (t0, t1) == (end, start):
        return -abs(curve)
    raise RuntimeError(
        f"curve {abs(curve)} does not join points {start} and {end} "
        f"(endpoints {t0}, {t1}): face topology is inconsistent"
    )


def canonical_geom(cs: CrossSection) -> dict:
    """Signed entity tags of *cs* indexed by corner (keys ip, op, ic, oc, rc)."""
    n = cs.n_outer
    op, ip = list(cs.outer_points), list(cs.inner_points)
    return {
        'op': op,
        'ip': ip,
        'oc': [_oriented(c, op[k], op[(k + 1) % n]) for k, c in enumerate(cs.outer_curves)],
        'ic': [_oriented(c, ip[k], ip[(k + 1) % n]) for k, c in enumerate(cs.inner_curves)],
        'rc': [_oriented(c, ip[k], op[k]) for k, c in enumerate(cs.radial_curves)],
    }


def corner0_angle(spec: PipeSpec) -> float:
    """Angle of corner 0 from ``frame.right`` for faces built from *spec*."""
    return math.pi / 4 + spec.rot


def frame_offset(a: Frame, b: Frame, spec: PipeSpec) -> int:
    """Index *j* such that corner 0 of the face at *a* is corner *j* at *b*.

    Pure numpy (runs in validation).  Corner 0's direction is carried from
    plane *a* to plane *b* by the minimal rotation between the normals; its
    angle in frame *b* names the matching corner.
    """
    n = spec.n_outer
    a0 = corner0_angle(spec)
    d = math.cos(a0) * a.right + math.sin(a0) * a.up

    axis = np.cross(a.normal, b.normal)
    s, c = float(np.linalg.norm(axis)), float(np.dot(a.normal, b.normal))
    if c < -1 + 1e-9:
        raise ValueError("faces are antiparallel: corner correspondence undefined")
    if s > 1e-14:
        k = axis / s
        d = d * c + np.cross(k, d) * s + k * np.dot(k, d) * (1 - c)

    phi = math.atan2(np.dot(d, b.up), np.dot(d, b.right))
    steps = (phi - a0) / (2 * math.pi / n)
    j = round(steps)
    if abs(steps - j) > 0.5 - 1e-9:
        raise ValueError(
            "corner correspondence is ambiguous: the slab twists by half the "
            "cross-section symmetry angle; use more axial layers"
        )
    return j % n


def connect_layer(in_cs: CrossSection, out_cs: CrossSection, n_layers: int,
                  offset: int, **kwargs):
    """``_connect_layer`` with correspondence from frames (*offset*)."""
    n = in_cs.n_outer
    g_in, g_out = canonical_geom(in_cs), canonical_geom(out_cs)
    g_out = {key: [v[(i + offset) % n] for i in range(n)] for key, v in g_out.items()}
    off = 1 if len(in_cs.surfaces) == n + 1 else 0
    in_quads = [in_cs.surfaces[off + i] for i in range(n)]
    out_quads = [out_cs.surfaces[off + (i + offset) % n] for i in range(n)]
    return _connect_layer_aligned(
        in_cs, out_cs, g_in, g_out, in_quads, out_quads, n_layers, **kwargs,
    )
