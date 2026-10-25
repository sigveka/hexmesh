"""
Unit tests for hexmesh/quality_hex.py.

Tests are pure-numpy (no GMSH session needed) and verify that every metric
returns the expected ideal value on a unit cube, and degrades correctly on
distorted elements.
"""
import numpy as np
import pytest

from hexmesh.quality_hex import (
    # Jacobian-based
    mean_ratio_min,
    mean_ratio_avg,
    shape_regularity_ratio,
    shape_regularity_knupp,
    # Face-aggregated
    hex_warping,
    hex_aspect_ratio,
    hex_skewness,
    hex_taper,
    hex_interpolation_quality,
    # Convenience
    all_metrics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def unit_cube():
    """GMSH hex-type-5 vertex ordering for the unit cube [0,1]³."""
    return np.array([
        [0, 0, 0],  # v0
        [1, 0, 0],  # v1
        [1, 1, 0],  # v2
        [0, 1, 0],  # v3
        [0, 0, 1],  # v4
        [1, 0, 1],  # v5
        [1, 1, 1],  # v6
        [0, 1, 1],  # v7
    ], dtype=float)


@pytest.fixture
def elongated_hex():
    """Hex stretched 3× in x — aspect ratio = 3, other metrics degrade."""
    v = np.array([
        [0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0],
        [0, 0, 1], [3, 0, 1], [3, 1, 1], [0, 1, 1],
    ], dtype=float)
    return v


@pytest.fixture
def warped_hex():
    """Hex with one vertex lifted — creates non-planar faces."""
    v = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ], dtype=float)
    v[6, 2] = 1.4   # lift one top corner — warps 3 faces
    return v


@pytest.fixture
def skewed_hex():
    """Parallelogram-prism: bottom face sheared in x."""
    v = np.array([
        [0,   0, 0], [1, 0, 0], [1.5, 1, 0], [0.5, 1, 0],
        [0,   0, 1], [1, 0, 1], [1.5, 1, 1], [0.5, 1, 1],
    ], dtype=float)
    return v


# ===========================================================================
# Jacobian-based metrics — unit cube
# ===========================================================================

class TestUnitCubeJacobianMetrics:
    def test_mean_ratio_min(self, unit_cube):
        assert mean_ratio_min(unit_cube) == pytest.approx(1.0, rel=1e-10)

    def test_mean_ratio_avg(self, unit_cube):
        assert mean_ratio_avg(unit_cube) == pytest.approx(1.0, rel=1e-10)

    def test_shape_regularity_ratio(self, unit_cube):
        assert shape_regularity_ratio(unit_cube) == pytest.approx(1.0, rel=1e-10)

    def test_shape_regularity_knupp(self, unit_cube):
        assert shape_regularity_knupp(unit_cube) == pytest.approx(1.0, rel=1e-10)


# ===========================================================================
# Face-aggregated metrics — unit cube
# ===========================================================================

class TestUnitCubeFaceMetrics:
    def test_warping_zero(self, unit_cube):
        assert hex_warping(unit_cube) == pytest.approx(0.0, abs=1e-12)

    def test_aspect_ratio_one(self, unit_cube):
        assert hex_aspect_ratio(unit_cube) == pytest.approx(1.0, rel=1e-10)

    def test_skewness_zero(self, unit_cube):
        assert hex_skewness(unit_cube) == pytest.approx(0.0, abs=1e-12)

    def test_taper_zero(self, unit_cube):
        assert hex_taper(unit_cube) == pytest.approx(0.0, abs=1e-12)

    def test_interp_quality_min_one(self, unit_cube):
        assert hex_interpolation_quality(unit_cube, variant="min") == pytest.approx(
            1.0, rel=1e-10
        )

    def test_interp_quality_avg_one(self, unit_cube):
        assert hex_interpolation_quality(unit_cube, variant="avg") == pytest.approx(
            1.0, rel=1e-10
        )


# ===========================================================================
# Distorted elements — metrics degrade in the expected direction
# ===========================================================================

class TestDistortedElements:
    def test_elongated_aspect_ratio_worse(self, unit_cube, elongated_hex):
        assert hex_aspect_ratio(elongated_hex) > hex_aspect_ratio(unit_cube)

    def test_elongated_aspect_ratio_value(self, elongated_hex):
        # 3× stretch → max(||x1||/||x2||, ||x2||/||x1||) = 3 on worst face
        ar = hex_aspect_ratio(elongated_hex)
        assert ar == pytest.approx(3.0, rel=1e-8)

    def test_warped_hex_nonzero_warping(self, unit_cube, warped_hex):
        assert hex_warping(warped_hex) > hex_warping(unit_cube)

    def test_skewed_hex_nonzero_skewness(self, unit_cube, skewed_hex):
        assert hex_skewness(skewed_hex) > hex_skewness(unit_cube)

    def test_mean_ratio_min_degrades_when_elongated(self, unit_cube, elongated_hex):
        assert mean_ratio_min(elongated_hex) < mean_ratio_min(unit_cube)

    def test_shape_regularity_ratio_uniform_for_uniform_stretch(self, elongated_hex):
        # Uniformly stretched hex still has all Jacobians equal → ratio = 1
        assert shape_regularity_ratio(elongated_hex) == pytest.approx(1.0, rel=1e-10)


# ===========================================================================
# all_metrics convenience function
# ===========================================================================

class TestAllMetrics:
    def test_returns_all_keys(self, unit_cube):
        m = all_metrics(unit_cube)
        expected_keys = {
            "warping", "aspect_ratio", "skewness", "taper",
            "interp_quality_min", "interp_quality_avg",
            "mean_ratio_min", "mean_ratio_avg",
            "shape_regularity_ratio", "shape_regularity_knupp",
            "scaled_jacobian", "nes",
        }
        assert set(m.keys()) == expected_keys

    def test_unit_cube_ideal_values(self, unit_cube):
        m = all_metrics(unit_cube)
        assert m["warping"]                == pytest.approx(0.0, abs=1e-12)
        assert m["aspect_ratio"]           == pytest.approx(1.0, rel=1e-10)
        assert m["skewness"]               == pytest.approx(0.0, abs=1e-12)
        assert m["taper"]                  == pytest.approx(0.0, abs=1e-12)
        assert m["interp_quality_min"]     == pytest.approx(1.0, rel=1e-10)
        assert m["interp_quality_avg"]     == pytest.approx(1.0, rel=1e-10)
        assert m["mean_ratio_min"]         == pytest.approx(1.0, rel=1e-10)
        assert m["mean_ratio_avg"]         == pytest.approx(1.0, rel=1e-10)
        assert m["shape_regularity_ratio"] == pytest.approx(1.0, rel=1e-10)
        assert m["shape_regularity_knupp"] == pytest.approx(1.0, rel=1e-10)

    def test_all_floats(self, unit_cube):
        m = all_metrics(unit_cube)
        for key, val in m.items():
            assert isinstance(val, float), f"{key} is not float: {type(val)}"
