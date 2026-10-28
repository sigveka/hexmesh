"""
Unit tests for pure-Python data structures:
  CircleShape, RectShape, PipeSpec.

No GMSH required — all tests run without a gmsh_session fixture.
"""

import math
import pytest
import numpy as np

from hexmesh.core.shape import CircleShape, RectShape
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

    def test_core_with_rect_shell(self):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(0.1, 4), nrad=3)
            .shell("sq", outer=RectShape(0.2, 0.2, 4, 4), nrad=2)
        )
        assert pipe.layer_names == ["fluid", "sq"]
        assert pipe.outlines[-1] == RectShape(0.2, 0.2, 4, 4)

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

    def test_dR_shell_after_rect_grows_the_rectangle(self):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(0.1, 4), nrad=3)
            .shell("sq", outer=RectShape(0.2, 0.1, 4, 4), nrad=2)
            .shell("extra", dR=0.01, nrad=2)
        )
        o = pipe.outlines[-1]
        assert (o.half_w, o.half_h) == pytest.approx((0.21, 0.11))
        assert o.counts == (4, 4)

    def test_shell_needs_exactly_one_of_dR_and_outer(self):
        base = PipeSpec(nang=4).core("fluid", CircleShape(0.1, 4), nrad=3)
        with pytest.raises(ValueError, match="exactly one of dR and outer"):
            base.shell("w", nrad=2)
        with pytest.raises(ValueError, match="exactly one of dR and outer"):
            base.shell("w", dR=0.1, outer=CircleShape(0.2, 4), nrad=2)

    def test_rect_stack_needs_equal_counts(self):
        with pytest.raises(ValueError, match="equal counts per side"):
            (
                PipeSpec(nang_w=3, nang_h=2)
                .core("air", RectShape(0.1, 0.08, 3, 2), nrad=3)
                .shell("sq", outer=RectShape(0.2, 0.2, 3, 2), nrad=2)
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
