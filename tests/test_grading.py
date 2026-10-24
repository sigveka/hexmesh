"""
Face-builder grading survives meshing (docs/TASKS.md task 0).

``mprg`` grades radial curves from the inner to the outer end (>1 refines
toward the inner boundary, ``core.spec.LayerSpec``); ``mbmp`` bumps the
angular arcs.  Before task 0 the assembly re-applied every curve as
uniform, silently discarding both.
"""

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight, Tee
from hexmesh.assembly.assembler import curve_constraints
from hexmesh.assembly.corners import canonical_geom, curve_endpoints
from hexmesh.assembly.sweep import CurveMesh
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

from tests.test_blocks import BlockStraight, _mesh_nodes


def _spec(mprg=1.0, shell_mprg=None, mbmp=1.0):
    spec = (PipeSpec(nang=4, mbmp=mbmp)
            .core("fluid", CircleShape(radius=0.1, nang=4), nrad=5, mprg=mprg))
    if shell_mprg is not None:
        spec = spec.shell("wall", dR=0.03, nrad=4, mprg=shell_mprg)
    return spec


def _cells_from(curve: int, start_point: int) -> np.ndarray:
    """Cell sizes along *curve* in its parameter, ordered from *start_point*.

    Lines and circular arcs are parametrised proportionally to length.
    """
    _, _, par = gmsh.model.mesh.getNodes(1, curve, includeBoundary=False)
    (lo,), (hi,) = gmsh.model.getParametrizationBounds(1, curve)
    d = np.diff(np.sort(np.concatenate([[lo], par, [hi]])))
    return d if curve_endpoints(curve)[0] == start_point else d[::-1]


def _radial_cells(face, layer: int) -> np.ndarray:
    """Cell lengths along radial 0 of *layer*, from its inner end."""
    g = canonical_geom(face.layers[layer][1])
    return _cells_from(abs(g['rc'][0]), g['ip'][0])


@pytest.mark.parametrize("mprg", [1.3, 0.8])
def test_core_radial_progression(gmsh_session, mprg):
    asm = Assembly(_spec(mprg), lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    asm.mesh()
    for iface in asm.interfaces:
        d = _radial_cells(iface.face, 0)
        np.testing.assert_allclose(d[1:] / d[:-1], mprg, rtol=1e-6)


def test_shell_radial_progression(gmsh_session):
    asm = Assembly(_spec(1.0, shell_mprg=1.25), lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    asm.mesh()
    core = _radial_cells(asm.inlet.face, 0)
    np.testing.assert_allclose(core, core[0], rtol=1e-6)      # core stays uniform
    d = _radial_cells(asm.inlet.face, 1)
    np.testing.assert_allclose(d[1:] / d[:-1], 1.25, rtol=1e-6)


def test_bend_station_radial_progression(gmsh_session):
    """Internal station faces of a sweep carry the grading too."""
    asm = Assembly(_spec(1.3), lc=0.1)
    asm.add(Bend(0.3, 90, n_layers=4))
    asm.mesh()
    # every radial curve in the model that belongs to a station face:
    for c in asm._fill.curves:
        if c.kind == "Progression" and c.coef != 1.0:
            assert c.coef in (pytest.approx(1.3), pytest.approx(1 / 1.3))
    graded = {c.tag for c in asm._fill.curves if c.coef != 1.0}
    assert len(graded) == 4 * 5          # 4 radials on each of 5 faces (2 ports + 3 stations)


def test_angular_bump(gmsh_session):
    asm = Assembly(_spec(mbmp=0.4), lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    asm.mesh()
    g = canonical_geom(asm.inlet.face.layers[0][1])
    d = _cells_from(abs(g['oc'][0]), g['op'][0])
    assert d[0] == pytest.approx(d[-1], rel=1e-6)          # symmetric
    assert not np.allclose(d, d.mean(), rtol=1e-3)          # not uniform


@pytest.mark.parametrize("spec", [_spec(1.3), _spec(1.2, shell_mprg=0.9)],
                         ids=["core", "core+shell"])
def test_block_layout_grades_like_sweep(spec):
    n_s, c_s, _ = _mesh_nodes(Straight(0.3, n_layers=3), spec)
    n_b, c_b, _ = _mesh_nodes(BlockStraight(0.3, n_layers=3), spec)
    assert n_b == n_s
    np.testing.assert_allclose(c_b, c_s, atol=1e-9)


def test_graded_tee_meshes(gmsh_session):
    asm = Assembly(_spec(1.3, mbmp=0.6), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Tee(run_length=0.2, branch_length=0.25, branch_radius=0.05),
            names=["main", "branch"])
    asm.mesh()
    report = asm.check_quality()
    assert report.ok, str(report)


def test_conflicting_constraints_rejected():
    with pytest.raises(AssemblyError, match="conflicting transfinite"):
        curve_constraints([CurveMesh(7, 5, "Progression", 1.2),
                           CurveMesh(7, 5, "Progression", 1.0)])
    same = curve_constraints([CurveMesh(7, 5, "Bump", 0.5), CurveMesh(7, 5, "Bump", 0.5)])
    assert list(same) == [7]
