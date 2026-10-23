"""
Tests for SplinePipe connector.

Tests cover:
  - Pure-Python helpers (_sample_spline, _bishop_frames) — no GMSH needed
  - Structural connector tests via Network.add() — require gmsh_session
"""

import math
import pytest
import numpy as np

from hexmesh.core.cursor import Cursor, Plane
from hexmesh.core.spec import PipeSpec
from hexmesh.core.shape import CircleShape
from hexmesh.network import Network
from hexmesh.connectors import SplinePipe
from hexmesh.connectors.spline_pipe import (
    _sample_spline,
    _bishop_frames,
    _rodrigues,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xz_cursor(pos=None):
    return Cursor.from_plane(Plane.XZ, position=pos or [0., 0., 0.])


def _circle_pipe(nrad=3):
    return (
        PipeSpec(nang=4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=nrad)
    )


def _two_layer_pipe():
    return (
        PipeSpec(nang=4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
        .shell("wall", dR=0.025, nrad=2)
    )


# ===========================================================================
# Pure-Python helper tests (no GMSH)
# ===========================================================================

class TestRodrigues:
    def test_rotate_90_around_z(self):
        v    = np.array([1.0, 0.0, 0.0])
        axis = np.array([0.0, 0.0, 1.0])
        r    = _rodrigues(v, axis, math.pi / 2)
        np.testing.assert_allclose(r, [0., 1., 0.], atol=1e-10)

    def test_rotate_180_around_y(self):
        v    = np.array([1.0, 0.0, 0.0])
        axis = np.array([0.0, 1.0, 0.0])
        r    = _rodrigues(v, axis, math.pi)
        np.testing.assert_allclose(r, [-1., 0., 0.], atol=1e-10)

    def test_zero_angle_identity(self):
        v    = np.array([0.5, 0.3, 0.8])
        axis = np.array([0.0, 0.0, 1.0])
        r    = _rodrigues(v, axis, 0.0)
        np.testing.assert_allclose(r, v, atol=1e-12)


class TestSampleSpline:
    def test_straight_line(self):
        """Spline through collinear waypoints should produce a straight line."""
        wps = [[0, 0, 0], [0, 0.5, 0], [0, 1.0, 0]]
        tangent_0 = np.array([0., 1., 0.])
        pos, tans = _sample_spline(wps, n_stations=5, tangent_0=tangent_0)
        assert pos.shape == (6, 3)
        assert tans.shape == (6, 3)
        # All positions should lie on the Y axis
        np.testing.assert_allclose(pos[:, 0], 0., atol=1e-8)
        np.testing.assert_allclose(pos[:, 2], 0., atol=1e-8)
        # Positions should be uniformly spaced in Y
        diffs = np.diff(pos[:, 1])
        np.testing.assert_allclose(diffs, diffs[0], rtol=1e-4)

    def test_station_count(self):
        wps = [[0, 0, 0], [0, 1, 0]]
        pos, tans = _sample_spline(wps, n_stations=10, tangent_0=np.array([0., 1., 0.]))
        assert pos.shape == (11, 3)
        assert tans.shape == (11, 3)

    def test_start_position(self):
        """Station 0 should coincide with the first waypoint."""
        wps = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        pos, _ = _sample_spline(wps, n_stations=4, tangent_0=np.array([1., 1., 1.]) / 3**0.5)
        np.testing.assert_allclose(pos[0], wps[0], atol=1e-8)

    def test_end_position(self):
        """Last station should coincide with the last waypoint."""
        wps = [[0, 0, 0], [0, 1, 0]]
        pos, _ = _sample_spline(wps, n_stations=5, tangent_0=np.array([0., 1., 0.]))
        np.testing.assert_allclose(pos[-1], wps[-1], atol=1e-6)

    def test_tangents_unit_length(self):
        wps = [[0, 0, 0], [0.1, 0.2, 0.0], [0.0, 0.4, 0.0]]
        pos, tans = _sample_spline(wps, n_stations=8, tangent_0=np.array([0., 1., 0.]))
        norms = np.linalg.norm(tans, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-8)

    def test_requires_two_waypoints(self):
        with pytest.raises(ValueError, match="at least 2"):
            _sample_spline([[0, 0, 0]], n_stations=5, tangent_0=np.array([0., 1., 0.]))


class TestBishopFrames:
    def test_straight_pipe_no_rotation(self):
        """Bishop frames along a straight line should have constant h and v."""
        N = 5
        positions = np.array([[0., i * 0.1, 0.] for i in range(N)])
        tangents  = np.tile([0., 1., 0.], (N, 1)).astype(float)
        h0 = np.array([1., 0., 0.])
        v0 = np.array([0., 0., 1.])
        frames = _bishop_frames(positions, tangents, h0, v0)
        assert len(frames) == N
        for fr in frames:
            np.testing.assert_allclose(fr['h'], h0, atol=1e-10)
            np.testing.assert_allclose(fr['v'], v0, atol=1e-10)

    def test_frame_orthogonality(self):
        """T, h, v must remain mutually orthogonal at all stations."""
        wps = [[0, 0, 0], [0.05, 0.1, 0.0], [0.0, 0.2, 0.05]]
        pos, tans = _sample_spline(wps, n_stations=8, tangent_0=np.array([0., 1., 0.]))
        frames = _bishop_frames(pos, tans, np.array([1., 0., 0.]), np.array([0., 0., 1.]))
        for fr in frames:
            T, h, v = fr['T'], fr['h'], fr['v']
            assert abs(np.dot(T, h)) < 1e-8, "T and h not orthogonal"
            assert abs(np.dot(T, v)) < 1e-8, "T and v not orthogonal"
            assert abs(np.dot(h, v)) < 1e-8, "h and v not orthogonal"

    def test_frame_unit_vectors(self):
        """h and v must remain unit vectors."""
        wps = [[0, 0, 0], [0.1, 0.1, 0.1], [0.2, 0.3, 0.0]]
        pos, tans = _sample_spline(wps, n_stations=6, tangent_0=np.array([0., 1., 0.]))
        frames = _bishop_frames(pos, tans, np.array([1., 0., 0.]), np.array([0., 0., 1.]))
        for fr in frames:
            assert abs(np.linalg.norm(fr['h']) - 1.0) < 1e-8
            assert abs(np.linalg.norm(fr['v']) - 1.0) < 1e-8


# ===========================================================================
# Structural connector tests (require GMSH)
# ===========================================================================

class TestSplinePipeConnector:
    def test_returns_node(self, gmsh_session):
        """net.add(SplinePipe(...)) should return a single Node."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.3, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        assert node is not None

    def test_straight_spline_cursor_position(self, gmsh_session):
        """Straight spline should advance cursor by total path length."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.4, 0]],
            n_stations = 4,
            n_layers   = 1,
        ))
        # Cursor should end near [0, 0.4, 0]
        np.testing.assert_allclose(
            node.cursor.position, [0., 0.4, 0.], atol=1e-5
        )

    def test_straight_spline_cursor_direction(self, gmsh_session):
        """Straight spline: cursor direction should remain [0,1,0]."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.4, 0]],
            n_stations = 4,
            n_layers   = 1,
        ))
        np.testing.assert_allclose(
            node.cursor.direction, [0., 1., 0.], atol=1e-5
        )

    def test_fluid_region_present(self, gmsh_session):
        """SplinePipe must register the 'fluid' region."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.3, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        assert "fluid" in net._all_regions
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_inlets_and_outlets_recorded(self, gmsh_session):
        """SplinePipe must register non-empty inlets and outlets for each material."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.3, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        rset = net._all_regions["fluid"]
        assert len(rset.inlets)  > 0
        assert len(rset.outlets) > 0

    def test_walls_recorded(self, gmsh_session):
        """SplinePipe must register outer wall surfaces."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.3, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        rset = net._all_regions["fluid"]
        assert len(rset.walls) > 0

    def test_two_layer_pipe(self, gmsh_session):
        """SplinePipe should handle multi-layer pipes (fluid + wall)."""
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.3, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        assert "fluid" in net._all_regions
        assert "wall"  in net._all_regions
        assert len(net._all_regions["fluid"].volumes) > 0
        assert len(net._all_regions["wall"].volumes)  > 0

    def test_curved_path(self, gmsh_session):
        """SplinePipe should work for a gently curved path (90° bend)."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        # Gentle S-shape in the XY plane
        node = net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0.05, 0.15, 0], [0.1, 0.3, 0]],
            n_stations = 5,
            n_layers   = 1,
        ))
        assert node is not None
        assert "fluid" in net._all_regions
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_chained_after_straight(self, gmsh_session):
        """SplinePipe can follow a Straight connector."""
        from hexmesh.connectors import Straight
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.1, n_layers=1))
        node = net.add(SplinePipe(
            waypoints  = [[0, 0.1, 0], [0, 0.4, 0]],
            n_stations = 3,
            n_layers   = 1,
        ))
        assert node is not None
        np.testing.assert_allclose(
            node.cursor.position, [0., 0.4, 0.], atol=1e-5
        )

    def test_invalid_single_waypoint(self):
        with pytest.raises(ValueError, match="at least 2"):
            SplinePipe(waypoints=[[0, 0, 0]])

    def test_invalid_zero_stations(self):
        with pytest.raises(ValueError, match="n_stations"):
            SplinePipe(waypoints=[[0, 0, 0], [0, 1, 0]], n_stations=0)

    def test_invalid_zero_layers(self):
        with pytest.raises(ValueError, match="n_layers"):
            SplinePipe(waypoints=[[0, 0, 0], [0, 1, 0]], n_layers=0)

    def test_volume_count_scales_with_stations(self, gmsh_session):
        """Volume count should scale with n_stations × layers × patches."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_stations = 4
        n_layers   = 1
        net.add(SplinePipe(
            waypoints  = [[0, 0, 0], [0, 0.4, 0]],
            n_stations = n_stations,
            n_layers   = n_layers,
        ))
        vols = net._all_regions["fluid"].volumes
        # 5-patch OH: 5 volumes per slab; n_stations slabs; n_layers axial
        expected = 5 * n_stations * n_layers
        assert len(vols) == expected
