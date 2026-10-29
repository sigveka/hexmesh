"""
Tee block layout (hexmesh/assembly/tee.py).  Conformance is covered by the
kit (tests/test_fitting_conformance.py); these tests cover the tee itself.
"""

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
        (dict(ratio=1.0), "branch radius"),
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
    return float(re.search(r"run_length ([0-9.e-]+) or more reaches it", message).group(1))


def test_short_run_rejected_with_the_length_that_works():
    asm = _shelled_tee(0.5, 0.02, 0.08)            # steel slab at SJ 0.06
    with pytest.raises(AssemblyError, match=r"Tee.*predicted corner scaled Jacobian "
                       r"0\.060 is below PREDICTED_SJ_MIN 0\.1; run_length .* or more") as e:
        asm.validate()
    need = _hint(str(e.value))
    assert 0.08 < need < 0.09
    with pytest.warns(UserWarning):                # at the hint: past the hard tier
        _shelled_tee(0.5, 0.02, need).validate()
    assert not gmsh.isInitialized()


def test_warning_names_the_run_that_reaches_it():
    asm = _shelled_tee(0.7, 0.02, 0.095)           # SJ 0.215
    with pytest.warns(UserWarning, match=r"below PREDICTED_SJ_WARN 0\.3; run_length "):
        asm.validate()
    assert len(asm.warnings) == 1 and asm.warnings[0].startswith("fitting #0 Tee(")
    need = _hint(asm.warnings[0])
    ok = _shelled_tee(0.7, 0.02, need)
    ok.validate()
    assert ok.warnings == []


def test_small_branch_warns_at_any_length():
    """r/R below about 0.57 can't reach 0.3: the message blames the ratio."""
    asm = _shelled_tee(0.5, 0.0, 0.5)
    with pytest.warns(UserWarning, match=r"no run_length reaches it: the branch ratio r/R 0\.5"):
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
