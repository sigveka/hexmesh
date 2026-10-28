"""
Tests for 2-D face builders:
  build_oh_circle, build_oh_rect, build_annulus, build_ring.

Each test verifies the returned CrossSection's structure (surface count,
boundary type, h_axis/v_axis, outer-boundary entity counts) and the
stacking protocol (conformal inner-boundary reuse between layers).

All tests require a GMSH session but do NOT mesh — they only call geo-kernel
functions to add points, curves and surfaces.
"""

import pytest
import math

import gmsh
import numpy as np

from hexmesh.core.cross_section import BoundaryType
from hexmesh.assembly.interface import Frame
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.faces.oh_circle import build_oh_circle, build_oh_circle8
from hexmesh.faces.oh_rect import build_oh_rect
from hexmesh.faces.annulus import build_annulus
from hexmesh.faces.annulus import build_ring


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cursor_xz():
    return Frame.from_vectors([0, 0, 0], [0, 1, 0], [0, 0, 1])  # right=+X, up=+Z


# ===========================================================================
# build_oh_circle
# ===========================================================================

class TestBuildOhCircle:
    def test_returns_five_surfaces(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.surfaces) == 5

    def test_boundary_type_circular(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert cs.boundary_type is BoundaryType.CIRCULAR

    def test_four_outer_points(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.outer_points) == 4
        assert all(isinstance(t, int) and t > 0 for t in cs.outer_points)

    def test_four_outer_curves(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.outer_curves) == 4

    def test_axes_stored_correctly(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        np.testing.assert_allclose(cs.h_axis, c.right, atol=1e-12)
        np.testing.assert_allclose(cs.v_axis, c.up,    atol=1e-12)

    def test_centre_coordinates_stored(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=1., cy=2., cz=3.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert cs.cx == pytest.approx(1.)
        assert cs.cy == pytest.approx(2.)
        assert cs.cz == pytest.approx(3.)

    def test_inner_taper_entities_populated(self, gmsh_session):
        """inner_points, inner_curves, radial_curves are set for taper support."""
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.inner_points)  == 4
        assert len(cs.inner_curves)  == 4
        assert len(cs.radial_curves) == 4

    def test_non_origin_position(self, gmsh_session):
        """Face can be built at any position, not just the origin."""
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0.5, cy=0.0, cz=0.5,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.surfaces) == 5

    def test_arbitrary_orientation(self, gmsh_session):
        """h_axis/v_axis from an arbitrary cursor are stored correctly."""
        c = Frame.from_vectors(
            [0., 0., 0.],
            np.array([1., 1., 0.]) / np.sqrt(2),
            np.array([0., 0., 1.]),
        )
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        np.testing.assert_allclose(cs.h_axis, c.right, atol=1e-12)
        np.testing.assert_allclose(cs.v_axis, c.up,    atol=1e-12)


# ===========================================================================
# build_oh_circle8
# ===========================================================================

class TestBuildOhCircle8:
    """Stage 1: 9-patch OH with n_outer=8 (8 outer corners at every 45°)."""

    def _build(self, gmsh_session, **kwargs):
        c = _cursor_xz()
        defaults = dict(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        defaults.update(kwargs)
        return build_oh_circle8(**defaults)

    def test_returns_nine_surfaces(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert len(cs.surfaces) == 9

    def test_boundary_type_circular(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert cs.boundary_type.value == "circular"

    def test_eight_outer_points(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert len(cs.outer_points) == 8
        assert all(isinstance(t, int) and t > 0 for t in cs.outer_points)

    def test_eight_outer_curves(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert len(cs.outer_curves) == 8

    def test_n_outer_property(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert cs.n_outer == 8

    def test_axes_stored_correctly(self, gmsh_session):
        c = _cursor_xz()
        cs = self._build(gmsh_session)
        np.testing.assert_allclose(cs.h_axis, c.right, atol=1e-12)
        np.testing.assert_allclose(cs.v_axis, c.up,    atol=1e-12)

    def test_centre_coordinates_stored(self, gmsh_session):
        cs = self._build(gmsh_session, cx=1., cy=2., cz=3.)
        assert cs.cx == pytest.approx(1.)
        assert cs.cy == pytest.approx(2.)
        assert cs.cz == pytest.approx(3.)

    def test_eight_inner_taper_entities(self, gmsh_session):
        """inner_points, inner_curves, radial_curves all have 8 entries."""
        cs = self._build(gmsh_session)
        assert len(cs.inner_points)  == 8
        assert len(cs.inner_curves)  == 8
        assert len(cs.radial_curves) == 8

    def test_outer_points_distinct(self, gmsh_session):
        """All 8 outer corner tags are unique GMSH point tags."""
        cs = self._build(gmsh_session)
        assert len(set(cs.outer_points)) == 8

    def test_outer_curves_distinct(self, gmsh_session):
        cs = self._build(gmsh_session)
        assert len(set(cs.outer_curves)) == 8

    def test_non_origin_position(self, gmsh_session):
        cs = self._build(gmsh_session, cx=0.5, cy=0.0, cz=0.5)
        assert len(cs.surfaces) == 9

    def test_arbitrary_orientation(self, gmsh_session):
        c = Frame.from_vectors(
            [0., 0., 0.],
            np.array([1., 1., 0.]) / np.sqrt(2),
            np.array([0., 0., 1.]),
        )
        cs = build_oh_circle8(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        np.testing.assert_allclose(cs.h_axis, c.right, atol=1e-12)
        np.testing.assert_allclose(cs.v_axis, c.up,    atol=1e-12)

    def test_odd_nang_raises(self, gmsh_session):
        """nang must be even for 8-corner OH."""
        with pytest.raises(ValueError, match="nang to be even"):
            self._build(gmsh_session, shape=CircleShape(radius=0.1, nang=3))

    def test_nang_6_works(self, gmsh_session):
        """nang=6 (even) is valid."""
        cs = self._build(gmsh_session, shape=CircleShape(radius=0.1, nang=6))
        assert len(cs.surfaces) == 9

    def test_rot_offset(self, gmsh_session):
        """rot parameter rotates all corners without changing surface count."""
        import math
        cs = self._build(gmsh_session, rot=math.pi / 8)
        assert len(cs.surfaces) == 9
        assert len(cs.outer_points) == 8

    def test_5patch_n_outer_is_4(self, gmsh_session):
        """Existing build_oh_circle still reports n_outer=4."""
        c = _cursor_xz()
        cs = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert cs.n_outer == 4


# ===========================================================================
# build_oh_rect
# ===========================================================================

class TestBuildOhRect:
    def test_returns_five_surfaces(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(half_w=0.1, half_h=0.05, nang_w=3, nang_h=2),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.surfaces) == 5

    def test_boundary_type_square(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(half_w=0.1, half_h=0.05, nang_w=3, nang_h=2),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert cs.boundary_type is BoundaryType.SQUARE

    def test_four_outer_points(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(half_w=0.1, half_h=0.05, nang_w=3, nang_h=2),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.outer_points) == 4

    def test_axes_stored(self, gmsh_session):
        c = _cursor_xz()
        cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(half_w=0.1, half_h=0.05, nang_w=3, nang_h=2),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        np.testing.assert_allclose(cs.h_axis, c.right, atol=1e-12)
        np.testing.assert_allclose(cs.v_axis, c.up,    atol=1e-12)

    def test_square_variant(self, gmsh_session):
        """Square duct (half_w == half_h) also produces 5 surfaces."""
        c = _cursor_xz()
        cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(half_w=0.1, half_h=0.1, nang_w=3, nang_h=3),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        assert len(cs.surfaces) == 5
        assert cs.boundary_type is BoundaryType.SQUARE


# ===========================================================================
# build_annulus
# ===========================================================================

class TestBuildAnnulus:
    def _core(self, gmsh_session):
        c = _cursor_xz()
        return build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )

    def test_returns_four_surfaces(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert len(ann.surfaces) == 4

    def test_boundary_type_circular(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.boundary_type is BoundaryType.CIRCULAR

    def test_four_outer_points(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert len(ann.outer_points) == 4

    def test_conformality_inner_points_reused(self, gmsh_session):
        """Annulus inner_points must equal the core outer_points (same GMSH tags)."""
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.inner_points == inner.outer_points

    def test_conformality_inner_curves_reused(self, gmsh_session):
        """Annulus inner_curves must reference the same tags as core outer_curves."""
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        # Tags should be identical (same GMSH entities, possibly signed)
        assert list(ann.inner_curves) == list(inner.outer_curves)

    def test_axes_inherited_from_inner(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        np.testing.assert_allclose(ann.h_axis, inner.h_axis, atol=1e-12)
        np.testing.assert_allclose(ann.v_axis, inner.v_axis, atol=1e-12)

    def test_outer_radius_increases(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.025, lc=0.1, nrad=2)
        from hexmesh.core.shape import CircleShape
        assert isinstance(ann.shape, CircleShape)
        assert ann.shape.radius == pytest.approx(0.1 + 0.025)

    def test_stacking_two_annuli(self, gmsh_session):
        """Three concentric layers all sharing entity tags conformally."""
        inner = self._core(gmsh_session)
        mid   = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        outer = build_annulus(inner=mid,   dR=0.02, lc=0.1, nrad=2)
        assert outer.inner_points == mid.outer_points
        assert list(outer.inner_curves) == list(mid.outer_curves)

    def test_rectangular_inner_grows_a_rectangle(self, gmsh_session):
        """On a rectangle, dR grows the rectangle (decision 0026)."""
        c = _cursor_xz()
        rect_cs = build_oh_rect(
            cx=0., cy=0., cz=0.,
            shape=RectShape(0.1, 0.05, 3, 2),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        ann = build_annulus(inner=rect_cs, dR=0.02, lc=0.1, nrad=2)
        assert ann.boundary_type is BoundaryType.SQUARE
        assert (ann.shape.half_w, ann.shape.half_h) == pytest.approx((0.12, 0.07))


# ===========================================================================
# build_annulus on 8-corner core (Stage 2)
# ===========================================================================

class TestBuildAnnulus8:
    """build_annulus stacked on an n_outer=8 core."""

    def _core8(self, gmsh_session):
        c = _cursor_xz()
        return build_oh_circle8(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )

    def test_returns_eight_surfaces(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert len(ann.surfaces) == 8

    def test_eight_outer_points(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert len(ann.outer_points) == 8

    def test_eight_outer_curves(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert len(ann.outer_curves) == 8

    def test_n_outer_is_8(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.n_outer == 8

    def test_conformality_inner_points_reused(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.inner_points == inner.outer_points

    def test_conformality_inner_curves_reused(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert list(ann.inner_curves) == list(inner.outer_curves)

    def test_corner_angles_propagated(self, gmsh_session):
        """corner_angles flow from core → first annulus → second annulus."""
        inner = self._core8(gmsh_session)
        mid   = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        outer = build_annulus(inner=mid,   dR=0.02, lc=0.1, nrad=2)
        assert len(outer.corner_angles) == 8
        np.testing.assert_allclose(outer.corner_angles, inner.corner_angles, atol=1e-12)

    def test_stacking_two_annuli_8(self, gmsh_session):
        inner = self._core8(gmsh_session)
        mid   = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        outer = build_annulus(inner=mid,   dR=0.02, lc=0.1, nrad=2)
        assert outer.inner_points == mid.outer_points
        assert list(outer.inner_curves) == list(mid.outer_curves)

    def test_outer_radius_increases(self, gmsh_session):
        inner = self._core8(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.025, lc=0.1, nrad=2)
        assert ann.shape.radius == pytest.approx(0.1 + 0.025)

    def test_4corner_n_outer_still_4(self, gmsh_session):
        """4-corner annulus still reports n_outer=4 after Stage 2 changes."""
        c = _cursor_xz()
        inner = build_oh_circle(
            cx=0., cy=0., cz=0.,
            shape=CircleShape(radius=0.1, nang=4),
            h_axis=c.right, v_axis=c.up,
            lc=0.1, nrad=3,
        )
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.n_outer == 4
        assert len(ann.surfaces) == 4


# ===========================================================================
# build_ring (decision 0026)
# ===========================================================================

def _boundary_xy(cs):
    """In-plane coordinates of a layer's outer corner points (xz cursor)."""
    return np.array([gmsh.model.getValue(0, p, [])[[0, 2]] for p in cs.outer_points])


class TestBuildRing:
    def _core(self, gmsh_session, shape=None):
        c = _cursor_xz()
        shape = shape or CircleShape(radius=0.1, nang=4)
        build = build_oh_circle if isinstance(shape, CircleShape) else build_oh_rect
        return build(cx=0., cy=0., cz=0., shape=shape,
                     h_axis=c.right, v_axis=c.up, lc=0.1, nrad=3)

    def test_circle_in_square(self, gmsh_session):
        inner = self._core(gmsh_session)
        sq = build_ring(inner, RectShape(0.18, 0.18, 4, 4), lc=0.1, nrad=2)
        assert len(sq.surfaces) == 4
        assert sq.boundary_type is BoundaryType.SQUARE
        assert sq.inner_points == inner.outer_points
        np.testing.assert_allclose(np.abs(_boundary_xy(sq)), 0.18, atol=1e-12)
        np.testing.assert_allclose(sq.h_axis, inner.h_axis, atol=1e-12)
        np.testing.assert_allclose(sq.v_axis, inner.v_axis, atol=1e-12)

    def test_corner_lines_go_to_the_rectangle_corners(self, gmsh_session):
        """A circle in a 2:1 rectangle: skewed corner lines, ending at the
        rectangle's corners; the recorded corner angles are theirs."""
        inner = self._core(gmsh_session)
        r = build_ring(inner, RectShape(0.3, 0.15, 4, 4), lc=0.1, nrad=2)
        np.testing.assert_allclose(_boundary_xy(r), [[0.3, 0.15], [-0.3, 0.15],
                                                     [-0.3, -0.15], [0.3, -0.15]], atol=1e-12)
        assert r.corner_angles[0] == pytest.approx(math.atan2(0.15, 0.3))

    def test_rectangle_in_circle(self, gmsh_session):
        """A 2:1 rectangle in a circle: corner lines run radially, so the
        circle's arcs are unequal; the outer sides are arcs."""
        inner = self._core(gmsh_session, RectShape(0.1, 0.05, 4, 4))
        r = build_ring(inner, CircleShape(0.2, 4), lc=0.1, nrad=2)
        assert r.boundary_type is BoundaryType.CIRCULAR
        xy = _boundary_xy(r)
        np.testing.assert_allclose(np.hypot(*xy.T), 0.2, atol=1e-12)
        np.testing.assert_allclose(np.arctan2(xy[0, 1], xy[0, 0]), math.atan2(0.05, 0.1))

    def test_build_annulus_is_a_grown_ring(self, gmsh_session):
        inner = self._core(gmsh_session)
        ann = build_annulus(inner=inner, dR=0.02, lc=0.1, nrad=2)
        assert ann.shape.radius == pytest.approx(0.12)
        sq = build_annulus(inner=build_ring(ann, RectShape(0.2, 0.2, 4, 4), lc=0.1, nrad=2),
                           dR=0.01, lc=0.1, nrad=2)
        np.testing.assert_allclose(np.abs(_boundary_xy(sq)), 0.21, atol=1e-12)
