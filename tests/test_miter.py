"""
Miter bends and standard elbows (docs/tasks/0012).

A miter cut face is the station face stretched into the exact ellipse where
the two pipe cylinders meet; its wall nodes must lie on both cylinders.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Elbow, MiterBend, Straight
from hexmesh.assembly.interface import Frame, outer_radius
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(shell=True):
    spec = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
    return spec.shell("wall", dR=0.02, nrad=2) if shell else spec


A = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])


def _axes(miter, spec):
    """(point, direction) of every straight segment's centreline."""
    pts = miter.corners(A) + [miter.ports(A, spec)[0][0].position]
    return [(p, (q - p) / np.linalg.norm(q - p)) for p, q in zip(pts, pts[1:])]


def _dist_to_line(x, line):
    p, d = line
    v = x - p
    return np.linalg.norm(v - np.outer(v @ d, d), axis=1)


class TestGeometry:
    def test_ports_match_smooth_bend(self):
        spec = _spec()
        for m in (MiterBend(0.3, 90), MiterBend(0.3, -60, n_cuts=3, roll=30)):
            bend = Bend(m.radius, m.angle, 4, m.roll)
            (a, _), = m.ports(A, spec)
            (b, _), = bend.ports(A, spec)
            np.testing.assert_allclose(a.position, b.position, atol=1e-12)
            np.testing.assert_allclose(a.normal, b.normal, atol=1e-12)
            np.testing.assert_allclose(a.up, b.up, atol=1e-12)

    def test_segments_are_tangent_polygon(self):
        m, spec = MiterBend(0.3, 90, n_cuts=3), _spec()
        pts = m.corners(A) + [m.ports(A, spec)[0][0].position]
        lengths = [np.linalg.norm(q - p) for p, q in zip(pts, pts[1:])]
        half = 0.3 * math.tan(math.radians(15))
        np.testing.assert_allclose(lengths, [half, 2 * half, 2 * half, half], rtol=1e-12)

    @pytest.mark.parametrize("n_cuts", [1, 3])
    def test_wall_nodes_exact(self, gmsh_session, n_cuts):
        """Every wall node is on a pipe cylinder; cut nodes are on two."""
        spec, m = _spec(), MiterBend(0.3, 90, n_cuts=n_cuts, n_layers=2)
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
        asm.add(m)
        asm.mesh()
        R = outer_radius(spec)
        axes = _axes(m, spec)
        walls = [(2, w) for w in asm._fill.walls]
        on_two = 0
        for _, c in gmsh.model.getBoundary(walls, combined=False, oriented=False):
            _, x, _ = gmsh.model.mesh.getNodes(1, abs(c), includeBoundary=True)
            dev = np.array([np.abs(_dist_to_line(x.reshape(-1, 3), ax) - R).max()
                            for ax in axes])
            hits = np.flatnonzero(dev < 1e-9 * R)
            assert hits.size >= 1, f"curve {c} off every cylinder by {dev.min() / R:.2e} R"
            if hits.size == 2:
                assert hits[1] - hits[0] == 1          # the two adjacent pipes
                on_two += 1
        assert on_two == 2 * 4 * n_cuts                 # 4 arcs per cut, counted per wall

        for w in asm._fill.walls:
            _, x, _ = gmsh.model.mesh.getNodes(2, w, includeBoundary=False)
            assert x.size == 0, "wall nodes off the station curves"


    def test_fine_station_spacing(self, gmsh_session):
        """Stations 0.125° apart: OCC plate filling left holes here."""
        asm = Assembly(_spec(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
        with pytest.warns(UserWarning, match="looks like radians"):   # 5° is meant
            asm.add(MiterBend(0.3, 5, n_cuts=1, n_layers=20))
        asm.mesh()
        assert asm.check_quality().ok


class TestValidation:
    def test_cut_angle_limits(self):
        with pytest.raises(ValueError, match="limit 90°.*n_cuts >= 2"):
            MiterBend(0.3, 120).check(_spec())
        with pytest.raises(ValueError, match="below 1°"):
            MiterBend(0.3, 5, n_cuts=10).check(_spec())
        MiterBend(0.3, 180, n_cuts=2).check(_spec())

    def test_radius_must_exceed_pipe(self):
        asm = Assembly(_spec(), lc=0.05)
        asm.add(MiterBend(0.11, 90))
        with pytest.raises(AssemblyError, match="tighter than"):
            asm.validate()

    def test_cell_count_without_gmsh(self):
        asm = Assembly(_spec(), lc=0.05)
        asm.add(MiterBend(0.3, 90, n_cuts=3, n_layers=2))
        asm.validate()
        assert not gmsh.isInitialized()
        section = 4 * 4 + 4 * 4 * (3 + 2)
        assert asm.cell_count() == section * (2 + 4 + 4 + 2)


class TestElbow:
    @pytest.mark.parametrize("schedule, factor", [("long", 1.5), ("short", 1.0)])
    @pytest.mark.parametrize("shell", [False, True])
    def test_radius_from_outer_diameter(self, schedule, factor, shell):
        spec = _spec(shell)
        e = Elbow(90, schedule)
        assert e.radius(spec) == pytest.approx(factor * 2 * outer_radius(spec))
        (a, _), = e.ports(A, spec)
        (b, _), = Bend(e.radius(spec), 90, 8).ports(A, spec)
        np.testing.assert_allclose(a.position, b.position, atol=1e-12)

    def test_unknown_schedule(self):
        with pytest.raises(ValueError, match="schedule"):
            Elbow(90, "medium").check(_spec())
