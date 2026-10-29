"""
Wall projection (decision 0029, task 0051): the tube-union projector
(hexmesh/assembly/projection.py) and its use in ``Assembly.mesh()``.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Wye, limits
from hexmesh.assembly.projection import Tube, TubeUnion
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

R = 0.1


def _wye_union(angle=60):
    h = math.radians(angle / 2)
    n = np.array([1.0, 0, 0])
    dl = np.array([math.cos(h), math.sin(h), 0])
    dr = np.array([math.cos(h), -math.sin(h), 0])
    return TubeUnion([Tube((0, 0, 0), tuple(d), R) for d in (-n, dl, dr)])


def _near_wall(union, n=4000, band=0.3, seed=0):
    p = np.random.default_rng(seed).uniform(-3 * R, 5 * R, (5 * n, 3))
    return p[np.abs(union.signed_distance(p)) < band * R][:n]


@pytest.mark.parametrize("angle", [60, 90])
def test_projections_land_on_the_wall(angle):
    """Both maps put every point on the union's boundary, and never inside
    another tube."""
    union = _wye_union(angle)
    p = _near_wall(union)
    for q in (union(p), union.nearest(p)):
        assert np.abs(union.signed_distance(q)).max() < 1e-12 * R
        inside = np.min([t.distance(q) - t.radius for t in union.tubes], axis=0)
        assert inside.min() > -1e-12 * R


def test_nearest_is_nearest():
    """No boundary point found by any route is nearer than ``nearest``."""
    union = _wye_union(60)
    p = _near_wall(union, 500)
    d = np.linalg.norm(union.nearest(p) - p, axis=1)
    for q in [union(p)] + [t.project(p) for t in union.tubes]:
        ok = np.abs(union.signed_distance(q)) < 1e-12 * R
        assert (d[ok] <= np.linalg.norm(q - p, axis=1)[ok] + 1e-12 * R).all()


def test_wall_points_stay():
    union = _wye_union(60)
    q = union.nearest(_near_wall(union, 500))
    np.testing.assert_allclose(union(q), q, atol=1e-12 * R)


@pytest.mark.parametrize("depth", [-0.01, 0.0, 0.01, 0.03])
def test_crease_keeps_order(depth):
    """A row of points across the crotch crease maps in order onto both
    flanks.  Just inside the crease, nearest points run backwards there,
    which folded the 60° wye's crotch cells (task 0051)."""
    union = _wye_union(60)
    apex = R / math.sin(math.radians(30))           # the crease on the mirror plane
    y = np.linspace(-0.3 * R, 0.3 * R, 25)
    p = np.c_[np.full_like(y, apex + depth), y, np.full_like(y, 0.02)]
    assert (np.diff(union(p)[:, 1]) > 0).all()
    if depth < 0:
        assert not (np.diff(union.nearest(p)[:, 1]) > 0).all()


def test_tee_union():
    """The tee's wall: a whole main line and a branch ray."""
    union = TubeUnion([Tube((0, 0, 0), (1, 0, 0), R, ray=False), Tube((0, 0, 0), (0, 0, 1), R / 2)])
    p = _near_wall(union, 2000, band=0.2)
    assert np.abs(union.signed_distance(union(p))).max() < 1e-12 * R
    below = np.array([[0.0, 0.0, -1.5 * R]])          # under the main line: no branch there
    np.testing.assert_allclose(union(below), [[0, 0, -R]], atol=1e-12)


# ---------------------------------------------------------------------------
# In the assembly
# ---------------------------------------------------------------------------

def _spec(nang=4, nrad=3):
    return PipeSpec(nang=nang).core("fluid", CircleShape(radius=R, nang=nang), nrad=nrad)


def _wye(angle=60, nang=4):
    asm = Assembly(_spec(nang), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.2, n_layers=2))
    a, b = asm.add(Wye(angle, run_length=0.4, branch_length=0.7), names=["a", "b"])
    asm.add(a, Straight(0.2, n_layers=2))
    asm.add(b, Straight(0.2, n_layers=2))
    return asm


@pytest.mark.parametrize("angle, nang", [(30, 8), (30, 16), (40, 16), (45, 16), (60, 8),
                                         (60, 16), (90, 16)])
def test_wye_projected_without_folds(gmsh_session, angle, nang):
    """The 60° wye's crotch folded under nearest-point projection at nang 8,
    and 30–50° wyes with a narrow smoothing (task 0051); along the smoothed
    direction none do."""
    asm = _wye(angle, nang)
    asm.mesh()
    report = asm.check_quality()
    assert report.ok and report.min_quality > 0, str(report)
    rep = asm.projection_report["Wye1"]
    assert 0.05 * R < rep["move"] < R                 # it did move the crotch
    assert rep["ratio"] <= limits.WALL_PROJECTION_MAX_MOVE


def test_shared_nodes_do_not_move(gmsh_session, monkeypatch):
    """Nodes on the wye's ports, shared with the swept straights, are on
    both walls already: projection leaves them where they are."""
    asm = _wye(60, 8)
    project = Assembly._project_walls
    seen = {}

    def spy(self):
        ports = {abs(s) for i in self.interfaces for _, cs in i.face.layers for s in cs.surfaces}
        nodes = lambda: np.vstack([gmsh.model.mesh.getNodes(2, s, includeBoundary=True)[1].reshape(-1, 3)
                                   for s in sorted(ports)])
        seen["before"] = nodes()
        out = project(self)
        seen["after"] = nodes()
        return out
    monkeypatch.setattr(Assembly, "_project_walls", spy)
    asm.mesh()
    assert np.abs(seen["after"] - seen["before"]).max() < 1e-12 * R


def test_move_limit_names_the_fitting(gmsh_session, monkeypatch):
    monkeypatch.setattr(limits, "WALL_PROJECTION_MAX_MOVE", 0.1)
    with pytest.raises(AssemblyError, match=r"Wye1: wall projection moves a node .* local cell heights, limit 0\.1"):
        _wye(60, 4).mesh()


def test_surface_mesh_is_projected_too(gmsh_session):
    """``mesh(2)`` projects as well: the wall is exact without volumes."""
    asm = _wye(60, 4)
    asm.mesh(2)
    e = asm.edges[1]
    sk = e.fitting.skeleton(e.ports[0].frame, e.ports[0].spec)
    vols = asm.fitting_volumes()[e.index]
    walls = {abs(t) for _, t in gmsh.model.getBoundary([(3, v) for v in vols], combined=False,
                                                     oriented=False)} & set(asm._fill.walls)
    x = np.vstack([gmsh.model.mesh.getNodes(2, s, includeBoundary=True)[1].reshape(-1, 3) for s in walls])
    assert np.abs(sk.distance(x) - R).max() < 1e-9 * R
