"""
PCF and bathymetry readers build an Assembly (docs/tasks/0015, 0021).

PCF fixtures are written from the reference guide's syntax rules (column 1
identifiers, column 5 attributes); see docs/integrations/pcf.md.
"""

import math
import textwrap
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import AssemblyError
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.io.readers.pcf import INCH, read_pcf


def _spec(radius=0.1):
    return (PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)
            .shell("wall", dR=0.01, nrad=2))


HEADER_MM = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
"""

# pipe → flange → elbow (bends toward +y, which is "down" for the default up)
# → concentric reducer 200 → 150 mm → pipe; coordinates in mm.  The elbow's
# CENTRE-POINT is the corner where its tangent legs meet (the guide's
# convention), 300 mm from both end points: a 90° bend of radius 300 mm.
LINE = HEADER_MM + """\
PIPE
    END-POINT 0 0 0 200
    END-POINT 900 0 0 200
FLANGE
    END-POINT 900 0 0 200
    END-POINT 1000 0 0 200
ELBOW
    END-POINT 1000 0 0 200
    END-POINT 1300 300 0 200
    CENTRE-POINT 1300 0 0
REDUCER-CONCENTRIC
    END-POINT 1300 300 0 200
    END-POINT 1300 600 0 150
PIPE
    END-POINT 1300 600 0 150
    END-POINT 1300 1100 0 150
"""


def _pcf(tmp_path, text, **kw):
    path = tmp_path / "line.pcf"
    path.write_text(textwrap.dedent(text))
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # a valid file reads without warnings
        return read_pcf(path, **kw)


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


KINKED = HEADER_MM + """\
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


# ---------------------------------------------------------------------------
# Conformance with the PCF reference guide (docs/tasks/0021)
# ---------------------------------------------------------------------------

def _bend(asm):
    from hexmesh.assembly import Bend
    bends = [e.fitting for e in asm.edges if isinstance(e.fitting, Bend)]
    assert len(bends) == 1
    return bends[0]


# Like the guide's BEND example: 4" line along −y, a 90° bend of 3D = 12"
# radius whose corner is 304.8 mm (12" × tan 45°) from both end points.
GUIDE_BEND = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE INCH
UNITS-CO-ORDS MM
UNITS-BOLT-DIA INCH
UNITS-BOLT-LENGTH INCH
UNITS-WEIGHT KGS
PIPELINE-REFERENCE LINE-1
    PIPING-SPEC A1
PIPE
    END-POINT 0 1000 0 4
    END-POINT 0 500 0 4
BEND
    END-POINT 0 500 0 4
    END-POINT 304.8 195.2 0 4
    CENTRE-POINT 0 195.2 0
    ANGLE 9000
    BEND-RADIUS 3D
PIPE
    END-POINT 304.8 195.2 0 4
    END-POINT 804.8 195.2 0 4
"""


def test_guide_bend_example(tmp_path, gmsh_session):
    net = _pcf(tmp_path, GUIDE_BEND)
    assert net.pipelines == {"LINE-1": {"PIPING-SPEC": "A1"}}
    assert net.header["UNITS-CO-ORDS"] == "MM"
    assert net.components[0].bore == pytest.approx(4 * INCH)          # nominal size
    asm = net.to_assembly(_spec(0.05))
    bend = _bend(asm)
    assert bend.radius == pytest.approx(0.3048) and bend.angle == pytest.approx(90)
    out = asm.interfaces[-1].frame
    assert np.linalg.norm(out.position - [0.8048, 0.1952, 0]) < net.report["tolerance"]
    np.testing.assert_allclose(out.normal, [1, 0, 0], atol=1e-9)
    predicted = asm.cell_count()
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


# 45° long-radius elbow, 6" (R = 1.5D = 228.6 mm): legs R·tan 22.5°.  The
# arc-centre reading would give a different radius and angle.
LEG = 228.6 * math.tan(math.radians(22.5))
C45 = 1000 + LEG
E45 = (C45 + LEG / math.sqrt(2), LEG / math.sqrt(2))
ELBOW_45 = HEADER_MM.replace("UNITS-BORE MM", "UNITS-BORE INCH") + f"""\
PIPE
    END-POINT 0 0 0 6
    END-POINT 1000 0 0 6
ELBOW
    END-POINT 1000 0 0 6
    END-POINT {E45[0]:.4f} {E45[1]:.4f} 0 6
    CENTRE-POINT {C45:.4f} 0 0
    ANGLE 4500
    BEND-RADIUS 1.5D
"""


def test_45_degree_elbow(tmp_path):
    asm = _pcf(tmp_path, ELBOW_45).to_assembly(_spec(0.05))
    bend = _bend(asm)
    assert bend.radius == pytest.approx(0.2286, rel=1e-5)
    assert bend.angle == pytest.approx(45, abs=1e-4)


@pytest.mark.parametrize("attr, match", [
    ("ANGLE 4600", "ANGLE 46° disagrees"),
    ("BEND-RADIUS 3D", r"BEND-RADIUS 3D \(0.4572 m\) disagrees"),
    ("BEND-RADIUS 250", r"BEND-RADIUS 250 \(0.25 m\) disagrees"),     # absolute, in mm
])
def test_elbow_cross_check_names_the_component(tmp_path, attr, match):
    key = attr.split()[0]
    text = "\n".join(l for l in ELBOW_45.splitlines() if not l.strip().startswith(key))
    text += f"\n    {attr}\n"
    with pytest.raises(AssemblyError, match=rf"component 1 \(ELBOW .*{match}"):
        _pcf(tmp_path, text).to_assembly(_spec(0.05))


def test_elbow_leg_must_follow_the_incoming_pipe(tmp_path):
    text = ELBOW_45.replace(f"CENTRE-POINT {C45:.4f} 0 0", f"CENTRE-POINT {C45:.4f} 20 0")
    with pytest.raises(AssemblyError, match="incoming leg .* is not along the incoming pipe"):
        _pcf(tmp_path, text).to_assembly(_spec(0.05))


# --- units -------------------------------------------------------------------

def _one_pipe(coords, bore_unit, x1, bore):
    return f"""\
UNITS-BORE {bore_unit}
UNITS-CO-ORDS {coords}
PIPELINE-REFERENCE P
PIPE
    END-POINT 0 0 0 {bore}
    END-POINT {x1} 0 0 {bore}
"""


@pytest.mark.parametrize("coords, x1, metres", [
    ("MM", 1500, 1.5), ("MM-HUNDREDTHS", 150000, 1.5), ("INCH", 60, 1.524)])
def test_coordinate_units(tmp_path, coords, x1, metres):
    net = _pcf(tmp_path, _one_pipe(coords, "MM", x1, 100))
    np.testing.assert_allclose(net.components[0].end, [metres, 0, 0])


@pytest.mark.parametrize("unit, value, metres", [
    ("MM", 100, 0.1), ("INCH", 4, 0.1016), ("INCH-SIXTEENTH", 96, 0.1524)])
def test_bore_units_are_independent_of_coordinates(tmp_path, unit, value, metres):
    net = _pcf(tmp_path, _one_pipe("INCH", unit, 60, value))
    assert net.components[0].bore == pytest.approx(metres)


def test_no_header_reads_mm_and_warns_once(tmp_path):
    path = tmp_path / "bare.pcf"
    path.write_text("PIPE\n    END-POINT 0 0 0 100\n    END-POINT 1000 0 0 100\n")
    with pytest.warns(UserWarning, match="no UNITS-CO-ORDS") as rec:
        net = read_pcf(path)
    assert len(rec) == 1
    np.testing.assert_allclose(net.components[0].end, [1, 0, 0])
    assert net.components[0].bore == pytest.approx(0.1)


def test_unit_scale_overrides_header(tmp_path):
    path = tmp_path / "p.pcf"
    path.write_text(_one_pipe("INCH", "INCH", 60, 4))
    with pytest.warns(UserWarning, match="overrides UNITS-CO-ORDS INCH"):
        net = read_pcf(path, unit_scale=1e-3)
    np.testing.assert_allclose(net.components[0].end, [0.06, 0, 0])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        read_pcf(path, unit_scale=INCH)                  # agrees: no warning


def test_unknown_units_rejected(tmp_path):
    path = tmp_path / "p.pcf"
    path.write_text(_one_pipe("FEET", "MM", 1, 100))
    with pytest.raises(ValueError, match="UNITS-CO-ORDS 'FEET'"):
        read_pcf(path)


# --- sections ----------------------------------------------------------------

MINIMAL = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM
UNITS-CO-ORDS MM
UNITS-BOLT-DIA MM
UNITS-BOLT-LENGTH MM
UNITS-WEIGHT KGS
PIPELINE-REFERENCE A-100
    PIPING-SPEC CS1
    INSULATION-THICKNESS 50
END-CONNECTION-PIPELINE
    CO-ORDS 0 0 0 100
    PIPELINE-REFERENCE B-200
PIPE
    END-POINT 0 0 0 100
    END-POINT 2000 0 0 100
    MATERIAL-IDENTIFIER 1
FLANGE
    END-POINT 2000 0 0 100
    END-POINT 2100 0 0 100
    MATERIAL-IDENTIFIER 2
MATERIALS
MATERIAL-IDENTIFIER 1
    DESCRIPTION PIPE 100 SCH40
MATERIAL-IDENTIFIER 2
    DESCRIPTION FLANGE WN 100
"""


def test_minimal_valid_file_reads_without_warnings(tmp_path):
    net = _pcf(tmp_path, MINIMAL)                      # warnings are errors here
    assert [c.record_type for c in net.components] == ["PIPE", "FLANGE"]
    assert net.skipped == []
    assert net.pipelines["A-100"] == {"PIPING-SPEC": "CS1", "INSULATION-THICKNESS": "50"}
    assert [n for n, _ in net.connections] == ["END-CONNECTION-PIPELINE"]
    assert all(c.pipeline == "A-100" for c in net.components)
    asm = net.to_assembly(_spec(0.05))
    np.testing.assert_allclose(asm.interfaces[-1].frame.position, [2.1, 0, 0], atol=1e-9)


# --- joints and real-file dialects ---------------------------------------------

# Our own equivalent of pcf2iso's demo spool (inches): flange, COCP gap
# couplings (1/16"), pipe, 90° LR elbow (1.5D = 6" legs), pipe with a set-on
# tee, cap, and ITEM-CODE in column 1 under MATERIALS.  The couplings, the
# lateral offsets and column-1 ITEM-CODE are documented non-spec dialects.
SPOOL = """\
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE INCH
UNITS-CO-ORDS INCH
PIPELINE-REFERENCE SPOOL-1
FLANGE
    END-POINT 0 0 50 4 FL
    END-POINT 0 4 50 4 PL
COUPLING
    END-POINT 0 4 50 4 PL
    END-POINT 0 4.0625 50 4 PL
    SKEY COCP
PIPE
    END-POINT 0 4.0625 50 4 PL
    END-POINT 0 40 50 4 PL
COUPLING
    END-POINT 0 40 50 4 PL
    END-POINT 0 40.0625 50 4 PL
    SKEY COCP
ELBOW
    END-POINT 0 40.0625 50 4 PL
    END-POINT 0 46.0625 56 4 PL
    CENTRE-POINT 0 46.0625 50
    ANGLE 9000
COUPLING
    END-POINT 0 46.0625 56 4 PL
    END-POINT 0 46.0625 56.0625 4 PL
    SKEY COCP
PIPE
    END-POINT 0 46.0625 56.0625 4 PL
    END-POINT 0 46.0625 90 4 PL
TEE-SET-ON
    CENTRE-POINT 0 46.0625 70
    BRANCH1-POINT 3 46.0625 70 1 PL
    SKEY TESO
COUPLING
    END-POINT 0 46.0625 90 4 PL
    END-POINT 0 46.0625 90.0625 4 PL
    SKEY COCP
CAP
    END-POINT 0 46.0625 90.0625 4 PL
    END-POINT 0 46.0625 92.5625 4 PL
MATERIALS
ITEM-CODE 1
    DESCRIPTION Flange
ITEM-CODE 2
    DESCRIPTION Shop weld
"""


SPOOL_NO_SETON = SPOOL.replace("""TEE-SET-ON
    CENTRE-POINT 0 46.0625 70
    BRANCH1-POINT 3 46.0625 70 1 PL
    SKEY TESO
""", "")


def test_spool_set_on_meshes_on_single_layer_spec(tmp_path):
    """The demo spool's set-on (task 0037): its host pipe is split, the gap
    couplings are still absorbed, and the branch lands on BRANCH1-POINT."""
    from hexmesh.assembly import Tee
    net = _read_spool(tmp_path, SPOOL)
    single = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.05, nang=4), nrad=3)
    asm = net.to_assembly(single)
    tee, = [e for e in asm.edges if isinstance(e.fitting, Tee)]
    assert tee.fitting.run_length == pytest.approx(1 * INCH)     # the branch bore
    np.testing.assert_allclose(tee.ports[2].frame.position,
                               np.array([3, 46.0625, 70]) * INCH, atol=1e-9)
    assert [a for _, a in net.report["joints"]] == ["absorbed"] * 4
    predicted = asm.cell_count()
    with Session("spool"):
        asm.mesh()
        assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


def test_spool_set_on_rejected_on_layered_spec(tmp_path):
    """A set-on tee's run is the branch bore each side (task 0037): too short
    for the wall's slab, which inverts.  Rejected before GMSH (task 0052,
    Questions for design)."""
    net = _read_spool(tmp_path, SPOOL)
    asm = net.to_assembly(_spec(0.05))
    with pytest.raises(AssemblyError, match=r"Tee.*inverted or degenerate"):
        asm.validate()
    assert not gmsh.isInitialized()


def _read_spool(tmp_path, text, name="spool.pcf"):
    """The set-on tee is read (task 0037): no warnings."""
    path = tmp_path / name
    path.write_text(text)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        net = read_pcf(path)
    assert net.skipped == []
    return net


def test_spool_with_gap_couplings(tmp_path, gmsh_session):
    from hexmesh.assembly import Straight
    net = _read_spool(tmp_path, SPOOL_NO_SETON)
    asm = net.to_assembly(_spec(0.05))
    bend = _bend(asm)
    assert bend.radius == pytest.approx(6 * INCH) and bend.angle == pytest.approx(90)
    assert all(isinstance(e.fitting, Straight) or e.fitting is bend for e in asm.edges)
    assert len(asm.edges) == 5                             # flange, pipe, elbow, pipe, cap
    assert [a for _, a in net.report["joints"]] == ["absorbed"] * 4
    np.testing.assert_allclose(asm.interfaces[-1].frame.position,
                               np.array([0, 46.0625, 92.5625]) * INCH, atol=1e-9)
    # the couplings' length went into the runs: total straight length matches
    straight = sum(e.fitting.length for e in asm.edges if isinstance(e.fitting, Straight))
    assert straight == pytest.approx((40.0625 + (92.5625 - 56)) * INCH, abs=1e-9)
    predicted = asm.cell_count()
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == predicted


def test_trailing_joint_after_elbow_is_dropped(tmp_path):
    """Like pcf2iso's lower_run: the line ends with a coupling after the elbow."""
    text = SPOOL[:SPOOL.index("PIPE\n    END-POINT 0 46.0625 56.0625")] + "MATERIALS\n"
    net = _pcf(tmp_path, text)
    asm = net.to_assembly(_spec(0.05))
    assert net.report["joints"][-1] == ("COUPLING", "dropped")
    np.testing.assert_allclose(asm.interfaces[-1].frame.position,
                               np.array([0, 46.0625, 56]) * INCH, atol=1e-9)


def test_gap_and_zero_length_weld_by_spec(tmp_path):
    text = MINIMAL.replace("""FLANGE
    END-POINT 2000 0 0 100""", """WELD
    END-POINT 2000 0 0 100
    END-POINT 2000 0 0 100
    SKEY WW
GAP
    END-POINT 2000 0 0 100
    END-POINT 2010 0 0 100
FLANGE
    END-POINT 2010 0 0 100""")
    net = _pcf(tmp_path, text)
    asm = net.to_assembly(_spec(0.05))
    assert [k for k, _ in net.report["joints"]] == ["WELD", "GAP"]
    assert len(asm.edges) == 2
    np.testing.assert_allclose(asm.interfaces[-1].frame.position, [2.1, 0, 0], atol=1e-9)


def test_long_coupling_is_a_fitting(tmp_path):
    text = MINIMAL.replace("FLANGE", "COUPLING")              # 100 mm: not a joint
    net = _pcf(tmp_path, text)
    assert net.components[1].kind == "fitting"


def test_lateral_offset_within_tolerance_is_absorbed(tmp_path):
    text = MINIMAL.replace("END-POINT 2100 0 0 100", "END-POINT 2100 1.5 0 100")
    net = _pcf(tmp_path, text)
    asm = net.to_assembly(_spec(0.05))
    assert net.report["tolerance"] == pytest.approx(0.11 * INCH)    # the floor
    assert net.report["max_offset"] == pytest.approx(1.5e-3)
    np.testing.assert_allclose(asm.interfaces[-1].frame.position, [2.1, 0, 0], atol=1e-9)
    bad = MINIMAL.replace("END-POINT 2100 0 0 100", "END-POINT 2100 5 0 100")
    with pytest.raises(AssemblyError, match="component 1 \\(FLANGE"):
        _pcf(tmp_path, bad).to_assembly(_spec(0.05))


def test_joint_between_two_elbows_rejected(tmp_path):
    """The coupling after the elbow is followed by a second elbow: no straight
    run on either side to absorb it."""
    text = SPOOL_NO_SETON.replace("""PIPE
    END-POINT 0 46.0625 56.0625 4 PL
    END-POINT 0 46.0625 90 4 PL
""", """ELBOW
    END-POINT 0 46.0625 56.0625 4 PL
    END-POINT 0 52.0625 62.0625 4 PL
    CENTRE-POINT 0 46.0625 62.0625
""")
    text = text[:text.index("COUPLING\n    END-POINT 0 46.0625 90 ")] + "MATERIALS\n"
    net = _read_spool(tmp_path, text)
    with pytest.raises(AssemblyError, match="COUPLING .* between two non-straight fittings"):
        net.to_assembly(_spec(0.05))
