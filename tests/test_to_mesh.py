"""
``Assembly.to_mesh()``: meshing without a Session (task 0167): the spike's
checks (docs/integrations/gmsh.md), and the design's answers to Q1.
"""

import contextlib
import gc
import importlib
import io
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from hexmesh import ELEMENT_TYPES, Assembly, AssemblyError, Mesh, PipeSpec, Session, Straight
from hexmesh import _gmsh, _occ
from hexmesh._gmsh import gmsh


@pytest.fixture(autouse=True)
def _no_gmsh_left():
    """Each test starts and ends with no gmsh that hexmesh started."""
    yield
    for m in list(_gmsh.open_meshes):
        m.close()
    assert not _gmsh.started()


def _example(name):
    with contextlib.redirect_stdout(io.StringIO()):
        return importlib.import_module("hexmesh.examples." + name).build()


def _pipe(n_layers=2):
    asm = Assembly(PipeSpec(n_arc=4).core("fluid", radius=0.01, n_radial=1)
                   .shell("steel", dR=0.002, n_radial=1))
    asm.add(Straight(0.05, n_layers=n_layers))
    return asm


def _in_session(build, path, **options):
    with Session():
        build().write(str(path), **options)
    return path.read_bytes()


A, B = "fittings.smooth_bend", "fittings.wye"


@pytest.mark.filterwarnings("ignore")
def test_to_mesh_writes_the_bytes_of_a_session(tmp_path):
    """Its .msh and its OpenFOAM .msh and roles are the Session's bytes,
    and so is ``Assembly.write`` outside a Session."""
    expected = _in_session(lambda: _example(A), tmp_path / "s.msh")
    with Session():
        _example(A).write_openfoam(str(tmp_path / "sf.msh"))
    with _example(A).to_mesh() as m:
        m.write(str(tmp_path / "m.msh"))
        m.write_openfoam(str(tmp_path / "mf.msh"))
    _example(A).write(str(tmp_path / "w.msh"))
    assert (tmp_path / "m.msh").read_bytes() == expected
    assert (tmp_path / "w.msh").read_bytes() == expected
    assert (tmp_path / "mf.msh").read_bytes() == (tmp_path / "sf.msh").read_bytes()
    assert ((tmp_path / "mf.roles.json").read_bytes()
            == (tmp_path / "sf.roles.json").read_bytes())


@pytest.mark.filterwarnings("ignore")
def test_interleaved_meshes_write_each_ones_bytes_alone(tmp_path):
    """A second-order mesh and a first-order one, written in turn, give
    the bytes each gives alone: models and gmsh options don't leak."""
    a_alone = _in_session(lambda: _example(A), tmp_path / "a.msh", order=2)
    b_alone = _in_session(lambda: _example(B), tmp_path / "b.msh")
    a, b = _example(A).to_mesh(order=2), _example(B).to_mesh()
    for k in range(2):
        a.write(str(tmp_path / f"a{k}.msh"))
        b.write(str(tmp_path / f"b{k}.msh"))
        assert (tmp_path / f"a{k}.msh").read_bytes() == a_alone
        assert (tmp_path / f"b{k}.msh").read_bytes() == b_alone
    a.close(), b.close()


def test_the_assembly_stays_unmeshed_and_meshes_again_with_other_options():
    asm = _pipe()
    with asm.to_mesh() as one, asm.to_mesh(order=2, incomplete=True) as two:
        assert set(one.cells) >= {"hex8", "quad4"} and "hex20" in two.cells
        assert len(one.cells["hex8"]) == len(two.cells["hex20"]) == asm.cell_count()
    assert not asm._meshed and asm._fill is None
    assert all(i.face is None for i in asm.interfaces)


def test_the_arrays():
    asm = _pipe()
    with asm.to_mesh() as m:
        nodes, cells, groups = m.nodes, m.cells, m.groups
        assert nodes.shape[1] == 3 and not nodes.flags.writeable
        assert set(cells) <= set(ELEMENT_TYPES.values())
        assert m.cell_count == len(cells["hex8"]) == asm.cell_count()
        for c in cells.values():
            assert c.min() >= 0 and c.max() < len(nodes)
        # every hex in exactly one volume group, every boundary row valid
        vols = np.concatenate([g["hex8"] for g in groups.values() if "hex8" in g])
        assert np.array_equal(np.sort(vols), np.arange(len(cells["hex8"])))
        assert set(groups) == {"fluid", "steel", "fluid_inlet", "steel_inlet", "fluid_outlet",
                               "steel_outlet", "steel_wall", "interface_fluid_steel"}
        inlet = cells["quad4"][groups["fluid_inlet"]["quad4"]]
        assert np.allclose(nodes[inlet][..., 0], 0.0)
        # the inlet's quads are hex faces: each one's nodes are a hex's
        hexes = {frozenset(h) for h in cells["hex8"][:, :4]} | {
            frozenset(h) for h in cells["hex8"][:, 4:]}
        assert all(frozenset(q) in hexes for q in inlet)


def test_the_groups_are_the_default_ones_after_a_walls_by_fitting_write(tmp_path):
    with _pipe().to_mesh() as m:
        m.write(str(tmp_path / "w.msh"), walls_by_fitting=True)
        assert "steel_wall" in m.groups


def test_the_callers_model_and_build_are_left_as_they_were(tmp_path):
    """Inside a Session, mid-build: to_mesh leaves the current model and
    hexmesh's build records as they were, and the Session's assembly then
    meshes to the bytes it gives alone."""
    expected = _in_session(_pipe, tmp_path / "alone.msh")
    with Session("mine"):
        asm = _pipe()
        asm.build_faces()
        records = (dict(_occ._ends), dict(_occ._kind))
        entities = gmsh.model.getEntities()
        with _pipe(3).to_mesh() as m:
            assert m.cell_count
        assert gmsh.model.getCurrent() == "mine"
        assert gmsh.model.getEntities() == entities
        assert (dict(_occ._ends), dict(_occ._kind)) == records
        asm.write(str(tmp_path / "after.msh"))
    assert (tmp_path / "after.msh").read_bytes() == expected


def test_a_session_closes_the_meshes_made_in_it_only():
    before = _pipe().to_mesh()
    with Session():
        inside = _pipe().to_mesh()
        assert len(_gmsh.models()) == 4       # "", before's, the session's, inside's
    assert inside.closed and not before.closed
    assert before.cell_count
    before.close()


def test_close_frees_the_model_and_a_closed_mesh_keeps_its_description():
    m = _pipe().to_mesh()
    assert len(_gmsh.models()) == 2
    m.close()
    m.close()                                     # again: nothing
    assert _gmsh.models() == [] and m.closed
    assert m.description["version"]
    for member in ("nodes", "cells", "groups", "cell_count", "dim", "order"):
        with pytest.raises(AssemblyError) as e:
            getattr(m, member)
        assert e.value.code == "mesh_closed"
    with pytest.raises(AssemblyError, match="closed"):
        m.write("x.msh")


def test_gmsh_finalized_under_a_mesh_closes_it(tmp_path):
    """The caller finalizes gmsh under an open Mesh: it raises mesh_closed,
    never a gmsh error, close() is safe, and gmsh the caller then starts
    is the caller's (mesh() runs in it)."""
    m = _pipe().to_mesh()
    gmsh.finalize()
    for member in ("nodes", "cell_count"):
        with pytest.raises(AssemblyError) as e:
            getattr(m, member)
        assert e.value.code == "mesh_closed"
    with pytest.raises(AssemblyError, match="closed"):
        m.write(str(tmp_path / "x.msh"))
    m.close()
    gmsh.initialize()
    try:
        gmsh.model.add("mine")
        asm = _pipe()
        asm.mesh()
        assert asm._meshed and gmsh.model.getCurrent() == "mine"
    finally:
        gmsh.finalize()
    assert not _gmsh.started()


def test_a_mesh_let_go_frees_its_model():
    m = _pipe().to_mesh()
    assert _gmsh.models()
    del m
    gc.collect()
    assert _gmsh.models() == []


def test_repeated_builds_leave_no_model_behind():
    asm = _pipe()
    for _ in range(5):
        with asm.to_mesh():
            assert len(_gmsh.models()) == 2
    assert _gmsh.models() == []


def test_a_mesh_is_not_picklable():
    with _pipe().to_mesh() as m, pytest.raises(AssemblyError) as e:
        pickle.dumps(m)
    assert e.value.code == "mesh_not_picklable"


class _Unregistered(Straight):
    """A fitting ``to_dict`` has no type for."""


def test_an_assembly_without_a_description_meshes(tmp_path):
    asm = Assembly(PipeSpec(n_arc=4).core("fluid", radius=0.01, n_radial=1))
    asm.add(_Unregistered(0.05, n_layers=2))
    with asm.to_mesh() as m:
        assert m.description is None and m.cell_count == asm.cell_count()
        m.write(str(tmp_path / "p.msh"))
    assert b"recipe: not serialisable" in (tmp_path / "p.msh").read_bytes()


def test_a_failed_build_leaves_no_model():
    asm = _pipe()
    with pytest.raises(AssemblyError) as e:
        asm.to_mesh(order=3)
    assert e.value.code == "mesh_order_invalid"
    assert _gmsh.models() == []


def test_mesh_needs_a_session_and_its_hint_names_to_mesh():
    with pytest.raises(AssemblyError) as e:
        _pipe().mesh()
    assert e.value.code == "no_gmsh_session" and "to_mesh()" in e.value.hint


def test_write_openfoam_outside_a_session_checks_before_meshing(tmp_path):
    with pytest.raises(AssemblyError) as e:
        _pipe().write_openfoam(str(tmp_path / "p.msh"), order=2)
    assert e.value.code == "openfoam_needs_order_1"
    assert _gmsh.models() == []


def test_mesh_is_exported():
    assert Mesh.__module__ == "hexmesh.assembly.mesh"
    assert ELEMENT_TYPES[5] == "hex8" and len(set(ELEMENT_TYPES.values())) == len(ELEMENT_TYPES)


# --- gmsh the caller started before hexmesh loaded it (task 0177) ------------
# A fresh process each, so no earlier test's load() can hide it.

_ROOT = Path(__file__).resolve().parents[1]


def _fresh(code: str) -> str:
    head = f"import sys; sys.path.insert(0, {str(_ROOT)!r})\n"
    return subprocess.run([sys.executable, "-c", head + code], capture_output=True,
                          text=True, check=True, cwd=_ROOT).stdout.strip()


@pytest.mark.subprocess
def test_gmsh_the_caller_started_before_hexmesh_loaded_it_meshes():
    out = _fresh(
        "import gmsh\n"
        "gmsh.initialize(); gmsh.option.setNumber('General.Verbosity', 1)\n"
        "from hexmesh import Assembly, PipeSpec, Straight, _gmsh\n"
        "print(_gmsh.caller_drives())\n"
        "asm = Assembly(PipeSpec(n_arc=4).core('fluid', radius=0.01, n_radial=1))\n"
        "asm.add(Straight(0.05, n_layers=2))\n"
        "asm.mesh()\n"
        "print(len(gmsh.model.mesh.getElements(3)[1][0]) == asm.cell_count())\n"
        "gmsh.finalize()\n")
    assert out.splitlines()[-2:] == ["True", "True"], out


@pytest.mark.subprocess
def test_a_process_that_never_imported_gmsh_still_does_not():
    out = _fresh("from hexmesh import _gmsh\n"
                 "print(_gmsh.caller_drives(), _gmsh.models(), 'gmsh' in sys.modules)\n")
    assert out == "False [] False", out
