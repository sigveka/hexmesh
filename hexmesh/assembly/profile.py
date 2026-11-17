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
Radius profiles along a sweep (decision 0008, task 0031).

A profile is a serialisable description of the radius ratio
``r(s) = R(s) / R_in`` along a sweep, with ``s`` the arc-length fraction
in [0, 1].  It is pure Python and numpy, so a sweep can evaluate it in
validation, and other sweeps can reuse it (a profiled ``SplinePipe`` is a
planned expansion, decision 0018).

A profile is a :class:`Profile`, built by one constructor per kind (no
callables: they can't be saved), and saved as ``{"kind": …, <fields>}``:

``Profile.cosine(s0)``
    ``r(s) = 1 − s0 · (1 + cos(2π(s − ½)))``: a smooth constriction
    (s0 > 0) or bulge (s0 < 0), with ``r = 1 − 2·s0`` at the middle and
    ``r = 1`` at both ends (Varghese et al. 2007, RESEARCH §7.3).  s0 runs
    from ``limits.COSINE_S0_MIN`` (−1: a bulge to 3 R) up to, not
    including, ``limits.COSINE_S0_MAX`` (0.5: a closed throat); s0 = 0 is
    a plain pipe.
``Profile.venturi(beta, divergent=15)``
    Classical Venturi tube proportions after ISO 5167-4: a convergent cone
    of 21° included angle from D to d = β·D, a cylindrical throat of
    length d, and a divergent cone of *divergent* degrees included angle
    (7°–15°) back to D.  Lengths follow from the inlet diameter, so they
    are absolute; any remaining length is a straight outlet run at D.
    Corners are sharp (the standard's fillets are left out), and the
    corners always fall on stations.
``Profile.table([(s0, r0), (s1, r1), …])``
    A table, interpolated by a monotone cubic (Fritsch–Carlson PCHIP), so
    there is no overshoot between points.  ``s`` must run from 0 to 1.

A new kind (decision 0021's restrictions) adds a row to :data:`KINDS`, a
constructor with named parameters, and a form in :class:`RadiusProfile`.
"""

from __future__ import annotations
import inspect
import math
from dataclasses import dataclass

import numpy as np

from .errors import AssemblyError
from .limits import COSINE_S0_MAX, COSINE_S0_MIN, VENTURI_DIVERGENT_MAX, VENTURI_DIVERGENT_MIN

# Largest gap between a slab's straight wall chord and the profile, as a
# fraction of the inlet radius (decision 0008, C1).
CHORD_TOL = 1e-3

VENTURI_CONVERGENT = 21.0          # included angle, degrees (ISO 5167-4)
VENTURI_DIVERGENT = (VENTURI_DIVERGENT_MIN, VENTURI_DIVERGENT_MAX)   # degrees (limits)


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


def _check_cosine(s0) -> dict:
    s0 = float(s0)
    if not COSINE_S0_MIN <= s0 < COSINE_S0_MAX:
        raise AssemblyError(
            f"cosine s0 must be in [{COSINE_S0_MIN:g}, {COSINE_S0_MAX:g}), got {s0!r}: "
            f"{COSINE_S0_MIN:g} is a bulge to {1 - 2 * COSINE_S0_MIN:g}·R (COSINE_S0_MIN), "
            f"{COSINE_S0_MAX:g} a throat of zero radius (COSINE_S0_MAX); s0 > 0 "
            f"constricts, s0 < 0 bulges",
            code="profile_parameter_out_of_range", where={"field": "s0"}, value=s0,
            limit={"min": "COSINE_S0_MIN", "max_exclusive": "COSINE_S0_MAX"})
    return {"s0": s0}


def _check_venturi(beta, divergent=15.0) -> dict:
    beta, divergent = float(beta), float(divergent)
    if not 0 < beta < 1:
        raise AssemblyError(f"venturi beta must be in (0, 1), got {beta!r}",
                            code="profile_parameter_out_of_range", where={"field": "beta"},
                            value=beta, limit={"min_exclusive": 0, "max_exclusive": 1})
    lo, hi = VENTURI_DIVERGENT
    if not lo <= divergent <= hi:
        raise AssemblyError(f"venturi divergent angle must be {lo:g}°–{hi:g}° "
                            f"(ISO 5167-4), got {divergent!r}",
                            code="profile_parameter_out_of_range",
                            where={"field": "divergent"}, value=divergent,
                            limit={"min": "VENTURI_DIVERGENT_MIN",
                                   "max": "VENTURI_DIVERGENT_MAX"})
    return {"beta": beta, "divergent": divergent}


def _check_table(points) -> dict:
    try:
        pts = np.array(points, dtype=float)
    except (TypeError, ValueError):
        raise AssemblyError(f"a profile table is a list of (s, r) pairs, got {points!r}",
                            code="profile_table_invalid", where={"field": "points"}) from None
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) < 2:
        raise AssemblyError("a profile table needs at least two (s, r) pairs",
                            code="profile_table_invalid", where={"field": "points"})
    s, r = pts[:, 0], pts[:, 1]
    if s[0] != 0.0 or s[-1] != 1.0 or np.any(np.diff(s) <= 0):
        raise AssemblyError("a profile table's s must increase from 0 to 1",
                            code="profile_table_invalid", where={"field": "points"})
    if np.any(r <= 0):
        raise AssemblyError("a profile table's r must be positive",
                            code="profile_table_invalid", where={"field": "points"})
    return {"points": tuple((float(a), float(b)) for a, b in pts)}


#: kind → its fields' check, which returns them normalised
KINDS = {"cosine": _check_cosine, "venturi": _check_venturi, "table": _check_table}


@dataclass(frozen=True, init=False, repr=False)
class Profile:
    """A radius profile for ``Reducer(profile=…)`` (decision 0008, decision
    0053): the radius ratio ``r(s) = R(s) / R_in`` along the sweep, ``s``
    the arc-length fraction in [0, 1].

    Build one with :meth:`cosine`, :meth:`venturi` or :meth:`table`; the
    parameters are checked there, and each is an attribute (``p.s0``).  A
    profile is an immutable value: equal when its kind and fields are,
    saved as ``{"kind": …, <fields>}``.
    """

    kind: str
    _fields: tuple

    def __init__(self, kind: str, **fields):
        if kind not in KINDS:
            raise AssemblyError(f"unknown profile kind {kind!r}; known: {', '.join(KINDS)}",
                                code="profile_unknown", where={"field": "kind"}, value=kind,
                                limit=list(KINDS))
        try:
            checked = KINDS[kind](**fields)
        except TypeError:
            raise AssemblyError(f"a {kind} profile takes "
                                f"{', '.join(inspect.signature(KINDS[kind]).parameters)}, "
                                f"got {', '.join(sorted(fields)) or 'nothing'}",
                                code="profile_fields_invalid", where={"field": kind},
                                value=sorted(fields)) from None
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "_fields", tuple(checked.items()))
        for k, v in checked.items():
            object.__setattr__(self, k, v)

    @classmethod
    def cosine(cls, s0: float) -> "Profile":
        """A smooth constriction (*s0* > 0) or bulge (*s0* < 0): ``r = 1 −
        2·s0`` at the middle, 1 at both ends; ``COSINE_S0_MIN <= s0 <
        COSINE_S0_MAX``."""
        return cls("cosine", s0=s0)

    @classmethod
    def venturi(cls, beta: float, divergent: float = 15.0) -> "Profile":
        """An ISO 5167-4 Venturi tube: a 21° convergent to ``beta`` · D, a
        throat one throat diameter long, and a *divergent* cone (7°–15°
        included) back to D."""
        return cls("venturi", beta=beta, divergent=divergent)

    @classmethod
    def table(cls, points) -> "Profile":
        """``(s, r)`` pairs, s from 0 to 1, joined by a monotone cubic."""
        return cls("table", points=points)

    def __repr__(self):
        if self.kind == "table":
            return f"Profile.table({[list(p) for p in self.points]})"
        return f"Profile.{self.kind}(" + ", ".join(f"{k}={v!r}" for k, v in self._fields) + ")"

    def to_dict(self) -> dict:
        """``{"kind": …, <fields>}``, JSON-ready."""
        return {"kind": self.kind, **{k: [list(p) for p in v] if k == "points" else v
                                      for k, v in self._fields}}

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        d = dict(d)
        return cls(d.pop("kind", None), **d)


def hint_for(value) -> str | None:
    """The :class:`Profile` call for a tuple of the form before decision
    0053 (``("cosine", s0)``), for an error's hint."""
    if isinstance(value, (tuple, list)) and value and isinstance(value[0], str):
        kind, *args = value
        if kind == "cosine" and len(args) == 1:
            return f"profile=Profile.cosine({args[0]!r})"
        if kind == "venturi" and 1 <= len(args) <= 2:
            return f"profile=Profile.venturi({', '.join(repr(a) for a in args)})"
        return None
    if isinstance(value, (tuple, list)):
        return "profile=Profile.table([(s, r), …])"
    return None


class RadiusProfile:
    """A :class:`Profile` evaluated for a sweep of *length* whose inlet
    radius is *r_in* (absolute lengths only matter for the venturi).
    ``kinks`` lists the fractions where r(s) has a corner."""

    def __init__(self, profile: Profile, length: float, r_in: float):
        self.profile, self.length, self.r_in = profile, length, r_in
        self.kinks: tuple[float, ...] = ()
        getattr(self, "_" + profile.kind)(profile)

    # -- forms -------------------------------------------------------------

    def _cosine(self, p: Profile) -> None:
        s0 = p.s0
        self._r = lambda s: 1.0 - s0 * (1.0 + np.cos(2 * np.pi * (s - 0.5)))

    def _venturi(self, p: Profile) -> None:
        beta, divergent = p.beta, p.divergent
        R, r = self.r_in, beta * self.r_in
        l1 = (R - r) / math.tan(math.radians(VENTURI_CONVERGENT / 2))
        l2 = 2 * r
        l3 = (R - r) / math.tan(math.radians(divergent / 2))
        need = l1 + l2 + l3
        if self.length < need * (1 - 1e-12):
            raise AssemblyError(f"venturi with beta {beta:g} and a {divergent:g}° "
                                f"divergent needs length >= {need:.6g}, got {self.length:.6g}",
                                code="profile_too_short", where={"field": "length"},
                                value=self.length, limit={"min": need},
                                hint=f"length >= {need:.6g}, a larger beta, or a wider divergent angle")
        s = np.array([0.0, l1, l1 + l2, need, max(need, self.length)]) / self.length
        x = np.array([1.0, beta, beta, 1.0, 1.0])
        self.kinks = tuple(float(v) for v in s[1:4])
        self._r = lambda q: np.interp(q, s, x)

    def _table(self, p: Profile) -> None:
        pts = np.array(p.points, dtype=float)
        s, r = pts[:, 0], pts[:, 1]
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
                raise AssemblyError("a venturi needs interior stations at its corners; "
                                    "use more layers",
                                    code="profile_stations_too_few", where={"field": "n_layers"},
                                    hint="use more layers")
            u[k] = kink
        if np.any(np.diff(u) <= 0):
            raise AssemblyError("venturi corners fall between too few stations; "
                                "use more layers",
                                code="profile_stations_too_few", where={"field": "n_layers"},
                                hint="use more layers")
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
