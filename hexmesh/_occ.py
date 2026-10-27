"""
What hexmesh knows about the OCC entities it creates (task 0036).

``gmsh.model`` queries (``getBoundary``, ``getValue``, ``getType``) only
see entities after ``occ.synchronize``, and each synchronize rebuilds the
model from the whole OCC model, so calling it per slab makes the build
time grow with the square of the model size (decision 0020).  hexmesh
creates every point and curve it later asks about, so it records the
answers when it creates them:

- a curve's start and end point tags, in its parametric direction;
- a curve's kind, as ``gmsh.model.getType`` names it;
- a point's coordinates come from ``occ.getBoundingBox`` (its centre is
  exact and works before a synchronize; docs/integrations/gmsh.md).

The records are used only during an assembly build (inside
:func:`building`), which resets them when it starts, so every curve it
asks about was recorded in the current model.  Outside a build, and for a
curve that was not recorded, the model is synchronized once, lazily, and
queried as before.
``fallbacks`` counts those, so a benchmark shows when one happens.

Face builders also set their own mesh constraints, which needs a
synchronized model.  ``Assembly`` sets every face constraint again after
its one synchronize, so it builds faces inside :func:`building`, where the
builders skip theirs.
"""

from __future__ import annotations

from contextlib import contextmanager

import gmsh
import numpy as np

_ends: dict[int, tuple[int, int]] = {}
_kind: dict[int, str] = {}
_discarded: list[int] = []
fallbacks = 0
in_build = False


def reset() -> None:
    """Forget every record (tags restart in a new GMSH model)."""
    _ends.clear()
    _kind.clear()


@contextmanager
def building():
    """Inside an assembly build: records are trusted (the build reset them),
    face builders skip their mesh constraints (and the synchronizes they
    need), and construction points wait for one batch removal."""
    global in_build
    old, in_build = in_build, True
    try:
        yield
    finally:
        in_build = old


def _record(tag: int, start: int, end: int, kind: str) -> int:
    _ends[tag] = (start, end)
    _kind[tag] = kind
    return tag


def line(start: int, end: int) -> int:
    return _record(gmsh.model.occ.addLine(start, end), start, end, "Line")


def circle_arc(start: int, centre: int, end: int) -> int:
    return _record(gmsh.model.occ.addCircleArc(start, centre, end), start, end, "Circle")


def spline(points: list[int]) -> int:
    return _record(gmsh.model.occ.addSpline(points), points[0], points[-1], "BSpline")


def bspline(points: list[int], **kw) -> int:
    return _record(gmsh.model.occ.addBSpline(points, **kw), points[0], points[-1], "BSpline")


def discard(point: int) -> None:
    """Remove construction *point* (an arc centre, a control point).

    Each ``occ.remove`` costs time in proportion to the model, so inside
    :func:`building` the point stays until ``Assembly.fill`` removes every
    unattached point in one call.  OCC does not reuse a removed tag, so the
    tags of later entities are the same either way.
    """
    if in_build:
        _discarded.append(point)
    else:
        gmsh.model.occ.remove([(0, point)])


def remove_discarded() -> None:
    """Remove the points :func:`discard` kept, in one call."""
    if _discarded:
        gmsh.model.occ.remove([(0, p) for p in _discarded])
        _discarded.clear()


def _synchronized() -> None:
    global fallbacks
    fallbacks += 1
    gmsh.model.occ.synchronize()


def endpoints(curve: int) -> tuple[int, int]:
    """(start, end) point tags of *curve* in its parametric direction."""
    curve = abs(curve)
    if in_build and curve in _ends:
        return _ends[curve]
    _synchronized()
    return _model_endpoints(curve)


def kind(curve: int) -> str:
    curve = abs(curve)
    if in_build and curve in _kind:
        return _kind[curve]
    _synchronized()
    return gmsh.model.getType(1, curve)


def coords(point: int) -> np.ndarray:
    """Exact coordinates of *point*, before or after a synchronize."""
    bb = np.asarray(gmsh.model.occ.getBoundingBox(0, point))
    return 0.5 * (bb[:3] + bb[3:])


def _model_endpoints(curve: int) -> tuple[int, int]:
    """Start and end of *curve* read from the synchronized model.

    With the OCC kernel ``getBoundary`` lists a curve's two end points in
    ascending tag order, not start → end, so the start is the end point at
    the curve's lower parameter bound.
    """
    pts = [t for _, t in gmsh.model.getBoundary([(1, curve)], oriented=False)]
    if len(pts) != 2:
        raise RuntimeError(f"curve {curve} has {len(pts)} end points")
    lo = gmsh.model.getParametrizationBounds(1, curve)[0][0]
    x0 = np.asarray(gmsh.model.getValue(1, curve, [lo]))
    d = [np.linalg.norm(np.asarray(gmsh.model.getValue(0, p, [])) - x0) for p in pts]
    return (pts[0], pts[1]) if d[0] <= d[1] else (pts[1], pts[0])
