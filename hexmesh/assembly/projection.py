"""
Wall projectors: analytic surfaces that mesh nodes are moved onto
(decision 0029, task 0051).

Where a wall can't be an exact, conformal OCC surface (a junction whose
wall crosses several smooth pieces, or a crease), the fitting supplies a
projector for it, and ``Assembly.mesh()`` moves the wall's mesh nodes onto
it between surface and volume meshing.

A projector is a callable ``points (n, 3) → points (n, 3)`` returning,
for each point, a nearby point exactly on the surface, with
``local_radius(points)``, the wall's radius there (moves are judged
against it).  Nearby points must
stay nearby and in order (no node crosses into another branch, and no two
collapse onto a crease), or the volume mesh folds.  This module provides
the one junctions need: the boundary of a union of tubes.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np


@dataclass(frozen=True)
class Tube:
    """The points within *radius* of an axis: a whole line, or a ray from
    *origin* along *direction* (then capped by a half-sphere about the
    origin)."""

    origin:    tuple
    direction: tuple
    radius:    float
    ray:       bool = True

    def nearest_axis(self, p: np.ndarray) -> np.ndarray:
        o, a = np.asarray(self.origin, float), np.asarray(self.direction, float)
        t = (p - o) @ a
        if self.ray:
            t = np.maximum(t, 0.0)
        return o + t[:, None] * a

    def distance(self, p: np.ndarray) -> np.ndarray:
        """Distance of each point from the axis."""
        return np.linalg.norm(p - self.nearest_axis(p), axis=1)

    def gradient(self, p: np.ndarray) -> np.ndarray:
        """Unit gradient of :meth:`distance` (away from the axis)."""
        v = p - self.nearest_axis(p)
        return v / np.maximum(np.linalg.norm(v, axis=1), 1e-300)[:, None]

    def project(self, p: np.ndarray) -> np.ndarray:
        """Nearest points on this tube's own surface (radially)."""
        q = self.nearest_axis(p)
        return q + self.radius * self.gradient(p)


class TubeUnion:
    """Projector onto the boundary of a union of tubes (decision 0029).

    ``nearest`` finds the nearest point: on one tube's surface, on the
    intersection curve of two (a crease, or the tee's saddle), or where
    three meet; candidates inside another tube are dropped, so no point
    lands across another branch.  Calling the projector maps along a
    smoothed normal instead (``__call__``).
    """

    # soft-minimum width for :meth:`direction`, × scale; 0.25–1 still fold
    # wyes of 30–50° at nang 8–16, 2 and 4 don't (task 0051)
    SOFT = 2.0

    def __init__(self, tubes: list[Tube]) -> None:
        self.tubes = list(tubes)
        self.scale = max(t.radius for t in self.tubes)

    def signed_distance(self, p: np.ndarray) -> np.ndarray:
        """Distance outside the union (negative inside) — exact outside,
        and zero exactly on the boundary."""
        p = np.atleast_2d(np.asarray(p, float))
        return np.min([t.distance(p) - t.radius for t in self.tubes], axis=0)

    def _on_boundary(self, c: np.ndarray) -> np.ndarray:
        tol = 1e-9 * self.scale
        return np.all([t.distance(c) >= t.radius - tol for t in self.tubes], axis=0)

    def _intersect(self, p: np.ndarray, tubes: tuple[Tube, ...]) -> tuple[np.ndarray, np.ndarray]:
        """Points on every tube of *tubes* near *p* (Gauss–Newton, minimum-
        norm steps, so close to the nearest such point); and which
        converged."""
        x = p.copy()
        ok = np.zeros(len(p), bool)
        for _ in range(50):
            F = np.stack([t.distance(x) - t.radius for t in tubes], axis=1)        # (n, m)
            J = np.stack([t.gradient(x) for t in tubes], axis=1)                    # (n, m, 3)
            ok = np.abs(F).max(axis=1) < 1e-13 * self.scale
            if ok.all():
                break
            JJ = J @ J.transpose(0, 2, 1)
            det = np.linalg.det(JJ)
            good = np.abs(det) > 1e-12
            step = np.zeros_like(x)
            if good.any():
                y = np.linalg.solve(JJ[good], F[good][..., None])[..., 0]
                step[good] = -np.einsum("nmk,nm->nk", J[good], y)
            x = x + step
        return x, ok

    def local_radius(self, q) -> np.ndarray:
        """Radius of the tube whose surface each wall point *q* lies on."""
        q = np.atleast_2d(np.asarray(q, float))
        off = np.stack([np.abs(t.distance(q) - t.radius) for t in self.tubes])
        return np.array([t.radius for t in self.tubes])[np.argmin(off, axis=0)]

    def direction(self, p: np.ndarray) -> np.ndarray:
        """Unit gradient of a soft minimum of the tubes' signed distances
        (width ``SOFT * scale``): a tube's own radial direction away from
        the creases, turning smoothly into the bisector across one."""
        p = np.atleast_2d(np.asarray(p, float))
        f = np.stack([t.distance(p) - t.radius for t in self.tubes])          # (m, n)
        w = np.exp(-(f - f.min(axis=0)) / (self.SOFT * self.scale))
        g = np.einsum("mn,mnk->nk", w, np.stack([t.gradient(p) for t in self.tubes]))
        return g / np.linalg.norm(g, axis=1)[:, None]

    def along(self, p, d, reach: float | None = None) -> np.ndarray:
        """Points on the boundary along the lines ``p + t d``, the root
        nearest ``t = 0`` within ``|t| ≤ reach`` (default the largest
        radius); NaN where the line meets no boundary within reach."""
        p = np.atleast_2d(np.asarray(p, float))
        d = np.atleast_2d(np.asarray(d, float))
        d = d / np.linalg.norm(d, axis=1)[:, None]
        reach = self.scale if reach is None else reach
        f = lambda t: self.signed_distance(p + t[:, None] * d)
        ts = np.linspace(-reach, reach, 161)
        fs = np.stack([f(np.full(len(p), t)) for t in ts], axis=1)          # (n, k)
        change = (np.sign(fs[:, :-1]) * np.sign(fs[:, 1:]) <= 0)
        mid = np.abs(0.5 * (ts[:-1] + ts[1:]))
        score = np.where(change, mid[None, :], np.inf)
        j = np.argmin(score, axis=1)
        found = np.isfinite(score[np.arange(len(p)), j])
        lo, hi = ts[j].copy(), ts[j + 1].copy()
        flo = fs[np.arange(len(p)), j]
        for _ in range(64):
            m = 0.5 * (lo + hi)
            fm = f(m)
            left = np.sign(fm) == np.sign(flo)
            lo, flo = np.where(left, m, lo), np.where(left, fm, flo)
            hi = np.where(left, hi, m)
        out = p + (0.5 * (lo + hi))[:, None] * d
        out[~found] = np.nan
        return out

    def __call__(self, p) -> np.ndarray:
        """The boundary point along :meth:`direction` from each point.

        Away from creases that is the nearest point.  Near one, the nearest
        point would collapse the band of points whose nearest point is the
        crease onto it, and fold the cells there; along the smoothed
        direction they spread over both flanks in order (task 0051).  Where
        the line misses, the nearest point."""
        p = np.atleast_2d(np.asarray(p, float))
        out = self.along(p, self.direction(p))
        miss = np.isnan(out[:, 0])
        if miss.any():
            out[miss] = self.nearest(p[miss])
        return out

    def nearest(self, p) -> np.ndarray:
        """Nearest points on the boundary (a tube's surface, or where two
        or three meet)."""
        p = np.atleast_2d(np.asarray(p, float))
        tol = 1e-9 * self.scale
        # one tube's surface
        cand = np.stack([t.project(p) for t in self.tubes])                  # (m, n, 3)
        dist = np.linalg.norm(cand - p, axis=2)
        dist[~np.stack([self._on_boundary(c) for c in cand])] = np.inf
        order = np.argsort(dist, axis=0)
        first = np.take_along_axis(dist, order[:1], 0)[0]
        second = (np.take_along_axis(dist, order[1:2], 0)[0] if len(self.tubes) > 1
                  else np.full(len(p), np.inf))
        out = cand[order[0], np.arange(len(p))]
        best = first.copy()
        # A tie between two tubes' surfaces: the point is on the bisector of
        # a concave crease, where the nearest point jumps from one flank to
        # the other.  It goes onto the crease (DESIGN §6, decision 0029).
        tie = np.isfinite(second)
        tie[tie] = second[tie] - first[tie] <= tol
        if tie.any():
            a = cand[order[0], np.arange(len(p))]
            b = cand[order[1], np.arange(len(p))]
            tie &= np.linalg.norm(a - b, axis=1) > tol
        best[tie] = np.inf
        # where two or three surfaces meet
        for k in (2, 3):
            for group in combinations(self.tubes, k):
                c, ok = self._intersect(p, group)
                d = np.linalg.norm(c - p, axis=1)
                take = ok & self._on_boundary(c) & (d < best)
                out[take], best = c[take], np.where(take, d, best)
        out[np.isinf(best)] = np.nan
        if np.isnan(out).any():
            raise ValueError("wall projection found no point on the wall for "
                             f"{int(np.isnan(out[:, 0]).sum())} node(s)")
        return out

