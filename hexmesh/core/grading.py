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
Radial grading from a first-cell height (pure; docs/tasks/0002).

A layer of thickness ``t`` split into ``n`` cells whose lengths grow by
``q`` from the first cell ``h`` satisfies ``h (q**n - 1) / (q - 1) = t``.
"""

from __future__ import annotations
import math

from ..errors import SpecError


def progression_for_first_cell(thickness: float, n_cells: int, h_first: float) -> float:
    """Growth ratio *q* of *n_cells* cells over *thickness* whose first cell
    is *h_first*.

    The sum ``h (1 + q + … + q**(n-1))`` increases monotonically from ``h``
    (q → 0) to infinity, so a solution exists exactly when
    ``0 < h_first < thickness`` (or ``h_first == thickness`` for one cell).
    Returns 1.0 for ``h_first == thickness / n_cells``.
    """
    if n_cells < 1:
        raise SpecError(f"n_cells must be >= 1, got {n_cells!r}",
                        code="count_below_minimum", where={"field": "n_cells"}, value=n_cells,
                        limit={"min": 1})
    if thickness <= 0:
        raise SpecError(f"thickness must be positive, got {thickness!r}",
                        code="size_not_positive", where={"field": "thickness"}, value=thickness,
                        limit={"min_exclusive": 0})
    if not 0 < h_first <= thickness:
        raise SpecError(
            f"first cell {h_first!r} must be positive and no larger than the "
            f"layer thickness {thickness!r}",
            code="first_cell_out_of_range", where={"field": "first_cell"},
            value=h_first, limit={"min_exclusive": 0, "max": thickness})
    if n_cells == 1:
        if not math.isclose(h_first, thickness, rel_tol=1e-9):
            raise SpecError(
                f"a single cell spans the whole thickness {thickness!r}; "
                f"first cell {h_first!r} is impossible (use more cells)",
                code="first_cell_out_of_range", where={"field": "first_cell"},
                value=h_first, hint="use more cells")
        return 1.0
    if math.isclose(h_first * n_cells, thickness, rel_tol=1e-12):
        return 1.0
    if math.isclose(h_first, thickness, rel_tol=1e-12):
        raise SpecError(
            f"first cell {h_first!r} equals the thickness; no ratio fits "
            f"{n_cells} cells",
            code="first_cell_out_of_range", where={"field": "first_cell"},
            value=h_first, limit={"max_exclusive": thickness})

    def total(log_q: float) -> float:
        if abs(log_q) < 1e-12:
            return h_first * n_cells
        return h_first * math.expm1(n_cells * log_q) / math.expm1(log_q)

    lo, hi = -1.0, 1.0                       # bracket in log q
    while total(lo) > thickness:
        lo *= 2
    while total(hi) < thickness:
        hi *= 2
    for _ in range(200):                     # bisection: robust, ~1e-15
        mid = 0.5 * (lo + hi)
        if total(mid) < thickness:
            lo = mid
        else:
            hi = mid
    return math.exp(0.5 * (lo + hi))


def first_cell_height(thickness: float, n_cells: int, q: float) -> float:
    """First cell of *n_cells* cells over *thickness* growing by *q*."""
    if math.isclose(q, 1.0, rel_tol=1e-15):
        return thickness / n_cells
    return thickness * (q - 1) / (q ** n_cells - 1)


# ---------------------------------------------------------------------------
# Two-sided wall grading: gmsh's transfinite "Bump" (task 0084)
# ---------------------------------------------------------------------------
# A side of an H core runs from wall to wall, so it is refined toward both
# ends.  gmsh's "Bump" is that law (docs/integrations/gmsh.md, 4.12.1:
# symmetric, coef < 1 refines toward both ends, matched by ``bump`` to
# ~5e-9); "Progression" and "Beta" refine toward one end only.

def bump(n: int, coef: float):
    """Fractions of the n + 1 nodes of a ``Bump`` curve.  GMSH places them
    at equal steps of the integral of a node density ∝ 1 / (K ∓ x²),
    x = t − ½: K = 1/(4(1 − coef)) refines toward both ends (coef < 1),
    K = 1/(4(coef − 1)) toward the middle (coef > 1)."""
    import numpy as np
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


def _solve_bump(n: int, f, target: float) -> float:
    """The ``Bump`` coefficient where *f(coef)* (monotone increasing in
    log coef) reaches *target*: bisection in log coef."""
    lo, hi = math.log(1e-12), math.log(1e6)
    if not f(math.exp(lo)) < target < f(math.exp(hi)):
        raise SpecError(f"no Bump coefficient reaches {target!r} with {n} cells",
                        code="grading_unreachable", value=target)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(math.exp(mid)) < target:
            lo = mid
        else:
            hi = mid
    return math.exp(0.5 * (lo + hi))


def bump_for_first_cell(length: float, n_cells: int, h_first: float) -> float:
    """``Bump`` coefficient giving end cells of *h_first* on a curve of
    *length* split into *n_cells* (both ends; 1.0 for uniform cells)."""
    if n_cells < 2:
        raise SpecError(f"wall grading needs at least 2 cells across, got {n_cells!r}",
                        code="count_below_minimum", where={"field": "n_cells"}, value=n_cells,
                        limit={"min": 2})
    if not 0 < h_first < length / 2:
        raise SpecError(f"first cell {h_first!r} must be positive and under half "
                         f"the side {length!r}",
                        code="first_cell_out_of_range", where={"field": "first_cell"},
                        value=h_first, limit={"min_exclusive": 0, "max_exclusive": length / 2})
    if math.isclose(h_first * n_cells, length, rel_tol=1e-12):
        return 1.0
    return _solve_bump(n_cells, lambda c: float(bump(n_cells, c)[1]), h_first / length)


def bump_for_ratio(n_cells: int, ratio: float) -> float:
    """``Bump`` coefficient whose second cell from each end is *ratio*
    times the end cell (> 1 refines toward both ends; 1.0 uniform)."""
    if n_cells < 3:
        raise SpecError(f"a wall growth ratio needs at least 3 cells across, got {n_cells!r}",
                        code="count_below_minimum", where={"field": "n_cells"}, value=n_cells,
                        limit={"min": 3})
    if ratio <= 0:
        raise SpecError(f"wall growth ratio must be positive, got {ratio!r}",
                        code="value_not_positive", where={"field": "mprg"}, value=ratio,
                        limit={"min_exclusive": 0})
    if math.isclose(ratio, 1.0, rel_tol=1e-15):
        return 1.0

    def growth(c):
        x = bump(n_cells, c)
        return float((x[2] - x[1]) / x[1])
    return _solve_bump(n_cells, lambda c: -growth(c), -ratio)


def progression(n: int, ratio: float) -> np.ndarray:
    """Fractions of the n + 1 nodes of a ``Progression`` curve: each cell
    *ratio* times the previous."""
    import numpy as np
    i = np.arange(n + 1)
    if abs(ratio - 1.0) < 1e-12:
        return i / n
    return (ratio ** i - 1.0) / (ratio ** n - 1.0)
