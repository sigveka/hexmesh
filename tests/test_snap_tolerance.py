"""The snap tolerance: one per reader, carried by the model (task 0138).

Ends closer than ``NetworkModel.snap_tolerance`` (or the relative
tolerance, if larger) are one point when a model is built; the default is
0.11" (``TOL_FLOOR``, pcf2iso's)."""
import pytest

from hexmesh import interchange as ix
from hexmesh.assembly import AssemblyError
from hexmesh.core.spec import PipeSpec
from hexmesh.errors import ReaderError
from hexmesh.interchange.model import TOL_FLOOR
from hexmesh.units import inch, mm

TUBE = 4 * mm                 # a lab rig's tubing: bore 4 mm


def _spec(bore=TUBE):
    return PipeSpec(nang=4).core("fluid", radius=bore / 2, nrad=3)


def _tubes(gap=2 * mm, snap=None):
    """Two 4 mm tubes in line, *gap* apart, built by hand."""
    m = ix.NetworkModel() if snap is None else ix.NetworkModel(snap_tolerance=snap)
    sec = ix.Section(nominal=TUBE)
    for i, (a, b) in enumerate((((0, 0, 0), (0.05, 0, 0)),
                                ((0.05 + gap, 0, 0), (0.1 + gap, 0, 0)))):
        part = m.add_part(ix.Straight, [a, b], id=f"t{i}", system="rig")
        for q in part.ports:
            m.ports[q].section = sec
    return m


def test_the_default_is_0_11_inch_and_joins_ends_2_mm_apart():
    m = _tubes()
    assert m.snap_tolerance == TOL_FLOOR == pytest.approx(0.11 * inch)
    assert m.snap_source == "default"
    ix.build(m, _spec())
    assert m.report["tolerance"] == TOL_FLOOR and m.report["tol_source"] == "default"


def test_a_small_snap_tolerance_keeps_ends_2_mm_apart_separate():
    m = _tubes(snap=1e-4)
    with pytest.raises(AssemblyError) as e:
        ix.build(m, _spec())
    # two pieces, the gap named (task 0138 said chain_gap: that's a gap
    # inside one chain; separate ends are this)
    assert e.value.code == "network_disconnected"
    assert "starts 0.002 m from the open end of part t0" in str(e.value)


def test_an_explicit_tol_wins_and_says_so():
    m = _tubes(snap=1e-4)
    ix.build(m, _spec(), tol=3 * mm)
    assert m.report["tolerance"] == 3 * mm and m.report["tol_source"] == "given"


def test_a_large_model_uses_the_relative_tolerance():
    m = ix.NetworkModel(snap_tolerance=1e-6)
    sec = ix.Section(nominal=0.1)
    part = m.add_part(ix.Straight, [(0, 0, 0), (100, 0, 0)], system="L")
    for q in part.ports:
        m.ports[q].section = sec
    ix.build(m, _spec(0.1))
    assert m.report["tol_source"] == "relative"
    assert m.report["tolerance"] == pytest.approx(1e-4 * 100)


LINE = """\
UNITS-BORE MM
UNITS-CO-ORDS MM
PIPELINE-REFERENCE L-1
PIPE
    END-POINT 0 0 0 100
    END-POINT 1000 0 0 100
PIPE
    END-POINT 1000 0 0 100
    END-POINT 2000 0 0 100
"""


def _pcf(tmp_path):
    p = tmp_path / "line.pcf"
    p.write_text(LINE, encoding="utf-8")
    return p


def test_a_pcf_read_stores_0_11_inch_and_the_log_keeps_it(tmp_path):
    path = _pcf(tmp_path)
    m = ix.read_pcf(path).to_model()
    assert (m.snap_tolerance, m.snap_source) == (TOL_FLOOR, "pcf")
    assert m.log[0]["args"]["options"]["snap_tolerance"] == TOL_FLOOR
    ix.build(m, _spec(0.1))
    assert m.report["tol_source"] == "reader pcf"


def test_read_pcf_takes_its_own_and_replay_keeps_it(tmp_path):
    path = _pcf(tmp_path)
    m = ix.read_pcf(path, snap_tolerance=0.5 * mm).to_model()
    assert m.snap_tolerance == 0.5 * mm
    assert m.log[0]["args"]["options"]["snap_tolerance"] == 0.5 * mm
    m.cut((m.parts["0"].ports[1], m.parts["1"].ports[0]))
    again = m.replay(ix.read_pcf(path, snap_tolerance=0.5 * mm).to_model())
    assert again.snap_tolerance == 0.5 * mm
    m.undo()
    assert m.snap_tolerance == 0.5 * mm


def test_an_old_log_without_the_key_rereads_with_the_default(tmp_path):
    from hexmesh.interchange.importers.pcf import _reread
    path = _pcf(tmp_path)
    old = {"unit_scale": None, "joint_max": 1.6e-3, "ignore_types": None}
    assert _reread([str(path)], old).snap_tolerance == TOL_FLOOR


@pytest.mark.parametrize("bad", [0.0, -1e-3, float("nan"), "2mm"])
def test_read_pcf_rejects_a_bad_one(tmp_path, bad):
    with pytest.raises(ReaderError) as e:
        ix.read_pcf(_pcf(tmp_path), snap_tolerance=bad)
    assert e.value.code == "size_not_positive" and e.value.where == {"field": "snap_tolerance"}


def test_merge_takes_the_larger():
    a, b = _tubes(snap=1e-4), ix.NetworkModel(snap_tolerance=TOL_FLOOR)
    b.snap_source = "pcf"
    part = b.add_part(ix.Straight, [(1, 1, 0), (2, 1, 0)], id="x", system="other")
    m = ix.NetworkModel.merge(a, b, prefix="b_")
    assert (m.snap_tolerance, m.snap_source) == (TOL_FLOOR, "pcf")
    m = ix.NetworkModel.merge(b, a, prefix="a_")
    assert (m.snap_tolerance, m.snap_source) == (TOL_FLOOR, "pcf")


def test_describe_shows_it():
    from hexmesh.agent import describe
    d = describe(_tubes(snap=1e-4))
    assert d["snap_tolerance"] == {"value": 1e-4, "source": "default"}
