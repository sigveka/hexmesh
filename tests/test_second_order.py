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
"""Second-order export, ``Assembly.mesh(order=2)`` (task 0076, decision 0034)."""

import importlib
import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh import Assembly, Bend, PipeSpec, Session, Straight, Tee
from hexmesh.assembly import AssemblyError
from hexmesh.examples import ALL

HEX27, HEX20 = 12, 17
R, L, RHO = 0.1, 0.4, 0.3
WYES = {"fittings.wye", "fittings.junction_walls", "sections.insulated_network",
        "networks.bifurcation_tree", "applications.cooling_channels",
        "fittings.equal_tee",   # and the equal tee (task 0122)
        "applications.idealised_aorta"}   # its iliac wye (task 0121)


def _integrate(dim, entities):
    """Σ w·det over Gauss6 points: volume (dim 3) or area (dim 2)."""
    total = 0.0
    for tag in entities:
        for t, tags, _ in zip(*gmsh.model.mesh.getElements(dim, tag)):
            pts, w = gmsh.model.mesh.getIntegrationPoints(int(t), "Gauss6")
            _, det, _ = gmsh.model.mesh.getJacobians(int(t), pts, tag=tag)
            total += float((det.reshape(len(tags), -1) @ np.asarray(w)).sum())
    return total


def _walls():
    return [e for d, t in gmsh.model.getPhysicalGroups(2)
            if gmsh.model.getPhysicalName(d, t).endswith("_wall")
            for e in gmsh.model.getEntitiesForPhysicalGroup(d, t)]


def _spec(k):
    return PipeSpec(nang=4 * k).core("f", radius=R, nrad=2 * k)


def _straight(k):
    a = Assembly(_spec(k))
    a.add(Straight(L, n_layers=2 * k))
    return a


def _bend(k):
    a = Assembly(_spec(k))
    a.add(Bend(RHO, 90, n_layers=4 * k))
    return a


def _tee(k):
    a = Assembly(_spec(k))
    a.add(Straight(0.2, n_layers=2 * k))
    a.add(Tee(branch_length=0.3, branch_radius=0.05, n_run=2 * k, n_branch=2 * k, n_turn=2 * k))
    return a


def _measure(build, k, order):
    with Session("order2"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm = build(k)
        asm.mesh(order=order)
        return _integrate(3, [t for _, t in gmsh.model.getEntities(3)]), _integrate(2, _walls())


def _orders(err):
    return [math.log(err[i] / err[i + 1], 2) for i in range(len(err) - 1)]


# --- examples ---------------------------------------------------------------------

@pytest.mark.parametrize("name", ALL)
def test_every_example_meshes_at_order_2(name):
    """Valid Hex27 everywhere (``mesh`` checks every hex at its nodes and
    Gauss points), except the wye and the equal tee, rejected before meshing."""
    asm = importlib.import_module(f"hexmesh.examples.{name}").build()
    with Session(name), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if name in WYES:
            with pytest.raises(AssemblyError, match="order=2 is not supported") as info:
                asm.mesh(order=2)
            assert info.value.code == "second_order_unsupported"
            assert not gmsh.model.mesh.getNodes()[0].size        # rejected before meshing
            return
        asm.mesh(order=2)
        types = {int(t) for t in gmsh.model.mesh.getElementTypes(3)}
        assert types == {HEX27} and asm.mesh_order == 2
        assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == asm.cell_count()


# --- convergence (step 5) ---------------------------------------------------------

@pytest.mark.parametrize("build, volume, area", [
    (_straight, math.pi * R * R * L, 2 * math.pi * R * L),
    (_bend, math.pi * R * R * RHO * math.pi / 2, 2 * math.pi * R * RHO * math.pi / 2),
], ids=["straight", "bend"])
def test_volume_and_area_converge_at_order_4(build, volume, area):
    """Linear: about h²; order 2: about h⁴ (measured 4.00), gated at 3.5."""
    for order, gate in ((1, (1.8, 2.3)), (2, (3.5, 4.5))):
        m = [_measure(build, k, order) for k in (1, 2, 4)]
        for i, exact in ((0, volume), (1, area)):
            p = _orders([abs(x[i] / exact - 1) for x in m])
            assert all(gate[0] <= q <= gate[1] for q in p), (order, i, p)


def test_tee_converges_faster_at_order_2():
    """No closed form: the observed order from three levels (successive
    differences), order 2's at least 1 above linear's (measured 3.99 and
    1.99 for volume, 3.98 and 2.00 for area)."""
    out = {}
    for order in (1, 2):
        m = [_measure(_tee, k, order) for k in (1, 2, 4)]
        out[order] = [math.log(abs(m[1][i] - m[0][i]) / abs(m[2][i] - m[1][i]), 2)
                      for i in (0, 1)]
    for i in (0, 1):
        assert out[2][i] >= out[1][i] + 1, out


# --- details ----------------------------------------------------------------------

def test_projected_wall_nodes_are_on_the_analytic_wall():
    """A tee's high-order wall nodes are projected too: on its tube union
    to round-off (gmsh alone leaves them ~1e-3 R off, on the OCC surface)."""
    with Session("tee"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        asm = _tee(1)
        asm.mesh(order=2)
        (project, surfs), = [p for e in asm.edges
                             for p in asm._fitting_projections.get(e.index, [])]
        tags = {int(n) for s in surfs for t, _, ns in zip(*gmsh.model.mesh.getElements(2, s))
                for n in ns}
        x = np.array([gmsh.model.mesh.getNode(t)[0] for t in sorted(tags)])
        assert np.abs(project.signed_distance(x)).max() < 1e-10 * R


def test_bend_high_order_nodes_are_exact():
    """Interior axial edges of a bend lie on its arcs: every node of the
    torus wall is at distance R from the bend's centreline circle."""
    with Session("bend"):
        asm = _bend(1)
        asm.mesh(order=2)
        x = np.array([gmsh.model.mesh.getNode(int(n))[0] for e in _walls()
                      for n in gmsh.model.mesh.getNodes(2, e, includeBoundary=True)[0]])
    path = asm.edges[0].fitting.path(asm.edges[0].ports[0].frame, asm.edges[0].ports[1].frame,
                                     asm.edges[0].ports[0].spec)
    axis = path.axial.axis / np.linalg.norm(path.axial.axis)
    r = x - path.axial.centre
    h = r @ axis
    rho = np.linalg.norm(r - np.outer(h, axis), axis=1)
    np.testing.assert_allclose(np.hypot(rho - RHO, h), R, atol=1e-12)


def test_incomplete_gives_hex20():
    with Session("hex20"):
        asm = _straight(1)
        asm.mesh(order=2, incomplete=True)
        assert {int(t) for t in gmsh.model.mesh.getElementTypes(3)} == {HEX20}
        assert gmsh.option.getNumber("Mesh.SecondOrderIncomplete") == 0     # restored


@pytest.mark.parametrize("version", [2.2, 4.1])
def test_msh_carries_hex27_and_groups(tmp_path, version):
    path = tmp_path / f"bend{version}.msh"
    with Session("write"):
        asm = _bend(1)
        gmsh.option.setNumber("Mesh.MshFileVersion", version)
        asm.write(str(path), order=2)
        groups = sorted(gmsh.model.getPhysicalName(d, t)
                        for d, t in gmsh.model.getPhysicalGroups())
    assert b"order=2 incomplete=False" in path.read_bytes()
    with Session("read"):
        gmsh.open(str(path))
        assert {int(t) for t in gmsh.model.mesh.getElementTypes(3)} == {HEX27}
        back = sorted(gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups())
    assert back == groups and {"f_inlet", "f_outlet", "f_wall"} <= set(groups)


def test_write_openfoam_refuses_order_2(tmp_path):
    with Session("foam"):
        with pytest.raises(AssemblyError, match="first-order meshes only") as info:
            _straight(1).write_openfoam(str(tmp_path / "x.msh"), order=2)
    assert info.value.code == "openfoam_needs_order_1"


@pytest.mark.parametrize("kw, code", [({"order": 3}, "mesh_order_invalid"),
                                      ({"order": 2, "dim": 2}, "mesh_order_needs_volume")])
def test_bad_order_arguments(kw, code):
    with Session("bad"):
        with pytest.raises(AssemblyError) as info:
            _straight(1).mesh(**kw)
    assert info.value.code == code
