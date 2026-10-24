"""
Exact cell count before GMSH (docs/TASKS.md task 3, DESIGN P4).  The kit
checks prediction == mesh for every fitting; these tests cover the
counting rules and the budget.
"""

import gmsh
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Straight, Tee
from hexmesh.assembly.sweep import section_cells
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(nang=4, nrad=3, shells=()):
    s = PipeSpec(nang=nang).core("fluid", CircleShape(radius=0.1, nang=nang), nrad=nrad)
    for i, n in enumerate(shells):
        s = s.shell(f"s{i}", dR=0.02, nrad=n)
    return s


@pytest.mark.parametrize("nang, nrad, shells, expected", [
    (4, 3, (), 4 * 4 + 4 * 4 * 3),
    (6, 4, (2,), 6 * 6 + 4 * 6 * (4 + 2)),
    (8, 5, (2, 3), 8 * 8 + 4 * 8 * (5 + 2 + 3)),
])
def test_section_cells(nang, nrad, shells, expected):
    assert section_cells(_spec(nang, nrad, shells)) == expected


def test_density_scales_cubically():
    """refinement ×2 in every direction ⇒ 8× cells (CLAUDE.md)."""
    def count(f):
        asm = Assembly(_spec(nang=4 * f, nrad=3 * f), lc=0.1)
        asm.add(Straight(0.3, n_layers=3 * f))
        asm.add(Bend(0.3, 90, n_layers=4 * f))
        return asm.cell_count()
    assert count(2) == 8 * count(1)


def test_counts_without_gmsh():
    asm = Assembly(_spec(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Tee(0.2, 0.25, 0.05), names=["m", "b"])
    assert asm.cell_counts() == {0: 912}
    assert not gmsh.isInitialized()


def test_budget():
    asm = Assembly(_spec())
    asm.add(Straight(0.3, n_layers=3))
    asm.add(Bend(0.3, 90, n_layers=10))
    asm.validate(max_cells=asm.cell_count())
    with pytest.raises(AssemblyError, match=r"832 cells, over the budget of 700; "
                                            r"largest is fitting #1 Bend"):
        asm.validate(max_cells=700)
