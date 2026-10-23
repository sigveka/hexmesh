"""
Unit tests for pure-Python data structures:
  CircleShape, RectShape, Cursor, PipeSpec.

No GMSH required — all tests run without a gmsh_session fixture.
"""

import math
import pytest
import numpy as np

from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.cursor import Cursor, Plane
from hexmesh.core.spec import PipeSpec


# ===========================================================================
# CircleShape
# ===========================================================================

class TestCircleShape:
    def test_valid_construction(self):
        s = CircleShape(radius=0.3, nang=5)
        assert s.radius == 0.3
        assert s.nang == 5

    def test_max_extent_equals_radius(self):
        s = CircleShape(radius=0.25, nang=4)
        assert s.max_extent == pytest.approx(0.25)

    def test_frozen(self):
        s = CircleShape(radius=0.1, nang=4)
        with pytest.raises((AttributeError, TypeError)):
            s.radius = 0.2  # type: ignore[misc]

    def test_zero_radius_rejected(self):
        with pytest.raises(ValueError):
            CircleShape(radius=0.0, nang=5)

    def test_negative_radius_rejected(self):
        with pytest.raises(ValueError):
            CircleShape(radius=-0.1, nang=5)

    def test_zero_nang_rejected(self):
        with pytest.raises(ValueError):
            CircleShape(radius=0.1, nang=0)

    def test_negative_nang_rejected(self):
        with pytest.raises(ValueError):
            CircleShape(radius=0.1, nang=-1)


# ===========================================================================
# RectShape
# ===========================================================================

class TestRectShape:
    def test_valid_construction(self):
        s = RectShape(half_w=0.1, half_h=0.2, nang_w=3, nang_h=4)
        assert s.half_w == 0.1
        assert s.half_h == 0.2
        assert s.nang_w == 3
        assert s.nang_h == 4

    def test_max_extent_is_corner_diagonal(self):
        # 3-4-5 right triangle
        s = RectShape(half_w=0.03, half_h=0.04, nang_w=2, nang_h=2)
        assert s.max_extent == pytest.approx(0.05)

    def test_max_extent_square(self):
        s = RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=3)
        assert s.max_extent == pytest.approx(math.sqrt(2) * 0.1)

    def test_is_square_true(self):
        s = RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=3)
        assert s.is_square

    def test_is_square_false_dims(self):
        s = RectShape(half_w=0.1, half_h=0.2, nang_w=3, nang_h=3)
        assert not s.is_square

    def test_is_square_false_nang(self):
        s = RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=4)
        assert not s.is_square

    def test_zero_half_w_rejected(self):
        with pytest.raises(ValueError):
            RectShape(half_w=0.0, half_h=0.1, nang_w=3, nang_h=3)

    def test_zero_half_h_rejected(self):
        with pytest.raises(ValueError):
            RectShape(half_w=0.1, half_h=0.0, nang_w=3, nang_h=3)

    def test_zero_nang_w_rejected(self):
        with pytest.raises(ValueError):
            RectShape(half_w=0.1, half_h=0.1, nang_w=0, nang_h=3)

    def test_zero_nang_h_rejected(self):
        with pytest.raises(ValueError):
            RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=0)

    def test_frozen(self):
        s = RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=3)
        with pytest.raises((AttributeError, TypeError)):
            s.half_w = 0.2  # type: ignore[misc]


# ===========================================================================
# Cursor
# ===========================================================================

class TestCursorFromPlane:
    """Cursor.from_plane should produce correct direction/up/right."""

    def test_xz_direction(self):
        c = Cursor.from_plane(Plane.XZ)
        np.testing.assert_allclose(c.direction, [0., 1., 0.], atol=1e-12)

    def test_xz_up_is_plus_z(self):
        # Fixed bug: was −Z, now +Z
        c = Cursor.from_plane(Plane.XZ)
        np.testing.assert_allclose(c.up, [0., 0., 1.], atol=1e-12)

    def test_xz_right_is_plus_x(self):
        c = Cursor.from_plane(Plane.XZ)
        np.testing.assert_allclose(c.right, [1., 0., 0.], atol=1e-12)

    def test_xy_direction(self):
        c = Cursor.from_plane(Plane.XY)
        np.testing.assert_allclose(c.direction, [0., 0., 1.], atol=1e-12)

    def test_xy_up_is_plus_y(self):
        c = Cursor.from_plane(Plane.XY)
        np.testing.assert_allclose(c.up, [0., 1., 0.], atol=1e-12)

    def test_yz_direction(self):
        c = Cursor.from_plane(Plane.YZ)
        np.testing.assert_allclose(c.direction, [1., 0., 0.], atol=1e-12)

    def test_yz_up_is_plus_z(self):
        c = Cursor.from_plane(Plane.YZ)
        np.testing.assert_allclose(c.up, [0., 0., 1.], atol=1e-12)

    def test_right_orthogonal_to_direction(self):
        for plane in (Plane.XY, Plane.XZ, Plane.YZ):
            c = Cursor.from_plane(plane)
            assert abs(np.dot(c.direction, c.right)) < 1e-12

    def test_right_orthogonal_to_up(self):
        for plane in (Plane.XY, Plane.XZ, Plane.YZ):
            c = Cursor.from_plane(plane)
            assert abs(np.dot(c.up, c.right)) < 1e-12

    def test_custom_position(self):
        c = Cursor.from_plane(Plane.XZ, position=[1.0, 2.0, 3.0])
        np.testing.assert_allclose(c.position, [1., 2., 3.], atol=1e-12)

    def test_default_position_is_origin(self):
        c = Cursor.from_plane(Plane.XZ)
        np.testing.assert_allclose(c.position, [0., 0., 0.], atol=1e-12)


class TestCursorValidation:
    def test_non_orthogonal_rejected(self):
        """direction and up must be perpendicular."""
        with pytest.raises(ValueError, match="perpendicular"):
            Cursor(
                position=[0., 0., 0.],
                direction=[1., 0., 0.],
                up=[1., 0., 0.],  # parallel — invalid
            )

    def test_nearly_parallel_rejected(self):
        with pytest.raises(ValueError):
            Cursor(
                position=[0., 0., 0.],
                direction=[1., 0., 0.],
                up=[0.9999, 0.01, 0.],  # nearly parallel
            )

    def test_direction_auto_normalized(self):
        c = Cursor(
            position=[0., 0., 0.],
            direction=[0., 2., 0.],  # magnitude 2
            up=[0., 0., 1.],
        )
        assert np.linalg.norm(c.direction) == pytest.approx(1.0)

    def test_up_auto_normalized(self):
        c = Cursor(
            position=[0., 0., 0.],
            direction=[0., 1., 0.],
            up=[0., 0., 5.],  # magnitude 5
        )
        assert np.linalg.norm(c.up) == pytest.approx(1.0)


class TestCursorAdvanced:
    def test_position_moves_along_direction(self):
        c = Cursor.from_plane(Plane.XZ)  # direction = +Y
        c2 = c.advanced(0.5)
        np.testing.assert_allclose(c2.position, [0., 0.5, 0.], atol=1e-12)

    def test_direction_unchanged(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.advanced(1.0)
        np.testing.assert_allclose(c2.direction, c.direction, atol=1e-12)

    def test_up_unchanged(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.advanced(1.0)
        np.testing.assert_allclose(c2.up, c.up, atol=1e-12)

    def test_zero_length(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.advanced(0.0)
        np.testing.assert_allclose(c2.position, c.position, atol=1e-12)

    def test_negative_length(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.advanced(-0.3)
        np.testing.assert_allclose(c2.position, [0., -0.3, 0.], atol=1e-12)


class TestCursorRotated:
    """Invariants after rotation: unit vectors, orthogonality, correct angle."""

    def test_direction_is_unit_vector(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.up, math.radians(45))
        assert np.linalg.norm(c2.direction) == pytest.approx(1.0)

    def test_up_is_unit_vector(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.right, math.radians(30))
        assert np.linalg.norm(c2.up) == pytest.approx(1.0)

    def test_direction_up_remain_orthogonal(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.up, math.radians(60))
        assert abs(np.dot(c2.direction, c2.up)) < 1e-10

    def test_rotation_angle_matches(self):
        """The angle between old and new direction equals the rotation angle."""
        c = Cursor.from_plane(Plane.XZ)
        angle = math.radians(37)
        c2 = c.rotated(c.up, angle)
        dot = np.dot(c.direction, c2.direction)
        assert dot == pytest.approx(math.cos(angle), abs=1e-10)

    def test_rotation_around_up_preserves_up(self):
        """Rotating around the up axis should leave up unchanged."""
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.up, math.radians(90))
        np.testing.assert_allclose(c2.up, c.up, atol=1e-10)

    def test_rotation_around_right_preserves_right(self):
        """Rotating around the right axis should leave right unchanged."""
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.right, math.radians(45))
        np.testing.assert_allclose(c2.right, c.right, atol=1e-10)

    def test_position_unchanged(self):
        c = Cursor.from_plane(Plane.XZ, position=[1., 2., 3.])
        c2 = c.rotated(c.up, math.radians(90))
        np.testing.assert_allclose(c2.position, [1., 2., 3.], atol=1e-12)

    def test_identity_rotation(self):
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.up, 0.0)
        np.testing.assert_allclose(c2.direction, c.direction, atol=1e-10)
        np.testing.assert_allclose(c2.up, c.up, atol=1e-10)

    def test_full_circle(self):
        """360° rotation returns the original direction."""
        c = Cursor.from_plane(Plane.XZ)
        c2 = c.rotated(c.up, 2 * math.pi)
        np.testing.assert_allclose(c2.direction, c.direction, atol=1e-10)


# ===========================================================================
# PipeSpec builder
# ===========================================================================

class TestPipeSpec:
    def test_single_circular_layer(self):
        pipe = PipeSpec().core("fluid", CircleShape(0.1, 4), nrad=3)
        assert pipe.layer_names == ["fluid"]
        assert pipe.nang == 4

    def test_core_plus_shells(self):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid",  CircleShape(0.1, 4), nrad=3)
            .shell("wall",  dR=0.02, nrad=2)
            .shell("outer", dR=0.01, nrad=2)
        )
        assert pipe.layer_names == ["fluid", "wall", "outer"]
        assert len(pipe.shells) == 2

    def test_core_with_square_shell(self):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(0.1, 4), nrad=3)
            .square_shell("sq", half_w=0.2, half_h=0.2, nrad=2)
        )
        assert pipe.layer_names == ["fluid", "sq"]

    def test_core_called_twice_raises(self):
        with pytest.raises(RuntimeError, match="once"):
            (
                PipeSpec()
                .core("a", CircleShape(0.1, 4), nrad=3)
                .core("b", CircleShape(0.1, 4), nrad=3)
            )

    def test_shell_before_core_raises(self):
        with pytest.raises(RuntimeError, match="core"):
            PipeSpec(nang=4).shell("wall", dR=0.02, nrad=2)

    def test_shell_after_square_shell_raises(self):
        with pytest.raises(RuntimeError, match="square_shell"):
            (
                PipeSpec(nang=4)
                .core("fluid", CircleShape(0.1, 4), nrad=3)
                .square_shell("sq", half_w=0.2, half_h=0.2, nrad=2)
                .shell("extra", dR=0.01, nrad=2)
            )

    def test_square_shell_requires_circle_core(self):
        with pytest.raises(TypeError, match="circular"):
            (
                PipeSpec(nang_w=3, nang_h=2)
                .core("air", RectShape(0.1, 0.08, 3, 2), nrad=3)
                .square_shell("sq", half_w=0.2, half_h=0.2, nrad=2)
            )

    def test_nang_mismatch_raises(self):
        with pytest.raises(ValueError, match="nang"):
            PipeSpec(nang=5).core("fluid", CircleShape(0.1, nang=4), nrad=3)

    def test_rect_pipe_nang(self):
        pipe = PipeSpec().core("air", RectShape(0.1, 0.05, 3, 2), nrad=3)
        assert pipe.nang_w == 3
        assert pipe.nang_h == 2
        assert pipe.nang is None

    def test_graph_single_layer(self):
        pipe = PipeSpec().core("fluid", CircleShape(0.1, 4), nrad=3)
        g = pipe.graph
        assert "fluid" in g
        assert g.interfaces == []

    def test_graph_two_layers(self):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(0.1, 4), nrad=3)
            .shell("wall", dR=0.02, nrad=2)
        )
        g = pipe.graph
        assert "fluid" in g and "wall" in g
        assert len(g.interfaces) == 1
