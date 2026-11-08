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
OpenFOAM runner selection (decision 0012's toolchain amendment; built in
task 0067): ``native`` sources the local bashrc, ``docker:<image>`` runs
each command in a container as the calling user with the case mounted at
its own path.
"""

import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np
import pytest

from hexmesh.study import openfoam as of


@pytest.fixture
def restore_runner():
    before = of.runner()
    yield
    of.set_runner(before)


def test_native_command_line(restore_runner):
    of.set_runner("native")
    argv = of._argv("checkMesh", Path("/tmp"))
    assert argv[:2] == ["bash", "-c"] and str(of.OPENFOAM_RC) in argv[2]


def _vols(argv):
    return [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]


def test_docker_command_line_mounts_case_and_extra_dirs(restore_runner, tmp_path):
    of.set_runner(of.V2406)
    case, mesh = tmp_path / "case", tmp_path / "mesh"
    case.mkdir()
    mesh.mkdir()
    argv = of._argv(f"gmshToFoam {mesh / 'x.msh'}", case, mounts=[mesh, case])
    assert argv[:3] == ["docker", "run", "--rm"]
    if hasattr(os, "getuid"):                          # POSIX hosts only
        assert f"{os.getuid()}:{os.getgid()}" in argv
    assert _vols(argv) == [f"{case}:/work/0", f"{mesh}:/work/1"]        # deduplicated
    assert argv[argv.index("-w") + 1] == "/work/0"
    assert argv[-1].endswith("gmshToFoam /work/1/x.msh")


def test_docker_command_line_without_getuid(restore_runner, tmp_path, monkeypatch):
    """Windows has no ``os.getuid``: no ``--user`` (Docker Desktop maps
    file ownership itself)."""
    of.set_runner(of.V2406)
    monkeypatch.delattr(os, "getuid", raising=False)
    argv = of._argv("checkMesh", tmp_path)
    assert "--user" not in argv and argv[argv.index("-w") + 1] == "/work/0"


def test_docker_command_line_from_a_windows_host():
    """Host paths are Windows paths; the container sees Linux ones."""
    case = PureWindowsPath(r"C:\Users\me\study\v0\case")
    mesh = PureWindowsPath(r"D:\meshes")
    cmd = rf"gmshToFoam {mesh}\pipe.msh && cp {case}\log.x {mesh}\log.x"
    argv = of.docker_argv(cmd, case, [mesh, case.parent], image="opencfd/openfoam-default:2406")
    assert "--user" not in argv
    assert _vols(argv) == [r"C:\Users\me\study\v0:/work/0", r"D:\meshes:/work/1"]
    assert argv[argv.index("-w") + 1] == "/work/0/case"
    assert argv[-1].endswith("gmshToFoam /work/1/pipe.msh && cp /work/0/case/log.x /work/1/log.x")
    assert "\\" not in argv[-1] and "C:" not in argv[-1]


def test_container_command_rewrites_whole_paths_only():
    mapping = of.container_paths([PurePosixPath("/a/b"), PurePosixPath("/a/b/c")])
    assert mapping == [(PurePosixPath("/a/b"), "/work/0", True),
                       (PurePosixPath("/a/b/c"), "/work/0/c", False)]
    cmd = "x /a/b/c/f; y /a/bc z=/a/b '/a/b/d e' ../f /x/a/b"
    assert of.container_command(cmd, mapping) == \
        "x /work/0/c/f; y /a/bc z=/work/0 '/work/0/d e' ../f /x/a/b"


@pytest.mark.parametrize("bad", ["docker:", "docker", "v2406", ""])
def test_bad_runner_rejected(restore_runner, bad):
    with pytest.raises(ValueError, match="native"):
        of.set_runner(bad)


def _have_image() -> bool:
    if shutil.which("docker") is None:
        return False
    run = subprocess.run(["docker", "image", "inspect", "opencfd/openfoam-default:2406"],
                         capture_output=True)
    return run.returncode == 0


@pytest.mark.openfoam
@pytest.mark.skipif(not _have_image(), reason="no opencfd/openfoam-default:2406 image")
def test_docker_runner_reports_v2406(restore_runner, tmp_path):
    of.set_runner(of.V2406)
    assert of.have_openfoam() and of.openfoam_version() == "v2406"
    out = of.foam("touch made_here && echo ok", tmp_path, "log.touch")
    assert "ok" in out
    if hasattr(os, "getuid"):                          # POSIX hosts: files are the caller's
        assert (tmp_path / "made_here").stat().st_uid == os.getuid()


@pytest.mark.openfoam
@pytest.mark.skipif(not _have_image(), reason="no opencfd/openfoam-default:2406 image")
def test_docker_container_stops_with_its_caller(tmp_path):
    """A caller killed by ``timeout`` (SIGTERM) stops its container: a
    Docker container otherwise outlives its client."""
    import sys
    script = ("import sys; from pathlib import Path; from hexmesh.study import openfoam as of;"
              f"of.set_runner(of.V2406); of.foam('sleep 120', Path({str(tmp_path)!r}), 'log.sleep')")
    run = subprocess.run(["timeout", "8", sys.executable, "-c", script],
                         cwd=Path(__file__).resolve().parents[1], capture_output=True)
    assert run.returncode != 0
    left = subprocess.run(["docker", "ps", "-q", "--filter", "volume=" + str(tmp_path)],
                          capture_output=True, text=True).stdout.split()
    assert left == []


# ---------------------------------------------------------------------------
# Parallel runs (task 0090)
# ---------------------------------------------------------------------------

def test_cpuinfo_counts_cores_not_threads():
    """Two hardware threads per core: 2 sockets × 2 cores × 2 threads."""
    blocks = [f"processor\t: {i}\nphysical id\t: {i // 4}\ncore id\t\t: {(i // 2) % 2}\n"
              for i in range(8)]
    assert of.cpuinfo_cores("\n".join(blocks)) == 4
    assert of.cpuinfo_cores("processor\t: 0\n") == 0


def test_physical_cores_is_at_most_the_thread_count():
    assert 1 <= of.physical_cores() <= (os.cpu_count() or 1)


@pytest.mark.parametrize("axis, n", [(0, "(3 1 1)"), (1, "(1 3 1)"), (2, "(1 1 3)")])
def test_decompose_dict_slabs_along_the_axis(axis, n):
    text = of.decompose_dict(3, axis)
    assert "numberOfSubdomains 3;" in text and "method          simple;" in text
    assert f"n {n};" in text


@pytest.mark.parametrize("n_proc, match", [(0, ">= 1"), (3, "more than this machine's 2 "
                                                             "physical cores")])
def test_run_solver_rejects_bad_process_counts(monkeypatch, tmp_path, n_proc, match):
    """Rejected before any OpenFOAM command runs."""
    monkeypatch.setattr(of, "physical_cores", lambda: 2)
    monkeypatch.setattr(of, "foam", lambda *a, **k: pytest.fail("ran a command"))
    with pytest.raises(ValueError, match=match):
        of.run_solver(tmp_path, "simpleFoam", n_proc=n_proc)


def _cavity(root: Path, name: str) -> Path:
    of.foam(f"cp -r $FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity {name}", root,
            f"log.cp.{name}")
    case = root / name
    of.foam("blockMesh", case, "log.blockMesh")
    return case


@pytest.mark.openfoam
@pytest.mark.skipif(not _have_image(), reason="no opencfd/openfoam-default:2406 image")
def test_run_solver_serial_and_two_processes(restore_runner, tmp_path):
    """``n_proc`` 1 is ``foam``; 2 decomposes, runs under ``mpirun``,
    reconstructs every written time and removes the processor
    directories.  Decomposition changes round-off only: the fields agree
    to the solver's tolerance (cavity tutorial, icoFoam, 1e-6)."""
    if of.physical_cores() < 2:
        pytest.skip("needs 2 physical cores")
    of.set_runner(of.V2406)
    serial, parallel = _cavity(tmp_path, "serial"), _cavity(tmp_path, "parallel")
    log1 = of.run_solver(serial, "icoFoam")
    log2 = of.run_solver(parallel, "icoFoam", n_proc=2)
    assert "End" in log1 and "End" in log2
    assert "Number of processors = 2" in log2 or "nProcs : 2" in log2
    assert not list(parallel.glob("processor*"))
    assert [d.name for d in sorted(parallel.glob("0.*"))] == [d.name for d in
                                                               sorted(serial.glob("0.*"))]
    u1 = of.read_internal(serial / "0.5" / "U", 3)
    u2 = of.read_internal(parallel / "0.5" / "U", 3)
    assert abs(u1 - u2).max() < 1e-5
    # keep=True leaves the decomposed case, as decomposed
    of.run_solver(parallel, "icoFoam", n_proc=2, keep=True, log="log.again")
    assert sorted(d.name for d in parallel.glob("processor*")) == ["processor0", "processor1"]


@pytest.mark.parametrize("control, want", [
    ("startFrom latestTime;\nstartTime 0;\n", "-latestTime"),
    ("startFrom startTime;\nstartTime 0.25;\n", "-time 0.25"),
    ("startTime 0;\n", "-time 0"),                       # OpenFOAM's default startFrom
    ("startFrom firstTime;\n", "-time 0.1"),
])
def test_decompose_the_time_the_solver_starts_from(tmp_path, control, want):
    (tmp_path / "system").mkdir()
    (tmp_path / "system/controlDict").write_text(
        of.header("dictionary", "controlDict", "system") + control, encoding="utf-8")
    for t in ("0.1", "0.5"):
        (tmp_path / t).mkdir()
    assert of.start_time_option(tmp_path) == want


# --- gmshToFoam's orientation test (task 0108) ---------------------------------

#: one of the six right-handed hexes gmshToFoam v2406 flipped in the MMS 90°
#: wye at k = 4 (task 0074), gmsh's vertex order, rounded to 1e-9
WYE_HEX = [[0.140454948, -0.035709517, 0.0329221], [0.140373787, -0.036716389, 0.033939752],
           [0.16016109, -0.040652435, 0.0309896], [0.160091727, -0.0405037, 0.030681642],
           [0.145205343, -0.035346842, 0.033262729], [0.145250608, -0.03635809, 0.034323306],
           [0.16357587, -0.041767246, 0.032944481], [0.163469687, -0.041467103, 0.032435794]]
CUBE = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
#: each corner's three neighbours, right-handed in gmsh's hex order
_CORNERS = ((1, 3, 4), (2, 0, 5), (3, 1, 6), (0, 2, 7), (7, 5, 0), (4, 6, 1), (5, 7, 2),
            (6, 4, 3))


def corner_sj(p) -> list[float]:
    p = np.asarray(p, float)
    out = []
    for i, nb in enumerate(_CORNERS):
        e = np.array([p[j] - p[i] for j in nb])
        out.append(float(np.linalg.det(e / np.linalg.norm(e, axis=1)[:, None])))
    return out


def _msh(path: Path, hexes) -> Path:
    """An MSH 2.2 ASCII file of *hexes*, as write_openfoam writes it: a
    boundary quad first, element tags, node ids from 1."""
    pts = np.asarray(hexes, float).reshape(-1, 3)
    nodes = "".join(f"{i + 1} {x!r} {y!r} {z!r}\n" for i, (x, y, z) in enumerate(pts))
    els = ["1 3 2 7 1 1 2 3 4"] + [f"{h + 2} 5 2 99 5 " + " ".join(str(8 * h + j + 1)
                                                                  for j in range(8))
                                    for h in range(len(hexes))]
    path.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n"
                    f"$Nodes\n{len(pts)}\n{nodes}$EndNodes\n"
                    f"$Elements\n{len(els)}\n" + "\n".join(els) + "\n$EndElements\n",
                    encoding="utf-8")
    return path


def test_the_orientation_test_flips_the_0074_wye_hex():
    """Right-handed at every corner, and gmshToFoam's test flips it."""
    assert min(corner_sj(WYE_HEX)) > 0.13
    assert of.foam_would_invert([WYE_HEX]).tolist() == [True]


def test_the_orientation_test_keeps_a_cube_and_flips_a_mirrored_one():
    assert corner_sj(CUBE) == [1.0] * 8
    mirrored = [[-x, y, z] for x, y, z in CUBE]
    assert of.foam_would_invert([CUBE, mirrored]).tolist() == [False, True]


def test_would_invert_reads_the_written_msh(tmp_path):
    msh = _msh(tmp_path / "m.msh", [CUBE, WYE_HEX, CUBE])
    assert of.msh_hexes(msh).shape == (3, 8, 3)
    np.testing.assert_allclose(of.msh_hexes(msh)[1], WYE_HEX)
    assert of.would_invert(msh) == 1


def test_msh_hexes_wants_msh_2_2(tmp_path):
    msh = tmp_path / "m.msh"
    msh.write_text("$MeshFormat\n4.1 0 8\n$EndMeshFormat\n", encoding="utf-8")
    from hexmesh.errors import ReaderError
    with pytest.raises(ReaderError, match="not MSH 2.2") as e:
        of.msh_hexes(msh)
    assert e.value.code == "msh_format_invalid"


def test_a_straight_would_flip_nothing(tmp_path):
    from hexmesh import Assembly, PipeSpec, Session, Straight
    asm = Assembly(PipeSpec(nang=6).core("fluid", radius=0.05, nrad=3),
                   direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=4))
    with Session("would-invert-straight"):
        asm.write_openfoam(str(tmp_path / "s.msh"))
    assert len(of.msh_hexes(tmp_path / "s.msh")) == asm.cell_count()
    assert of.would_invert(tmp_path / "s.msh") == 0


@pytest.mark.parametrize("keep, flag", [(False, ""), (True, " -keepOrientation")])
def test_convert_keep_orientation_flag(monkeypatch, tmp_path, keep, flag):
    """``keep_orientation`` skips gmshToFoam's orientation test, which flips
    valid warped hexes (task 0074); off by default.

    Checked as OpenFOAM receives it: ``convert`` names the mesh by its host
    path (``C:\\…`` on Windows) and the Docker runner rewrites it to the
    container's POSIX path, so the command OpenFOAM runs is the same on
    every host (task 0105)."""
    ran = []
    monkeypatch.setattr(of, "foam", lambda cmd, case, log, mounts=(): ran.append(
        (cmd, case, mounts)) or "")
    import hexmesh.io.writers.openfoam_boundary as ob
    monkeypatch.setattr(ob, "apply_boundary_roles", lambda case, roles: [])
    of.convert(tmp_path, tmp_path / "mesh.msh", keep_orientation=keep)
    cmd, case, mounts = ran[0]
    assert cmd == f"gmshToFoam{flag} {(tmp_path / 'mesh.msh').resolve()}"
    argv = of.docker_argv(cmd, Path(case).resolve(), [Path(m).resolve() for m in mounts],
                          image="img")
    assert argv[-1].endswith(f"; gmshToFoam{flag} /work/0/mesh.msh"), (cmd, argv[-1])
