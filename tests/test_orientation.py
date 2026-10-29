"""
Named ports, absolute orientation and angle units (task 0040, decision 0024).

* ``add(…, names=…)`` takes a list in port order or a dict keyed by port name.
* ``toward=`` on bends resolves to ``roll`` at ``add()``; only ``roll`` is saved.
* ``Tee`` / ``Wye`` take a ``roll`` that is a multiple of the section's
  period, or a ``toward`` snapped to one; rolled junctions stay conformal.
* ``PipeSpec(rot=…)`` is in degrees; version-1 files (radians) still load.
* A bend angle that looks like radians warns.
"""

import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly import (
    Assembly, AssemblyError, Bend, Elbow, MiterBend, Straight, Tee, Wye,
)
from hexmesh.assembly.interface import Frame, rotate
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _pipe(rot=0.0):
    return PipeSpec(nang=4, rot=rot).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)


def _tee():
    return Tee(run_length=0.2, branch_length=0.25, branch_radius=0.06)


def _wye(**kw):
    return Wye(60, run_length=0.25, branch_length=0.4, **kw)


# ---------------------------------------------------------------------------
# Port names
# ---------------------------------------------------------------------------

def test_port_names_declared():
    assert Tee.port_names == ("main", "branch")
    assert Wye.port_names == ("left", "right")
    assert Straight.port_names == ("outlet",)


@pytest.mark.parametrize("fitting, as_list, as_dict", [
    (_tee(), ["run", "tap"], {"branch": "tap", "main": "run"}),
    (_wye(), ["l", "r"], {"right": "r", "left": "l"}),
    (Straight(0.2, n_layers=2), ["end"], {"outlet": "end"}),
])
def test_dict_and_list_names_agree(fitting, as_list, as_dict):
    dicts = []
    for names in (as_list, as_dict):
        a = Assembly(_pipe())
        a.add(Straight(0.2, n_layers=2))
        a.add(fitting, names=names)
        dicts.append(a.to_dict())
    assert dicts[0] == dicts[1]


def test_partial_dict_names_only_those():
    a = Assembly(_pipe())
    main, branch = a.add(_tee(), names={"branch": "tap"})
    assert branch.name == "tap" and main.name is None


def test_wrong_port_name_lists_valid_ones():
    a = Assembly(_pipe())
    with pytest.raises(AssemblyError, match="main, branch") as exc:
        a.add(_tee(), names={"side": "tap"})
    assert "'side'" in str(exc.value)


def test_wrong_number_of_names():
    a = Assembly(_pipe())
    with pytest.raises(AssemblyError, match="2 outlet"):
        a.add(_tee(), names=["only"])


def test_tail_continues_on_first_port():
    a = Assembly(_pipe())
    main, _ = a.add(_tee())
    out = a.add(Straight(0.2, n_layers=2))
    assert a.edges[-1].ports[0] is main and out is a.interfaces[-1]


# ---------------------------------------------------------------------------
# toward= on bends
# ---------------------------------------------------------------------------

def _random_frame(rng):
    n = rng.normal(size=3)
    u = rng.normal(size=3)
    return Frame.from_vectors(rng.normal(size=3), n, u)


@pytest.mark.parametrize("make", [
    lambda t: Bend(radius=0.4, angle=70, n_layers=6, toward=t),
    lambda t: Elbow(angle=50, n_layers=6, toward=t),
    lambda t: MiterBend(radius=0.4, angle=60, n_cuts=2, toward=t),
], ids=["Bend", "Elbow", "MiterBend"])
def test_toward_turns_into_the_plane_toward_side(make):
    rng = np.random.default_rng(40)
    for _ in range(25):
        inlet = _random_frame(rng)
        t = rng.normal(size=3)
        a = Assembly(_pipe(), inlet.position, inlet.normal, inlet.up)
        out = a.add(make(tuple(t)))
        n, m = inlet.normal, out.frame.normal
        p = t - np.dot(t, n) * n
        p /= np.linalg.norm(p)
        assert abs(np.dot(m, np.cross(n, p))) < 1e-9       # in the (n, toward) plane
        assert np.dot(m, p) > 0                              # on the toward side
        fitting = a.edges[0].fitting
        assert fitting.toward is None
        d = a.to_dict()["edges"][0]["fitting"]
        assert "toward" not in d and d["roll"] == pytest.approx(fitting.roll)


def test_toward_is_stored_as_roll_and_round_trips():
    a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1])
    a.add(Bend(radius=0.3, angle=90, n_layers=6, toward=(0, 1, 0)))
    roll = a.edges[0].fitting.roll
    # right = normal × up = (0, -1, 0), so +y is roll -90
    assert roll == pytest.approx(-90.0)
    b = Assembly.from_dict(a.to_dict())
    assert b.to_dict() == a.to_dict()
    np.testing.assert_allclose(b.interfaces[1].frame.normal, [0, 1, 0], atol=1e-12)


def test_toward_and_roll_together_rejected():
    a = Assembly(_pipe())
    with pytest.raises(AssemblyError, match="roll or toward, not both"):
        a.add(Bend(radius=0.3, angle=90, n_layers=6, roll=30, toward=(0, 1, 0)))


def test_toward_along_normal_rejected_naming_angle():
    a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1])
    with pytest.raises(AssemblyError, match=r"0\.5\d*° from the inlet normal"):
        a.add(Bend(radius=0.3, angle=90, n_layers=6,
                   toward=(1, math.tan(math.radians(0.5)), 0)))


def test_unresolved_toward_rejected_by_validate():
    with pytest.raises(ValueError, match="resolved by Assembly.add"):
        Bend(radius=0.3, angle=90, n_layers=6, toward=(0, 1, 0)).check(_pipe())


# ---------------------------------------------------------------------------
# Junction roll
# ---------------------------------------------------------------------------

def test_tee_branch_follows_roll():
    for roll, want in ((0, [0, 0, 1]), (90, [0, -1, 0]), (180, [0, 0, -1]),
                       (270, [0, 1, 0]), (-90, [0, 1, 0])):
        a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1])
        main, branch = a.add(Tee(0.2, 0.25, 0.06, roll=roll))
        np.testing.assert_allclose(branch.frame.normal, want, atol=1e-12)
        np.testing.assert_allclose(main.frame.up, [0, 0, 1], atol=1e-12)


def test_roll_off_period_rejected():
    a = Assembly(_pipe())
    a.add(Tee(0.2, 0.25, 0.06, roll=45))
    with pytest.raises(AssemblyError, match="period 90°"):
        a.validate()
    b = Assembly(_pipe())
    with pytest.raises(AssemblyError, match="period 90°"):   # in add(): resolving counts
        b.add(_wye(roll=45))
        b.validate()


def test_junction_toward_snaps_and_rejects():
    a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1])
    _, branch = a.add(Tee(0.2, 0.25, 0.06, toward=(0, 1, 0.01)))   # 0.57° off +y
    assert a.edges[0].fitting.roll == pytest.approx(-90.0)
    np.testing.assert_allclose(branch.frame.normal, [0, 1, 0], atol=1e-12)
    with pytest.raises(AssemblyError, match=r"5\.71° from the nearest"):
        a.add(a.interfaces[1], Tee(0.2, 0.25, 0.06, toward=(0, 0.1, 1)))


def test_wye_toward_names_right_daughter():
    a = Assembly(_pipe(), direction=[1, 0, 0], up=[0, 0, 1])
    left, right = a.add(_wye(toward=(0, 0, 1)))
    assert right.frame.normal[2] > 0.4 and left.frame.normal[2] < -0.4
    assert abs(right.frame.normal[1]) < 1e-12


def _junction_case(kind, roll, after_bend):
    a = Assembly(_pipe(), direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    if after_bend:
        a.add(Bend(radius=0.3, angle=60, n_layers=4, roll=30))
    else:
        a.add(Straight(0.2, n_layers=2))
    j = (Tee(0.2, 0.25, 0.06, roll=roll) if kind == "tee" else _wye(roll=roll))
    for out in a.add(j):
        a.add(out, Straight(0.15, n_layers=2))
    return a


@pytest.mark.parametrize("after_bend", [False, True], ids=["after_straight", "after_bend"])
@pytest.mark.parametrize("roll", [0, 90, 180, 270])
@pytest.mark.parametrize("kind", ["tee", "wye"])
def test_rolled_junction_meshes_conformally(kind, roll, after_bend):
    a = _junction_case(kind, roll, after_bend)
    a.validate()
    j = a.edges[1]
    for p in j.ports[1:]:            # inlet → each outlet: class 0
        assert classify(signature(j.ports[0].spec), signature(p.spec)).cls == 0
    predicted = a.cell_count()
    with Session("roll"):
        a.mesh()
        types, tags, enodes = gmsh.model.mesh.getElements(3)
        assert list(types) == [5]                                 # hexahedra only
        assert sum(len(t) for t in tags) == predicted
        used = np.unique(np.concatenate(enodes))
        ntags, xyz, _ = gmsh.model.mesh.getNodes()
        coords = dict(zip(ntags, xyz.reshape(-1, 3)))
        c = np.round(np.array([coords[t] for t in used]), 9)
        assert len(c) == len(np.unique(c, axis=0)), "coincident hex nodes"
        report = a.check_quality()
        assert report.ok, str(report)


# ---------------------------------------------------------------------------
# rot in degrees
# ---------------------------------------------------------------------------

def _rot_run(spec):
    a = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    a.add(Straight(0.3, n_layers=2))
    a.add(Bend(radius=0.4, angle=90, n_layers=4))
    return a


def _nodes(a):
    with Session("rot"):
        a.mesh()
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        return xyz.reshape(-1, 3)[np.argsort(tags)]


def test_rot_is_degrees():
    assert _pipe(rot=45).rot == 45.0
    assert _pipe(rot=45).rot_rad == pytest.approx(math.pi / 4)


def test_version_1_file_converts_rot():
    d = _rot_run(_pipe(rot=45)).to_dict()
    assert d["version"] == 2 and d["inlet"]["spec"]["rot"] == 45.0
    v1 = dict(d, version=1, inlet=dict(d["inlet"], spec=dict(d["inlet"]["spec"],
                                                             rot=math.pi / 4)))
    loaded = Assembly.from_dict(v1)
    assert loaded.inlet.spec.rot == pytest.approx(45.0, abs=1e-12)
    assert loaded.to_dict()["version"] == 2
    np.testing.assert_allclose(_nodes(loaded), _nodes(_rot_run(_pipe(rot=45))),
                               atol=1e-12, rtol=0)


def test_rot_45_turns_corners():
    """Corner 0 sits at 45° + rot from right: at rot = 45 it points along up."""
    from hexmesh.assembly.corners import corner0_angle
    assert corner0_angle(_pipe(rot=45)) == pytest.approx(math.pi / 2)


# ---------------------------------------------------------------------------
# Radians warning
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fitting", [
    Bend(radius=0.3, angle=1.57, n_layers=2),
    Elbow(angle=1.57, n_layers=2),
    MiterBend(radius=0.3, angle=1.57, n_cuts=1),
], ids=["Bend", "Elbow", "MiterBend"])
def test_radians_like_angle_warns(fitting):
    a = Assembly(_pipe())
    with pytest.warns(UserWarning, match="looks like radians"):
        a.add(fitting)


def test_degrees_angle_does_not_warn():
    a = Assembly(_pipe())
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        a.add(Bend(radius=0.3, angle=15, n_layers=2))
