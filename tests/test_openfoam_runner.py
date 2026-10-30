"""
OpenFOAM runner selection (decision 0012's toolchain amendment; built in
task 0067): ``native`` sources the local bashrc, ``docker:<image>`` runs
each command in a container as the calling user with the case mounted at
its own path.
"""

import os
import shutil
import subprocess
from pathlib import Path

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


def test_docker_command_line_mounts_case_and_extra_dirs(restore_runner, tmp_path):
    of.set_runner(of.V2406)
    msh_dir = tmp_path / "mesh"
    msh_dir.mkdir()
    argv = of._argv("gmshToFoam x.msh", tmp_path, mounts=[msh_dir, tmp_path])
    assert argv[:3] == ["docker", "run", "--rm"]
    assert f"{os.getuid()}:{os.getgid()}" in argv
    vols = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    assert vols == [f"{tmp_path}:{tmp_path}", f"{msh_dir}:{msh_dir}"]     # deduplicated
    assert argv[argv.index("-w") + 1] == str(tmp_path)
    assert "opencfd/openfoam-default:2406" in argv and argv[-1].endswith("gmshToFoam x.msh")


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
    assert "ok" in out and (tmp_path / "made_here").stat().st_uid == os.getuid()
