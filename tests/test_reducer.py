"""
Reducer / expander (docs/tasks/0013).

A reducer changes radii only.  Its stations interpolate the radii and its
corners are joined by cone generators, so wall nodes lie on the cone.
"""

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Reducer, Straight
from hexmesh.assembly.interface import outer_radius
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(radius=0.1, dR=0.02, nrad=3, nang=4, rot=0.0, name="wall"):
    return (PipeSpec(nang=nang, rot=rot)
            .core("fluid", CircleShape(radius=radius, nang=nang), nrad=nrad)
            .shell(name, dR=dR, nrad=2))


@pytest.mark.parametrize("r_out", [0.06, 0.15], ids=["reducer", "expander"])
def test_wall_nodes_on_cone(gmsh_session, r_out):
    a, b, L = _spec(), _spec(r_out, 0.015), 0.2
    asm = Assembly(a, direction=[1, 0, 0], up=[0, 0, 1], lc=0.05)
    asm.add(Reducer(b, L, n_layers=4))
    asm.mesh()
    R0, R1 = outer_radius(a), outer_radius(b)
    nodes = []
    for w in asm._fill.walls:
        _, x, _ = gmsh.model.mesh.getNodes(2, w, includeBoundary=True)
        nodes.append(x.reshape(-1, 3))
    x = np.vstack(nodes)
    expected = R0 + (R1 - R0) * x[:, 0] / L          # axis along +x from the origin
    np.testing.assert_allclose(np.hypot(x[:, 1], x[:, 2]), expected, atol=1e-12)


@pytest.mark.parametrize("outlet, field", [
    (_spec(0.06, nrad=4), "core nrad"),
    (_spec(0.06, nang=6), "nang"),
    (_spec(0.06, rot=0.1), "rot"),
    (_spec(0.06, name="steel"), "shells"),
    (PipeSpec(nang=4).core("fluid", CircleShape(radius=0.06, nang=4), nrad=3), "shells"),
])
def test_topology_change_rejected_before_gmsh(outlet, field):
    asm = Assembly(_spec(), lc=0.05)
    asm.add(Reducer(outlet, 0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=f"differs from the inlet in {field}"):
        asm.validate()
    assert not gmsh.isInitialized()


def test_outlet_port_carries_outlet_spec():
    asm = Assembly(_spec(), lc=0.05)
    out = asm.add(Reducer(_spec(0.06, 0.015), 0.2, n_layers=3))
    nxt = asm.add(Straight(0.1, n_layers=2))
    asm.validate()
    assert outer_radius(out.spec) == pytest.approx(0.075)
    assert outer_radius(nxt.spec) == pytest.approx(0.075)
    assert asm.cell_count() == (16 + 4 * 4 * 5) * (3 + 2)
