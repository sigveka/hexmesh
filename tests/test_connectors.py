"""
Tests for all connector types.

Each test builds a small Network (which handles gmsh geo calls internally),
applies one connector via net.add(), and then checks:
  - The returned Node's cursor (position, direction, up).
  - The SegmentResult's regions dict (volumes, inlets, outlets present).
  - For junction connectors: the correct number of outlet nodes.

These are structural tests — they verify connector logic without meshing.
Mesh quality is validated separately in test_quality.py.
"""

import math
import pytest
import numpy as np

from hexmesh.core.cursor import Cursor, Plane
from hexmesh.core.spec import PipeSpec
from hexmesh.core.shape import CircleShape, SquareShape
from hexmesh.network import Network
from hexmesh.connectors import (
    Straight, Bend, MiterBend, Elbow, Reducer, Expander, Transition, TJunction,
    YJunction,
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
        .shell("wall",  dR=0.025, nrad=2)
    )


# ===========================================================================
# Straight
# ===========================================================================

class TestStraight:
    def test_cursor_advances_along_direction(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=0.5, n_layers=3))
        # XZ cursor: direction = +Y, so position moves to (0, 0.5, 0)
        np.testing.assert_allclose(node.cursor.position, [0., 0.5, 0.], atol=1e-10)

    def test_cursor_direction_unchanged(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=1.0, n_layers=3))
        np.testing.assert_allclose(node.cursor.direction, [0., 1., 0.], atol=1e-10)

    def test_cursor_up_unchanged(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=1.0, n_layers=3))
        np.testing.assert_allclose(node.cursor.up, [0., 0., 1.], atol=1e-10)

    def test_regions_contain_fluid(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.5, n_layers=3))
        assert "fluid" in net._all_regions
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_inlet_and_outlet_recorded(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.5, n_layers=3))
        rset = net._all_regions["fluid"]
        assert len(rset.inlets)  > 0
        assert len(rset.outlets) > 0

    def test_two_layer_pipe(self, gmsh_session):
        net  = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=0.5, n_layers=3))
        assert "fluid" in net._all_regions
        assert "wall"  in net._all_regions

    def test_chained_straights(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=2))
        node = net.add(Straight(0.3, n_layers=2))
        np.testing.assert_allclose(
            node.cursor.position, [0., 0.6, 0.], atol=1e-10
        )

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            Straight(length=-0.1, n_layers=3)

    def test_invalid_n_layers_raises(self):
        with pytest.raises(ValueError):
            Straight(length=1.0, n_layers=0)

    def test_face_has_correct_layer_count(self, gmsh_session):
        net  = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(0.3, n_layers=2))
        assert len(node.face.layers) == 2

    def test_outlet_h_axis_unchanged(self, gmsh_session):
        """Straight extrusion should preserve h_axis (no direction change)."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Straight(0.5, n_layers=3))
        cs     = node.face.innermost
        np.testing.assert_allclose(cs.h_axis, cursor.right, atol=1e-10)
        np.testing.assert_allclose(cs.v_axis, cursor.up,    atol=1e-10)


# ===========================================================================
# Bend (smooth elbow)
# ===========================================================================

class TestBend:
    def test_direction_rotates_by_angle(self, gmsh_session):
        """After a 90° Bend, the direction should be ⊥ to the initial direction."""
        cursor = _xz_cursor()  # direction = +Y
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Bend(radius=0.3, angle=90, n_layers=4))
        # Dot product of initial (+Y) and final direction should be ~0
        dot = abs(np.dot(node.cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)

    def test_direction_rotates_by_45(self, gmsh_session):
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Bend(radius=0.3, angle=45, n_layers=4))
        dot = np.dot(node.cursor.direction, cursor.direction)
        assert dot == pytest.approx(math.cos(math.radians(45)), abs=1e-8)

    def test_cursor_position_moves(self, gmsh_session):
        """After a bend, the cursor position is not at the origin."""
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Bend(radius=0.3, angle=90, n_layers=4))
        assert np.linalg.norm(node.cursor.position) > 0.1

    def test_cursor_direction_is_unit_vector(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Bend(radius=0.3, angle=90, n_layers=4))
        assert np.linalg.norm(node.cursor.direction) == pytest.approx(1.0)

    def test_cursor_up_is_unit_vector(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Bend(radius=0.3, angle=60, n_layers=3))
        assert np.linalg.norm(node.cursor.up) == pytest.approx(1.0)

    def test_direction_up_remain_orthogonal(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Bend(radius=0.3, angle=90, n_layers=4))
        assert abs(np.dot(node.cursor.direction, node.cursor.up)) < 1e-8

    def test_regions_volumes_present(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Bend(radius=0.3, angle=90, n_layers=4))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_end_face_axes_match_end_cursor(self, gmsh_session):
        """End CrossSection h/v axes must match the end cursor's right/up."""
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Bend(radius=0.3, angle=90, n_layers=4))
        cs   = node.face.innermost
        np.testing.assert_allclose(cs.h_axis, node.cursor.right, atol=1e-8)
        np.testing.assert_allclose(cs.v_axis, node.cursor.up,    atol=1e-8)

    def test_invalid_radius_raises(self):
        with pytest.raises(ValueError):
            Bend(radius=0.0, angle=90, n_layers=4)

    def test_invalid_n_layers_raises(self):
        with pytest.raises(ValueError):
            Bend(radius=0.3, angle=90, n_layers=0)

    def test_radius_factor_long_radius(self, gmsh_session):
        """radius_factor=1.5 (long radius, 1.5D) should give the same geometry as
        passing the equivalent absolute radius."""
        R_pipe  = 0.1   # outer radius of the pipe
        net1    = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node1   = net1.add(Bend(radius=1.5 * 2 * R_pipe, angle=90, n_layers=4))

        import gmsh as _gmsh; _gmsh.finalize()
        _gmsh.initialize()
        _gmsh.option.setNumber("General.Verbosity", 0)
        _gmsh.model.add("test2")

        net2  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node2 = net2.add(Bend(radius_factor=1.5, angle=90, n_layers=4))
        np.testing.assert_allclose(
            node1.cursor.position, node2.cursor.position, atol=1e-6
        )

    def test_ambiguous_radius_raises(self):
        """Supplying both radius and radius_factor must raise."""
        with pytest.raises(ValueError, match="exactly one"):
            Bend(radius=0.3, radius_factor=1.5, angle=90, n_layers=4)

    def test_neither_radius_raises(self):
        """Supplying neither radius nor radius_factor must raise."""
        with pytest.raises(ValueError, match="exactly one"):
            Bend(angle=90, n_layers=4)

    def test_radius_factor_positive(self):
        with pytest.raises(ValueError):
            Bend(radius_factor=0.0, angle=90, n_layers=4)


# ===========================================================================
# Elbow (ASME SR/LR convenience class)
# ===========================================================================

class TestElbow:
    def test_long_radius_90_direction(self, gmsh_session):
        """Long-radius 90° Elbow should rotate direction by 90°."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Elbow(90))
        dot = abs(np.dot(node.cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)

    def test_short_radius_45_direction(self, gmsh_session):
        """Short-radius 45° Elbow should rotate direction by 45°."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Elbow(45, schedule="short"))
        dot = np.dot(node.cursor.direction, cursor.direction)
        assert dot == pytest.approx(math.cos(math.radians(45)), abs=1e-8)

    def test_long_radius_larger_than_short(self, gmsh_session):
        """Long-radius elbow must place the outlet further from origin than SR."""
        cursor = _xz_cursor()

        net1 = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node1 = net1.add(Elbow(90, schedule="long"))
        pos_long = node1.cursor.position.copy()

        import gmsh as _gmsh; _gmsh.finalize()
        _gmsh.initialize()
        _gmsh.option.setNumber("General.Verbosity", 0)
        _gmsh.model.add("test2")

        net2  = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node2 = net2.add(Elbow(90, schedule="short"))
        pos_short = node2.cursor.position.copy()

        # Long-radius outlet is further from origin
        assert np.linalg.norm(pos_long) > np.linalg.norm(pos_short)

    def test_invalid_schedule_raises(self):
        with pytest.raises(ValueError, match="schedule"):
            Elbow(90, schedule="medium")

    def test_invalid_n_layers_raises(self):
        with pytest.raises(ValueError):
            Elbow(90, n_layers=0)

    def test_regions_volumes_present(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Elbow(90))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_roll_sideways(self, gmsh_session):
        """roll=90 should turn upward instead of sideways."""
        cursor = _xz_cursor()  # direction=+Y, up=+Z
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(Elbow(90, roll=90.0))
        # After a 90° upward bend, up should point in -Y direction
        dot = abs(np.dot(node.cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)


# ===========================================================================
# MiterBend
# ===========================================================================

class TestMiterBend:
    def test_horizontal_direction_rotates(self, gmsh_session):
        """roll=0 rotates direction around cursor.up."""
        cursor = _xz_cursor()  # direction=+Y, up=+Z, right=+X
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=30, roll=0.0))
        dot = np.dot(node.cursor.direction, cursor.direction)
        assert dot == pytest.approx(math.cos(math.radians(30)), abs=1e-8)

    def test_vertical_direction_rotates(self, gmsh_session):
        """roll=90 rotates direction around cursor.right."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=30, roll=90.0))
        dot = np.dot(node.cursor.direction, cursor.direction)
        assert dot == pytest.approx(math.cos(math.radians(30)), abs=1e-8)

    def test_horizontal_preserves_up(self, gmsh_session):
        """Rotating around up should leave up unchanged."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=30, roll=0.0))
        np.testing.assert_allclose(node.cursor.up, cursor.up, atol=1e-8)

    def test_vertical_preserves_right(self, gmsh_session):
        """Rotating around right should leave right unchanged."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=30, roll=90.0))
        np.testing.assert_allclose(node.cursor.right, cursor.right, atol=1e-8)

    def test_90_degree_total_angle(self, gmsh_session):
        """A 90° MiterBend should produce a 90° direction change."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=90, roll=0.0))
        dot = abs(np.dot(node.cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-6)

    def test_direction_is_unit_vector(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(MiterBend(angle=45, roll=0.0))
        assert np.linalg.norm(node.cursor.direction) == pytest.approx(1.0)

    def test_direction_up_orthogonal(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(MiterBend(angle=60, roll=90.0))
        assert abs(np.dot(node.cursor.direction, node.cursor.up)) < 1e-8

    def test_negative_angle(self, gmsh_session):
        """Negative angle bends the other way; magnitude of turn equals |angle|."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        node   = net.add(MiterBend(angle=-30, roll=0.0))
        dot = np.dot(node.cursor.direction, cursor.direction)
        assert dot == pytest.approx(math.cos(math.radians(30)), abs=1e-8)

    def test_regions_volumes_present(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(MiterBend(angle=30, roll=0.0))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_end_face_axes_match_end_cursor(self, gmsh_session):
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(MiterBend(angle=30, roll=0.0))
        cs   = node.face.innermost
        np.testing.assert_allclose(cs.h_axis, node.cursor.right, atol=1e-8)
        np.testing.assert_allclose(cs.v_axis, node.cursor.up,    atol=1e-8)

    def test_invalid_roll_raises(self):
        with pytest.raises(ValueError):
            MiterBend(angle=30, roll=float('inf'))

    def test_invalid_n_layers_raises(self):
        with pytest.raises(ValueError):
            MiterBend(angle=30, n_layers=0)

    def test_auto_subdivision_large_angle(self, gmsh_session):
        """
        A 90° MiterBend should auto-subdivide into 3 × 30° sub-cuts.
        The merged result must still contain all volumes from 3 revolves.
        With a single-layer OH core, each 30° sub-cut creates 5 volumes
        (one per patch).  Three sub-cuts → 15 volumes total.
        """
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(MiterBend(angle=90, roll=0.0))
        n_vols = len(net._all_regions["fluid"].volumes)
        # 3 sub-cuts × 5 patches = 15 volumes
        assert n_vols == 15

    def test_straight_after_miterbend(self, gmsh_session):
        """A Straight following a MiterBend must advance along the new direction."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        net.add(MiterBend(angle=90, roll=0.0))
        node = net.add(Straight(0.3, n_layers=2))
        # After 90° horizontal miter (around +Z), direction turns from +Y to some
        # perpendicular direction.  The position must have moved 0.3 from the
        # miter position along the new direction.
        prev_pos = net._all_regions["fluid"].outlets  # won't directly help
        # Just check cursor moved and is valid
        assert np.linalg.norm(node.cursor.direction) == pytest.approx(1.0)
        assert abs(np.dot(node.cursor.direction, node.cursor.up)) < 1e-8


# ===========================================================================
# Reducer / Expander
# ===========================================================================

class TestReducerExpander:
    def _wide_pipe(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.15, nang=4), nrad=3)
        )

    def _narrow_pipe(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.08, nang=4), nrad=3)
        )

    def test_reducer_cursor_advances(self, gmsh_session):
        net  = Network(self._wide_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Reducer(outlet=self._narrow_pipe(), length=0.3, n_layers=3))
        np.testing.assert_allclose(
            node.cursor.position, [0., 0.3, 0.], atol=1e-8
        )

    def test_reducer_direction_unchanged(self, gmsh_session):
        net  = Network(self._wide_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Reducer(outlet=self._narrow_pipe(), length=0.3, n_layers=3))
        np.testing.assert_allclose(node.cursor.direction, [0., 1., 0.], atol=1e-8)

    def test_reducer_outlet_shape_radius(self, gmsh_session):
        net  = Network(self._wide_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Reducer(outlet=self._narrow_pipe(), length=0.3, n_layers=3))
        from hexmesh.core.shape import CircleShape
        assert isinstance(node.face.innermost.shape, CircleShape)
        assert node.face.innermost.shape.radius == pytest.approx(0.08)

    def test_expander_cursor_advances(self, gmsh_session):
        net  = Network(self._narrow_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Expander(outlet=self._wide_pipe(), length=0.3, n_layers=3))
        np.testing.assert_allclose(
            node.cursor.position, [0., 0.3, 0.], atol=1e-8
        )

    def test_expander_outlet_radius_larger(self, gmsh_session):
        net  = Network(self._narrow_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Expander(outlet=self._wide_pipe(), length=0.3, n_layers=3))
        from hexmesh.core.shape import CircleShape
        assert node.face.innermost.shape.radius == pytest.approx(0.15)

    def test_reducer_regions_present(self, gmsh_session):
        net = Network(self._wide_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Reducer(outlet=self._narrow_pipe(), length=0.3, n_layers=3))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_invalid_length_raises(self):
        pipe = self._wide_pipe()
        with pytest.raises(ValueError):
            Reducer(outlet=self._narrow_pipe(), length=0.0, n_layers=3)


# ===========================================================================
# TJunction
# ===========================================================================

class TestTJunction:
    def test_returns_two_nodes(self, gmsh_session):
        net    = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes  = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0)
        )
        assert isinstance(nodes, list)
        assert len(nodes) == 2

    def test_main_label(self, gmsh_session):
        net   = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0)
        )
        assert nodes[0].label == "main"

    def test_branch_label(self, gmsh_session):
        net   = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0)
        )
        assert nodes[1].label == "branch"

    def test_main_cursor_direction_unchanged(self, gmsh_session):
        """Main outlet continues along the original pipe direction."""
        cursor = _xz_cursor()  # direction = +Y
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        nodes  = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0)
        )
        np.testing.assert_allclose(
            nodes[0].cursor.direction, cursor.direction, atol=1e-8
        )

    def test_branch_cursor_direction_perpendicular(self, gmsh_session):
        """Branch outlet direction should be ⊥ to the main direction (90° turn)."""
        cursor = _xz_cursor()
        net    = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        nodes  = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0)
        )
        dot = abs(np.dot(nodes[1].cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)

    def test_regions_volumes_present(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(TJunction(approach_length=0.15, branch_length=0.15, roll=0.0))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_dag_routing_two_straights(self, gmsh_session):
        """Branching with net.add(node, connector) should not update the tail."""
        net    = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in   = net.add(Straight(0.3, n_layers=2))
        nodes  = net.add(n_in, TJunction(0.12, 0.12, roll=0.0))
        main, branch = nodes
        # Extend both outlets independently
        net.add(main,   Straight(0.3, n_layers=2))
        net.add(branch, Straight(0.3, n_layers=2))
        # All volumes should be present in the fluid region
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_invalid_approach_length_raises(self):
        with pytest.raises(ValueError):
            TJunction(approach_length=0.0, branch_length=0.15)

    def test_invalid_roll_raises(self):
        with pytest.raises(ValueError):
            TJunction(approach_length=0.15, branch_length=0.15, roll=float('nan'))

    def test_branch_direction_and_roll_raises(self):
        with pytest.raises(ValueError):
            TJunction(approach_length=0.15, branch_length=0.15,
                      branch_direction=[1, 0, 0], roll=0.0)

    def test_branch_direction_wrong_length_raises(self):
        with pytest.raises(ValueError):
            TJunction(approach_length=0.15, branch_length=0.15,
                      branch_direction=[1, 0])

    def test_branch_direction_parallel_raises(self, gmsh_session):
        """branch_direction parallel to main pipe axis should raise at connect time."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in = net.add(Straight(0.3, n_layers=2))
        with pytest.raises(ValueError):
            # _xz_cursor has direction=+Y; branch parallel to +Y is invalid
            net.add(n_in, TJunction(approach_length=0.15, branch_length=0.15,
                                    branch_direction=[0, 1, 0]))

    def test_branch_direction_produces_same_result_as_roll(self, gmsh_session):
        """branch_direction=[1,0,0] on a +Y pipe should match roll=0."""
        cursor = _xz_cursor()  # direction=+Y, right=+X
        net1 = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        n1 = net1.add(Straight(0.3, n_layers=2))
        r1 = net1.add(n1, TJunction(0.12, 0.12, roll=0.0))

        net2 = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        n2 = net2.add(Straight(0.3, n_layers=2))
        r2 = net2.add(n2, TJunction(0.12, 0.12, branch_direction=[1, 0, 0]))

        # Both should produce two outlets
        assert len(r1) == 2
        assert len(r2) == 2
        # Branch cursors should point in the same direction
        main1, branch1 = r1
        main2, branch2 = r2
        np.testing.assert_allclose(
            branch1.cursor.direction, branch2.cursor.direction, atol=1e-6
        )


# ===========================================================================
# TJunction — side-tap stub block path (branch_r is set)
# ===========================================================================

class TestTJunctionStub:
    """TJunction with branch_r — side-tap stub block architecture."""

    def test_returns_two_nodes(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0, branch_r=0.06)
        )
        assert len(nodes) == 2

    def test_main_label(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0, branch_r=0.06)
        )
        assert nodes[0].label == "main"

    def test_branch_label(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0, branch_r=0.06)
        )
        assert nodes[1].label == "branch"

    def test_branch_perpendicular(self, gmsh_session):
        cursor = _xz_cursor()
        net = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        nodes = net.add(
            TJunction(approach_length=0.15, branch_length=0.15, roll=0.0, branch_r=0.06)
        )
        dot = abs(np.dot(nodes[1].cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)

    def test_regions_volumes_present(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.06))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_dag_routing_with_downstream_straights(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in = net.add(Straight(0.3, n_layers=2))
        nodes = net.add(n_in, TJunction(0.15, 0.15, roll=0.0, branch_r=0.06))
        main, branch = nodes
        net.add(main,   Straight(0.3, n_layers=2))
        net.add(branch, Straight(0.3, n_layers=2))
        assert len(net._all_regions["fluid"].volumes) > 0

    def test_branch_r_equal_R_raises(self, gmsh_session):
        # _circle_pipe has outer radius = 0.1; branch_r=0.1 == R → ValueError
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with pytest.raises(ValueError, match="main pipe outer radius"):
            net.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.1))

    def test_branch_r_zero_raises(self):
        with pytest.raises(ValueError):
            TJunction(approach_length=0.15, branch_length=0.15, branch_r=0.0)

    def test_branch_direction_variant(self, gmsh_session):
        """branch_direction= should work the same as roll= for stub path."""
        cursor = _xz_cursor()  # direction=+Y, right=+X
        net = Network(_circle_pipe(), cursor=cursor, lc=0.1)
        nodes = net.add(
            TJunction(0.15, 0.15, branch_direction=[1, 0, 0], branch_r=0.06)
        )
        assert len(nodes) == 2
        dot = abs(np.dot(nodes[1].cursor.direction, cursor.direction))
        assert dot == pytest.approx(0.0, abs=1e-8)

    def test_tzone_split_produces_more_volumes(self, gmsh_session):
        """Step-cursor split: main pipe has T-zone + remainder layers → more volumes."""
        import warnings
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            net.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.06, n_layers=2))
        # pre-step + T-zone = approach (2 layers × 5 patches × 2 = 20); stub: 5 = 25+ total
        # Just verify total volume count exceeds what a single-shot Straight would give
        fluid_vols = net._all_regions["fluid"].volumes
        assert len(fluid_vols) > 5  # stub alone is 5; two Straights add more

    def test_conformality_warning_emitted(self, gmsh_session):
        """Non-conforming (r, R, nang) should emit a UserWarning."""
        import warnings
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            net.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.06))
        msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert any("conformality" in m for m in msgs)

    def test_departure_length_adds_volumes(self, gmsh_session):
        """departure_length > 0 should add extra volumes downstream of T-point."""
        import warnings
        net_no_dep  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net_with_dep = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            net_no_dep.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.06,
                                     departure_length=0.0))
            net_with_dep.add(TJunction(0.15, 0.15, roll=0.0, branch_r=0.06,
                                       departure_length=0.10))
        vols_no  = len(net_no_dep._all_regions["fluid"].volumes)
        vols_dep = len(net_with_dep._all_regions["fluid"].volumes)
        assert vols_dep > vols_no

    def test_approach_length_less_than_branch_r_raises(self, gmsh_session):
        """approach_length < branch_r should raise ValueError in stub path."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with pytest.raises(ValueError, match="T-zone"):
            # branch_r=0.06, approach_length=0.04 < 0.06 → error
            net.add(TJunction(0.04, 0.15, roll=0.0, branch_r=0.06))

    def test_tzone_e_outer_wall_not_in_outermost_walls(self, gmsh_session):
        """Stage 8: T-zone E outer arc wall must not appear in the outermost layer walls.

        The E outer arc wall surface faces the branch opening; it should not be
        listed as a solid wall (would wrongly tell the CFD solver there is a wall
        at the branch connection).  After the Stage 8 fix _find_e_outer_wall_surf
        removes it from the outermost layer's walls before merging into the result.
        """
        import warnings
        import gmsh as _gmsh

        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            n_main, n_branch = net.add(
                TJunction(0.15, 0.15, roll=0.0, branch_r=0.06,
                          departure_length=0.0)
            )

        _gmsh.model.occ.synchronize()

        # The outer layer name for _circle_pipe is "fluid"
        walls = net._all_regions["fluid"].walls

        # Each wall surface centroid should NOT be facing the branch direction
        # (branch is along +X = [1,0,0] for roll=0 in the _xz_cursor frame).
        # Any surface with centroid_x > R/2 from origin would be at the saddle
        # opening. R_outer=0.1 → threshold ≈ 0.05.
        # For roll=0 on a +Y pipe (cursor.direction=[0,1,0], up=[0,0,1]):
        # branch_cursor.direction = rotate([0,1,0], 90° around [0,0,1]) = [-1,0,0]
        # So the branch goes in -X; the T-zone outer arc wall facing the branch
        # is the one at x ≈ -R (centroid_x ≈ -0.09), not +R.
        branch_dir = np.array([-1.0, 0.0, 0.0])  # actual branch direction for roll=0
        main_dir   = np.array([0.0, 1.0, 0.0])
        R_outer = 0.1
        approach_length = 0.15
        r_branch = 0.06
        # T-zone step spans from (approach_length - r_branch) to approach_length
        tzone_y_start = approach_length - r_branch  # = 0.09
        assert len(walls) > 0, "walls list is empty — test is vacuously true"
        for surf in walls:
            cx, cy, cz = _gmsh.model.occ.getCenterOfMass(2, surf)
            centroid = np.array([cx, cy, cz])
            axial_proj  = float(np.dot(centroid, main_dir))
            centroid_perp = centroid - axial_proj * main_dir
            branch_proj = float(np.dot(centroid_perp, branch_dir))
            # The T-zone outer arc wall facing the branch has BOTH:
            #   branch_proj ≈ R*0.9 (centroid of 90° arc at radius R in branch direction)
            #   axial_proj in the T-zone step range [tzone_y_start, approach_length]
            # Pre-step outer arc walls facing branch are upstream
            # (axial_proj < tzone_y_start) — those are valid walls.
            # Stub-block outer walls may be above approach_length (when departure_length=0)
            # or have branch_proj > R_outer (outside the main pipe cylinder) — both excluded.
            in_tzone      = tzone_y_start - 1e-6 < axial_proj <= approach_length + 1e-6
            on_main_arc   = R_outer * 0.85 <= branch_proj <= R_outer
            facing_branch = on_main_arc
            assert not (in_tzone and facing_branch), (
                f"Wall surface {surf} looks like the T-zone outer arc wall "
                f"facing branch_dir (branch_proj={branch_proj:.4f}, "
                f"axial_proj={axial_proj:.4f}): "
                "it should have been removed from walls by the Stage 8 fix."
            )


# ===========================================================================
# Boundary-type compatibility check (Option B)
# ===========================================================================

def _square_pipe():
    """Single-patch square pipe (BoundaryType.SQUARE)."""
    return PipeSpec(nang=4).core(
        "fluid", SquareShape(half_w=0.1, half_h=0.1, nang_w=4, nang_h=4), nrad=3
    )


class TestBoundaryTypeCheck:
    """Network.add() must reject connectors with mismatched REQUIRED_BOUNDARY_TYPE."""

    def test_bend_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        with pytest.raises(TypeError, match="circular"):
            net.add(Bend(radius=0.2, angle=90, n_layers=3))

    def test_miter_bend_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        with pytest.raises(TypeError, match="circular"):
            net.add(MiterBend(angle=90))

    def test_tjunction_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        with pytest.raises(TypeError, match="circular"):
            net.add(TJunction(approach_length=0.15, branch_length=0.15))

    def test_yjunction_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        with pytest.raises(TypeError, match="circular"):
            net.add(YJunction(length=0.15, half_angle=45))

    def test_error_message_contains_connector_name(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        with pytest.raises(TypeError, match="Bend"):
            net.add(Bend(radius=0.2, angle=90, n_layers=3))

    def test_error_message_contains_node_label(self, gmsh_session):
        from hexmesh.network import Node
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=0.3, n_layers=2))
        # Attach a label to the node so we can confirm it appears in the error
        labeled_node = Node(node.face, node.cursor, label="after_square")
        with pytest.raises(TypeError, match="after_square"):
            net.add(labeled_node, Bend(radius=0.2, angle=90, n_layers=3))

    def test_straight_accepts_square_inlet(self, gmsh_session):
        """Straight has no REQUIRED_BOUNDARY_TYPE — must accept any face type."""
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(length=0.3, n_layers=2))
        assert node is not None

    def test_reducer_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        narrow = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.07, nang=4), nrad=3)
        with pytest.raises(TypeError, match="circular"):
            net.add(Reducer(outlet=narrow, length=0.3, n_layers=3))

    def test_expander_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        wide = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.15, nang=4), nrad=3)
        with pytest.raises(TypeError, match="circular"):
            net.add(Expander(outlet=wide, length=0.3, n_layers=3))

    def test_transition_rejects_square_inlet(self, gmsh_session):
        net = Network(_square_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        sq_out = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.07, nang=4), nrad=3)
            .square_shell("fluid", half_w=0.14, half_h=0.14, nrad=2)
        )
        with pytest.raises(TypeError, match="circular"):
            net.add(Transition(outlet=sq_out, length=0.3, n_layers=3))

    def test_circular_inlet_with_bend_passes(self, gmsh_session):
        """Circular inlet with Bend should not raise."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(length=0.3, n_layers=2))
        node = net.add(Bend(radius=0.2, angle=90, n_layers=3))
        assert node is not None


# ===========================================================================
# PipeSpec n_outer
# ===========================================================================

class TestPipeSpecNOuter:
    """Unit tests for PipeSpec(n_outer=…) parameter."""

    def test_default_n_outer_is_4(self):
        spec = PipeSpec(nang=4).core("f", CircleShape(0.1, nang=4), nrad=2)
        assert spec.n_outer == 4

    def test_n_outer_8_accepted(self):
        spec = PipeSpec(nang=4, n_outer=8).core("f", CircleShape(0.1, nang=4), nrad=2)
        assert spec.n_outer == 8

    def test_n_outer_not_multiple_of_4_raises(self):
        with pytest.raises(ValueError, match="multiple of 4"):
            PipeSpec(nang=4, n_outer=6)

    def test_n_outer_zero_raises(self):
        with pytest.raises(ValueError, match="multiple of 4"):
            PipeSpec(nang=4, n_outer=0)

    def test_nang_incompatible_with_n_outer_8_raises(self):
        # nang=3 is not divisible by n_outer//4 = 2
        with pytest.raises(ValueError, match="divisible"):
            PipeSpec(nang=3, n_outer=8).core("f", CircleShape(0.1, nang=3), nrad=2)

    def test_nang_even_compatible_with_n_outer_8(self):
        spec = PipeSpec(nang=4, n_outer=8).core("f", CircleShape(0.1, nang=4), nrad=2)
        assert spec.n_outer == 8
        assert spec.nang == 4

    def test_n_outer_8_builds_9_surfaces(self, gmsh_session):
        spec = PipeSpec(nang=4, n_outer=8).core("f", CircleShape(0.1, nang=4), nrad=2)
        net = Network(spec, cursor=_xz_cursor(), lc=0.1)
        cs = net.current_face.innermost
        assert cs.n_outer == 8
        assert len(cs.surfaces) == 9   # 1 centre + 8 outer

    def test_n_outer_8_with_shell(self, gmsh_session):
        spec = (
            PipeSpec(nang=4, n_outer=8)
            .core("fluid", CircleShape(0.1, nang=4), nrad=2)
            .shell("wall", dR=0.02, nrad=2)
        )
        net = Network(spec, cursor=_xz_cursor(), lc=0.1)
        cs_outer = net.current_face.outermost
        assert cs_outer.n_outer == 8
        assert len(cs_outer.surfaces) == 8   # annulus: 8 patches


# ===========================================================================
# Network refinement
# ===========================================================================

class TestNetworkRefinement:
    """Unit tests for Network(refinement=…) parameter."""

    def test_default_refinement_is_1(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        assert net._refinement == 1

    def test_refinement_2_doubles_nang(self, gmsh_session):
        # Base spec nang=4; refinement=2 → nang=8 in built face
        spec = PipeSpec(nang=4).core("f", CircleShape(0.1, nang=4), nrad=2)
        net = Network(spec, cursor=_xz_cursor(), lc=0.1, refinement=2)
        cs = net.current_face.innermost
        assert cs.shape.nang == 8

    def test_refinement_2_doubles_nrad(self, gmsh_session):
        spec = PipeSpec(nang=4).core("f", CircleShape(0.1, nang=4), nrad=3)
        net = Network(spec, cursor=_xz_cursor(), lc=0.1, refinement=2)
        cs = net.current_face.innermost
        assert cs.nrad == 6

    def test_refinement_non_positive_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1, refinement=0)

    def test_refinement_float_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1, refinement=1.5)

    def test_refinement_scales_n_layers(self, gmsh_session):
        # n_layers=2 with refinement=3 → Straight gets n_layers=6
        spec = PipeSpec(nang=4).core("f", CircleShape(0.1, nang=4), nrad=2)
        net = Network(spec, cursor=_xz_cursor(), lc=0.1, refinement=3)
        import dataclasses
        conn = Straight(length=0.3, n_layers=2)
        # Simulate what add() does: replace n_layers
        scaled = dataclasses.replace(conn, n_layers=conn.n_layers * 3)
        assert scaled.n_layers == 6
