"""
Tee block layout (hexmesh/assembly/tee.py).  Conformance is covered by the
kit (tests/test_fitting_conformance.py); these tests cover the tee itself.
"""

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Tee
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec

R = 0.1


def _spec(nang=4, nrad=3):
    return PipeSpec(nang=nang).core("fluid", CircleShape(radius=R, nang=nang), nrad=nrad)


def _tee_asm(ratio=0.5, spec=None, **kw):
    asm = Assembly(spec or _spec(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    tee = Tee(run_length=kw.pop("run", 2 * R), branch_length=kw.pop("branch", 2.5 * R),
              branch_radius=ratio * R, **kw)
    main, branch = asm.add(tee, names=["main", "branch"])
    return asm, main, branch


class TestTopology:
    def test_ports(self):
        asm, main, branch = _tee_asm(0.5)
        np.testing.assert_allclose(main.frame.position, [0.4, 0, 0], atol=1e-12)
        np.testing.assert_allclose(branch.frame.position, [0.2, 0, 0.25], atol=1e-12)
        np.testing.assert_allclose(branch.frame.normal, [0, 0, 1], atol=1e-12)
        assert branch.spec.core_shape.radius == pytest.approx(0.05)

    def test_layout_validates_without_gmsh(self):
        asm, main, branch = _tee_asm(0.5)
        tee = asm.edges[0].fitting
        report = tee.layout([asm.inlet.frame, main.frame, branch.frame],
                            asm.inlet.spec).validate()
        assert not gmsh.isInitialized()
        assert report["blocks"] == 24
        assert report["min_corner_sj"] > 0.2

    @pytest.mark.parametrize("kw, message", [
        (dict(ratio=1.0), "branch radius"),
        (dict(ratio=0.5, run=0.04), "run_length"),
        (dict(ratio=0.5, branch=0.11), "branch_length"),
    ])
    def test_rejected_before_gmsh(self, kw, message):
        asm, _, _ = _tee_asm(**kw)
        with pytest.raises(AssemblyError, match=message):
            asm.validate()
        assert not gmsh.isInitialized()

    def test_multilayer_rejected(self):
        spec = _spec().shell("wall", dR=0.02, nrad=2)
        asm, _, _ = _tee_asm(0.5, spec=spec)
        with pytest.raises(AssemblyError, match="single-layer"):
            asm.validate()


@pytest.mark.parametrize("ratio", [0.3, 0.5, 0.8, 0.95])
def test_all_hex_valid_mesh(gmsh_session, ratio):
    asm, _, _ = _tee_asm(ratio)
    asm.mesh()
    types = gmsh.model.mesh.getElements(3)[0]
    assert [gmsh.model.mesh.getElementProperties(t)[0] for t in types] == ["Hexahedron 8"]
    report = asm.check_quality()
    assert report.ok and report.min_quality > 0.1, str(report)
    names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
    assert names == {"fluid", "fluid_inlet", "fluid_main", "fluid_branch", "fluid_wall"}


# ---------------------------------------------------------------------------
# Exact wall faces (task 0051)
# ---------------------------------------------------------------------------

def _tee_wall_deviation(nang, ratio):
    """Largest distance of the tee's wall nodes from its cylinders (× R)."""
    from test_fitting_conformance import wall_deviations
    asm = Assembly(_spec(nang), direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(run_length=2 * R, branch_length=2.5 * R,
                               branch_radius=ratio * R), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    asm.mesh()
    tee = asm.edges[1]
    assert isinstance(tee.fitting, Tee)
    return wall_deviations(asm)[tee.name]


def test_tee_wall_nodes_on_cylinders(gmsh_session):
    """Every tee wall node within 1e-3 R of the two cylinders (task 0051)."""
    assert _tee_wall_deviation(8, 0.5) < 1e-3


def test_tee_wall_check_catches_filled_faces(gmsh_session, monkeypatch):
    """Without the wall projection the faces are plain fillings, 2–3 % of R
    off: the check must see it."""
    from hexmesh.assembly import tee as tee_mod
    monkeypatch.setattr(tee_mod, "tee_wall", lambda *a: None)
    assert _tee_wall_deviation(4, 0.5) > 0.02
