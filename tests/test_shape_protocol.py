#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
The shape protocol (task 0083): every shape answers the same questions,
checked against values known in closed form for a circle, a square, a 2:1
rectangle and blends at u = 0.5.
"""

import math

import numpy as np
import pytest

from hexmesh.core.shape import BlendShape, CircleShape, RectShape, Shape

R2 = math.sqrt(2)

#: name → (shape, known answers); a blend of two squares (or two circles)
#: at u = 0.5 is the square (circle) halfway between
CASES = {
    "circle": (CircleShape(0.05, 4), dict(
        is_round=True, is_station=False, hydraulic_diameter=0.1, label="circle",
        angular_counts={"nang": 4}, max_extent=0.05, counts=(4, 4),
        corner0=(0.05 / R2, 0.05 / R2), side_count1=4, extent=(0.05, 0.05),
        period=math.pi / 2)),
    "square": (RectShape(0.06, 0.06, 4, 4), dict(
        is_round=False, is_station=False, hydraulic_diameter=0.12, label="1:1 rectangle",
        angular_counts={"nang_w": 4, "nang_h": 4}, max_extent=0.06 * R2, counts=(4, 4),
        corner0=(0.06, 0.06), side_count1=4, extent=(0.06, 0.06),
        period=math.pi / 2)),
    "rect-2": (RectShape(0.10, 0.05, 6, 3), dict(
        is_round=False, is_station=False, hydraulic_diameter=0.4 / 3, label="2:1 rectangle",
        angular_counts={"nang_w": 6, "nang_h": 3}, max_extent=math.hypot(0.1, 0.05),
        counts=(6, 3), corner0=(0.10, 0.05), side_count1=3, extent=(0.10, 0.05),
        period=math.pi)),
    "blend-squares": (BlendShape(RectShape(0.1, 0.1, 4, 4), RectShape(0.2, 0.2, 4, 4), 0.5), dict(
        is_round=False, is_station=True, hydraulic_diameter=0.3, label="blended station",
        angular_counts={"nang_w": 4, "nang_h": 4}, max_extent=0.2 * R2, counts=(4, 4),
        corner0=(0.15, 0.15), side_count1=4, extent=(0.15, 0.15),
        period=math.pi / 2)),
}


@pytest.mark.parametrize("name", CASES)
def test_shape_answers_the_protocol(name):
    shape, want = CASES[name]
    assert isinstance(shape, Shape)
    for q in ("is_round", "is_station", "label", "angular_counts", "counts"):
        assert getattr(shape, q) == want[q], q
    assert shape.hydraulic_diameter == pytest.approx(want["hydraulic_diameter"], rel=1e-12)
    assert shape.max_extent == pytest.approx(want["max_extent"], rel=1e-12)
    assert np.allclose(shape.corner(0), want["corner0"], rtol=0, atol=1e-15)
    assert shape.side_count(1, 4) == want["side_count1"]
    assert [float(shape.extent(a)) for a in (0.0, math.pi / 2)] == pytest.approx(want["extent"])
    assert shape.period(4) == pytest.approx(want["period"])
    assert shape.side_curve in ("arc", "line", "spline")
    assert len(shape.corners_from([math.pi / 4 + k * math.pi / 2 for k in range(4)])) == 4


def test_blended_circle_hydraulic_diameter_from_its_samples():
    """A blend's 4A/P comes from its sampled outline: a circle halfway from
    r = 0.1 to 0.2 is read within the sampling error (1024 points)."""
    b = BlendShape(CircleShape(0.1, 4), CircleShape(0.2, 4), 0.5)
    assert b.hydraulic_diameter == pytest.approx(0.3, rel=1e-5)


def test_a_round_shapes_radius_is_its_max_extent():
    """Round-only fittings (wye, interchange) read the radius this way."""
    assert CircleShape(0.037, 4).max_extent == 0.037
