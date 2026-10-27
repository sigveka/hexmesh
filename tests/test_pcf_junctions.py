"""
PCF branched networks (task 0037, decision 0023).

The reader turns TEE, TEE-SET-ON / OLET and Y-PIECE-FABRICATED records into
``Tee`` and ``Wye`` fittings, joins components across pipelines and files by
their end points, and names fittings and open ends from the file.  Every
junction outside the fittings' limits is rejected naming the component.

The fixtures are hand-written (millimetres, nominal bores) and only use the
keywords of the PCF guide's component sheets.
"""

import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import AssemblyError, Straight, Tee, Wye
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.io.readers.pcf import read_pcf


def _spec(radius=0.05):
    """Single-layer: the junction prototypes take no shells."""
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)


HEADER = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
"""

C30, S30 = 400 * math.cos(math.radians(30)), 400 * math.sin(math.radians(30))

# Main line along +x: a TEE with its branch to +y, a set-on to +z, and a
# Y piece at the end (60°, daughters in the x-y plane).  An OLET sits on the
# tee's branch pipe.  Pipeline B-200 (second file) continues the branch.
NETWORK_A = HEADER + f"""\
PIPELINE-REFERENCE A-100
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
    SKEY TEBW
PIPE
    END-POINT 1200 0 0 100
    END-POINT 2000 0 0 100
TEE-SET-ON
    CENTRE-POINT 1600 0 0
    BRANCH1-POINT 1600 0 250 50
    SKEY TESO
PIPE
    END-POINT 1100 300 0 50
    END-POINT 1100 800 0 50
OLET
    CENTRE-POINT 1100 550 0
    BRANCH1-POINT 1100 550 200 25
    SKEY WTBW
END-CONNECTION-PIPELINE
    CO-ORDS 1100 800 0 50
    PIPELINE-REFERENCE B-200
Y-PIECE-FABRICATED
    CENTRE-POINT 2000 0 0
    BRANCH1-POINT {2000 + C30:.6f} {S30:.6f} 0 100
    BRANCH2-POINT {2000 + C30:.6f} {-S30:.6f} 0 100
    SKEY TYSO
PIPE
    END-POINT {2000 + C30:.6f} {S30:.6f} 0 100
    END-POINT {2000 + 2 * C30:.6f} {2 * S30:.6f} 0 100
"""

NETWORK_B = HEADER + """\
PIPELINE-REFERENCE B-200
PIPE
    END-POINT 1100 800 0 50
    END-POINT 1100 1200 0 50
"""


def _write(tmp_path, text, name="net.pcf"):
    p = tmp_path / name
    p.write_text(text)
    return p


def _read(tmp_path, *texts):
    paths = [_write(tmp_path, t, f"f{i}.pcf") for i, t in enumerate(texts)]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        return read_pcf(paths if len(paths) > 1 else paths[0])


@pytest.fixture
def network(tmp_path):
    net = _read(tmp_path, NETWORK_A, NETWORK_B)
    return net, net.to_assembly(_spec())


# --- parsing --------------------------------------------------------------------

def test_junction_records_parsed(tmp_path):
    net = _read(tmp_path, NETWORK_A)
    kinds = [c.kind for c in net.components]
    assert kinds == ["pipe", "tee", "pipe", "seton", "pipe", "seton", "ypiece", "pipe"]
    tee = net.components[1]
    np.testing.assert_allclose(tee.branch, [1.1, 0.3, 0])
    assert tee.branch_bore == pytest.approx(0.05) and tee.skey == "TEBW"
    y = net.components[6]
    assert y.branch2 is not None and y.branch_bore == pytest.approx(0.1)
    assert net.skipped == []


def test_tee_third_end_point_is_the_branch(tmp_path):
    text = NETWORK_A.replace("    BRANCH1-POINT 1100 300 0 50\n",
                             "    END-POINT 1100 300 0 50\n")
    net = _read(tmp_path, text)
    np.testing.assert_allclose(net.components[1].branch, [1.1, 0.3, 0])
    np.testing.assert_allclose(net.components[1].end, [1.2, 0, 0])


def test_several_files_merge_in_order(tmp_path):
    net = _read(tmp_path, NETWORK_A, NETWORK_B)
    assert len(net.components) == 9
    assert net.components[-1].pipeline == "B-200"
    assert net.components[-1].source.endswith("f1.pcf")


# --- the assembly ---------------------------------------------------------------

def test_junctions_become_fittings(network):
    _, asm = network
    tees = [e for e in asm.edges if isinstance(e.fitting, Tee)]
    wyes = [e for e in asm.edges if isinstance(e.fitting, Wye)]
    assert [e.name for e in tees] == ["TEE_1", "TEE_SET_ON_1", "OLET_1"]
    assert [e.name for e in wyes] == ["Y_PIECE_FABRICATED_1"]
    tee = tees[0].fitting
    assert tee.run_length == pytest.approx(0.1)
    assert tee.branch_length == pytest.approx(0.3)
    assert tee.branch_radius == pytest.approx(0.025)        # 50 / 100 of the main
    seton = tees[1].fitting
    assert seton.run_length == pytest.approx(0.05)          # the branch diameter
    assert wyes[0].fitting.angle == pytest.approx(60)


def test_set_on_splits_its_host(network):
    _, asm = network
    names = [e.name for e in asm.edges]
    assert "PIPE_2_1" in names and "PIPE_2_2" in names
    for e in asm.edges:
        if e.name == "PIPE_2_1":
            assert e.fitting.length == pytest.approx(1.55 - 1.2)


def test_ports_land_on_pcf_points(network):
    _, asm = network
    tee = next(e for e in asm.edges if e.name == "TEE_1")
    np.testing.assert_allclose(tee.ports[1].frame.position, [1.2, 0, 0], atol=1e-9)
    np.testing.assert_allclose(tee.ports[2].frame.position, [1.1, 0.3, 0], atol=1e-9)
    np.testing.assert_allclose(tee.ports[2].frame.normal, [0, 1, 0], atol=1e-9)
    olet = next(e for e in asm.edges if e.name == "OLET_1")
    np.testing.assert_allclose(olet.ports[2].frame.normal, [0, 0, 1], atol=1e-9)
    wye = next(e for e in asm.edges if e.name == "Y_PIECE_FABRICATED_1")
    left, right = wye.ports[1:]
    np.testing.assert_allclose(right.frame.position, [2 + C30 / 1000, S30 / 1000, 0],
                               atol=1e-9)                   # BRANCH1 → right
    np.testing.assert_allclose(left.frame.position, [2 + C30 / 1000, -S30 / 1000, 0],
                               atol=1e-9)


def test_open_ends_named_by_pipeline(network):
    _, asm = network
    names = sorted(i.name for i in asm.interfaces if i.name)
    assert asm.inlet.name == "A_100_end1"
    assert "B_200_end1" in names
    # A-100: inlet, olet branch, set-on branch, wye left, wye right daughter pipe
    assert sum(n.startswith("A_100_end") for n in names) == 5


def test_same_file_same_assembly(tmp_path):
    a = _read(tmp_path, NETWORK_A, NETWORK_B).to_assembly(_spec()).to_dict()
    b = _read(tmp_path, NETWORK_A, NETWORK_B).to_assembly(_spec()).to_dict()
    assert a == b


def test_branched_network_meshes_all_hex(network):
    _, asm = network
    asm.validate()
    predicted = asm.cell_count()
    with Session("pcf_junctions"):
        asm.mesh()
        types, tags, _ = gmsh.model.mesh.getElements(3)
        assert list(types) == [5]
        assert sum(len(t) for t in tags) == predicted
        assert asm.check_quality().ok


def test_root_by_name_and_point(tmp_path):
    net = _read(tmp_path, NETWORK_A, NETWORK_B)
    asm = net.to_assembly(_spec(), inlet=[0, 0, 0])
    assert asm.inlet.name == "A_100_end1"
    with pytest.raises(AssemblyError, match="would be entered from its branch"):
        net.to_assembly(_spec(), inlet="B_200_end1")
    with pytest.raises(AssemblyError, match="not an open end.*A_100_end1"):
        net.to_assembly(_spec(), inlet="nowhere")


def test_default_root_skips_branch_ends(tmp_path):
    """The first open end in file order is a branch: the root moves on."""
    text = HEADER + """\
PIPE
    END-POINT 1100 600 0 50
    END-POINT 1100 300 0 50
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
"""
    asm = _read(tmp_path, text).to_assembly(_spec())
    np.testing.assert_allclose(asm.inlet.frame.position, [1.2, 0, 0], atol=1e-12)


def test_flow_marks_the_upstream_end(tmp_path):
    text = HEADER + """\
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
    FLOW 2
"""
    asm = _read(tmp_path, text).to_assembly(_spec())
    np.testing.assert_allclose(asm.inlet.frame.position, [2, 0, 0], atol=1e-12)


def test_root_roll_puts_branch_on_allowed_roll(tmp_path):
    """A pipe along a skew direction: the root's up is rolled so the branch
    lands on a multiple of 90°."""
    d = np.array([1.0, 2.0, 2.0]) / 3
    b = np.cross(d, [0, 0, 1])
    b /= np.linalg.norm(b)
    P = lambda x: " ".join(f"{v * 1000:.6f}" for v in x)
    text = HEADER + f"""\
PIPE
    END-POINT 0 0 0 100
    END-POINT {P(d)} 100
TEE
    END-POINT {P(d)} 100
    END-POINT {P(1.2 * d)} 100
    CENTRE-POINT {P(1.1 * d)}
    BRANCH1-POINT {P(1.1 * d + 0.3 * b)} 50
"""
    asm = _read(tmp_path, text).to_assembly(_spec())
    tee = asm.edges[-1]
    np.testing.assert_allclose(tee.ports[2].frame.normal, b, atol=1e-9)
    assert tee.fitting.roll % 90 == pytest.approx(0, abs=1e-9)


# --- rejections -----------------------------------------------------------------

LINE = HEADER + """\
PIPELINE-REFERENCE A-100
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
"""


@pytest.mark.parametrize("record, match", [
    ("""TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 100
""", r"component 1 \(TEE TEE_1.*equal tees"),
    ("""TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1273.205 300 0 50
""", r"TEE_1.*branch at 60° to the run"),
    ("""TEE
    END-POINT 1000 0 0 100
    END-POINT 1300 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
""", r"TEE_1.*not symmetric"),
    ("""CROSS
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
""", r"component 1 \(CROSS .*crosses"),
    ("""PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
TEE-SET-ON
    CENTRE-POINT 1500 0 0
    BRANCH1-POINT 1500 300 0 50
    SKEY TOSO
""", r"TEE-SET-ON TEE_SET_ON_1, SKEY TOSO.*tangential and offset"),
    ("""PIPE
    END-POINT 1000 0 0 100
    END-POINT 1080 0 0 100
TEE-SET-ON
    CENTRE-POINT 1040 0 0
    BRANCH1-POINT 1040 300 0 50
""", r"TEE_SET_ON_1.*host pipe PIPE_2 is too short"),
    ("""OLET
    CENTRE-POINT 1500 700 0
    BRANCH1-POINT 1500 900 0 25
""", r"OLET OLET_1.*no PIPE passes through its CENTRE-POINT"),
    ("""Y-PIECE-FABRICATED
    CENTRE-POINT 1000 0 0
    BRANCH1-POINT 1346.41 200 0 100
    BRANCH2-POINT 1200 -346.41 0 100
""", r"Y_PIECE_FABRICATED_1.*asymmetric Y piece"),
    ("""PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
PIPE
    END-POINT 1000 0 0 100
    END-POINT 1000 1000 0 100
""", r"3 components meet at .*PIPE_1, PIPE_2, PIPE_3"),
    ("""PIPE
    END-POINT 1500 0 0 100
    END-POINT 2000 0 0 100
""", r"component 1 \(PIPE PIPE_2.*starts 0.5 m from the open end of component 0"),
])
def test_rejections_name_the_component(tmp_path, record, match):
    net = _read(tmp_path, LINE + record)
    with pytest.raises(AssemblyError, match=match):
        net.to_assembly(_spec())


def test_loop_rejected(tmp_path):
    text = LINE + """\
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
PIPE
    END-POINT 1100 300 0 50
    END-POINT 1200 0 0 50
"""
    with pytest.raises(AssemblyError, match="on a loop"):
        _read(tmp_path, text).to_assembly(_spec())


def test_layered_spec_rejected_naming_the_tee(tmp_path):
    text = LINE + """\
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
"""
    layered = _spec().shell("wall", dR=0.005, nrad=2)
    with pytest.raises(AssemblyError, match=r"TEE_1.*single-layer"):
        _read(tmp_path, text).to_assembly(layered)


def test_component_identifier_labels(tmp_path):
    text = LINE + """\
TEE
    COMPONENT-IDENTIFIER T-7/A
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
"""
    asm = _read(tmp_path, text).to_assembly(_spec())
    assert asm.edges[-1].name == "TEE_T_7_A"


def test_spec_callable_sizes_the_branch(tmp_path):
    """With a spec callable, the branch radius comes from the branch bore."""
    text = LINE + """\
TEE
    END-POINT 1000 0 0 100
    END-POINT 1200 0 0 100
    CENTRE-POINT 1100 0 0
    BRANCH1-POINT 1100 300 0 50
PIPE
    END-POINT 1100 300 0 50
    END-POINT 1100 600 0 50
"""
    sizes = []

    def by_bore(bore):
        sizes.append(bore)
        return _spec(0.4 * bore)
    asm = _read(tmp_path, text).to_assembly(by_bore)
    tee = next(e for e in asm.edges if isinstance(e.fitting, Tee))
    assert tee.fitting.branch_radius == pytest.approx(0.4 * 0.05)
    assert asm.inlet.spec.core_shape.radius == pytest.approx(0.4 * 0.1)
    assert 0.05 in sizes
    asm.validate()
