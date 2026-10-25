"""
Material-interface group names (decision 0013, docs/tasks/0022).

hexmesh names interface groups ``interface_<inner>_<outer>``, never
``<a>_to_<b>``: those are the names OpenFOAM's ``splitMeshRegions`` gives
its own ``mappedWall`` patches.
"""

import gmsh
import pytest

from hexmesh.core.cross_section import interface_group_name
from hexmesh.core.spec import PipeSpec

from test_fitting_conformance import CASES, _session


def _layers(case):
    return len(CASES[case]().inlet.spec.layer_names)


MULTI = [c for c in CASES if _layers(c) > 1]


def test_some_kit_cases_have_several_layers():
    assert len(MULTI) >= 5


@pytest.mark.parametrize("case", MULTI)
def test_no_to_names_in_kit_cases(case):
    _session()
    try:
        asm = CASES[case]()
        asm.mesh()
        names = [gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()]
        assert not [n for n in names if "_to_" in n]
        layers = asm.inlet.spec.layer_names
        want = {interface_group_name(a, b) for a, b in zip(layers, layers[1:])}
        assert want <= set(names)
    finally:
        gmsh.finalize()


def test_helper_is_inner_then_outer():
    assert interface_group_name("fluid", "steel") == "interface_fluid_steel"


@pytest.mark.parametrize("bad", ["fluid-1", "steel wall", "", "ü", None])
def test_layer_names_restricted(bad):
    with pytest.raises(ValueError, match="letters, digits"):
        PipeSpec(nang=4).core(bad, radius=0.1, nrad=2)
    with pytest.raises(ValueError, match="letters, digits"):
        PipeSpec(nang=4).core("fluid", radius=0.1, nrad=2).shell(bad, dR=0.01, nrad=1)
