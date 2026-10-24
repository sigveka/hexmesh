"""
Spline pipe (docs/tasks/0014).

Ports the applicable assertions of the legacy ``tests/test_spline_pipe.py``
to the assembly API: station sampling, Bishop frames, outlet placement,
validation and meshing.  Rodrigues rotation and connector bookkeeping
(nodes, inlet/outlet lists) have no counterpart here; the conformance kit
covers groups, walls and interfaces.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, SplinePipe, Straight
from hexmesh.assembly.fittings import _cubic_spline, _transported_stations
from hexmesh.assembly.interface import Frame, outer_radius
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(shell=False):
    spec = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.05, nang=4), nrad=3)
    return spec.shell("wall", dR=0.01, nrad=2) if shell else spec


A = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
S_BEND = ((0, 0, 0), (0.3, 0.05, 0), (0.6, 0.25, 0), (0.9, 0.3, 0))
CURVE_3D = ((0, 0, 0), (0.3, 0.1, 0.05), (0.5, 0.35, 0.2), (0.6, 0.6, 0.4))


class TestSpline:
    def test_straight_line(self):
        c = _cubic_spline(np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.]]), np.array([1., 0, 0]))
        pos, d1, d2 = c(np.linspace(0, 1, 11))
        np.testing.assert_allclose(pos[:, 0], np.linspace(0, 2, 11), atol=1e-12)
        np.testing.assert_allclose(pos[:, 1:], 0, atol=1e-12)
        np.testing.assert_allclose(d2, 0, atol=1e-9)

    def test_interpolates_and_clamps(self):
        P = np.array(CURVE_3D, dtype=float)
        c = _cubic_spline(P, np.array([1., 0, 0]), np.array([0, 0.6, 0.8]))
        h = np.linalg.norm(np.diff(P, axis=0), axis=1)
        pos, d1, _ = c(np.concatenate([[0], np.cumsum(h)]) / h.sum())
        np.testing.assert_allclose(pos, P, atol=1e-14)
        np.testing.assert_allclose(d1[0] / np.linalg.norm(d1[0]), [1, 0, 0], atol=1e-12)
        np.testing.assert_allclose(d1[-1] / np.linalg.norm(d1[-1]), [0, 0.6, 0.8], atol=1e-12)


class TestStations:
    def test_station_count_and_ends(self):
        f = SplinePipe(S_BEND, n_layers=10)
        out = f.ports(A, _spec())[0][0]
        frames = f.path(A, out, _spec()).frames
        assert len(frames) == 11
        np.testing.assert_allclose(frames[0].position, S_BEND[0], atol=1e-14)
        np.testing.assert_allclose(frames[-1].position, S_BEND[-1], atol=1e-12)

    def test_straight_pipe_no_rotation(self):
        f = SplinePipe(((0, 0, 0), (0.5, 0, 0), (1, 0, 0)), n_layers=5)
        for fr in f.path(A, f.ports(A, _spec())[0][0], _spec()).frames:
            np.testing.assert_allclose(fr.normal, A.normal, atol=1e-12)
            np.testing.assert_allclose(fr.up, A.up, atol=1e-12)

    def test_frames_orthonormal(self):
        f = SplinePipe(CURVE_3D, n_layers=12)
        for fr in f.path(A, f.ports(A, _spec())[0][0], _spec()).frames:
            for v in (fr.normal, fr.up):
                assert np.linalg.norm(v) == pytest.approx(1.0, abs=1e-12)
            assert abs(np.dot(fr.normal, fr.up)) < 1e-12

    def test_bishop_frames_do_not_twist(self):
        """Parallel transport: up turns only by the turn of the tangent."""
        curve = _cubic_spline(np.array(CURVE_3D, dtype=float), A.normal)
        frames, twist = _transported_stations(curve, 200, A)
        assert twist == 0.0
        for a, b in zip(frames, frames[1:]):
            # transported up has no component of rotation about the tangent
            w = np.cross(a.up, b.up)
            assert abs(np.dot(w, a.normal + b.normal)) < 1e-4

    def test_outlet_follows_end_tangent(self):
        f = SplinePipe(S_BEND, n_layers=10, end_tangent=(0, 1, 0))
        out = f.ports(A, _spec())[0][0]
        np.testing.assert_allclose(out.normal, [0, 1, 0], atol=1e-12)


class TestValidation:
    def test_first_point_must_be_inlet(self):
        with pytest.raises(ValueError, match="not the inlet position"):
            SplinePipe(((0.1, 0, 0), (1, 0, 0)), n_layers=3).ports(A, _spec())

    @pytest.mark.parametrize("points", [((0, 0, 0),), ((0, 0, 0), (0, 0, 0))],
                             ids=["single", "coincident"])
    def test_invalid_points(self, points):
        with pytest.raises(ValueError, match="at least two|coincide"):
            SplinePipe(points, n_layers=3).ports(A, _spec())

    def test_zero_layers(self):
        with pytest.raises(ValueError, match="n_layers"):
            SplinePipe(S_BEND, n_layers=0).ports(A, _spec())

    def test_too_tight(self):
        asm = Assembly(_spec(), lc=0.05)
        asm.add(SplinePipe(((0, 0, 0), (0.05, 0.05, 0), (0, 0.1, 0)), n_layers=20))
        with pytest.raises(AssemblyError, match="tighter than"):
            asm.validate()

    def test_too_few_stations(self):
        asm = Assembly(_spec(), lc=0.05)
        asm.add(SplinePipe(S_BEND, n_layers=10, end_tangent=(-1, 0.2, 0)))
        with pytest.raises(AssemblyError, match="use more axial layers|tighter than"):
            asm.validate()


class TestMesh:
    @pytest.mark.parametrize("points", [S_BEND, CURVE_3D], ids=["s-bend", "3d"])
    @pytest.mark.parametrize("shell", [False, True], ids=["1layer", "2layer"])
    def test_chained_and_meshed(self, gmsh_session, points, shell):
        spec = _spec(shell)
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
        asm.add(Straight(0.1, n_layers=2))
        start = asm.interfaces[-1].frame.position
        asm.add(SplinePipe(tuple(tuple(np.add(p, start)) for p in points), n_layers=16))
        asm.add(Straight(0.1, n_layers=2))
        asm.validate()
        predicted = asm.cell_count()
        asm.mesh()
        assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted
        assert asm.check_quality().ok

    def test_cells_scale_with_layers(self):
        counts = []
        for n in (8, 16):
            asm = Assembly(_spec(), lc=0.05)
            asm.add(SplinePipe(S_BEND, n_layers=n))
            asm.validate()
            counts.append(asm.cell_count())
        assert counts[1] == 2 * counts[0]
