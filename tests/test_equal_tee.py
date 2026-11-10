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
"""
Equal tees and equal laterals (decision 0043 amendment 2026-11-10; task
0122): ``Tee`` with the branch as wide as the main delegates to the
oriented junction cube (``hexmesh.assembly.cube``).
"""

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import Assembly, AssemblyError, Straight, Tee
from hexmesh.assembly import cube
from hexmesh.assembly.limits import EQUAL_LATERAL_ANGLE_MIN, EQUAL_TEE_RTOL, PREDICTED_SJ_WARN
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.spec import PipeSpec
from hexmesh.quality_hex import min_scaled_jacobians

R = 0.1


def _spec(shell=False):
    s = PipeSpec(nang=8).core("fluid", radius=R, nrad=3)
    return s.shell("steel", dR=0.1 * R, nrad=2) if shell else s


def _asm(shell=False, **kw):
    asm = Assembly(_spec(shell), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.2, n_layers=2))
    kw.setdefault("branch_length", 0.7)
    main, branch = asm.add(Tee(branch_radius=R, **kw), names=["main", "branch"])
    return asm, main, branch


def _tee(asm):
    return next(e for e in asm.edges if type(e.fitting).__name__ == "Tee")


def test_an_equal_tee_routes_to_the_cube_and_validates_without_gmsh():
    asm, main, branch = _asm()
    e = _tee(asm)
    assert e.fitting._is_equal(asm.inlet.spec)
    asm.validate()
    assert not asm.warnings
    lay = e.fitting.layout([p.frame for p in e.ports], e.ports[0].spec)
    # the centre hex, three wall sides, three ports of five blocks, three runs of five
    assert lay.validate()["blocks"] == 1 + 3 + 3 * 5 + 3 * 5
    assert not gmsh.isInitialized()


def test_the_ports_are_class_0_and_equal_to_the_inlet():
    asm, main, branch = _asm(shell=True)
    sig = signature(asm.inlet.spec)
    for port in (main, branch):
        assert classify(sig, signature(port.spec)).cls == 0
        assert port.spec.to_dict() == asm.inlet.spec.to_dict()


def test_a_branch_within_the_tolerance_is_taken_as_the_mains():
    asm = Assembly(_spec(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Tee(branch_length=0.7, branch_radius=R * (1 + 0.5 * EQUAL_TEE_RTOL)))
    assert _tee(asm).fitting.branch_radius == R


def test_run_length_resolves_past_the_stations():
    asm, _, _ = _asm()
    f = _tee(asm).fitting
    run, branch = cube.CubeTee(f).run_needed(asm.inlet.spec)
    assert f.run_length > run and 0.7 > branch


@pytest.mark.parametrize("kw, code, field", [
    (dict(run_length=0.12), "run_length_too_short", "run_length"),
    (dict(branch_length=0.08), "branch_length_too_short", "branch_length"),
    (dict(angle=EQUAL_LATERAL_ANGLE_MIN - 5), "equal_lateral_angle_below_min", "angle"),
    (dict(offset=0.01), "tee_offset_out_of_range", "offset"),
])
def test_rejected_before_gmsh_with_a_code(kw, code, field):
    with pytest.raises(AssemblyError) as e:
        _asm(**kw)[0].validate()
    assert e.value.code == code and e.value.where["field"] == field
    assert not gmsh.isInitialized()


@pytest.mark.parametrize("angle", [89.0, 60.0, 45.0])
def test_an_equal_lateral_is_rejected_naming_the_reduced_branch(angle):
    """Square only (``EQUAL_LATERAL_ANGLE_MIN``): an equal lateral's
    quality falls as nang rises (task 0122)."""
    with pytest.raises(AssemblyError) as e:
        _asm(angle=angle)[0].validate()
    assert e.value.code == "equal_lateral_angle_below_min"
    assert "reduced branch" in e.value.hint and "TEE_MAX_RATIO" in e.value.hint


def test_second_order_is_rejected_before_meshing():
    asm, main, branch = _asm()
    with Session("equal-tee-o2"):
        with pytest.raises(AssemblyError) as e:
            asm.mesh(order=2)
        assert e.value.code == "second_order_unsupported"
        assert not gmsh.model.mesh.getNodes()[0].size


def test_the_layout_cache_hands_out_copies():
    asm, _, _ = _asm()
    e = _tee(asm)
    frames, spec = [p.frame for p in e.ports], e.ports[0].spec
    a = e.fitting.layout(frames, spec)
    a.coords.clear()
    assert e.fitting.layout(frames, spec).coords


def test_the_meshed_sj_hint_is_the_equal_tees():
    asm, _, _ = _asm()
    f, spec = _tee(asm).fitting, asm.inlet.spec
    assert f.meshed_sj_check(spec) and "TEE_MAX_RATIO" in f.meshed_sj_hint(spec)


def test_at_90_degrees_the_cube_is_square_to_every_pipe():
    asm, _, _ = _asm()
    e = _tee(asm)
    E, sides, align = cube.CubeTee(e.fitting).cube(e.ports[0].frame)
    np.testing.assert_allclose(np.abs(E), np.eye(3), atol=1e-12)
    assert min(align.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("shell", [False, True])
def test_the_equal_tee_meshes_at_90_degrees(shell):
    """The task's acceptance at nang 8: corner SJ ≥ ``PREDICTED_SJ_WARN``,
    nothing inverted, the cell count exact, walls projected."""
    asm, main, branch = _asm(shell=shell)
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    with Session("equal-tee"):
        asm.mesh()
        e = _tee(asm)
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        conn = np.vstack([n.reshape(-1, 8) for v in asm._fitting_volumes[e.index]
                          for t, _, n in zip(*gmsh.model.mesh.getElements(3, v)) if t == 5])
        sj = min_scaled_jacobians(nx.reshape(-1, 3)[pos[conn.astype(int)]])
        types, tags, _ = gmsh.model.mesh.getElements(3)
        n_hex = sum(len(t) for ty, t in zip(types, tags) if ty == 5)
        assert sj.min() >= PREDICTED_SJ_WARN
        assert (sj > 0).all()
        assert n_hex == asm.cell_count()
        assert asm.projection_report[e.name]["move"] > 0
