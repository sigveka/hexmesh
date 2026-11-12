"""
Tee block layout (hexmesh/assembly/tee.py).  Conformance is covered by the
kit (tests/test_fitting_conformance.py); these tests cover the tee itself.
"""

import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Tee
from hexmesh.core.shape import CircleShape, RectShape
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
        (dict(ratio=1.05), "branch radius"),
        (dict(ratio=0.5, run=0.04), "run_length"),
        (dict(ratio=0.5, branch=0.11), "branch_length"),
    ])
    def test_rejected_before_gmsh(self, kw, message):
        asm, _, _ = _tee_asm(**kw)
        with pytest.raises(AssemblyError, match=message):
            asm.validate()
        assert not gmsh.isInitialized()

    @pytest.mark.parametrize("kw, message", [
        # single-layer these fit; shells of 0.04 need more room (task 0052)
        (dict(run=0.07), r"run_length must exceed the branch's outer radius 0\.09"),
        (dict(branch=0.17), r"turning station's height 0\.185"),
    ])
    def test_shells_need_room(self, kw, message):
        spec = _spec().shell("steel", dR=0.01, nrad=2).shell("insulation", dR=0.03, nrad=2)
        for s in (_spec(), spec):
            asm, _, _ = _tee_asm(0.5, spec=s, **kw)
            if s is spec:
                with pytest.raises(AssemblyError, match=message):
                    asm.validate()
            else:
                asm.validate()
        assert not gmsh.isInitialized()

    def test_rectangular_shell_rejected(self):
        spec = _spec().shell("box", outer=RectShape(0.15, 0.15, 4, 4), nrad=2)
        # the branch spec needs circular shells, so it fails in add()
        with pytest.raises((AssemblyError, ValueError), match="circular only.*0026"):
            asm, _, _ = _tee_asm(0.5, spec=spec)
            asm.validate()
        assert not gmsh.isInitialized()


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
    """Every tee wall node within 1e-6 R of the two cylinders (task 0051,
    by node projection: decision 0029)."""
    assert _tee_wall_deviation(8, 0.5) < 1e-6


def test_tee_wall_check_catches_filled_faces(gmsh_session, monkeypatch):
    """Without wall surfaces or projection the faces are plain fillings,
    2–3 % of R off: the check must see it."""
    layout = Tee.layout

    def bare(self, frames, spec):
        lay = layout(self, frames, spec)
        lay.walls = {}
        return lay
    monkeypatch.setattr(Tee, "layout", bare)
    assert _tee_wall_deviation(4, 0.5) > 0.02


# ---------------------------------------------------------------------------
# Shells through the junction (task 0052)
# ---------------------------------------------------------------------------

def _layered_tee(ratio=0.5, nang=4):
    spec = (_spec(nang).shell("steel", dR=0.01, nrad=2)
            .shell("insulation", dR=0.03, nrad=2))
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(run_length=2 * R, branch_length=3 * R,
                               branch_radius=ratio * R), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    return asm


def test_branch_spec_copies_shells():
    from hexmesh.assembly.tee import branch_spec
    spec = _spec().shell("steel", dR=0.01, nrad=2, mprg=1.2).shell("insulation", dR=0.03, nrad=3)
    b = branch_spec(spec, 0.05)
    assert b.layer_names == spec.layer_names
    assert [o.radius for o in b.outlines] == pytest.approx([0.05, 0.06, 0.09])
    assert [(s.nrad, s.mprg) for s in b.shells] == [(2, 1.2), (3, 1.0)]


def test_branch_keeps_the_given_dR_so_a_stack_change_matches(gmsh_session):
    """A shell given by dR keeps it exactly on the branch, so insulation
    can start on the branch line (task 0155: dR rebuilt from the outline
    radii was 0.0015000000000000013, and the stack change was rejected)."""
    from hexmesh.assembly.tee import branch_spec
    main = (PipeSpec(nang=8).core("lox", radius=0.0149, nrad=4)
            .shell("steel", dR=0.0015, nrad=2))
    assert branch_spec(main, 0.01215).shells[0].dR == 0.0015
    asm = Assembly(main, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.05, n_layers=2))
    run, branch = asm.add(Tee(branch_radius=0.01215, branch_length=0.05))
    asm.add(run, Straight(0.05, n_layers=2))
    insulated = (PipeSpec(nang=8).core("lox", radius=0.01215, nrad=4)
                 .shell("steel", dR=0.0015, nrad=2).shell("insulation", dR=0.02, nrad=2))
    asm.add(branch, Straight(0.12, n_layers=8, stack_changes=((2, insulated),)))
    asm.mesh()
    _, _, nodes = gmsh.model.mesh.getElements(3)
    assert sum(len(n) for n in nodes) > 0


@pytest.mark.parametrize("ratio", [0.5, 0.9])
def test_interfaces_continuous_through_tee(gmsh_session, ratio):
    """Each interface group covers all four fittings, main and branch, as one
    edge-connected sheet of quads (task 0052)."""
    asm = _layered_tee(ratio)
    predicted = asm.cell_count()
    asm.mesh()
    types, tags, _ = gmsh.model.mesh.getElements(3)
    assert list(types) == [5] and sum(len(t) for t in tags) == predicted
    owner = {}
    for i, vols in asm.fitting_volumes().items():
        for _, s in gmsh.model.getBoundary([(3, v) for v in vols], combined=False,
                                           oriented=False):
            owner.setdefault(abs(s), set()).add(i)
    groups = {gmsh.model.getPhysicalName(2, t): t for _, t in gmsh.model.getPhysicalGroups(2)}
    names = sorted(n for n in groups if n.startswith("interface_"))
    assert names == ["interface_fluid_steel", "interface_steel_insulation"]
    for name in names:
        surfs = gmsh.model.getEntitiesForPhysicalGroup(2, groups[name])
        assert set().union(*(owner[s] for s in surfs)) == {0, 1, 2, 3}, name
        quads = np.vstack([n.reshape(-1, 4) for s in surfs
                           for t, n in zip(*gmsh.model.mesh.getElements(2, s)[::2]) if t == 3])
        by_edge = {}
        for q, nodes in enumerate(quads):
            for a, b in zip(nodes, np.roll(nodes, -1)):
                by_edge.setdefault(frozenset((a, b)), []).append(q)
        seen, todo = {0}, [0]
        while todo:
            q = todo.pop()
            for a, b in zip(quads[q], np.roll(quads[q], -1)):
                for n in by_edge[frozenset((a, b))]:
                    if n not in seen:
                        seen.add(n)
                        todo.append(n)
        assert len(seen) == len(quads), f"{name}: {len(seen)} of {len(quads)} quads connected"


# ---------------------------------------------------------------------------
# Predicted quality and the default run length (task 0052, Q1)
# ---------------------------------------------------------------------------

def _shelled_tee(ratio, T, run):
    spec = _spec() if T == 0 else _spec().shell("steel", dR=T, nrad=2)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Tee(run, 0.5, ratio * R), names=["main", "branch"])
    return asm


def _hint(message):
    import re
    return float(re.search(r"a run of ([0-9.e-]+) m or more each side of the centre reaches it", message).group(1))


def test_short_run_rejected_with_the_length_that_works():
    asm = _shelled_tee(0.5, 0.02, 0.08)            # steel slab at SJ 0.06
    with pytest.raises(AssemblyError, match=r"Tee.*predicted corner scaled Jacobian "
                       r"0\.060 is below PREDICTED_SJ_MIN 0\.1; a run of .* m or more") as e:
        asm.validate()
    need = _hint(str(e.value))
    assert 0.08 < need < 0.09
    with pytest.warns(UserWarning):                # at the hint: past the hard tier
        _shelled_tee(0.5, 0.02, need).validate()
    assert not gmsh.isInitialized()


def test_warning_names_the_run_that_reaches_it():
    asm = _shelled_tee(0.7, 0.02, 0.095)           # SJ 0.215
    with pytest.warns(UserWarning, match=r"below PREDICTED_SJ_WARN 0\.3; a run of "):
        asm.validate()
    assert len(asm.warnings) == 1 and asm.warnings[0].startswith("fitting #0 Tee(")
    need = _hint(asm.warnings[0])
    ok = _shelled_tee(0.7, 0.02, need)
    ok.validate()
    assert ok.warnings == []


def test_small_branch_warns_at_any_length():
    """r/R below about 0.57 can't reach 0.3: the message blames the ratio."""
    asm = _shelled_tee(0.5, 0.0, 0.5)
    with pytest.warns(UserWarning, match=r"no run length reaches it: the branch ratio r/R 0\.5"):
        asm.validate()


@pytest.mark.parametrize("ratio, T", [(0.25, 0.0), (0.25, 0.05), (0.5, 0.02), (0.9, 0.0), (0.9, 0.05)])
def test_default_run_length(ratio, T):
    """run_length=None resolves on add() to max(r + T + 0.5 R, the shortest
    run reaching PREDICTED_SJ_WARN), and is stored."""
    asm = _shelled_tee(ratio, T, None)
    e = asm.edges[0]
    tee, inlet, spec = e.fitting, e.ports[0].frame, e.ports[0].spec
    need = tee.shortest_run(inlet, spec, 0.3) or 0.0
    assert tee.run_length == pytest.approx(max(ratio * R + T + 0.5 * R, need))
    assert asm.to_dict()["edges"][0]["fitting"]["run_length"] == tee.run_length
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")            # r/R 0.25 and 0.5 warn at any run
        asm.validate()
    # the default nearly reaches the long-run quality (0.493 of 0.509 at r/R 0.9)
    assert tee.predicted_sj(inlet, spec) == pytest.approx(
        tee.predicted_sj(inlet, spec, tee.run_length + R), abs=0.02)


def test_default_run_length_needs_an_assembly():
    tee = Tee(branch_length=0.25, branch_radius=0.05)
    with pytest.raises(ValueError, match="run_length=None is resolved by Assembly.add"):
        tee.check(_spec())
    with pytest.raises(TypeError, match="missing required argument.*branch_radius"):
        Tee(0.2, 0.25)


# -- laterals: Tee(angle=…) (task 0060) --------------------------------------

from hexmesh.assembly.tee import lean, saddle_point, tip_reach, turning_height  # noqa: E402


@pytest.mark.parametrize("angle", [30, 45, 60, 75, 90])
def test_saddle_points_on_both_cylinders(angle):
    """RESEARCH §3.1 with h = 0: every point on the main cylinder and on the
    branch cylinder, whose axis is (cos α, 0, sin α)."""
    ca, sa = lean(angle)
    d = np.array([ca, 0.0, sa])
    for phi in np.linspace(0, 2 * math.pi, 37):
        p = np.array(saddle_point(R, 0.6 * R, ca, sa, phi))
        assert math.hypot(p[1], p[2]) == pytest.approx(R, abs=1e-15)
        assert np.linalg.norm(p - (p @ d) * d) == pytest.approx(0.6 * R, abs=1e-15)
        assert p @ d > 0                         # the branch side of the main axis


def test_lateral_reaches_farther_downstream():
    up, down = tip_reach(R, 0.6 * R, 45)
    assert up < 0.6 * R < down                    # the acute side is downstream
    assert tip_reach(R, 0.6 * R, 90) == (0.6 * R, 0.6 * R)
    assert turning_height(R, 0.6 * R, 0.0, 45) > turning_height(R, 0.6 * R, 0.0)


def test_lateral_branch_port_on_the_analytic_axis():
    """The branch outlet leans by α from the run's downstream direction, in
    the branch plane, also in an oblique assembly; its up is in that plane."""
    direction = np.array([1.0, 1.0, 0.2]) / np.linalg.norm([1.0, 1.0, 0.2])
    asm = Assembly(_spec(), direction=list(direction), up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.2, n_layers=2))
    tee = Tee(run_length=0.3, branch_length=0.5, branch_radius=0.9 * R, angle=45)
    main, branch = asm.add(tee, names=["main", "branch"])
    inlet = asm.edges[1].ports[0].frame
    o = inlet.position + 0.3 * inlet.normal
    d = math.cos(math.radians(45)) * inlet.normal + math.sin(math.radians(45)) * inlet.up
    np.testing.assert_allclose(branch.frame.position, o + 0.5 * d, atol=1e-9)
    np.testing.assert_allclose(branch.frame.normal, d, atol=1e-9)
    assert abs(branch.frame.up @ np.cross(inlet.normal, inlet.up)) < 1e-9
    np.testing.assert_allclose(main.frame.position, o + 0.3 * inlet.normal, atol=1e-9)
    asm.validate()


@pytest.mark.parametrize("kw, code, message", [
    (dict(angle=0), "tee_angle_out_of_range", r"angle 0° must be in \(0, 90\]"),
    (dict(angle=100), "tee_angle_out_of_range", r"angle 100° must be in \(0, 90\]"),
    (dict(angle=45, run=0.2), "run_length_too_short", r"acute-side tip\) 0\.2273"),
    (dict(angle=45, run=0.3, branch=0.2), "branch_length_too_short",
     r"distance along the branch axis 0\.2951 .* at its acute side"),
])
def test_lateral_rejected_before_gmsh(kw, code, message):
    with pytest.raises(AssemblyError, match=message) as e:
        _tee_asm(0.9, **kw)[0].validate()
    assert e.value.code == code
    assert not gmsh.isInitialized()


def test_steep_lateral_rejected_naming_the_angle():
    """30° is below PREDICTED_SJ_MIN at every branch ratio (task 0060)."""
    with pytest.raises(AssemblyError, match=r"no run length reaches it: .* at angle 30°; no "
                       r"ratio up to TEE_MAX_RATIO 0\.95 reaches it there") as e:
        _tee_asm(0.9, angle=30, run=None, branch=0.8)[0].validate()
    assert e.value.code == "predicted_sj_below_minimum"


def test_lateral_hint_names_the_smallest_ratio():
    """45° passes PREDICTED_SJ_MIN from r/R 0.50 (task 0060; meshed SJ =
    predicted there to 1e-3)."""
    with pytest.raises(AssemblyError, match=r"at angle 45°; r/R 0\.50\d or more reaches it "
                       r"there, or a larger angle"):
        _tee_asm(0.3, angle=45, run=None, branch=0.8)[0].validate()
    with pytest.warns(UserWarning, match=r"at angle 45°; no ratio up to TEE_MAX_RATIO"):
        _tee_asm(0.6, angle=45, run=None, branch=0.8)[0].validate()


@pytest.mark.parametrize("ratio, code, hint", [
    (0.96, "tee_ratio_above_max", "an equal tee, or a branch radius <= 0.95 R"),
])
def test_branch_ratio_cut_off(ratio, code, hint):
    with pytest.raises(AssemblyError) as e:
        _tee_asm(ratio)[0].validate()
    assert e.value.code == code and e.value.hint.startswith(hint)
    _tee_asm(0.95)[0].validate()                 # at the cut-off: accepted


def test_duct_tap_rejects_an_offset():
    spec = PipeSpec(nang=4).core("air", RectShape(half_w=0.1, half_h=0.05, nang_w=4, nang_h=2))
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    with pytest.raises(AssemblyError) as e:
        asm.add(Tee(branch_length=0.2, branch=RectShape(half_w=0.02, half_h=0.02, nang_w=4,
                                                        nang_h=2), offset=0.01))
    assert e.value.code == "offset_on_duct_tap"


# -- offset taps: Tee(offset=…) (task 0061) ---------------------------------------

@pytest.mark.parametrize("angle", [45, 90])
@pytest.mark.parametrize("h", [-0.3, 0.2, 0.45])
def test_offset_saddle_points_on_both_cylinders(angle, h):
    """RESEARCH §3.1 with h ≠ 0: every point on the main cylinder and on the
    branch cylinder, whose axis is (cos α, 0, sin α) through (0, h, 0)."""
    ca, sa = lean(angle)
    d, ob = np.array([ca, 0.0, sa]), np.array([0.0, h * R, 0.0])
    for phi in np.linspace(0, 2 * math.pi, 37):
        p = np.array(saddle_point(R, 0.5 * R, ca, sa, phi, h * R))
        assert math.hypot(p[1], p[2]) == pytest.approx(R, abs=1e-15)
        w = p - ob
        assert np.linalg.norm(w - (w @ d) * d) == pytest.approx(0.5 * R, abs=1e-15)
        assert p[2] > 0                          # the branch side of the main axis


def test_offset_lateral_reach_is_even_in_the_offset():
    """An offset moves a lateral's tips (RESEARCH §3.2), the same for ±h; a
    90° tee's hole still reaches r each side."""
    up, down = tip_reach(R, 0.6 * R, 45, 0.3 * R)
    assert (up, down) == pytest.approx(tip_reach(R, 0.6 * R, 45, -0.3 * R), abs=1e-12)
    assert (up, down) != pytest.approx(tip_reach(R, 0.6 * R, 45), abs=1e-6)
    assert tip_reach(R, 0.6 * R, 90, 0.3 * R) == (0.6 * R, 0.6 * R)


@pytest.mark.parametrize("h", [0.3, -0.3])
def test_offset_branch_port_on_the_offset_axis(h):
    """The branch axis is off the main axis by h along the inlet's right
    (normal × up = −y here)."""
    asm, main, branch = _tee_asm(0.5, offset=h * R)
    np.testing.assert_allclose(branch.frame.position, [0.2, -h * R, 0.25], atol=1e-12)
    np.testing.assert_allclose(branch.frame.normal, [0, 0, 1], atol=1e-12)
    np.testing.assert_allclose(main.frame.position, [0.4, 0, 0], atol=1e-12)
    asm.validate()


@pytest.mark.parametrize("ratio, h, limit, hint", [
    (0.5, 0.5, {"max_exclusive": pytest.approx(0.5 * R)}, "|offset| < 0.05, or a smaller branch"),
    (0.3, -0.4, "TEE_MAX_OFFSET_RATIO", "|offset| <= 0.03, or a branch radius >= 0.04"),
])
def test_offset_out_of_range_rejected_before_gmsh(ratio, h, limit, hint):
    """Past the main's wall (|h| + r ≥ R), or past TEE_MAX_OFFSET_RATIO × r,
    where OCC's fills fail erratically (task 0061)."""
    with pytest.raises(AssemblyError) as e:
        _tee_asm(ratio, offset=h * R)[0].validate()
    assert e.value.code == "tee_offset_out_of_range" and e.value.where["field"] == "offset"
    assert e.value.limit == limit and e.value.hint == hint
    assert not gmsh.isInitialized()
    _tee_asm(0.3, offset=-0.3 * R)[0].validate()        # h = r: accepted


def test_offset_quality_names_the_smallest_ratio():
    """A lateral's smallest-ratio hint stays inside the offset's range."""
    with pytest.raises(AssemblyError, match=r"at angle 45°; r/R 0\.5\d\d or more reaches it") as e:
        _tee_asm(0.45, angle=45, run=None, branch=0.8, offset=0.2 * R)[0].validate()
    assert e.value.code == "predicted_sj_below_minimum"
