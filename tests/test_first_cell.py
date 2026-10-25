"""
Radial grading from a first-cell height (docs/tasks/0002).

``first_cell=`` on ``core()`` / ``shell()`` sets the height of the cell at
the layer's outer boundary.  For a shell every radial is ``dR`` long, so
the height is exact all round; the core grades its corner radials, of
length ``(1 - OH_RATIO) * radius``.
"""

import math

import numpy as np
import pytest

from hexmesh.assembly import Assembly, Straight
from hexmesh.core.grading import first_cell_height, progression_for_first_cell
from hexmesh.core.shape import OH_RATIO
from hexmesh.core.spec import PipeSpec

from tests import test_fitting_conformance as kit

R, DR = 0.1, 0.01


class TestSolver:
    @pytest.mark.parametrize("q", [0.4, 0.9, 1.0, 1.2, 2.5])
    @pytest.mark.parametrize("n", [2, 5, 30])
    def test_round_trip(self, q, n):
        h = first_cell_height(0.04, n, q)
        assert progression_for_first_cell(0.04, n, h) == pytest.approx(q, rel=1e-10)

    def test_uniform(self):
        assert progression_for_first_cell(0.04, 8, 0.005) == 1.0
        assert progression_for_first_cell(0.04, 1, 0.04) == 1.0

    @pytest.mark.parametrize("t, n, h", [
        (0.04, 5, 0.04),     # first cell is the whole layer
        (0.04, 5, 0.05),     # larger than the layer
        (0.04, 5, 0.0),
        (0.04, 5, -0.001),
        (0.04, 1, 0.01),     # one cell must span the layer
    ])
    def test_impossible_raises(self, t, n, h):
        with pytest.raises(ValueError):
            progression_for_first_cell(t, n, h)


class TestSpec:
    def test_wall_cell_is_outer(self):
        spec = (PipeSpec(nang=4).core("fluid", radius=R, nrad=6, first_cell=1e-3)
                .shell("wall", dR=DR, nrad=4, first_cell=1e-3))
        core_t = (1 - OH_RATIO) * R
        assert spec._core_mprg < 1 and spec.shells[0].mprg < 1    # fine at the outer end
        # mprg grows cells outward, so the last (outer) cell is the first-cell height
        assert first_cell_height(core_t, 6, spec._core_mprg) * spec._core_mprg ** 5 \
            == pytest.approx(1e-3)
        assert first_cell_height(DR, 4, spec.shells[0].mprg) * spec.shells[0].mprg ** 3 \
            == pytest.approx(1e-3)

    def test_mprg_and_first_cell_exclusive(self):
        with pytest.raises(TypeError, match="not both"):
            PipeSpec(nang=4).core("fluid", radius=R, nrad=6, mprg=1.0, first_cell=1e-3)
        with pytest.raises(TypeError, match="not both"):
            PipeSpec(nang=4).core("fluid", radius=R, nrad=6).shell(
                "wall", dR=DR, nrad=3, mprg=1.2, first_cell=1e-3)

    def test_rect_core_rejected(self):
        with pytest.raises(TypeError, match="circular cores only"):
            PipeSpec(nang_w=4, nang_h=4).core("air", half_w=0.1, half_h=0.1, nrad=4,
                                              first_cell=1e-3)

    def test_impossible_reported_at_build(self):
        with pytest.raises(ValueError, match="no larger than the layer thickness"):
            PipeSpec(nang=4).core("fluid", radius=R, nrad=6).shell(
                "wall", dR=DR, nrad=3, first_cell=0.02)

    def test_default_unchanged(self):
        spec = PipeSpec(nang=4).core("fluid", radius=R, nrad=6).shell("wall", dR=DR, nrad=3)
        assert spec._core_mprg == 1.0 and spec.shells[0].mprg == 1.0


# ---------------------------------------------------------------------------
# Realisation
# ---------------------------------------------------------------------------

H = 1.5e-3


def _face_nodes():
    """(radius, angle mod 90°) of the hex nodes on the inlet face (x = 0)."""
    c = kit._hex_nodes()
    c = c[np.abs(c[:, 0]) < 1e-9]
    r = np.hypot(c[:, 1], c[:, 2])
    a = np.degrees(np.arctan2(c[:, 2], c[:, 1])) % 90.0
    return r, a


def _wall_cell(r, a, angle, wall):
    """Radial height of the cell just inside radius *wall* along *angle*."""
    on = r[(np.abs(a - angle) < 1e-6) & (r < wall + 1e-9)]
    on = np.unique(np.round(on, 9))
    return wall - on[-2]


@pytest.fixture
def meshed(gmsh_session):
    spec = (PipeSpec(nang=6).core("fluid", radius=R, nrad=8, first_cell=H)
            .shell("wall", dR=DR, nrad=4, first_cell=H))
    asm = Assembly(spec, lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    asm.mesh()
    assert asm.check_quality().ok
    return _face_nodes()


def test_core_first_cell_at_corner_radial(meshed):
    r, a = meshed
    assert _wall_cell(r, a, 45.0, R) == pytest.approx(H, rel=0.01)


def test_shell_first_cell_all_round(meshed):
    r, a = meshed
    for angle in (45.0, 60.0, 75.0, 0.0):
        assert _wall_cell(r, a, angle, R + DR) == pytest.approx(H, rel=0.01)


def test_core_mid_arc_cell_is_larger_by_thickness_ratio(meshed):
    """Between corners the core is thicker (inner arcs bulge inward); the
    transfinite fractions are the corner's, so the wall cell scales with the
    local thickness (recorded in docs/tasks/0002)."""
    r, a = meshed
    # inner arc NE→SE is centred on the opposite square point W = (-ρ, 0),
    # ρ = OH_RATIO·R, and passes through the corner (ρ/√2, ρ/√2)
    rho = OH_RATIO * R
    inner_mid = math.hypot(rho + rho / math.sqrt(2), rho / math.sqrt(2)) - rho
    ratio = (R - inner_mid) / ((1 - OH_RATIO) * R)
    h_mid = _wall_cell(r, a, 0.0, R)
    assert h_mid == pytest.approx(H * ratio, rel=0.01)
    assert 1.2 < ratio < 1.3
