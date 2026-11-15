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
``tools/check_dist.py`` (task 0149): the release workflow's check of the
wheel and the sdist, on small hand-made archives (no build).
"""

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_dist", ROOT / "tools/check_dist.py")
check_dist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_dist)

DATA = ["hexmesh/agent/support.json"]
ENTRY = "[console_scripts]\nhexmesh = hexmesh.agent.cli:main\nhexmesh-study = x:main\n"


def _dist(tmp_path, version="0.7.0", extra=(), data=DATA, entry=ENTRY, meta_version=None):
    info = f"hexmesh-{version}.dist-info"
    with zipfile.ZipFile(tmp_path / f"hexmesh-{version}-py3-none-any.whl", "w") as z:
        for name in ["hexmesh/__init__.py", *data, *extra]:
            z.writestr(name, "")
        z.writestr(f"{info}/METADATA",
                   f"Metadata-Version: 2.4\nName: hexmesh\nVersion: {meta_version or version}\n")
        z.writestr(f"{info}/entry_points.txt", entry)
    with tarfile.open(tmp_path / f"hexmesh-{version}.tar.gz", "w:gz") as t:
        member = tarfile.TarInfo(f"hexmesh-{version}/pyproject.toml")
        t.addfile(member, io.BytesIO(b""))
    return tmp_path


def test_a_good_dist_passes(tmp_path):
    assert check_dist.problems(_dist(tmp_path), "v0.7.0", DATA) == []


def test_the_tag_s_version_is_required(tmp_path):
    found = check_dist.problems(_dist(tmp_path), "v0.8.0", DATA)
    assert any("METADATA version '0.7.0', the tag says '0.8.0'" in f for f in found)
    assert any("not hexmesh-0.8.0.tar.gz" in f for f in found)


def test_tests_docs_and_missing_data_are_refused(tmp_path):
    found = check_dist.problems(_dist(tmp_path, extra=["tests/test_x.py", "docs/a.md"], data=[]),
                                "v0.7.0", DATA)
    assert any("['docs', 'tests'] besides hexmesh/" in f for f in found)
    assert any("package data missing: ['hexmesh/agent/support.json']" in f for f in found)


def test_the_commands_are_required(tmp_path):
    found = check_dist.problems(_dist(tmp_path, entry="[console_scripts]\n"), "v0.7.0", DATA)
    assert [f for f in found if "command" in f] == [
        "hexmesh-0.7.0-py3-none-any.whl: no 'hexmesh' command in entry_points.txt",
        "hexmesh-0.7.0-py3-none-any.whl: no 'hexmesh-study' command in entry_points.txt"]


def test_one_wheel_and_one_sdist(tmp_path):
    found = check_dist.problems(tmp_path, "v0.7.0", DATA)
    assert len(found) == 1 and "expected one wheel and one sdist" in found[0]


def test_package_data_is_what_git_tracks():
    data = check_dist.package_data()
    assert "hexmesh/agent/support.json" in data
    assert all(not p.endswith(".py") for p in data)
