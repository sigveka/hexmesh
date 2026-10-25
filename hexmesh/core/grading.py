"""
Radial grading from a first-cell height (pure; docs/tasks/0002).

A layer of thickness ``t`` split into ``n`` cells whose lengths grow by
``q`` from the first cell ``h`` satisfies ``h (q**n - 1) / (q - 1) = t``.
"""

from __future__ import annotations
import math


def progression_for_first_cell(thickness: float, n_cells: int, h_first: float) -> float:
    """Growth ratio *q* of *n_cells* cells over *thickness* whose first cell
    is *h_first*.

    The sum ``h (1 + q + … + q**(n-1))`` increases monotonically from ``h``
    (q → 0) to infinity, so a solution exists exactly when
    ``0 < h_first < thickness`` (or ``h_first == thickness`` for one cell).
    Returns 1.0 for ``h_first == thickness / n_cells``.
    """
    if n_cells < 1:
        raise ValueError(f"n_cells must be >= 1, got {n_cells!r}")
    if thickness <= 0:
        raise ValueError(f"thickness must be positive, got {thickness!r}")
    if not 0 < h_first <= thickness:
        raise ValueError(
            f"first cell {h_first!r} must be positive and no larger than the "
            f"layer thickness {thickness!r}"
        )
    if n_cells == 1:
        if not math.isclose(h_first, thickness, rel_tol=1e-9):
            raise ValueError(
                f"a single cell spans the whole thickness {thickness!r}; "
                f"first cell {h_first!r} is impossible (use more cells)"
            )
        return 1.0
    if math.isclose(h_first * n_cells, thickness, rel_tol=1e-12):
        return 1.0
    if math.isclose(h_first, thickness, rel_tol=1e-12):
        raise ValueError(
            f"first cell {h_first!r} equals the thickness; no ratio fits "
            f"{n_cells} cells"
        )

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
