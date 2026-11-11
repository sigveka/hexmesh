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
"""``hexmesh.units`` and scale (task 0128, decision 0047).

The constants are metres per unit, defined once.  A network built with
every length × 1e-3 (millimetre scale) gives the same mesh scaled: same
cell count, same quality.
"""

import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Assembly, Bend, PipeSpec, Session, Straight, Tee, Wye
from hexmesh.quality_hex import min_scaled_jacobians


def test_constants():
    from hexmesh import units
    from hexmesh.units import cm, ft, inch, m, mm, um
    assert (m, cm, mm, um) == (1.0, 0.01, 1e-3, 1e-6)
    assert inch == 0.0254 and ft == pytest.approx(0.3048, rel=1e-15)
    assert 13.25 * mm == pytest.approx(0.01325)
    assert set(units.__all__) == {"m", "cm", "mm", "um", "inch", "ft"}
    import hexmesh
    assert not hasattr(hexmesh, "mm")          # not re-exported (decision 0047)


def test_one_source_for_unit_constants():
    """The PCF reader's units come from ``hexmesh.units``."""
    from hexmesh.interchange.importers import pcf
    from hexmesh.units import inch, mm
    assert pcf.INCH is inch or pcf.INCH == inch
    assert pcf.COORD_UNITS["MM"] == mm and pcf.BORE_UNITS["INCH"] == inch


def _readme(s):
    """The README's first example, every length × *s*."""
    pipe = (PipeSpec(nang=6)
            .core("fluid", radius=0.1 * s, nrad=5, first_cell=0.01 * s)
            .shell("steel", dR=0.008 * s, nrad=2)
            .shell("insulation", dR=0.04 * s, nrad=3))
    asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5 * s, n_layers=8))
    main, branch = asm.add(Tee(branch_length=0.3 * s, branch_radius=0.06 * s))
    asm.add(main, Straight(0.5 * s, n_layers=8), names=["main_end"])
    bend = asm.add(branch, Bend(radius=0.3 * s, angle=90, n_layers=10))
    asm.add(bend, Straight(0.3 * s, n_layers=6), names=["branch_end"])
    return asm


def _wye(s):
    pipe = PipeSpec(nang=6).core("fluid", radius=0.1 * s, nrad=4).shell("steel", dR=0.01 * s, nrad=2)
    asm = Assembly(pipe, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3 * s, n_layers=4))
    left, right = asm.add(Wye(60, run_length=0.3 * s, branch_length=0.5 * s))
    asm.add(left, Straight(0.2 * s, n_layers=3), names=["left"])
    asm.add(right, Straight(0.2 * s, n_layers=3), names=["right"])
    return asm


def _meshed(build, s):
    with Session("scale"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm = build(s)
        asm.validate()
        predicted = asm.cell_count()
        asm.mesh()
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        pos = np.empty(int(tags.max()) + 1, dtype=int)
        pos[tags.astype(int)] = np.arange(len(tags))
        xyz = xyz.reshape(-1, 3)
        types, _, nodes = gmsh.model.mesh.getElements(3)
        hexes = np.concatenate([n for t, n in zip(types, nodes) if t == 5]).reshape(-1, 8)
        assert all(t == 5 for t in types)
        cells = xyz[pos[hexes.astype(int)]]
    return predicted, cells


@pytest.mark.parametrize("build, s", [(_readme, 0.05), (_wye, 1e-3)],
                         ids=["readme_tee_1:20", "wye_1:1000"])
def test_scaled_build_same_cells_and_quality(build, s):
    """Every length × *s*: same cell count, same min SJ (task 0128, step 6).

    Not the same nodes: hexmesh isn't scale-free.  gmsh's
    ``addSurfaceFilling`` default ``tol3d`` (1e-4, a length) and OCC's own
    absolute tolerances move nodes by up to 3e-4 of the size (the tee at
    1:20; the wye at 1:1000 by 4e-6); see task 0128's Outcome.
    """
    n1, c1 = _meshed(build, 1.0)
    n2, c2 = _meshed(build, s)
    assert n1 == n2 == len(c1) == len(c2)
    assert abs(min_scaled_jacobians(c1).min() - min_scaled_jacobians(c2).min()) < 1e-9


@pytest.mark.xfail(strict=True, reason="not scale-free: a 2 mm tee fails its fill "
                                       "(absolute OCC tolerances; task 0128)")
def test_small_tee_builds():
    """The README tee at 1:50 (2 mm main radius; it builds to about 1:33).
    When this passes, the GUIDE's *Current limitations* line on scale can
    go."""
    _meshed(_readme, 0.02)


@pytest.mark.parametrize("s", [1.0, 1e-3, 1e-5, 1e-6])
def test_quality_metrics_do_not_depend_on_cell_size(s):
    """A perfect cube scores 1 at any size: the singular-Jacobian guard is
    relative (task 0128's audit; a 10 µm cube scored mean ratio 0)."""
    from hexmesh import quality_hex as q
    cube = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                     [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float) * s
    for f in (q.mean_ratio_min, q.mean_ratio_avg, q.hex_interpolation_quality, q.scaled_jacobian):
        assert f(cube) == pytest.approx(1.0, abs=1e-12), f.__name__
