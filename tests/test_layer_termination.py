"""
Layer termination in sweeps: insulation stops and starts (decision 0006,
docs/tasks/0018).
"""

import gmsh
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight
from hexmesh.core.spec import PipeSpec


def _bare(nrad=2, mprg=None, dR=0.01, r=0.1):
    return (PipeSpec(nang=4).core("fluid", radius=r, nrad=3)
            .shell("pipe_wall", dR=dR, nrad=nrad, mprg=mprg))


def _ins(**kw):
    return _bare(**kw).shell("insulation", dR=0.03, nrad=2)


def _gap(fitting=None):
    asm = Assembly(_ins(), lc=0.05)
    asm.add(Straight(0.2, n_layers=2))
    asm.add(fitting or Straight(1.0, n_layers=10,
                                stack_changes=((3, _bare()), (7, _ins()))))
    asm.add(Straight(0.2, n_layers=2))
    return asm


# ---------------------------------------------------------------------------
# Validation (no GMSH)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("change, match", [
    # a middle layer cannot stop
    (PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3).shell("insulation", dR=0.03, nrad=2),
     r"Straight: stack change at cell 3: only outermost layers may stop or start; "
     r"`pipe_wall` is not outermost"),
    (_bare(nrad=4), r"Straight: stack change at cell 3: the remaining layers must match "
                    r"\(shell `pipe_wall` nrad \(2 vs 4\)\); use a Reducer"),
    (_bare(mprg=1.2), r"remaining layers must match \(shell `pipe_wall` mprg \(1.0 vs 1.2\)\)"),
    (_bare(dR=0.02), r"remaining layers must match \(`pipe_wall` radius 0.01 vs 0.02\)"),
    (_bare(r=0.12), r"remaining layers must match \(`fluid` radius 0.1 vs 0.12\)"),
    (_ins(), r"keeps the layers"),
])
def test_invalid_stack_change_rejected_before_gmsh(change, match):
    asm = _gap(Straight(1.0, n_layers=10, stack_changes=((3, change),)))
    with pytest.raises(AssemblyError, match=match):
        asm.validate()
    assert not gmsh.isInitialized()


@pytest.mark.parametrize("cells", [(0,), (10,), (5, 3), (4, 4)])
def test_changes_inside_the_fitting_only(cells):
    asm = _gap(Straight(1.0, n_layers=10, stack_changes=tuple((i, _bare()) for i in cells)))
    with pytest.raises(AssemblyError, match="increasing cell boundaries 1 … 9"):
        asm.validate()


def test_ports_and_cell_count_follow_the_stack():
    asm = Assembly(_ins(), lc=0.05)
    out = asm.add(Bend(0.5, 90, n_layers=8, stack_changes=((5, _bare()),)))
    assert out.spec.layer_names == ["fluid", "pipe_wall"]
    # 5 cells of 3 layers + 3 cells of 2: 4×4 core + 4·4·(3+2[+2]) per section
    assert asm.cell_count() == 5 * (16 + 16 * 7) + 3 * (16 + 16 * 5)
    assert type(asm.cell_count()) is int        # JSON-serialisable (task 0048)


def test_gap_saved_and_loaded():
    asm = _gap()
    back = Assembly.from_dict(asm.to_dict())
    assert back.to_dict() == asm.to_dict()                  # PipeSpec has no __eq__
    assert [n for _, sp in back.edges[1].fitting.stack_changes
            for n in sp.layer_names[-1:]] == ["pipe_wall", "insulation"]
    assert back.cell_count() == asm.cell_count()


# ---------------------------------------------------------------------------
# Realisation
# ---------------------------------------------------------------------------

def _groups():
    out = {}
    for d, t in gmsh.model.getPhysicalGroups(2):
        out[gmsh.model.getPhysicalName(d, t)] = list(gmsh.model.getEntitiesForPhysicalGroup(d, t))
    return out


@pytest.mark.usefixtures("gmsh_session")
@pytest.mark.parametrize("fitting", [
    Straight(1.0, n_layers=10, stack_changes=((3, _bare()), (7, _ins()))),
    Bend(0.5, 90, n_layers=8, stack_changes=((2, _bare()), (6, _ins()))),
], ids=["straight", "bend"])
def test_insulation_gap_meshes(fitting):
    asm = _gap(fitting)
    asm.mesh()
    types, tags, _ = gmsh.model.mesh.getElements(3)
    assert list(types) == [5]                                   # all hex
    assert sum(len(t) for t in tags) == asm.cell_count()
    g = _groups()
    assert len(g["insulation_end"]) == 2 * 4                    # 2 × patches per gap
    surfaces = [s for tags in g.values() for s in tags]
    assert len(surfaces) == len(set(surfaces))                  # one group each
    # the bare stretch: pipe_wall is the wall, and no insulation interface
    assert len(g["pipe_wall_wall"]) == 4 * (1 if isinstance(fitting, Straight) else 4)
    assert set(g["pipe_wall_wall"]).isdisjoint(g["interface_pipe_wall_insulation"])
    assert asm.group_roles()["insulation_end"] == "wall"


@pytest.mark.usefixtures("gmsh_session")
def test_end_walls_by_fitting():
    asm = _gap()
    asm.mesh(walls_by_fitting=True)
    g = _groups()
    assert len(g["insulation_end_Straight1"]) == 8
    assert len(g["pipe_wall_wall_Straight1"]) == 4
    assert "insulation_end" not in g and "insulation_wall" not in g


@pytest.mark.usefixtures("gmsh_session")
def test_uniform_stack_unchanged():
    """No stack changes: one slab, one wall group, as before."""
    asm = Assembly(_ins(), lc=0.05)
    asm.add(Straight(1.0, n_layers=10))
    path = asm.edges[0].fitting.path(*[p.frame for p in asm.edges[0].ports], _ins())
    assert path.layers == [10] and path.fill is None
    asm.mesh()
    roles = asm.group_roles()
    assert {k for k, r in roles.items() if r == "wall"} == {"insulation_wall"}
