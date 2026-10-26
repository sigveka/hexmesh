"""
Reducer / expander (docs/tasks/0013).

A reducer changes radii and radial grading only.  Its stations interpolate
the radii (linearly) and the grading (geometrically, decision 0016), and its
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


# --- grading-only changes (decision 0016, task 0027) -------------------------

def _wall_resolved(radius, first_cell=1e-3):
    """Same absolute first cell at the wall: the solved mprg depends on R."""
    return (PipeSpec(nang=8).core("fluid", radius=radius, nrad=8, first_cell=first_cell)
            .shell("wall", dR=0.01, nrad=3))


def test_wall_resolved_reducer(gmsh_session):
    """The use case: pipe(0.1) → pipe(0.06), same absolute first_cell and nrad."""
    a, b = _wall_resolved(0.1), _wall_resolved(0.06)
    assert a._core_mprg != b._core_mprg                       # really a grading change
    asm = Assembly(a, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=4))
    asm.add(Reducer(b, 0.2, n_layers=6))
    asm.add(Straight(0.2, n_layers=4))
    asm.validate()
    asm.mesh()
    _, tags, _ = gmsh.model.mesh.getElements(3)
    assert sum(len(t) for t in tags) == asm.cell_count()
    types, _, _ = gmsh.model.mesh.getElements(3)
    assert list(types) == [5]                                  # all hex
    report = asm.check_quality()
    assert report.ok, str(report)


@pytest.mark.parametrize("u_grading", [1.0, 1.4])
def test_grading_interpolated_per_station(u_grading):
    """mprg_k = mprg_in^(1-u) · mprg_out^u at the radii's fractions u."""
    from hexmesh.assembly.interface import Frame
    a = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3, mprg=1.0).shell("wall", dR=0.02, nrad=2, mprg=1.3)
    b = PipeSpec(nang=4).core("fluid", radius=0.06, nrad=3, mprg=1.5).shell("wall", dR=0.02, nrad=2, mprg=0.8)
    red = Reducer(b, 0.2, n_layers=5, axial_grading=u_grading)
    fa = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])
    fb = red.ports(fa, a)[0][0]
    path = red.path(fa, fb, a)
    u = red.fractions(5)
    for k in range(6):
        spec = path.spec_at(k, a)
        want = [1.0 ** (1 - u[k]) * 1.5 ** u[k], 1.3 ** (1 - u[k]) * 0.8 ** u[k]]
        got = [spec._core_mprg, spec.shells[0].mprg]
        np.testing.assert_allclose(got, want, rtol=1e-14)
        np.testing.assert_allclose(spec.core_shape.radius, 0.1 + (0.06 - 0.1) * u[k], rtol=1e-14)


def test_grading_change_rejects_mbmp():
    """Angular grading stays a class-2 count/grading change without a bridge."""
    a = _spec()
    b = (PipeSpec(nang=4, mbmp=0.6).core("fluid", CircleShape(radius=0.06, nang=4), nrad=3)
         .shell("wall", dR=0.02, nrad=2))
    asm = Assembly(a, lc=0.05)
    asm.add(Reducer(b, 0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=r"mbmp.*switch class 2 beyond radial grading"):
        asm.validate()
