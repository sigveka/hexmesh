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
