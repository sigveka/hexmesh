"""
The package as installed (task 0080): what the sdist and wheel hold, and a
wheel installed into a fresh venv imports, meshes an example and runs the
console command.  Opt-in: ``-m slow``.

The build uses the installed setuptools (``setuptools.build_meta``, no
isolated environment), so it needs no network.  The venv reuses the
system's site packages for the dependencies (gmsh, numpy, scipy) and
installs only the wheel, with ``--no-index``; its own ``hexmesh`` comes from
the wheel alone (the test runs outside the checkout).
"""

import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

import hexmesh

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.slow


def _pyproject_version() -> str:
    return re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(),
                     re.M).group(1)


def test_versions_agree():
    """``hexmesh.__version__`` = pyproject's = CITATION.cff's."""
    cff = re.search(r"^version:\s*(\S+)", (ROOT / "CITATION.cff").read_text(), re.M).group(1)
    assert hexmesh.__version__ == _pyproject_version() == cff


@pytest.fixture(scope="module")
def dists(tmp_path_factory):
    """(sdist, wheel) built from a copy of the checkout, so the build
    leaves nothing in the working tree."""
    pytest.importorskip("setuptools")
    src = tmp_path_factory.mktemp("src")
    tracked = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True,
                             check=True).stdout.decode().split("\0")
    for rel in filter(None, tracked):
        f = ROOT / rel
        if f.is_file():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, src / rel)
    out = tmp_path_factory.mktemp("dist")
    built = []
    for what in ("sdist", "wheel"):                 # one process each
        code = (f"import sys; from setuptools import build_meta as b; "
                f"print('BUILT', b.build_{what}(sys.argv[1]))")
        run = subprocess.run([sys.executable, "-c", code, str(out)], cwd=src,
                             capture_output=True, text=True)
        assert run.returncode == 0, run.stderr[-3000:]
        built.append(next(l for l in run.stdout.splitlines() if l.startswith("BUILT")).split()[1])
    sdist, wheel = built
    return out / sdist, out / wheel


def test_wheel_holds_every_subpackage(dists):
    _, wheel = dists
    names = zipfile.ZipFile(wheel).namelist()
    found = {str(Path(n).parent).replace("/", ".") for n in names
             if n.endswith("__init__.py")}
    expected = {str(p.parent.relative_to(ROOT)).replace("/", ".")
                for p in (ROOT / "hexmesh").rglob("__init__.py")}
    assert expected <= found
    assert "hexmesh.examples.applications" in found
    assert any(n.endswith("hexmesh/examples/applications/hvac_branched.py") for n in names)
    entry = next(n for n in names if n.endswith(".dist-info/entry_points.txt"))
    assert "hexmesh-study = hexmesh.study.__main__:main" in \
        zipfile.ZipFile(wheel).read(entry).decode()


def test_sdist_contents(dists):
    sdist, _ = dists
    names = [n.split("/", 1)[1] for n in tarfile.open(sdist).getnames() if "/" in n]
    for f in ("LICENSE", "README.md", "CITATION.cff", "pyproject.toml"):
        assert f in names, f
    assert not [n for n in names if n.startswith(("docs/papers", "validation/"))
                or n.endswith((".msh", ".pdf"))]


@pytest.fixture(scope="module")
def venv(dists, tmp_path_factory):
    import venv as _venv                                   # noqa: F401  (skip without it)
    _, wheel = dists
    env = tmp_path_factory.mktemp("venv")
    made = subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(env)],
                          capture_output=True, text=True)
    if made.returncode != 0:
        pytest.skip(f"no venv: {made.stderr.strip()[-200:]}")
    py = env / "bin" / "python"
    run = subprocess.run([str(py), "-m", "pip", "install", "--no-index", "--no-deps",
                          str(wheel)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    check = subprocess.run([str(py), "-m", "pip", "check"], capture_output=True, text=True)
    assert "hexmesh" not in check.stdout, check.stdout       # its dependencies are met
    return env


def test_installed_package_meshes_an_example(venv, tmp_path):
    code = ("import json, hexmesh; from hexmesh.examples.fittings import tee; "
            "r = tee.main(); print(json.dumps({'file': hexmesh.__file__, "
            "'version': hexmesh.__version__, 'predicted': r.predicted, 'meshed': r.meshed}))")
    run = subprocess.run([str(venv / "bin" / "python"), "-c", code], cwd=tmp_path,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-3000:]
    r = json.loads(run.stdout.strip().splitlines()[-1])
    assert str(venv) in r["file"]                          # the installed copy, not the checkout
    assert r["version"] == _pyproject_version()
    assert r["meshed"] == r["predicted"] > 0
    assert (tmp_path / "tee.msh").stat().st_size > 0


def test_console_command(venv, tmp_path):
    run = subprocess.run([str(venv / "bin" / "hexmesh-study"), "--help"], cwd=tmp_path,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.startswith("usage: hexmesh-study")
