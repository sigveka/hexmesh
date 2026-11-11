"""
Twisted straights, ``Straight(twist=…)``, and junctions placed with
``toward=`` between the period's rolls (task 0062, decision 0031 stage 3).
Conformance is covered by the kit (tests/test_fitting_conformance.py).
"""

import math
import re
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Tee, Wye
from hexmesh.assembly.interface import Frame
from hexmesh.assembly.section_quality import section_quality, twist_quality
from hexmesh.core.spec import PipeSpec

R = 0.1


def _spec(nrad=3):
    return PipeSpec(nang=8).core("fluid", radius=R, nrad=nrad)


def _asm(spec=None):
    return Assembly(spec or _spec(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)


def _validated(*fittings):
    """Add *fittings* in a row and validate; (assembly, warning messages)."""
    asm = _asm()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for f in fittings:
            asm.add(f)
        asm.validate()
    return asm, [str(w.message) for w in caught]


# -- geometry --------------------------------------------------------------------

def test_untwisted_path_is_unchanged():
    a = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    b = Frame(np.array([0.5, 0, 0]), a.normal, a.up)
    path = Straight(0.5, n_layers=6).path(a, b, _spec())
    assert len(path.frames) == 2 and path.layers == [6] and not path.twisted


@pytest.mark.parametrize("twist", [37.0, -90.0, 400.0])
def test_outlet_up_is_rolled_by_the_twist(twist):
    asm = _asm()
    out = asm.add(Straight(0.6, n_layers=30, twist=twist))
    t = math.radians(twist)
    np.testing.assert_allclose(out.frame.up, [0, -math.sin(t), math.cos(t)], atol=1e-12)
    np.testing.assert_allclose(out.frame.position, [0.6, 0, 0], atol=1e-12)


def test_stations_roll_linearly_with_distance():
    """A graded run: each station rolled by twist × its axial fraction."""
    s = Straight(0.6, n_layers=8, twist=80, axial_grading=1.2)
    a = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    path = s.path(a, s.ports(a, _spec())[0][0], _spec())
    assert path.twisted and path.layers == [1] * 8
    for f in path.frames:
        roll = math.degrees(math.atan2(-f.up[1], f.up[2]))
        assert roll == pytest.approx(80 * f.position[0] / 0.6, abs=1e-9)


def test_twisted_straight_meshes_on_its_prediction(gmsh_session):
    """All hex, the predicted cell count; wall nodes on the cylinder; the
    meshed SJ and non-orthogonality equal ``twist_quality``'s."""
    from hexmesh.quality_hex import max_non_orthogonality, min_scaled_jacobians
    asm = _asm()
    asm.add(Straight(0.3, n_layers=4, twist=45))
    asm.mesh()
    types, tags, nodes = gmsh.model.mesh.getElements(3)
    assert [int(t) for t in types] == [5] and len(tags[0]) == asm.cell_count()
    ntag, x, _ = gmsh.model.mesh.getNodes()
    x = x.reshape(-1, 3)
    r = np.hypot(x[:, 1], x[:, 2])
    assert np.abs(r[r > 0.999 * R] - R).max() < 1e-12
    pos = np.full(int(ntag.max()) + 1, -1)
    pos[ntag.astype(int)] = np.arange(len(ntag))
    c = pos[nodes[0].reshape(-1, 8).astype(int)]
    sj, nonorth, _ = twist_quality(_spec(), 45 / 4, 0.3 / 4)
    assert min_scaled_jacobians(x[c]).min() == pytest.approx(sj, abs=1e-9)
    assert max_non_orthogonality(x[c], c) == pytest.approx(nonorth, abs=1e-6)


def test_the_shear_sets_the_quality_not_the_layer_count():
    """SJ and non-orthogonality follow atan(R dθ / dz) alone; face warp
    follows dθ."""
    a = twist_quality(_spec(), 5.0, 0.25 * R)
    b = twist_quality(_spec(), 20.0, 1.0 * R)
    assert a[0] == pytest.approx(b[0], abs=1e-3) and a[1] == pytest.approx(b[1], abs=0.5)
    assert b[2] > 3 * a[2]
    flat = twist_quality(_spec(), 0.0, R)
    own = section_quality(_spec())
    assert flat[0] == pytest.approx(min(q.min_sj for q in own), abs=1e-9)
    assert flat[2] < 1e-4


# -- limits ----------------------------------------------------------------------

def test_roll_per_layer_rejected_naming_the_layers():
    with pytest.raises(AssemblyError) as e:
        _validated(Straight(0.6, n_layers=2, twist=90))
    assert e.value.code == "twist_per_layer_above_maximum"
    assert e.value.limit == "STRAIGHT_TWIST_MAX" and e.value.hint == "n_layers >= 3"
    assert not gmsh.isInitialized()


def test_roll_per_layer_warns_naming_the_layers():
    _, msgs = _validated(Straight(0.6, n_layers=4, twist=90))
    assert any("rolls one axial layer by 22.5°, above STRAIGHT_TWIST_WARN 15°" in m
               and "n_layers >= 6 reaches it" in m for m in msgs)
    _, msgs = _validated(Straight(0.6, n_layers=6, twist=90))
    assert not msgs


def test_n_layers_none_resolves_to_the_warning_tier():
    asm = Assembly(_spec(), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05, axial_cell=0.2)
    asm.add(Straight(0.6, twist=100))
    assert asm.edges[0].fitting.n_layers == 7         # 3 from axial_cell; 100/7 ≤ 15°


@pytest.mark.parametrize("length, code", [(0.02, "predicted_sj_below_minimum"),
                                          (0.05, "predicted_nonorth_above_maximum")])
def test_wall_shear_rejected_naming_length_or_twist(length, code):
    """The shear is the twist per length: more layers don't help, and the
    hint's length or twist passes the error tiers."""
    with pytest.raises(AssemblyError) as e:
        _validated(Straight(length, n_layers=20, twist=180))
    assert e.value.code == code and "n_layers doesn't change it" in e.value.hint
    with pytest.raises(AssemblyError):
        _validated(Straight(length, n_layers=60, twist=180))
    m = re.match(r"length >= ([\d.]+) or \|twist\| <= ([\d.]+)°", e.value.hint)
    _validated(Straight(float(m.group(1)), n_layers=20, twist=180))
    _validated(Straight(length, n_layers=20, twist=float(m.group(2))))


def test_wall_shear_warns():
    _, msgs = _validated(Straight(0.1, n_layers=20, twist=180))
    assert any("above OUTLINE_NONORTH_WARN 70°: the twist shears the wall cells" in m
               for m in msgs)


# -- toward= between the rolls -----------------------------------------------------

def _toward(deg):
    """37° etc. from the inlet's up (+z) toward its right (−y)."""
    a = math.radians(deg)
    return (0.0, -math.sin(a), math.cos(a))


def test_toward_at_37_degrees_twists_the_straight_before():
    asm = _asm()
    asm.add(Straight(0.4, n_layers=4))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")              # r/R 0.5 warns
        _, branch = asm.add(Tee(run_length=0.2, branch_length=0.3, branch_radius=0.5 * R,
                                toward=_toward(37)), names=["main", "branch"])
    assert asm.edges[0].fitting.twist == pytest.approx(37, abs=1e-9)
    assert asm.edges[1].fitting.roll == 0 and asm.edges[1].fitting.toward is None
    np.testing.assert_allclose(branch.frame.normal, _toward(37), atol=1e-9)
    d = asm.to_dict()
    assert d["edges"][0]["fitting"]["twist"] == pytest.approx(37, abs=1e-9)


def test_toward_on_a_wye_twists_the_straight_before():
    asm = _asm()
    asm.add(Straight(0.4, n_layers=4))
    left, right = asm.add(Wye(60, 0.3, 0.3, toward=_toward(100)))
    assert asm.edges[0].fitting.twist == pytest.approx(10, abs=1e-9)
    assert asm.edges[1].fitting.roll % 90 == 0


def test_toward_within_tolerance_still_snaps():
    asm = _asm()
    asm.add(Straight(0.4, n_layers=4))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm.add(Tee(run_length=0.2, branch_length=0.3, branch_radius=0.5 * R,
                    toward=_toward(90.5)))
    assert asm.edges[0].fitting.twist == 0 and asm.edges[1].fitting.roll == 90


TOWARD_HINT = (r"add Straight\(([\d.e-]+), n_layers=(\d+)\) before the Tee; hexmesh "
               r"twists it by 37° to reach toward")


@pytest.mark.parametrize("before, code, hint", [
    (None, "toward_off_allowed", TOWARD_HINT),
    (Straight(0.4, n_layers=4, twist=10), "toward_off_allowed", TOWARD_HINT),
    (Straight(0.4, n_layers=1), "twist_per_layer_above_maximum", re.escape("n_layers >= 2")),
])
def test_toward_without_a_straight_to_twist_is_rejected(before, code, hint):
    asm = _asm()
    if before is not None:
        asm.add(before)
    with pytest.raises(AssemblyError) as e:
        asm.add(Tee(run_length=0.2, branch_length=0.3, branch_radius=0.5 * R,
                    toward=_toward(37 + (before.twist if before else 0))))
    assert e.value.code == code and re.fullmatch(hint, e.value.hint)
    assert len(asm.edges) == (before is not None)
    if before is not None:
        assert asm.edges[0].fitting == before          # untouched


@pytest.mark.parametrize("deg", [1.3, 37])
def test_the_hints_straight_takes_the_roll(deg):
    """Task 0129: the hint's Straight(L, n_layers=n), added as it says,
    builds the tee with no twist warning; L is at least the outer radius
    and each layer rolls at most STRAIGHT_TWIST_WARN."""
    from hexmesh.assembly import limits
    with pytest.raises(AssemblyError) as e:
        _asm().add(Tee(run_length=0.2, branch_length=0.3, branch_radius=0.5 * R,
                       toward=_toward(deg)))
    L, n = re.match(r"add Straight\(([\d.e-]+), n_layers=(\d+)\)", e.value.hint).groups()
    assert f"twists it by {deg:g}°" in e.value.hint
    L, n = float(L), int(n)
    assert L >= R and deg / n <= limits.STRAIGHT_TWIST_WARN
    asm = _asm()
    asm.add(Straight(L, n_layers=n))
    with warnings.catch_warnings(record=True) as ws:
        warnings.simplefilter("always")
        asm.add(Tee(run_length=0.2, branch_length=0.3, branch_radius=0.5 * R,
                    toward=_toward(deg)))
        asm.validate()
    assert asm.edges[0].fitting.twist == pytest.approx(deg, abs=1e-9)
    twist_warnings = [w for w in ws if "twist" in str(w.message)]
    assert twist_warnings == []


def test_refined_keeps_the_twist():
    asm = _asm()
    asm.add(Straight(0.6, n_layers=6, twist=90))
    fine = asm.refined(2)
    s = fine.edges[0].fitting
    assert s.twist == 90 and s.n_layers == 12
