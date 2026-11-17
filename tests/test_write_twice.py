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
Writing an assembly twice in one session (task 0163): ``mesh()`` runs
once per option set, so a second write reuses the mesh.
"""

import re

import gmsh
import pytest

from hexmesh import Assembly, Bend, PipeSpec, Session, Straight, Tee
from hexmesh.assembly import AssemblyError


def _tee():
    """A tee: transfinite surfaces with more than four corners."""
    asm = Assembly(PipeSpec(n_arc=6).core("fluid", radius=0.1, n_radial=5, first_cell=0.01),
                   direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=4))
    main, branch = asm.add(Tee(branch_length=0.3, branch_radius=0.06))
    asm.add(main, Straight(0.5, n_layers=4), names=["main_end"])
    asm.add(branch, Straight(0.3, n_layers=4), names=["branch_end"])
    return asm


def _bend():
    """A bend: no such surface."""
    asm = Assembly(PipeSpec(n_arc=4).core("fluid", radius=0.05, n_radial=3))
    asm.add(Straight(0.2, n_layers=3))
    asm.add(Bend(radius=0.2, angle=90, n_layers=6))
    return asm


BUILDS = {"tee": _tee, "bend": _bend}


def _write(asm, writer, path, **kw):
    if writer == "write":
        asm.write(str(path), **kw)
    else:
        asm.write_openfoam(str(path), **kw)


def _body(path) -> str:
    """The file without its recipe block (``$Comments``), which names the
    writer."""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"\$Comments\n.*?\$EndComments\n", "", text, flags=re.S)


@pytest.mark.parametrize("build", BUILDS)
@pytest.mark.parametrize("first, second", [("write", "write"),
                                           ("write", "write_openfoam"),
                                           ("write_openfoam", "write"),
                                           ("write_openfoam", "write_openfoam")])
def test_a_second_write_reuses_the_mesh(tmp_path, monkeypatch, build, first, second):
    with Session("twice"):
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        asm = BUILDS[build]()
        _write(asm, first, tmp_path / "a.msh")
        calls = []
        real = gmsh.model.mesh.generate
        monkeypatch.setattr(gmsh.model.mesh, "generate",
                            lambda *a, **k: calls.append(a) or real(*a, **k))
        _write(asm, second, tmp_path / "b.msh")
        assert calls == []                     # no meshing the second time
        if first == second:
            assert _body(tmp_path / "a.msh") == _body(tmp_path / "b.msh")


@pytest.mark.parametrize("build", BUILDS)
def test_the_openfoam_writer_leaves_the_msh_unchanged(tmp_path, build):
    """Its side effects (interface groups dropped, file options, scale)
    are undone: the .msh written before and after it is the same, byte
    for byte, the recipe block aside."""
    with Session("side_effects"):
        asm = BUILDS[build]()
        asm.write(str(tmp_path / "before.msh"))
        asm.write_openfoam(str(tmp_path / "of.msh"), scale=1e-3)
        asm.write(str(tmp_path / "after.msh"))
    assert _body(tmp_path / "before.msh") == _body(tmp_path / "after.msh")


def test_walls_by_fitting_rewrites_only_the_groups(tmp_path, monkeypatch):
    with Session("walls"):
        asm = _tee()
        asm.write(str(tmp_path / "merged.msh"))
        calls = []
        real = gmsh.model.mesh.generate
        monkeypatch.setattr(gmsh.model.mesh, "generate",
                            lambda *a, **k: calls.append(a) or real(*a, **k))
        asm.write(str(tmp_path / "split.msh"), walls_by_fitting=True)
        assert calls == []
        names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
        assert "fluid_wall" not in names and any(n.startswith("fluid_wall_") for n in names)
        # back to merged walls: the groups again, not duplicated
        asm.write(str(tmp_path / "merged2.msh"))
        groups = [gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()]
        assert "fluid_wall" in groups and len(groups) == len(set(groups))
    assert _body(tmp_path / "merged.msh") == _body(tmp_path / "merged2.msh")


@pytest.mark.parametrize("kw", [{"order": 2}, {"dim": 2}])
def test_other_options_need_a_new_session(tmp_path, kw):
    with Session("other"):
        asm = _bend()
        asm.write(str(tmp_path / "a.msh"))
        with pytest.raises(AssemblyError, match="new session") as e:
            asm.mesh(**kw)
    assert e.value.code == "remesh_with_other_options"
