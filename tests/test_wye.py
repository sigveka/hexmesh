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
from hexmesh.core.shape import CircleShape
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
        (_spec().shell("wall", dR=0.02, nrad=2), "single-layer"),
        (_spec(rot=0.2), "rot = 0"),
    ])
    def test_spec_limits(self, spec, message):
        with pytest.raises(AssemblyError, match=message):
            asm, _, _ = _wye_asm(spec=spec)
            asm.validate()

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
