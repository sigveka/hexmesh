"""
Wye block layout (hexmesh/assembly/wye.py; decision 0017, task 0030).
Conformance is covered by the kit (tests/test_fitting_conformance.py);
these tests cover the wye itself.  Quality is measured, not gated
(decision 0017): the mesh tests require valid hexes only.
"""

import math
import pathlib
import shutil
import subprocess

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Wye, limits
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import PipeSpec

R = 0.1


def _spec(nang=4, nrad=3, **kw):
    return PipeSpec(nang=nang, **kw).core("fluid", CircleShape(radius=R, nang=nang), nrad=nrad)


def _wye_asm(angle=60, spec=None, run=0.3, branch=0.5, direction=(1, 0, 0), **kw):
    asm = Assembly(spec or _spec(), direction=list(direction), up=[0, 0, 1], lc=0.05)
    left, right = asm.add(Wye(angle, run_length=run, branch_length=branch, **kw),
                          names=["left", "right"])
    return asm, left, right


def _layout(asm):
    wye = asm.edges[0].fitting
    return wye.layout([p.frame for p in asm.edges[0].ports], asm.inlet.spec)


class TestTopology:
    def test_ports(self):
        asm, left, right = _wye_asm(60, run=0.3, branch=0.5)
        h = math.radians(30)
        for port, side in ((left, +1), (right, -1)):    # frame.right = −y here
            d = [math.cos(h), side * math.sin(h), 0]
            np.testing.assert_allclose(port.frame.normal, d, atol=1e-12)
            np.testing.assert_allclose(port.frame.position, np.array([0.3, 0, 0]) + 0.5 * np.array(d),
                                       atol=1e-12)
            np.testing.assert_allclose(port.frame.up, [0, 0, 1], atol=1e-12)
            assert port.spec == asm.inlet.spec

    def test_right_turns_toward_frame_right(self):
        asm, _, right = _wye_asm(90)
        assert np.dot(right.frame.normal, asm.inlet.frame.right) > 0.5

    def test_layout_validates_without_gmsh(self):
        asm, _, _ = _wye_asm(60)
        report = _layout(asm).validate()
        assert not gmsh.isInitialized()
        assert report["blocks"] == 29
        assert report["min_corner_sj"] > 0

    @pytest.mark.parametrize("angle", [30, 60, 120])
    def test_resolved_counts_follow_the_angular_cell(self, angle):
        """Unset counts resolve from the arcs (task 0056): doubling nang
        about doubles n_run and n_branch; n_split stays at the cap."""
        coarse, fine = (_wye_asm(angle, spec=_spec(nang))[0].edges[0].fitting
                        for nang in (8, 16))
        for name in ("n_run", "n_branch"):
            assert abs(getattr(fine, name) - 2 * getattr(coarse, name)) <= 1, name
        assert coarse.n_split == fine.n_split == limits.WYE_N_SPLIT_MAX
        assert not gmsh.isInitialized()

    def test_explicit_counts_are_kept(self):
        asm, _, _ = _wye_asm(60, n_run=2, n_branch=3, n_split=9)
        wye = asm.edges[0].fitting
        assert (wye.n_run, wye.n_branch, wye.n_split) == (2, 3, 9)

    @pytest.mark.parametrize("n_split, k, expected",
                             [(2, 2, 4), (3, 4, 6), (6, 2, 6), (9, 2, 9)])
    def test_refined_holds_n_split_at_the_cap(self, n_split, k, expected):
        """A 120° wye at nang 16 folds at n_split 12 (task 0056): refined
        scales n_split only up to the cap, and never below its own value."""
        asm, _, _ = _wye_asm(60, n_run=2, n_branch=3, n_split=n_split)
        wye = asm.refined(k).edges[0].fitting
        assert (wye.n_run, wye.n_branch, wye.n_split) == (2 * k, 3 * k, expected)

    @pytest.mark.parametrize("nang, nrad, n_run, n_branch, n_split",
                             [(4, 3, 3, 3, 3), (6, 2, 2, 5, 4), (5, 4, 1, 1, 2)])
    def test_cell_count_closed_form(self, nang, nrad, n_run, n_branch, n_split):
        asm, _, _ = _wye_asm(60, spec=_spec(nang, nrad), n_run=n_run, n_branch=n_branch,
                             n_split=n_split)
        face = nang**2 + 4 * nang * nrad
        expected = ((n_run + 2 * n_branch) * face + nang**3 + 3 * nang**2 * nrad
                    + 2 * n_split * face)
        assert asm.cell_count() == expected
        assert not gmsh.isInitialized()

    @pytest.mark.parametrize("kw, message", [
        (dict(angle=20), "outside the prototype range"),
        (dict(angle=130), "outside the prototype range"),
        (dict(run=0.06), "run_length must exceed"),
        (dict(branch=0.2), "branch_length must exceed"),
        (dict(n_split=0), "layer counts"),
    ])
    def test_rejected_before_gmsh(self, kw, message):
        # resolving unset counts runs the checks in add(); explicit ones in validate()
        with pytest.raises(AssemblyError, match=message):
            asm, _, _ = _wye_asm(**kw)
            asm.validate()
        assert not gmsh.isInitialized()

    @pytest.mark.parametrize("spec, message", [
        (_spec().shell("box", outer=RectShape(0.15, 0.15, 4, 4), nrad=2),
         "circular only.*0026"),
        (_spec(rot=0.2), "rot = 0"),
    ])
    def test_spec_limits(self, spec, message):
        with pytest.raises(AssemblyError, match=message):
            asm, _, _ = _wye_asm(spec=spec)
            asm.validate()

    @pytest.mark.parametrize("angle, inside, outside", [
        (60, 0.35, 0.40),        # limit 0.65 tan 30° = 0.375 R
        (90, 0.50, 0.60),        # limit capped at 0.55 R
    ])
    def test_shell_thickness_limit(self, angle, inside, outside):
        """Task 0053: total shell thickness ≤ R·min(0.65 tan(angle/2), 0.55),
        checked before GMSH, the error naming angle, thickness and limit."""
        two = lambda t: _spec().shell("wall", dR=t / 2 * R, nrad=1).shell(
            "insulation", dR=t / 2 * R, nrad=1)
        asm, _, _ = _wye_asm(angle, spec=two(inside), run=0.4, branch=0.7)
        asm.validate()
        with pytest.raises(AssemblyError, match=rf"Wye at {angle}°: total shell "
                           rf"thickness .*\({outside:g} R\) exceeds the limit"):
            asm, _, _ = _wye_asm(angle, spec=two(outside), run=0.4, branch=0.7)
            asm.validate()
        assert not gmsh.isInitialized()

    def test_shell_min_angle(self):
        """Shelled wyes start at WYE_SHELL_MIN_ANGLE (40°); single-layer at 30°."""
        thin = _spec().shell("wall", dR=0.04 * R, nrad=1)
        asm, _, _ = _wye_asm(40, spec=thin, run=0.4, branch=0.7)
        asm.validate()
        with pytest.raises(AssemblyError, match="35° with shells .*WYE_SHELL_MIN_ANGLE 40°"):
            asm, _, _ = _wye_asm(35, spec=thin, run=0.4, branch=0.7)
            asm.validate()
        asm, _, _ = _wye_asm(35, run=0.4, branch=0.7)
        asm.validate()

    @pytest.mark.parametrize("angle, warns", [(30, True), (35, True), (45, False)])
    def test_narrow_wye_warns(self, angle, warns):
        """Predicted min corner SJ < PREDICTED_SJ_MIN warns (task 0053); the
        wye has no reject tier until its layout redesign."""
        asm, _, _ = _wye_asm(angle, run=0.4, branch=0.7)
        if warns:
            with pytest.warns(UserWarning, match=r"predicted min corner scaled "
                              r"Jacobian 0\.\d+ is below PREDICTED_SJ_MIN"):
                asm.validate()
        else:
            asm.validate()
            assert not [w for w in asm.warnings if "PREDICTED_SJ_MIN" in w]

    def test_crotch_corners_on_the_wall(self):
        """The wall vertices of the crotch lie on the intended wall."""
        asm, _, _ = _wye_asm(60)
        lay = _layout(asm)
        sk = asm.edges[0].fitting.skeleton(asm.inlet.frame, asm.inlet.spec)
        w = np.array([lay.coords[("W", 1, k)] for k in range(4)])
        np.testing.assert_allclose(sk.distance(w), R, rtol=1e-12)


def _hex_nodes():
    _, _, enodes = gmsh.model.mesh.getElements(3)
    used = np.unique(np.concatenate(enodes))
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    lookup = dict(zip(tags, xyz.reshape(-1, 3)))
    return np.array([lookup[t] for t in used])


@pytest.mark.parametrize("angle", [30, 60, 90, 120])
def test_all_hex_valid_mesh(gmsh_session, angle):
    asm, _, _ = _wye_asm(angle, run=0.4, branch=0.7)
    asm.mesh()
    types = gmsh.model.mesh.getElements(3)[0]
    assert [gmsh.model.mesh.getElementProperties(t)[0] for t in types] == ["Hexahedron 8"]
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == asm.cell_count()
    report = asm.check_quality()
    assert report.ok, str(report)
    names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
    assert names == {"fluid", "fluid_inlet", "fluid_left", "fluid_right", "fluid_wall"}


@pytest.mark.parametrize("angle", [90, 120])
def test_thin_wall_shell(gmsh_session, angle):
    """A realistic pipe wall (T/R = 0.04) through the wye (task 0053 step 0):
    wall and shell boundary projected, no fold, the shell's cells no worse
    than the fluid's (min corner SJ 0.16 / 0.12 at 90° / 120°)."""
    asm, _, _ = _wye_asm(angle, spec=_spec().shell("wall", dR=0.04 * R, nrad=1),
                         run=0.4, branch=0.7)
    asm.mesh()
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == asm.cell_count()
    names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
    assert {"fluid", "wall", "interface_fluid_wall", "wall_wall"} <= names, names
    assert asm.projection_report[asm.edges[0].name]["min_sj"] > 0.1


def test_fill_errors_are_assembly_errors(gmsh_session, monkeypatch):
    """No raw OCC/GMSH exception escapes a fill (task 0053): it becomes an
    AssemblyError naming the fitting and quoting the original message."""
    def boom(self, *a, **k):
        raise Exception("OpenCASCADE exception  GeomFill_BSplineCurves: forced")
    monkeypatch.setattr(Wye, "fill", boom)
    asm, _, _ = _wye_asm(60)
    with pytest.raises(AssemblyError, match=r"Wye.*fill failed \(Exception: "
                       r"OpenCASCADE exception  GeomFill_BSplineCurves: forced\)"):
        asm.mesh()


def test_mesh_is_mirror_symmetric(gmsh_session):
    """The layout is symmetric about the plane of the inlet axis and `up`."""
    from scipy.spatial import cKDTree
    asm, _, _ = _wye_asm(60)
    asm.mesh()
    x = _hex_nodes()
    mirrored = x * [1, -1, 1]                  # inlet along x, plane y = 0
    d, _ = cKDTree(x).query(mirrored)
    assert d.max() < 1e-6 * R, d.max()


def test_junction_wall_near_intended_surface(gmsh_session):
    """Wall nodes stay near the canal surface of the skeleton (reported in
    the task's measurements; a regression guard, not a quality limit)."""
    asm, _, _ = _wye_asm(60)
    asm.mesh()
    sk = asm.edges[0].fitting.skeleton(asm.inlet.frame, asm.inlet.spec)
    x = np.vstack([gmsh.model.mesh.getNodes(2, s, includeBoundary=True)[1].reshape(-1, 3)
                   for s in asm._fill.walls])
    dev = (sk.distance(x) - R) / R
    assert np.abs(dev).max() < 0.25, (dev.min(), dev.max())


def test_save_load_round_trip(tmp_path):
    asm, _, _ = _wye_asm(60)
    path = tmp_path / "wye.json"
    asm.save(path)
    again = Assembly.load(path)
    assert again.to_dict() == asm.to_dict()
    assert again.cell_count() == asm.cell_count()


OPENFOAM_RC = pathlib.Path("/usr/share/openfoam/etc/bashrc")


@pytest.mark.openfoam
@pytest.mark.skipif(not OPENFOAM_RC.exists() or shutil.which("bash") is None,
                    reason="OpenFOAM not installed")
def test_openfoam_check_mesh(gmsh_session, tmp_path):
    """gmshToFoam + checkMesh on a 60° wye between straights: Mesh OK."""
    from test_openfoam_output import foam_case
    asm = Assembly(_spec(nang=6, nrad=3), direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Straight(0.3, n_layers=6))
    left, right = asm.add(Wye(60, run_length=0.3, branch_length=0.5, n_run=4,
                              n_branch=4, n_split=4), names=["left", "right"])
    asm.add(left, Straight(0.3, n_layers=6))
    asm.add(right, Straight(0.3, n_layers=6))
    msh = tmp_path / "wye.msh"
    asm.write_openfoam(msh)
    case = foam_case(tmp_path / "case")
    run = subprocess.run(
        ["bash", "-c", f"source {OPENFOAM_RC} >/dev/null 2>&1; set -e; "
                       f"gmshToFoam -case {case} {msh}; checkMesh -case {case}"],
        capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    assert "Mesh OK." in run.stdout, run.stdout[-3000:]


# --- the layout cache (task 0112) -------------------------------------------------

from hexmesh.assembly import wye as wye_module          # noqa: E402
from hexmesh.assembly.interface import Frame            # noqa: E402


def _fingerprint(lay):
    """What a stale layout would get wrong: its counts and its vertices.
    Each test below changes one input, and checks that the cache misses
    (builds again) and returns what a fresh build gives.  Some inputs leave
    this fingerprint as it was (``branch_length`` at fixed frames, the
    core's ``mprg``); a miss is required for them all the same."""
    return lay.cell_count(), sorted((repr(k), np.asarray(v).tobytes())
                                    for k, v in lay.coords.items())


@pytest.fixture
def cached(monkeypatch):
    """A clean cache, and how many layouts are built (misses)."""
    monkeypatch.setattr(wye_module, "_LAYOUTS", type(wye_module._LAYOUTS)())
    built = [0]
    inner = Wye._layout

    def counting(self, frames, spec):
        built[0] += 1
        return inner(self, frames, spec)
    monkeypatch.setattr(Wye, "_layout", counting)
    return built


def _resolved(**kw):
    asm, _, _ = _wye_asm(60, n_run=2, n_branch=2, n_split=2, **kw)
    e = asm.edges[0]
    return e.fitting, [p.frame for p in e.ports], asm.inlet.spec


def _copy_frames(frames):
    return [Frame(f.position.copy(), f.normal.copy(), f.up.copy()) for f in frames]


def test_equal_values_hit_and_copies_are_independent(cached):
    wye, frames, spec = _resolved()
    a = wye.layout(frames, spec)
    b = Wye(**{f: getattr(wye, f) for f in wye.__dataclass_fields__}).layout(
        _copy_frames(frames), PipeSpec.from_dict(spec.to_dict()))
    assert cached[0] == 1                                     # built once
    assert _fingerprint(a) == _fingerprint(b) and a is not b
    a.coords.clear()                                          # a caller's change
    assert _fingerprint(wye.layout(frames, spec)) == _fingerprint(b)


def _wye_changes(wye):
    return {"angle": 70, "run_length": wye.run_length * 1.1,
            "branch_length": wye.branch_length * 1.1, "n_run": 3, "n_branch": 3,
            "n_split": 3, "roll": 90.0}


@pytest.mark.parametrize("field", ["angle", "run_length", "branch_length", "n_run",
                                   "n_branch", "n_split", "roll"])
def test_a_changed_wye_field_misses(cached, field):
    from dataclasses import replace
    wye, frames, spec = _resolved()
    base = _fingerprint(wye.layout(frames, spec))
    other = replace(wye, **{field: _wye_changes(wye)[field]})
    got = _fingerprint(other.layout(frames, spec))
    assert cached[0] == 2                                    # missed
    assert got == _fingerprint(other._layout(frames, spec))
    if field != "branch_length":                             # the ports come from the frames
        assert got != base


def _rotate_z(v, deg=5.0):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    v[:] = [c * v[0] - s * v[1], s * v[0] + c * v[1], v[2]]


@pytest.mark.parametrize("port", [0, 1, 2])
@pytest.mark.parametrize("vector", ["position", "normal", "up"])
def test_a_frame_mutated_in_place_misses(cached, port, vector):
    """Frames are frozen dataclasses holding arrays, which can still be
    changed in place: the key reads their values at each call."""
    wye, frames, spec = _resolved(direction=(1, 1, 0))
    base = _fingerprint(wye.layout(frames, spec))
    f = frames[port]
    if vector == "position":
        f.position[1] += 0.01
    else:                         # keep the frame orthonormal: turn both vectors
        _rotate_z(f.normal), _rotate_z(f.up)
    got = _fingerprint(wye.layout(frames, spec))
    assert cached[0] == 2                                    # missed
    assert got == _fingerprint(wye._layout(frames, spec)) and got != base


@pytest.mark.parametrize("spec", [
    _spec(nang=8), _spec(nrad=4), _spec().shell("steel", dR=0.01, nrad=1),
    PipeSpec(nang=4).core("fluid", CircleShape(radius=R, nang=4), nrad=3, mprg=0.8),
    PipeSpec(nang=4).core("fluid", CircleShape(radius=1.1 * R, nang=4), nrad=3)],
    ids=["nang", "nrad", "shell", "mprg", "radius"])
def test_a_changed_spec_misses(cached, spec):
    wye, frames, base_spec = _resolved()
    base = _fingerprint(wye.layout(frames, base_spec))
    got = _fingerprint(wye.layout(frames, spec))
    assert cached[0] == 2                                    # missed
    assert got == _fingerprint(wye._layout(frames, spec))
    if spec.to_dict()["core"]["mprg"] == 1.0:                # mprg grades; no vertex moves
        assert got != base


def test_the_cache_is_bounded(cached, monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(wye_module, "LAYOUT_CACHE_SIZE", 3)
    wye, frames, spec = _resolved()
    for n in (2, 3, 4, 5, 6):
        replace(wye, n_run=n).layout(frames, spec)
    assert len(wye_module._LAYOUTS) == 3
    replace(wye, n_run=2).layout(frames, spec)               # dropped: built again
    assert cached[0] == 6
