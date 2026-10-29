"""
Radius profiles along a sweep (decision 0008, task 0031).

A profile is a serialisable description of the radius ratio
``r(s) = R(s) / R_in`` along a sweep, with ``s`` the arc-length fraction
in [0, 1].  It is pure Python and numpy, so a sweep can evaluate it in
validation, and other sweeps can reuse it (a profiled ``SplinePipe`` is a
planned expansion, decision 0018).

Forms (no callables: they can't be saved):

``("cosine", s0)``
    ``r(s) = 1 − s0 · (1 + cos(2π(s − ½)))``: a smooth constriction
    (s0 > 0) or bulge (s0 < 0), with ``r = 1 − 2·s0`` at the middle and
    ``r = 1`` at both ends (Varghese et al. 2007, RESEARCH §7.3).  s0 runs
    from ``limits.COSINE_S0_MIN`` (−1: a bulge to 3 R) up to, not
    including, ``limits.COSINE_S0_MAX`` (0.5: a closed throat); s0 = 0 is
    a plain pipe.
``("venturi", beta, divergent)``
    Classical Venturi tube proportions after ISO 5167-4: a convergent cone
    of 21° included angle from D to d = β·D, a cylindrical throat of
    length d, and a divergent cone of *divergent* degrees included angle
    (7°–15°) back to D.  Lengths follow from the inlet diameter, so they
    are absolute; any remaining length is a straight outlet run at D.
    Corners are sharp (the standard's fillets are left out), and the
    corners always fall on stations.
``((s0, r0), (s1, r1), …)``
    A table, interpolated by a monotone cubic (Fritsch–Carlson PCHIP), so
    there is no overshoot between points.  ``s`` must run from 0 to 1.
"""

from __future__ import annotations
import math

import numpy as np

from .limits import COSINE_S0_MAX, COSINE_S0_MIN

# Largest gap between a slab's straight wall chord and the profile, as a
# fraction of the inlet radius (decision 0008, C1).
CHORD_TOL = 1e-3

VENTURI_CONVERGENT = 21.0          # included angle, degrees (ISO 5167-4)
VENTURI_DIVERGENT = (7.0, 15.0)    # allowed included angles, degrees


def _pchip_slopes(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Fritsch–Carlson slopes: monotone between monotone data points."""
    h = np.diff(x)
    delta = np.diff(y) / h
    m = np.zeros_like(y)
    if len(x) == 2:
        return np.full_like(y, delta[0])
    for k in range(1, len(x) - 1):
        if delta[k - 1] * delta[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / delta[k - 1] + w2 / delta[k])
    for k, (d0, d1, h0, h1) in ((0, (delta[0], delta[1], h[0], h[1])),
                                (-1, (delta[-1], delta[-2], h[-1], h[-2]))):
        e = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)    # three-point end slope
        if np.sign(e) != np.sign(d0):
            e = 0.0
        elif np.sign(d0) != np.sign(d1) and abs(e) > abs(3 * d0):
            e = 3 * d0
        m[k] = e
    return m


class Profile:
    """Evaluated radius-ratio profile ``r(s)`` of a sweep of *length*
    whose inlet radius is *r_in* (absolute lengths only matter for the
    venturi).  ``kinks`` lists the fractions where r(s) has a corner."""

    def __init__(self, spec, length: float, r_in: float):
        self.spec, self.length, self.r_in = spec, length, r_in
        self.kinks: tuple[float, ...] = ()
        if isinstance(spec, (tuple, list)) and spec and isinstance(spec[0], str):
            kind, *args = spec
            if kind == "cosine":
                self._cosine(*args)
            elif kind == "venturi":
                self._venturi(*args)
            else:
                raise ValueError(f"unknown profile {kind!r}; known: 'cosine', "
                                 f"'venturi', or a table of (s, r) pairs")
        else:
            self._table(spec)

    # -- forms -------------------------------------------------------------

    def _cosine(self, s0: float) -> None:
        if not COSINE_S0_MIN <= s0 < COSINE_S0_MAX:
            raise ValueError(
                f"cosine s0 must be in [{COSINE_S0_MIN:g}, {COSINE_S0_MAX:g}), got {s0!r}: "
                f"{COSINE_S0_MIN:g} is a bulge to {1 - 2 * COSINE_S0_MIN:g}·R (COSINE_S0_MIN), "
                f"{COSINE_S0_MAX:g} a throat of zero radius (COSINE_S0_MAX); s0 > 0 "
                f"constricts, s0 < 0 bulges")
        self._r = lambda s: 1.0 - s0 * (1.0 + np.cos(2 * np.pi * (s - 0.5)))

    def _venturi(self, beta: float, divergent: float = 15.0) -> None:
        if not 0 < beta < 1:
            raise ValueError(f"venturi beta must be in (0, 1), got {beta!r}")
        lo, hi = VENTURI_DIVERGENT
        if not lo <= divergent <= hi:
            raise ValueError(f"venturi divergent angle must be {lo:g}°–{hi:g}° "
                             f"(ISO 5167-4), got {divergent!r}")
        R, r = self.r_in, beta * self.r_in
        l1 = (R - r) / math.tan(math.radians(VENTURI_CONVERGENT / 2))
        l2 = 2 * r
        l3 = (R - r) / math.tan(math.radians(divergent / 2))
        need = l1 + l2 + l3
        if self.length < need * (1 - 1e-12):
            raise ValueError(f"venturi with beta {beta:g} and a {divergent:g}° "
                             f"divergent needs length >= {need:.6g}, got {self.length:.6g}")
        s = np.array([0.0, l1, l1 + l2, need, max(need, self.length)]) / self.length
        x = np.array([1.0, beta, beta, 1.0, 1.0])
        self.kinks = tuple(float(v) for v in s[1:4])
        self._r = lambda q: np.interp(q, s, x)

    def _table(self, table) -> None:
        try:
            pts = np.array(table, dtype=float)
        except (TypeError, ValueError):
            raise ValueError(f"profile must be ('cosine', s0), ('venturi', beta, "
                             f"divergent) or a table of (s, r) pairs, got {table!r}") from None
        if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
            raise ValueError("a profile table needs at least two (s, r) pairs")
        s, r = pts[:, 0], pts[:, 1]
        if s[0] != 0.0 or s[-1] != 1.0 or np.any(np.diff(s) <= 0):
            raise ValueError("a profile table's s must increase from 0 to 1")
        if np.any(r <= 0):
            raise ValueError("a profile table's r must be positive")
        m = _pchip_slopes(s, r)

        def f(q):
            q = np.asarray(q, dtype=float)
            k = np.clip(np.searchsorted(s, q, side="right") - 1, 0, len(s) - 2)
            h = s[k + 1] - s[k]
            t = (q - s[k]) / h
            h00, h10 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t
            h01, h11 = -2 * t**3 + 3 * t**2, t**3 - t**2
            return h00 * r[k] + h10 * h * m[k] + h01 * r[k + 1] + h11 * h * m[k + 1]
        self._r = f

    # -- use ---------------------------------------------------------------

    def __call__(self, s):
        return self._r(np.asarray(s, dtype=float))

    def stations(self, fractions: np.ndarray) -> np.ndarray:
        """Station fractions: *fractions* with every kink moved onto the
        nearest interior station, so corners are exact (pure)."""
        u = np.array(fractions, dtype=float)
        for kink in self.kinks:
            k = int(np.argmin(np.abs(u[1:-1] - kink))) + 1 if len(u) > 2 else None
            if k is None:
                raise ValueError("a venturi needs interior stations at its corners; "
                                 "use more layers")
            u[k] = kink
        if np.any(np.diff(u) <= 0):
            raise ValueError("venturi corners fall between too few stations; "
                             "use more layers")
        return u

    def chord_gaps(self, u: np.ndarray, samples: int = 64) -> np.ndarray:
        """Largest gap between each slab's straight wall chord and the
        profile, as a fraction of the inlet radius (sampled, so kinks and
        inflections count)."""
        gaps = []
        for a, b in zip(u[:-1], u[1:]):
            q = np.linspace(a, b, samples + 2)
            chord = self(a) + (self(b) - self(a)) * (q - a) / (b - a)
            gaps.append(float(np.max(np.abs(self(q) - chord))))
        return np.array(gaps)
