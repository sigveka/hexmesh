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
The writers' ``scale=`` (task 0150, decision 0047's note of 2026-11-16):
the written nodes are the full-size mesh's times the scale, and nothing
else changes.
"""

import gmsh
import numpy as np
import pytest

from hexmesh import Assembly, PipeSpec, Session, Straight, Tee
from hexmesh.assembly import AssemblyError
from hexmesh.study.openfoam import msh_hexes


def _tee():
    """The README's tee, without its shells and bend."""
    asm = Assembly(PipeSpec(nang=6).core("fluid", radius=0.1, nrad=5, first_cell=0.01),
                   direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.5, n_layers=4))
    main, branch = asm.add(Tee(branch_length=0.3, branch_radius=0.06))
    asm.add(main, Straight(0.5, n_layers=4))
    asm.add(branch, Straight(0.3, n_layers=4))
    return asm


def _write(writer, path, **kw):
    """The tee, built and written in a session of its own (a second write
    in one session would mesh it again); the model's size after it."""
    with Session("scale"):
        asm = _tee()
        if writer == "write":
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)   # what msh_hexes reads
            asm.write(str(path), **kw)
        else:
            asm.write_openfoam(str(path), **kw)
        lo, hi = np.array(gmsh.model.getBoundingBox(-1, -1)).reshape(2, 3)
        assert gmsh.option.getNumber("Mesh.ScalingFactor") == 1.0      # restored
        return asm.cell_count(), float(np.max(hi - lo))


@pytest.mark.parametrize("writer", ["write", "write_openfoam"])
def test_the_nodes_are_the_full_size_mesh_times_the_scale(tmp_path, writer):
    cells, size_full = _write(writer, tmp_path / "full.msh")
    cells_small, size_model = _write(writer, tmp_path / "small.msh", scale=1e-3)
    full, small = msh_hexes(tmp_path / "full.msh"), msh_hexes(tmp_path / "small.msh")
    assert full.shape == small.shape and len(full) == cells == cells_small
    size = np.abs(full).max() * 1e-3
    assert np.abs(small - full * 1e-3).max() <= 1e-15 * size
    assert size_model == size_full                  # the model keeps its size


def test_the_recipe_block_records_the_scale(tmp_path):
    _write("write_openfoam", tmp_path / "small.msh", scale=1e-3)
    _write("write_openfoam", tmp_path / "full.msh")
    assert "scale=0.001" in (tmp_path / "small.msh").read_text(encoding="utf-8")
    assert "scale=" not in (tmp_path / "full.msh").read_text(encoding="utf-8")


@pytest.mark.parametrize("scale", [0, -1.0, float("nan"), float("inf"), True, "1"])
@pytest.mark.parametrize("writer", ["write", "write_openfoam"])
def test_a_scale_that_is_not_positive_and_finite_is_refused(tmp_path, writer, scale):
    with pytest.raises(AssemblyError, match="scale must be a positive") as e:
        getattr(_tee(), writer)(str(tmp_path / "x.msh"), scale=scale)
    assert e.value.code == "value_not_positive"
