"""
Reducer / expander (docs/tasks/0013).

A reducer changes radii and radial grading only.  Its stations interpolate
the radii (linearly) and the grading (geometrically, decision 0016), and its
corners are joined by cone generators, so wall nodes lie on the cone.
"""

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Reducer, Straight
from hexmesh.assembly.interface import outer_radius
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(radius=0.1, dR=0.02, n_radial=3, n_arc=4, rot=0.0, name="wall"):
    return (PipeSpec(n_arc=n_arc, rot=rot)
            .core("fluid", shape=CircleShape(radius=radius, n_arc=n_arc), n_radial=n_radial)
            .shell(name, dR=dR, n_radial=2))


@pytest.mark.parametrize("r_out", [0.06, 0.15], ids=["reducer", "expander"])
def test_wall_nodes_on_cone(gmsh_session, r_out):
    a, b, L = _spec(), _spec(r_out, 0.015), 0.2
    asm = Assembly(a, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Reducer(b, length=L, n_layers=4))
    asm.mesh()
    R0, R1 = outer_radius(a), outer_radius(b)
    nodes = []
    for w in asm._fill.walls:
        _, x, _ = gmsh.model.mesh.getNodes(2, w, includeBoundary=True)
        nodes.append(x.reshape(-1, 3))
    x = np.vstack(nodes)
    expected = R0 + (R1 - R0) * x[:, 0] / L          # axis along +x from the origin
    np.testing.assert_allclose(np.hypot(x[:, 1], x[:, 2]), expected, atol=1e-12)


@pytest.mark.parametrize("outlet, field", [
    (_spec(0.06, n_radial=4), "core n_radial"),
    (_spec(0.06, n_arc=6), "n_arc"),
    (_spec(0.06, rot=0.1), "rot"),
    (_spec(0.06, name="steel"), "shells"),
    (PipeSpec(n_arc=4).core("fluid", shape=CircleShape(radius=0.06, n_arc=4), n_radial=3), "shells"),
])
def test_topology_change_rejected_before_gmsh(outlet, field):
    asm = Assembly(_spec())
    asm.add(Reducer(outlet, length=0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=f"differs from the inlet in {field}"):
        asm.validate()
    assert not gmsh.isInitialized()


def test_outlet_port_carries_outlet_spec():
    asm = Assembly(_spec())
    out = asm.add(Reducer(_spec(0.06, 0.015), length=0.2, n_layers=3))
    nxt = asm.add(Straight(0.1, n_layers=2))
    asm.validate()
    assert outer_radius(out.spec) == pytest.approx(0.075)
    assert outer_radius(nxt.spec) == pytest.approx(0.075)
    assert asm.cell_count() == (16 + 4 * 4 * 5) * (3 + 2)


# --- grading-only changes (decision 0016, task 0027) -------------------------

def _wall_resolved(radius, first_cell=1e-3):
    """Same absolute first cell at the wall: the solved radial_grading depends on R."""
    return (PipeSpec(n_arc=8).core("fluid", radius=radius, n_radial=8, first_cell=first_cell)
            .shell("wall", dR=0.01, n_radial=3))


def test_wall_resolved_reducer(gmsh_session):
    """The use case: pipe(0.1) → pipe(0.06), same absolute first_cell and n_radial."""
    a, b = _wall_resolved(0.1), _wall_resolved(0.06)
    assert a._core_radial_grading != b._core_radial_grading                       # really a grading change
    asm = Assembly(a, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=4))
    asm.add(Reducer(b, length=0.2, n_layers=6))
    asm.add(Straight(0.2, n_layers=4))
    asm.validate()
    asm.mesh()
    _, tags, _ = gmsh.model.mesh.getElements(3)
    assert sum(len(t) for t in tags) == asm.cell_count()
    types, _, _ = gmsh.model.mesh.getElements(3)
    assert list(types) == [5]                                  # all hex
    report = asm.check_quality()
    assert report.ok, str(report)


@pytest.mark.parametrize("u_grading", [1.0, 1.4])
def test_grading_interpolated_per_station(u_grading):
    """radial_grading_k = radial_grading_in^(1-u) · radial_grading_out^u at the radii's fractions u."""
    from hexmesh.assembly.interface import Frame
    a = PipeSpec(n_arc=4).core("fluid", radius=0.1, n_radial=3, radial_grading=1.0).shell("wall", dR=0.02, n_radial=2, radial_grading=1.3)
    b = PipeSpec(n_arc=4).core("fluid", radius=0.06, n_radial=3, radial_grading=1.5).shell("wall", dR=0.02, n_radial=2, radial_grading=0.8)
    red = Reducer(b, length=0.2, n_layers=5, axial_grading=u_grading)
    fa = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
    fb = red.ports(fa, a)[0][0]
    path = red.path(fa, fb, a)
    u = red.fractions(5)
    for k in range(6):
        spec = path.spec_at(k, a)
        want = [1.0 ** (1 - u[k]) * 1.5 ** u[k], 1.3 ** (1 - u[k]) * 0.8 ** u[k]]
        got = [spec._core_radial_grading, spec.shells[0].radial_grading]
        np.testing.assert_allclose(got, want, rtol=1e-14)
        np.testing.assert_allclose(spec.core_shape.radius, 0.1 + (0.06 - 0.1) * u[k], rtol=1e-14)


def test_grading_change_rejects_arc_bump():
    """Angular grading stays a class-2 count/grading change without a bridge."""
    a = _spec()
    b = (PipeSpec(n_arc=4, arc_bump=0.6).core("fluid", shape=CircleShape(radius=0.06, n_arc=4), n_radial=3)
         .shell("wall", dR=0.02, n_radial=2))
    asm = Assembly(a)
    asm.add(Reducer(b, length=0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=r"arc_bump.*switch class 2 beyond radial grading"):
        asm.validate()


# ---------------------------------------------------------------------------
# Profiles (decision 0008, task 0031)
# ---------------------------------------------------------------------------

from hexmesh import Profile                              # noqa: E402
from hexmesh.assembly.profile import RadiusProfile      # noqa: E402

COSINE = Profile.cosine(0.25)
VENTURI = Profile.venturi(0.5, 15)
POINTS = ((0, 1), (0.3, 0.8), (0.6, 0.7), (1, 0.6))
TABLE = Profile.table(POINTS)


def _core(radius=0.1, n_arc=6):
    return PipeSpec(n_arc=n_arc).core("fluid", radius=radius, n_radial=3)


def _profiled(profile, outlet=None, length=0.4, n=40, spec=None, **kw):
    spec = spec or _core()
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Reducer(outlet or spec, length=length, n_layers=n, profile=profile, **kw))
    return asm


@pytest.mark.parametrize("profile, outlet, length, n", [
    (COSINE, None, 0.4, 40),
    (VENTURI, None, 0.8, 12),
    (TABLE, _core(0.06), 0.4, 16),
], ids=["cosine", "venturi", "table"])
def test_station_wall_nodes_on_profile(gmsh_session, profile, outlet, length, n):
    """Every wall node is at a station, exactly on R(s)."""
    asm = _profiled(profile, outlet, length, n)
    asm.mesh()
    x = np.vstack([gmsh.model.mesh.getNodes(2, t, includeBoundary=True)[1].reshape(-1, 3)
                   for t in asm._fill.walls])
    prof = RadiusProfile(profile, length, 0.1)
    r = np.hypot(x[:, 1], x[:, 2])
    np.testing.assert_allclose(r, 0.1 * prof(x[:, 0] / length), rtol=0, atol=1e-9 * 0.1)


def test_cosine_shape():
    prof = RadiusProfile(COSINE, 0.4, 0.1)
    np.testing.assert_allclose(prof([0, 0.5, 1]), [1, 0.5, 1], atol=1e-15)


@pytest.mark.parametrize("s0", [-1.0, -0.5, -0.1, 0.0])
def test_bulge_wall_nodes_on_profile(gmsh_session, s0):
    """s0 ≤ 0 (task 0055): a bulge to (1 − 2·s0)·R, or a plain pipe; every
    wall node at a station is on R(s), as for a constriction."""
    profile = Profile.cosine(s0)
    asm = _profiled(profile, n=72)
    asm.mesh()
    x = np.vstack([gmsh.model.mesh.getNodes(2, t, includeBoundary=True)[1].reshape(-1, 3)
                   for t in asm._fill.walls])
    prof = RadiusProfile(profile, 0.4, 0.1)
    r = np.hypot(x[:, 1], x[:, 2])
    np.testing.assert_allclose(r, 0.1 * prof(x[:, 0] / 0.4), rtol=0, atol=1e-9 * 0.1)
    assert r.max() == pytest.approx(0.1 * (1 - 2 * s0), rel=1e-9)


def test_bulge_shape_and_layers():
    np.testing.assert_allclose(RadiusProfile(Profile.cosine(-0.5), 0.4, 0.1)([0, 0.25, 0.5, 1]),
                               [1, 1.5, 2, 1], atol=1e-15)
    with pytest.raises(AssemblyError, match=r"use n_layers >= 50"):
        _profiled(Profile.cosine(-0.5), n=40).validate()
    _profiled(Profile.cosine(-0.5), n=50).validate()
    _profiled(Profile.cosine(0.0), n=1).validate()        # a plain pipe: one layer will do


def test_too_coarse_names_layers():
    with pytest.raises(AssemblyError, match=r"use n_layers >= 36"):
        _profiled(COSINE, n=12).validate()
    _profiled(COSINE, n=36).validate()
    _profiled(COSINE, n=12, chord_tol=0.02).validate()
    assert not gmsh.isInitialized()


def test_venturi_corners_on_stations():
    prof = RadiusProfile(VENTURI, 0.8, 0.1)
    u = prof.stations(np.linspace(0, 1, 13))
    for kink in prof.kinks:
        assert np.isclose(u, kink, atol=1e-15).any()
    assert prof.chord_gaps(u).max() < 1e-15
    # the throat is a cylinder of length d = 2·beta·R
    assert prof.kinks[1] - prof.kinks[0] == pytest.approx(0.1 / 0.8)


def test_table_is_monotone_between_points():
    """PCHIP: no overshoot past the data on a monotone run."""
    prof = RadiusProfile(TABLE, 0.4, 0.1)
    r = prof(np.linspace(0, 1, 2001))
    assert np.all(np.diff(r) <= 1e-15)
    np.testing.assert_allclose(prof([s for s, _ in POINTS]), [v for _, v in POINTS], atol=1e-15)


@pytest.mark.parametrize("kw, message", [
    (dict(profile=COSINE, outlet=_core(0.06)), "the outlet spec has"),
    (dict(profile=TABLE), "the outlet spec has"),
    (dict(profile=Profile.table([(0, 0.9), (1, 1)])), "the inlet spec has"),
    (dict(profile=VENTURI, length=0.5), r"needs length >= 0\.7"),
])
def test_profile_rejected(kw, message):
    with pytest.raises(AssemblyError, match=message):
        _profiled(**kw).validate()


@pytest.mark.parametrize("make, code, message", [
    (lambda: Profile.venturi(0.5, 20), "profile_parameter_out_of_range", "7°–15°"),
    (lambda: Profile.venturi(1.0), "profile_parameter_out_of_range", r"beta must be in \(0, 1\)"),
    (lambda: Profile.cosine(0.5), "profile_parameter_out_of_range",
     r"s0 must be in \[-1, 0\.5\), got 0\.5: -1 is a bulge to 3·R \(COSINE_S0_MIN\), 0\.5 a "
     r"throat of zero radius"),
    (lambda: Profile.cosine(-1.01), "profile_parameter_out_of_range",
     r"s0 must be in \[-1, 0\.5\), got -1\.01"),
    (lambda: Profile("parabola", a=1), "profile_unknown", "unknown profile kind 'parabola'"),
    (lambda: Profile("cosine", beta=0.5), "profile_fields_invalid", "a cosine profile takes s0"),
    (lambda: Profile.table([(0, 1), (0.5, 1), (0.4, 1), (1, 1)]), "profile_table_invalid",
     "increase from 0 to 1"),
    (lambda: Profile.table([(0, 1)]), "profile_table_invalid", "at least two"),
], ids=["divergent", "beta", "s0_max", "s0_min", "kind", "fields", "table_order", "table_short"])
def test_profile_constructors_check_parameters(make, code, message):
    """Decision 0053: the checks the tuples had, now at construction."""
    with pytest.raises(AssemblyError, match=message) as e:
        make()
    assert e.value.code == code


@pytest.mark.parametrize("old, hint", [
    (("cosine", 0.25), "profile=Profile.cosine(0.25)"),
    (("venturi", 0.5, 15), "profile=Profile.venturi(0.5, 15)"),
    (((0, 1), (1, 0.6)), "profile=Profile.table([(s, r), …])"),
])
def test_a_tuple_profile_is_a_coded_error_with_the_call(old, hint):
    with pytest.raises(AssemblyError, match="must be a Profile") as e:
        Reducer(_core(), length=0.4, profile=old)
    assert e.value.code == "profile_type_invalid" and e.value.hint == hint
    assert isinstance(e.value, TypeError)


def test_profile_is_a_value():
    assert Profile.cosine(0.25) == Profile.cosine(0.25) != Profile.cosine(0.3)
    assert len({Profile.cosine(0.25), Profile.cosine(0.25), VENTURI}) == 2
    assert (COSINE.kind, COSINE.s0) == ("cosine", 0.25)
    assert (VENTURI.beta, VENTURI.divergent) == (0.5, 15.0)
    assert Profile.venturi(0.5).divergent == 15.0
    assert repr(COSINE) == "Profile.cosine(s0=0.25)"
    with pytest.raises(AttributeError):
        COSINE.s0 = 0.3
    for p in (COSINE, VENTURI, TABLE):
        assert Profile.from_dict(p.to_dict()) == p
    assert TABLE.to_dict() == {"kind": "table", "points": [list(map(float, q)) for q in POINTS]}


def test_profile_scales_every_layer(gmsh_session):
    """A two-layer stack: the shell thickness scales with the profile too."""
    spec = _spec(0.1, 0.02)
    asm = _profiled(TABLE, _spec(0.06, 0.012), n=16, spec=spec)
    asm.mesh()
    e = asm.edges[0]
    path = e.fitting.path(*[p.frame for p in e.ports], spec)
    prof = RadiusProfile(TABLE, 0.4, 0.1)
    for k, f in enumerate(path.frames):
        s = path.spec_at(k, spec)
        ratio = float(prof(f.position[0] / 0.4))
        assert s.core_shape.radius == pytest.approx(0.1 * ratio, rel=1e-12)
        assert s.shells[0].dR == pytest.approx(0.02 * ratio, rel=1e-12)


@pytest.mark.parametrize("profile, outlet, length, n", [
    (COSINE, None, 0.4, 40), (VENTURI, None, 0.8, 12), (TABLE, _core(0.06), 0.4, 16),
], ids=["cosine", "venturi", "table"])
def test_profile_save_load(tmp_path, profile, outlet, length, n):
    asm = _profiled(profile, outlet, length, n)
    path = tmp_path / "p.json"
    asm.save(path)
    again = Assembly.load(path)
    assert again.to_dict() == asm.to_dict()
    assert again.edges[0].fitting.profile == profile
    assert again.cell_count() == asm.cell_count()


def _connectivity(asm):
    asm.mesh()
    hexes = np.concatenate(gmsh.model.mesh.getElements(3)[2])
    return gmsh.model.mesh.getNodes()[0].copy(), hexes


def test_stenosis_variants_aligned(gmsh_session):
    """The stenosis example's fixed counts (task 0055): constriction, plain
    pipe and bulge, short and long, are one cell count and one
    connectivity, so the variants are node-aligned."""
    from hexmesh.examples.fittings import stenosis
    variants = [(s0, L) for s0 in (-1.0, 0.0, 0.25) for L in (1.0, 4.0)]
    for s0, L in variants:
        stenosis.build(s0, L).validate()
    assert len({stenosis.build(s0, L).cell_count() for s0, L in variants}) == 1
    a = _connectivity(stenosis.build(-1.0, 1.0))
    gmsh.clear()
    b = _connectivity(stenosis.build(0.25, 4.0))
    for x, y in zip(a, b):
        np.testing.assert_array_equal(x, y)
