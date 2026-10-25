"""
Quality report per fitting, with hex metrics (docs/tasks/0004).

Scaled Jacobian (Knupp, 8 corners) and NES (normalized equiangle skewness)
are the metrics of docs/RESEARCH.md §4.2; ``check_quality(by="fitting")``
names the fitting that holds the worst cell.
"""

import math

import numpy as np
import pytest

from hexmesh.assembly import Assembly, Bend, Straight, Tee
from hexmesh.core.spec import PipeSpec
from hexmesh.quality_hex import METRICS, corner_scaled_jacobians, nes, scaled_jacobian

CUBE = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                 [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=float)


def _sheared(deg):
    """Unit cube with its +y faces shifted along x: face angles 90 ± deg."""
    v = CUBE.copy()
    v[[2, 3, 6, 7], 0] += math.tan(math.radians(deg))
    return v


class TestMetrics:
    def test_unit_cube(self):
        assert scaled_jacobian(CUBE) == pytest.approx(1.0)
        assert nes(CUBE) == pytest.approx(0.0, abs=1e-12)

    def test_box_is_ideal(self):
        box = CUBE * [3.0, 1.0, 0.2]                 # stretching is not distortion
        assert scaled_jacobian(box) == pytest.approx(1.0)
        assert nes(box) == pytest.approx(0.0, abs=1e-12)

    @pytest.mark.parametrize("deg", [15.0, 30.0, 45.0, 60.0])
    def test_sheared(self, deg):
        v = _sheared(deg)
        assert scaled_jacobian(v) == pytest.approx(math.cos(math.radians(deg)))
        assert nes(v) == pytest.approx(deg / 90.0)

    def test_folded_corner_is_negative(self):
        v = CUBE.copy()
        v[6] = [0.2, 0.2, 0.2]                       # push a corner through the cell
        assert corner_scaled_jacobians(v).min() < 0
        assert METRICS["scaled_jacobian"].higher_is_better
        assert not METRICS["nes"].higher_is_better


# ---------------------------------------------------------------------------
# Reports on a meshed assembly
# ---------------------------------------------------------------------------

@pytest.fixture
def tee_assembly(gmsh_session):
    spec = PipeSpec(nang=6).core("fluid", radius=0.1, nrad=5)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=4))
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.06))
    asm.add(main, Bend(0.3, 90, n_layers=8))
    asm.add(branch, Straight(0.3, n_layers=4))
    asm.mesh()
    return asm


def test_one_row_per_fitting(tee_assembly):
    report = tee_assembly.check_quality(by="fitting")
    assert [r.name for r in report.regions] == [
        "#0 Straight", "#1 Tee", "#2 Bend", "#3 Straight"]
    assert [r.fitting for r in report.regions] == [0, 1, 2, 3]
    assert report.total_elements == tee_assembly.cell_count()
    assert "#1 Tee" in str(report)


@pytest.mark.parametrize("metric", ["scaled_jacobian", "nes"])
def test_tee_row_is_worst(tee_assembly, metric):
    report = tee_assembly.check_quality(metric, by="fitting")
    assert report.ok
    assert report.worst_region.name == "#1 Tee"
    others = [r.worst for r in report.regions if r.fitting != 1]
    if report.higher_is_better:
        assert report.worst < min(others)
    else:
        assert report.worst > max(others)


def test_material_default_unchanged(tee_assembly):
    by_material = tee_assembly.check_quality()
    by_fitting = tee_assembly.check_quality(by="fitting")
    assert [r.name for r in by_material.regions] == ["fluid"]
    assert by_material.quality_name == "minSICN" and by_material.threshold == 0.0
    assert by_material.min_quality == pytest.approx(by_fitting.min_quality)


def test_lower_is_better_threshold(tee_assembly):
    """NES counts elements at or above the threshold as bad."""
    loose = tee_assembly.check_quality("nes", by="fitting")
    tight = tee_assembly.check_quality("nes", threshold=0.5, by="fitting")
    tee = tight.regions[1]
    assert loose.ok and not tight.ok
    assert tee.n_bad > 0 and tee.worst >= 0.5


def test_unknown_grouping_rejected(tee_assembly):
    with pytest.raises(ValueError, match="by must be"):
        tee_assembly.check_quality(by="layer")
