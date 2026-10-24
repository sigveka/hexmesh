"""
PCF and bathymetry readers build an Assembly (docs/tasks/0015).
"""

import textwrap

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import AssemblyError
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.io.readers.pcf import read_pcf


def _spec(radius=0.1):
    return (PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)
            .shell("wall", dR=0.01, nrad=2))


# pipe → flange → elbow (bends toward +y, which is "down" for the default up)
# → concentric reducer 200 → 150 mm → pipe; coordinates in mm
LINE = """\
PIPE
    END-POINT 0 0 0 200
    END-POINT 900 0 0 200
FLANGE
    END-POINT 900 0 0 200
    END-POINT 1000 0 0 200
ELBOW
    END-POINT 1000 0 0 200
    END-POINT 1300 300 0 200
    CENTRE-POINT 1000 300 0
REDUCER-CONCENTRIC
    END-POINT 1300 300 0 200
    END-POINT 1300 600 0 150
PIPE
    END-POINT 1300 600 0 150
    END-POINT 1300 1100 0 150
"""


def _pcf(tmp_path, text):
    path = tmp_path / "line.pcf"
    path.write_text(textwrap.dedent(text))
    return read_pcf(path)


def test_pcf_line_builds_and_meshes(tmp_path, gmsh_session):
    net = _pcf(tmp_path, LINE)
    asm = net.to_assembly(_spec())
    asm.validate()
    predicted = asm.cell_count()
    assert len(asm.interfaces) == 6                       # 5 fittings
    out = asm.interfaces[-1]
    np.testing.assert_allclose(out.frame.position, [1.3, 1.1, 0], atol=1e-9)
    np.testing.assert_allclose(out.frame.normal, [0, 1, 0], atol=1e-9)
    assert out.spec.core_shape.radius == pytest.approx(0.075)
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted
    assert asm.check_quality().ok


def test_bore_to_spec_callable(tmp_path):
    net = _pcf(tmp_path, LINE)
    asm = net.to_assembly(lambda bore: _spec(bore / 2))
    asm.validate()
    assert asm.interfaces[-1].spec.core_shape.radius == pytest.approx(0.075)


def test_gap_names_the_component(tmp_path):
    text = LINE.replace("END-POINT 1300 600 0 150\n    END-POINT 1300 1100",
                        "END-POINT 1300 650 0 150\n    END-POINT 1300 1100")
    with pytest.raises(AssemblyError, match=r"component 4 \(PIPE .*starts 0.05 m"):
        _pcf(tmp_path, text).to_assembly(_spec())


def test_wrong_elbow_end_point(tmp_path):
    text = LINE.replace("END-POINT 1300 300 0 200\n    CENTRE",
                        "END-POINT 1300 310 0 200\n    CENTRE")
    with pytest.raises(AssemblyError, match=r"component 2 \(ELBOW"):
        _pcf(tmp_path, text).to_assembly(_spec())


def test_eccentric_reducer_rejected(tmp_path):
    with pytest.raises(AssemblyError, match="eccentric"):
        _pcf(tmp_path, LINE.replace("REDUCER-CONCENTRIC", "REDUCER-ECCENTRIC")).to_assembly(_spec())


KINKED = """\
PIPE
    END-POINT 0 0 0 200
    END-POINT 1000 0 0 200
PIPE
    END-POINT 1000 0 0 200
    END-POINT 2000 200 0 200
PIPE
    END-POINT 2000 200 0 200
    END-POINT 3000 200 100 200
"""


def test_kinks_rejected_or_splined(tmp_path, gmsh_session):
    net = _pcf(tmp_path, KINKED)
    with pytest.raises(AssemblyError, match=r"component 1 .*changes direction"):
        net.to_assembly(_spec())
    asm = net.to_assembly(_spec(), kinks="spline", axial_cell=0.1)
    asm.validate()
    np.testing.assert_allclose(asm.interfaces[-1].frame.position, [3, 0.2, 0.1], atol=1e-9)
    predicted = asm.cell_count()
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


def test_bathymetry_route(tmp_path, gmsh_session):
    pytest.importorskip("scipy")
    from hexmesh.io.readers.bathymetry import read_bathymetry
    x, y = np.meshgrid(np.linspace(-1, 6, 15), np.linspace(-2, 2, 9))
    z = -10 + 0.3 * np.sin(x)                         # gently undulating seabed
    surf = tmp_path / "seabed.xyz"
    np.savetxt(surf, np.column_stack([x.ravel(), y.ravel(), z.ravel()]))
    net = read_bathymetry(surf, [(0, 0), (2, 0.3), (4, 0.2), (5, -0.4)],
                          burial_depth=0.5)
    asm = net.to_assembly(_spec(), kinks="spline", axial_cell=0.1)
    asm.validate()
    predicted = asm.cell_count()
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted
    assert asm.check_quality().ok
