"""
Hexahedral mesh quality metrics — Table 2 of Sorgente et al. (2023),
"A Survey of Indicators for Mesh Quality Assessment", CGF 42(2).

Table 2 organises 3-D indicators into two groups:

    Face-based  (warping, aspect ratio, skewness, taper, interpolation quality)
        Computed on each of the 6 quad faces, then aggregated
        (min / max / mean / sum) over the element.

    Jacobian-based  (mean ratio, shape regularity)
        Computed from the 3×3 Jacobian matrix at each of the 8 hex vertices.

All element-level functions accept ``verts``: an (8, 3) float array of the
eight hex-node coordinates in **GMSH element-type-5 ordering**::

    3 ── 2       7 ── 6
    │    │  →    │    │
    0 ── 1       4 ── 5
    (bottom z-)    (top z+)

i.e. bottom face 0-1-2-3 (CCW from above) and top face 4-5-6-7 directly
above them.  This is the standard EXODUS / GMSH hex ordering.

GMSH integration
----------------
``evaluate_hex_quality_in_volumes`` fetches element nodes from an open GMSH
session and returns per-element quality arrays for every requested volume.

References
----------
Sorgente, T., Biasotti, S., Manzini, G., Spagnuolo, M. (2023).
    A Survey of Indicators for Mesh Quality Assessment.
    Computer Graphics Forum 42(2), 461–483.  DOI 10.1111/cgf.14779
Knupp, P.M. (2001). Algebraic Mesh Quality Metrics.
    SIAM J. Sci. Comput. 23(1), 193–218.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.linalg import det, inv, norm

# ---------------------------------------------------------------------------
# Hex topology constants (verified on the unit cube — det = 1 at every vertex)
# ---------------------------------------------------------------------------

# At vertex k the Jacobian is  A_k = [v[j]-v[k], v[l]-v[k], v[m]-v[k]]  (columns).
# Triplets (j, l, m) are chosen so that det(A_k) > 0 for a right-handed element.
_JACOBIAN_TRIPLETS: list[tuple[int, int, int]] = [
    (1, 3, 4),  # vertex 0
    (2, 0, 5),  # vertex 1
    (3, 1, 6),  # vertex 2
    (0, 2, 7),  # vertex 3
    (7, 5, 0),  # vertex 4
    (4, 6, 1),  # vertex 5
    (5, 7, 2),  # vertex 6
    (6, 4, 3),  # vertex 7
]

# 6 quad faces as (i, j, k, l) in CCW order when viewed from *outside* the hex.
# Outward normals verified on the unit cube.
_HEX_FACES: list[tuple[int, int, int, int]] = [
    (0, 3, 2, 1),  # bottom  (−z)
    (4, 5, 6, 7),  # top     (+z)
    (0, 1, 5, 4),  # front   (−y)
    (1, 2, 6, 5),  # right   (+x)
    (2, 3, 7, 6),  # back    (+y)
    (3, 0, 4, 7),  # left    (−x)
]

_AggMode = Literal["min", "max", "mean", "sum"]

# GMSH element-type code for the 8-node linear hexahedron
_GMSH_HEX8 = 5


# ===========================================================================
# Low-level helpers
# ===========================================================================

def _frob_cond(A: np.ndarray) -> float:
    """Frobenius-norm condition number  κ(A) = ‖A‖_F · ‖A⁻¹‖_F.

    Returns ``inf`` for singular or near-singular matrices.
    Note: κ(Iₙ) = n  (not 1), matching the convention in Knupp (2001) and
    Sorgente et al. (2023), so that  d / κ(Iₙ) = 1  for a perfect element
    of spatial dimension d = n.
    """
    J = det(A)
    if abs(J) < 1e-14:
        return np.inf
    try:
        Ainv = inv(A)
    except np.linalg.LinAlgError:
        return np.inf
    return float(norm(A, "fro") * norm(Ainv, "fro"))


def _jacobian_at_vertex(verts: np.ndarray, k: int) -> np.ndarray:
    """Return the 3×3 Jacobian at hex vertex k (columns = 3 edge vectors)."""
    j, l, m = _JACOBIAN_TRIPLETS[k]
    return np.column_stack([
        verts[j] - verts[k],
        verts[l] - verts[k],
        verts[m] - verts[k],
    ])


# ===========================================================================
# Jacobian-based hex metrics  (Table 2, rows "mean ratio" and "shape
# regularity" — computed directly from the 8 vertex Jacobians)
# ===========================================================================

def mean_ratio_min(verts: np.ndarray) -> float:
    """min_{k=0..7}  3 / κ(A_k).

    Range (0, 1].  Perfect unit cube → 1.  Inverted or degenerate → 0.
    (Table 2, "mean ratio", first variant.)
    """
    kappas = [_frob_cond(_jacobian_at_vertex(verts, k)) for k in range(8)]
    if any(np.isinf(k) for k in kappas):
        return 0.0
    return float(min(3.0 / k for k in kappas))


def mean_ratio_avg(verts: np.ndarray) -> float:
    """72 / Σ_{k=0..7} κ(A_k)².

    Range (0, 1].  Perfect unit cube → 1.  Degenerate → 0.
    (Table 2, "mean ratio", second variant — harmonic mean of κ values.)
    """
    kappas = [_frob_cond(_jacobian_at_vertex(verts, k)) for k in range(8)]
    if any(np.isinf(k) for k in kappas):
        return 0.0
    return float(72.0 / sum(k ** 2 for k in kappas))


def shape_regularity_ratio(verts: np.ndarray) -> float:
    """min_k J_k / max_k J_k.

    Range [0, 1].  1 when all vertex Jacobians are equal.  0 when any J_k ≤ 0.
    (Table 2, "shape regularity", first variant.)
    """
    Js = [float(det(_jacobian_at_vertex(verts, k))) for k in range(8)]
    if min(Js) <= 0.0:
        return 0.0
    return float(min(Js) / max(Js))


def shape_regularity_knupp(verts: np.ndarray) -> float:
    """24 / Σ_{k=0..7} (‖col₁(A_k)‖² + ‖col₂(A_k)‖² + ‖col₃(A_k)‖²) / J_k^{2/3}.

    Range (0, 1].  Perfect unit cube → 1.  Degenerate → 0.
    (Table 2, "shape regularity", second variant — Knupp's ζ₅³ᴰ.)
    """
    total = 0.0
    for k in range(8):
        A = _jacobian_at_vertex(verts, k)
        J = float(det(A))
        if J <= 0.0:
            return 0.0
        lam_sum = norm(A[:, 0]) ** 2 + norm(A[:, 1]) ** 2 + norm(A[:, 2]) ** 2
        total += lam_sum / (J ** (2.0 / 3.0))
    return float(24.0 / total)


# ===========================================================================
# Quad-face helpers
# ===========================================================================

def _quad_principal_axes(
    p: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (x₁, x₂, x₁₂) — principal axes and cross-derivative of quad p[0..3].

    Using 0-indexed notation (p₀ … p₃ = paper's v₁ … v₄):
        x₁  = (p₁−p₀) + (p₂−p₃)
        x₂  = (p₂−p₁) + (p₃−p₀)
        x₁₂ = (p₀−p₁) + (p₂−p₃)   [cross-derivative / taper axis]
    """
    x1  = (p[1] - p[0]) + (p[2] - p[3])
    x2  = (p[2] - p[1]) + (p[3] - p[0])
    x12 = (p[0] - p[1]) + (p[2] - p[3])
    return x1, x2, x12


def _quad_corner_normals(p: np.ndarray) -> list[np.ndarray]:
    """Unit cross-product normals at each corner of the quad.

    n_i = normalise(e_i × e_{i+1})  where e_i = p_{i+1} − p_i  (cyclic).
    For a flat quad all four normals are parallel.
    """
    normals = []
    for i in range(4):
        e1 = p[(i + 1) % 4] - p[i]
        e2 = p[(i + 2) % 4] - p[(i + 1) % 4]
        cross = np.cross(e1, e2)
        nc = float(norm(cross))
        normals.append(cross / nc if nc > 1e-14 else np.zeros(3))
    return normals


def _quad_corner_jacobians(p: np.ndarray) -> list[np.ndarray]:
    """3×3 Jacobians at each of the 4 corners of a 3-D quad face.

    At corner i:  A_i = [ê_fwd | ê_rev | n̂]
        ê_fwd  = normalise(p_{i+1} − p_i)   (CCW edge leaving corner i)
        ê_rev  = normalise(p_{i−1} − p_i)   (CCW edge arriving, reversed)
        n̂     = face unit normal (average of corner normals)

    All three columns are unit vectors, so A_i is orthogonal for a perfect
    square face and κ(A_i) = 3 regardless of element size → 3/κ = 1 ✓.
    Without normalisation the face normal (always length 1) and the edge
    vectors (length = element size s) would mix scales, making the formula
    size-dependent.
    """
    ns = _quad_corner_normals(p)
    n_avg = sum(ns) / 4.0
    nn = float(norm(n_avg))
    nhat = n_avg / nn if nn > 1e-14 else ns[0]

    Js = []
    for i in range(4):
        e_fwd = p[(i + 1) % 4] - p[i]
        e_rev = p[(i - 1) % 4] - p[i]
        nf = float(norm(e_fwd))
        nr = float(norm(e_rev))
        e_fwd_n = e_fwd / nf if nf > 1e-14 else e_fwd
        e_rev_n = e_rev / nr if nr > 1e-14 else e_rev
        Js.append(np.column_stack([e_fwd_n, e_rev_n, nhat]))
    return Js


# ===========================================================================
# Per-face metrics (quad-level indicators used as building blocks for hexes)
# ===========================================================================

def _face_warping(p: np.ndarray) -> float:
    """φ₂ = 1 − min{(n₀·n₂)³, (n₁·n₃)³}.

    0 = perfectly flat, approaching 1 = maximally warped.
    (Equation 16 in the paper, Section 4.2.)
    """
    n = _quad_corner_normals(p)
    d02 = float(np.dot(n[0], n[2]))
    d13 = float(np.dot(n[1], n[3]))
    return float(1.0 - min(d02 ** 3, d13 ** 3))


def _face_aspect_ratio(p: np.ndarray) -> float:
    """ε₁ = max(‖x₁‖/‖x₂‖, ‖x₂‖/‖x₁‖).

    1 = square, → ∞ for degenerate faces.
    (Equation 17 in the paper.)
    """
    x1, x2, _ = _quad_principal_axes(p)
    n1, n2 = float(norm(x1)), float(norm(x2))
    if min(n1, n2) < 1e-14:
        return np.inf
    return float(max(n1 / n2, n2 / n1))


def _face_skewness(p: np.ndarray) -> float:
    """ϑ = |x̂₁ · x̂₂|  (absolute cosine of angle between principal axes).

    0 = orthogonal (perfect rectangle), 1 = collinear (degenerate).
    (Equation 20 in the paper.)
    """
    x1, x2, _ = _quad_principal_axes(p)
    n1, n2 = float(norm(x1)), float(norm(x2))
    if min(n1, n2) < 1e-14:
        return 1.0
    return float(abs(np.dot(x1 / n1, x2 / n2)))


def _face_taper(p: np.ndarray) -> float:
    """τ = ‖x₁₂‖ / min(‖x₁‖, ‖x₂‖).

    0 = parallelogram (perfect), → ∞ for degenerate faces.
    (Equation 22 in the paper.)
    """
    x1, x2, x12 = _quad_principal_axes(p)
    denom = float(min(norm(x1), norm(x2)))
    if denom < 1e-14:
        return np.inf
    return float(norm(x12) / denom)


def _face_interp_quality_min(p: np.ndarray) -> float:
    """min_{i=0..3} 3/κ(A_i)  (quad interpolation quality, min-corner variant).

    The Jacobians A_i are 3×3 (face-plane edges + unit normal as third column),
    so the normalisation constant is d=3 rather than the intrinsic d=2 from
    Table 1.  κ(I₃) = 3  →  3/κ = 1 for a unit-square face.
    Range (0, 1].  Unit square → 1.
    """
    kappas = [_frob_cond(J) for J in _quad_corner_jacobians(p)]
    if any(np.isinf(k) for k in kappas):
        return 0.0
    return float(min(3.0 / k for k in kappas))


def _face_interp_quality_avg(p: np.ndarray) -> float:
    """36 / Σ_{i=0..3} κ(A_i)²  (quad interpolation quality, sum variant).

    Range (0, 1] for well-shaped elements.  Unit square → 1.
    (Table 1 "mean ratio" / "interpolation quality", second variant for quads.)
    """
    kappas = [_frob_cond(J) for J in _quad_corner_jacobians(p)]
    if any(np.isinf(k) for k in kappas):
        return 0.0
    return float(36.0 / sum(k ** 2 for k in kappas))


# ===========================================================================
# Face-aggregated hex metrics  (Table 2, rows: warping / aspect ratio /
# skewness / taper / interpolation quality — "min/max/mean/sum of the faces")
# ===========================================================================

def _aggregate(values: list[float], mode: _AggMode) -> float:
    if mode == "min":
        return min(values)
    if mode == "max":
        return max(values)
    if mode == "mean":
        return sum(values) / len(values)
    if mode == "sum":
        return sum(values)
    raise ValueError(f"Unknown aggregation mode {mode!r}; expected min/max/mean/sum")


def _hex_face_metric(
    verts: np.ndarray,
    face_fn,
    mode: _AggMode = "min",
) -> float:
    """Apply *face_fn* to each of the 6 hex quad faces and aggregate."""
    vals = [face_fn(verts[list(face)]) for face in _HEX_FACES]
    return _aggregate(vals, mode)


def hex_warping(verts: np.ndarray, mode: _AggMode = "max") -> float:
    """Hex warping — aggregated face warpings.

    Default aggregation: ``"max"``  (worst face sets the element score).
    0 = all faces flat.  Higher = more warped.
    """
    return _hex_face_metric(verts, _face_warping, mode)


def hex_aspect_ratio(verts: np.ndarray, mode: _AggMode = "max") -> float:
    """Hex aspect ratio — aggregated face aspect ratios.

    Default aggregation: ``"max"`` (worst face).
    1 = all faces square; larger values indicate elongated faces.
    """
    return _hex_face_metric(verts, _face_aspect_ratio, mode)


def hex_skewness(verts: np.ndarray, mode: _AggMode = "max") -> float:
    """Hex skewness — aggregated face skewnesses.

    Default aggregation: ``"max"`` (worst face).
    0 = all faces rectangular; 1 = degenerate.
    """
    return _hex_face_metric(verts, _face_skewness, mode)


def hex_taper(verts: np.ndarray, mode: _AggMode = "max") -> float:
    """Hex taper — aggregated face tapers.

    Default aggregation: ``"max"`` (worst face).
    0 = all faces are parallelograms; larger values indicate tapered faces.
    """
    return _hex_face_metric(verts, _face_taper, mode)


def hex_interpolation_quality(
    verts: np.ndarray,
    mode: _AggMode = "min",
    variant: Literal["min", "avg"] = "min",
) -> float:
    """Hex interpolation quality — aggregated face interpolation qualities.

    Default aggregation: ``"min"`` (worst face).
    ``variant="min"`` uses  min_{corner} 2/κ per face;
    ``variant="avg"`` uses  36/Σκ² per face.
    """
    face_fn = _face_interp_quality_min if variant == "min" else _face_interp_quality_avg
    return _hex_face_metric(verts, face_fn, mode)


# ===========================================================================
# Verdict-style metrics used in docs/RESEARCH.md §4.2 and §7.1
# ===========================================================================

def corner_scaled_jacobians(verts: np.ndarray) -> np.ndarray:
    """det(A_k) / (|e1| |e2| |e3|) at each of the 8 corners (Knupp).

    1 at every corner of a rectangular box; ≤ 0 at a folded corner.
    ``BlockLayout.corner_jacobians`` uses this on block corners before GMSH.
    """
    out = np.empty(8)
    for k in range(8):
        A = _jacobian_at_vertex(verts, k)
        n = norm(A[:, 0]) * norm(A[:, 1]) * norm(A[:, 2])
        out[k] = det(A) / n if n > 0 else 0.0
    return out


def min_scaled_jacobians(verts: np.ndarray) -> np.ndarray:
    """:func:`scaled_jacobian` of many hexes at once: *verts* (n, 8, 3) →
    (n,), the smallest det(A_k) / (|e1| |e2| |e3|) over the eight corners
    (0 where an edge has no length)."""
    verts = np.asarray(verts, float)
    out = np.full(len(verts), np.inf)
    for k, (j, l, m) in enumerate(_JACOBIAN_TRIPLETS):
        e = np.stack([verts[:, j] - verts[:, k], verts[:, l] - verts[:, k],
                      verts[:, m] - verts[:, k]], axis=2)
        n = np.prod(np.linalg.norm(e, axis=1), axis=1)
        sj = np.divide(np.linalg.det(e), n, out=np.zeros(len(verts)), where=n > 0)
        out = np.minimum(out, sj)
    return out


def scaled_jacobian(verts: np.ndarray) -> float:
    """Minimum corner scaled Jacobian, in [-1, 1]; 1 for a box.

    The 8-corner form specified in docs/tasks/0004.  Verdict's hex version
    also includes the Jacobian at the element centre (principal axes), so it
    can be lower on strongly tapered cells.
    """
    return float(corner_scaled_jacobians(verts).min())


def face_angles(verts: np.ndarray) -> np.ndarray:
    """The 24 interior corner angles of the 6 quad faces, in degrees."""
    out = []
    for face in _HEX_FACES:
        p = verts[list(face)]
        for i in range(4):
            a, b = p[i - 1] - p[i], p[(i + 1) % 4] - p[i]
            c = np.dot(a, b) / (norm(a) * norm(b))
            out.append(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))
    return np.array(out)


def nes(verts: np.ndarray) -> float:
    """Normalized equiangle skewness, in [0, 1]; 0 when every face angle is 90°.

    ``max((θmax − 90) / 90, (90 − θmin) / 90)`` over the face angles: the
    EquiAngle skewness of GAMBIT/Fluent with θe = 90°.
    """
    ang = face_angles(verts)
    return float(max((ang.max() - 90.0) / 90.0, (90.0 - ang.min()) / 90.0))


# ===========================================================================
# Convenience: all metrics at once
# ===========================================================================

def all_metrics(verts: np.ndarray) -> dict[str, float]:
    """Return a dict of all Table-2 hex metrics for a single element.

    Parameters
    ----------
    verts : (8, 3) array
        Vertex coordinates in GMSH hex-type-5 ordering.

    Returns
    -------
    dict[str, float]
        Keys and ideal values for a unit cube:

        ========================  =======
        Key                       Ideal
        ========================  =======
        warping                   0
        aspect_ratio              1
        skewness                  0
        taper                     0
        interp_quality_min        1
        interp_quality_avg        1
        mean_ratio_min            1
        mean_ratio_avg            1
        shape_regularity_ratio    1
        shape_regularity_knupp    1
        scaled_jacobian           1
        nes                       0
        ========================  =======
    """
    return {
        "scaled_jacobian":        scaled_jacobian(verts),
        "nes":                    nes(verts),
        "warping":                hex_warping(verts),
        "aspect_ratio":           hex_aspect_ratio(verts),
        "skewness":               hex_skewness(verts),
        "taper":                  hex_taper(verts),
        "interp_quality_min":     hex_interpolation_quality(verts, variant="min"),
        "interp_quality_avg":     hex_interpolation_quality(verts, variant="avg"),
        "mean_ratio_min":         mean_ratio_min(verts),
        "mean_ratio_avg":         mean_ratio_avg(verts),
        "shape_regularity_ratio": shape_regularity_ratio(verts),
        "shape_regularity_knupp": shape_regularity_knupp(verts),
    }


# ===========================================================================
# GMSH integration
# ===========================================================================

@dataclass(frozen=True)
class Metric:
    """An element metric: *fn(verts)*, its direction, and the default limit
    below (or above) which an element counts as bad."""

    fn:                object
    higher_is_better:  bool
    default_threshold: float


#: Metrics accepted by ``Assembly.check_quality`` besides GMSH quality names.
METRICS: dict[str, Metric] = {
    "scaled_jacobian":        Metric(scaled_jacobian, True, 0.0),
    "nes":                    Metric(nes, False, 1.0),
    "mean_ratio_min":         Metric(mean_ratio_min, True, 0.0),
    "mean_ratio_avg":         Metric(mean_ratio_avg, True, 0.0),
    "shape_regularity_ratio": Metric(shape_regularity_ratio, True, 0.0),
    "shape_regularity_knupp": Metric(shape_regularity_knupp, True, 0.0),
    "interp_quality_min":     Metric(lambda v: hex_interpolation_quality(v, variant="min"),
                                     True, 0.0),
    "interp_quality_avg":     Metric(lambda v: hex_interpolation_quality(v, variant="avg"),
                                     True, 0.0),
    "warping":                Metric(hex_warping, False, np.inf),
    "aspect_ratio":           Metric(hex_aspect_ratio, False, np.inf),
    "skewness":               Metric(hex_skewness, False, 1.0),
    "taper":                  Metric(hex_taper, False, np.inf),
}


def hex_vertices(volume_tags: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Element tags and (N, 8, 3) vertex coordinates of the hex-8 elements
    in *volume_tags* (open GMSH session with a mesh)."""
    import gmsh

    tags, xyz, _ = gmsh.model.mesh.getNodes()
    lookup = dict(zip(tags.tolist(), range(len(tags))))
    xyz = xyz.reshape(-1, 3)
    etags, verts = [], []
    for v in volume_tags:
        for etype, et, nt in zip(*gmsh.model.mesh.getElements(3, v)):
            if int(etype) != _GMSH_HEX8:
                continue
            idx = np.array([lookup[t] for t in nt.tolist()]).reshape(-1, 8)
            etags.append(np.asarray(et))
            verts.append(xyz[idx])
    if not etags:
        return np.empty(0, dtype=int), np.empty((0, 8, 3))
    return np.concatenate(etags), np.concatenate(verts)


@dataclass
class HexElementQuality:
    """Per-element quality values for one hexahedral element."""
    tag:                    int
    warping:                float
    aspect_ratio:           float
    skewness:               float
    taper:                  float
    interp_quality_min:     float
    interp_quality_avg:     float
    mean_ratio_min:         float
    mean_ratio_avg:         float
    shape_regularity_ratio: float
    shape_regularity_knupp: float


@dataclass
class HexVolumeQuality:
    """Aggregate quality statistics for one named physical volume.

    Each attribute holds a numpy array (one entry per hex element) except
    for the summary properties which are scalars.
    """
    name:                   str
    element_tags:           np.ndarray   # shape (N,)  — GMSH element tags
    warping:                np.ndarray   # shape (N,)
    aspect_ratio:           np.ndarray
    skewness:               np.ndarray
    taper:                  np.ndarray
    interp_quality_min:     np.ndarray
    interp_quality_avg:     np.ndarray
    mean_ratio_min:         np.ndarray
    mean_ratio_avg:         np.ndarray
    shape_regularity_ratio: np.ndarray
    shape_regularity_knupp: np.ndarray

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    @property
    def n_elements(self) -> int:
        return len(self.element_tags)

    def summary(self) -> dict[str, dict[str, float]]:
        """Return {metric_name: {min, mean, max}} statistics."""
        metrics = [
            "warping", "aspect_ratio", "skewness", "taper",
            "interp_quality_min", "interp_quality_avg",
            "mean_ratio_min", "mean_ratio_avg",
            "shape_regularity_ratio", "shape_regularity_knupp",
        ]
        out = {}
        for m in metrics:
            arr = getattr(self, m)
            out[m] = {
                "min":  float(arr.min()),
                "mean": float(arr.mean()),
                "max":  float(arr.max()),
            }
        return out

    def __str__(self) -> str:
        lines = [f"HexVolumeQuality  region={self.name!r}  n={self.n_elements}"]
        lines.append(f"  {'metric':<28s}  {'min':>9s}  {'mean':>9s}  {'max':>9s}")
        lines.append("  " + "-" * 52)
        for metric, stats in self.summary().items():
            lines.append(
                f"  {metric:<28s}  {stats['min']:>+9.4f}  "
                f"{stats['mean']:>+9.4f}  {stats['max']:>+9.4f}"
            )
        return "\n".join(lines)


def evaluate_hex_quality(
    volume_tags: list[int],
    name: str = "volume",
) -> HexVolumeQuality | None:
    """Compute all Table-2 hex metrics for elements in the given GMSH volumes.

    Requires an open GMSH session with an already-generated mesh.

    Parameters
    ----------
    volume_tags : list[int]
        GMSH volume (region) tags to evaluate.
    name : str
        Label for the returned ``HexVolumeQuality`` object.

    Returns
    -------
    HexVolumeQuality or None
        ``None`` if no hexahedral elements are found.
    """
    import gmsh  # lazy import — only needed when GMSH is active

    # -----------------------------------------------------------------
    # Build a node-tag → coordinate lookup from the current GMSH mesh
    # -----------------------------------------------------------------
    all_node_tags, coords_flat, _ = gmsh.model.mesh.getNodes()
    coords_arr = coords_flat.reshape(-1, 3)
    coord_map: dict[int, np.ndarray] = {
        int(tag): coords_arr[i] for i, tag in enumerate(all_node_tags)
    }

    # -----------------------------------------------------------------
    # Collect all hex-8 elements across the requested volumes
    # -----------------------------------------------------------------
    all_elem_tags: list[int] = []
    all_node_tag_groups: list[list[int]] = []

    for vol_tag in volume_tags:
        elem_types, elem_tags_per_type, node_tags_per_type = (
            gmsh.model.mesh.getElements(3, vol_tag)
        )
        for etype, etags, ntags in zip(
            elem_types, elem_tags_per_type, node_tags_per_type
        ):
            if int(etype) != _GMSH_HEX8:
                continue  # skip non-hex elements (wedges, tets, etc.)
            n_elem = len(etags)
            ntags_reshaped = ntags.reshape(n_elem, 8)
            for tag, node8 in zip(etags, ntags_reshaped):
                all_elem_tags.append(int(tag))
                all_node_tag_groups.append(node8.tolist())

    if not all_elem_tags:
        return None

    # -----------------------------------------------------------------
    # Evaluate metrics element by element
    # -----------------------------------------------------------------
    n = len(all_elem_tags)
    warping                = np.empty(n)
    aspect_ratio           = np.empty(n)
    skewness               = np.empty(n)
    taper                  = np.empty(n)
    interp_quality_min     = np.empty(n)
    interp_quality_avg     = np.empty(n)
    mrmin                  = np.empty(n)
    mravg                  = np.empty(n)
    sratio                 = np.empty(n)
    sknupp                 = np.empty(n)

    for i, (_, node8) in enumerate(zip(all_elem_tags, all_node_tag_groups)):
        verts = np.array([coord_map[t] for t in node8])   # (8, 3)
        warping[i]            = hex_warping(verts)
        aspect_ratio[i]       = hex_aspect_ratio(verts)
        skewness[i]           = hex_skewness(verts)
        taper[i]              = hex_taper(verts)
        interp_quality_min[i] = hex_interpolation_quality(verts, variant="min")
        interp_quality_avg[i] = hex_interpolation_quality(verts, variant="avg")
        mrmin[i]              = mean_ratio_min(verts)
        mravg[i]              = mean_ratio_avg(verts)
        sratio[i]             = shape_regularity_ratio(verts)
        sknupp[i]             = shape_regularity_knupp(verts)

    return HexVolumeQuality(
        name                   = name,
        element_tags           = np.array(all_elem_tags),
        warping                = warping,
        aspect_ratio           = aspect_ratio,
        skewness               = skewness,
        taper                  = taper,
        interp_quality_min     = interp_quality_min,
        interp_quality_avg     = interp_quality_avg,
        mean_ratio_min         = mrmin,
        mean_ratio_avg         = mravg,
        shape_regularity_ratio = sratio,
        shape_regularity_knupp = sknupp,
    )
