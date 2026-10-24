"""
Tests for the interface-first assembly prototype (DESIGN.md §4–§6).

Each test targets one design rule:

* Topology/validation runs without GMSH (principles 3, 4)
* Quality matches the legacy Network pipeline for the same geometry
* Conformal by construction: no coincident hex nodes, no node merging (P2)
* Fill order is irrelevant (A6)
* Physical groups come from the graph, one group per surface (A7)
* Loops close between existing interfaces, absorbing residual twist (§8)
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Bend, Closure, Frame, Straight
from hexmesh.assembly.interface import roll_mismatch
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec
from hexmesh.quality_hex import evaluate_hex_quality


def _one_layer():
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)


def _two_layer():
    return _one_layer().shell("wall", dR=0.025, nrad=2)


def _sbs(spec, angle=90.0, roll=0.0):
    """Straight → Bend → Straight along +Y with up = +Z."""
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Bend(radius=0.3, angle=angle, n_layers=6, roll=roll))
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _all_vols(asm):
    return [v for vs in asm.volumes.values() for v in vs]


def _hex_node_coords():
    _, _, enodes = gmsh.model.mesh.getElements(3)
    used = np.unique(np.concatenate(enodes))
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    lookup = dict(zip(tags, xyz.reshape(-1, 3)))
    return np.round(np.array([lookup[t] for t in used]), 9)


def _full_check(asm):
    asm.mesh()
    report = asm.check_quality()
    assert report.ok, str(report)
    q = evaluate_hex_quality(_all_vols(asm), name="all")
    assert q is not None and int((q.mean_ratio_min == 0).sum()) == 0, str(q)


# ---------------------------------------------------------------------------
# Topology layer — no GMSH session
# ---------------------------------------------------------------------------

class TestTopologyWithoutGmsh:
    def test_placement_is_analytic(self):
        asm = _sbs(_one_layer())
        out = asm.interfaces[-1].frame
        # 0.2 straight, 90° bend of R=0.3 toward +Z, 0.2 straight
        np.testing.assert_allclose(out.position, [0, 0.5, 0.5], atol=1e-12)
        np.testing.assert_allclose(out.normal, [0, 0, 1], atol=1e-12)

    def test_validate_passes_without_gmsh(self):
        assert not gmsh.isInitialized()
        _sbs(_one_layer()).validate()
        assert not gmsh.isInitialized()

    def test_bend_radius_rejected_before_gmsh(self):
        asm = Assembly(_two_layer())
        asm.add(Straight(0.2, n_layers=2))
        asm.add(Bend(radius=0.12, angle=90, n_layers=4))
        with pytest.raises(AssemblyError, match=r"fitting #1 .*Bend.*outer radius"):
            asm.validate()
        assert not gmsh.isInitialized()

    def test_port_type_mismatch_rejected(self):
        """An interface whose type differs from what its fitting declares
        (here: a closure joining two different pipes) is rejected."""
        asm = Assembly(_one_layer(), up=[0, 0, 1])
        for _ in range(3):
            asm.add(Straight(0.6, n_layers=3))
            asm.add(Bend(radius=0.3, angle=90, n_layers=4, roll=90))
        tail = asm.interfaces[-1]
        tail.spec = PipeSpec(nang=6).core("fluid", CircleShape(radius=0.1, nang=6), nrad=3)
        asm.close(tail, asm.inlet, Closure(n_layers=8))
        with pytest.raises(AssemblyError, match="port type"):
            asm.validate()

    def test_empty_assembly_rejected(self):
        with pytest.raises(AssemblyError, match="no fittings"):
            Assembly(_one_layer()).validate()

    def test_frame_up_is_orthogonalised(self):
        f = Frame.from_vectors([0, 0, 0], [1, 0, 0], [1, 0, 1])
        assert abs(np.dot(f.normal, f.up)) < 1e-12


# ---------------------------------------------------------------------------
# Realisation
# ---------------------------------------------------------------------------

class TestQuality:
    @pytest.mark.parametrize("angle", [45.0, 90.0, -60.0])
    def test_single_layer(self, gmsh_session, angle):
        _full_check(_sbs(_one_layer(), angle=angle))

    def test_two_layer(self, gmsh_session):
        _full_check(_sbs(_two_layer()))

    def test_rolled_bend(self, gmsh_session):
        _full_check(_sbs(_one_layer(), roll=90.0))

    def test_s_curve(self, gmsh_session):
        asm = Assembly(_one_layer(), direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
        asm.add(Straight(0.2, n_layers=2))
        asm.add(Bend(radius=0.3, angle=45, n_layers=4))
        asm.add(Straight(0.1, n_layers=2))
        asm.add(Bend(radius=0.3, angle=-45, n_layers=4))
        asm.add(Straight(0.2, n_layers=2))
        _full_check(asm)

    def test_bend_outlet_on_true_arc(self, gmsh_session):
        """Bend wall nodes lie exactly on the torus."""
        asm = Assembly(_one_layer(), lc=0.1)
        asm.add(Bend(radius=0.3, angle=90, n_layers=6))
        asm.mesh()
        tags = asm._fill.walls
        centre = np.array([0, 0, 0.3])          # bend centre, axis = +Y
        for s in tags:
            _, xyz, _ = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)
            p = xyz.reshape(-1, 3) - centre
            ring = np.hypot(p[:, 0], p[:, 2]) - 0.3   # distance from centreline circle
            tube = np.hypot(ring, p[:, 1])
            np.testing.assert_allclose(tube, 0.1, atol=1e-9)


class TestConformalByConstruction:
    def test_no_coincident_hex_nodes(self, gmsh_session):
        asm = _sbs(_two_layer())
        asm.mesh()
        c = _hex_node_coords()
        assert len(c) == len(np.unique(c, axis=0))

    def test_no_stray_nodes(self, gmsh_session):
        asm = _sbs(_one_layer())
        asm.mesh()
        _, _, enodes = gmsh.model.mesh.getElements(3)
        tags, _, _ = gmsh.model.mesh.getNodes()
        assert set(tags) == set(np.unique(np.concatenate(enodes)))

    def test_each_interface_face_built_once(self, gmsh_session):
        asm = _sbs(_one_layer())
        asm.build()
        surfs = [s for i in asm.interfaces for _, cs in i.face.layers for s in cs.surfaces]
        assert len(surfs) == len(set(surfs))
        # Interior interfaces are shared by exactly two fittings
        assert [len(i.edges) for i in asm.interfaces] == [1, 2, 2, 1]


class TestOrderIndependence:
    def _mesh(self, order):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("order")
        try:
            asm = _sbs(_two_layer())
            asm.build(order)
            asm.mesh()
            c = _hex_node_coords()
            n = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
            return n, c[np.lexsort(c.T)]
        finally:
            gmsh.finalize()

    def test_reverse_order_gives_identical_mesh(self):
        n_a, c_a = self._mesh([0, 1, 2])
        n_b, c_b = self._mesh([2, 0, 1])
        assert n_a == n_b
        np.testing.assert_allclose(c_a, c_b, atol=1e-9)

    def test_order_must_be_permutation(self, gmsh_session):
        with pytest.raises(AssemblyError, match="permutation"):
            _sbs(_one_layer()).build([0, 1])


class TestPhysicalGroups:
    def _groups(self):
        return {
            gmsh.model.getPhysicalName(d, t): (d, t)
            for d, t in gmsh.model.getPhysicalGroups()
        }

    def test_two_layer_names(self, gmsh_session):
        asm = _sbs(_two_layer())
        asm.mesh()
        assert set(self._groups()) == {
            "fluid", "wall",
            "fluid_inlet", "wall_inlet", "fluid_outlet", "wall_outlet",
            "wall_wall", "fluid_to_wall",
        }

    def test_each_surface_in_one_group(self, gmsh_session):
        asm = _sbs(_two_layer())
        asm.mesh()
        seen: dict[int, str] = {}
        for name, (d, t) in self._groups().items():
            if d != 2:
                continue
            for s in gmsh.model.getEntitiesForPhysicalGroup(d, t):
                assert s not in seen, f"surface {s} in {seen.get(s)} and {name}"
                seen[s] = name

    def test_named_outlet(self, gmsh_session):
        asm = Assembly(_one_layer(), inlet_name="supply")
        asm.add(Straight(0.2, n_layers=2), names=["drain"])
        asm.mesh()
        assert {"fluid_supply", "fluid_drain"} <= set(self._groups())


# ---------------------------------------------------------------------------
# Loop closure (DESIGN.md §8)
# ---------------------------------------------------------------------------

def _chain(rolls, side=0.6):
    """Inlet, then (Straight → Bend(roll)) per roll; open tail returned."""
    asm = Assembly(_one_layer(), up=[0, 0, 1], lc=0.1)
    for r in rolls:
        asm.add(Straight(side, n_layers=3))
        asm.add(Bend(radius=0.3, angle=90, n_layers=4, roll=r))
    return asm


def _tail(asm):
    return asm.interfaces[-1]


def _assert_closed_and_conformal(asm):
    assert asm.open_interfaces() == []
    assert all(len(i.edges) == 2 for i in asm.interfaces)
    c = _hex_node_coords()
    assert len(c) == len(np.unique(c, axis=0))


class TestLoopClosure:
    def test_ring_closed_by_closure(self, gmsh_session):
        asm = _chain([90, 90, 90])
        asm.close(_tail(asm), asm.inlet, Closure(n_layers=8))
        _full_check(asm)
        _assert_closed_and_conformal(asm)
        names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups()}
        assert names == {"fluid", "fluid_wall"}

    def test_ring_closed_by_exact_bend(self, gmsh_session):
        """Any fitting closes a loop if it validates — here a plain Bend."""
        asm = _chain([90, 90, 90])
        asm.add(Straight(0.6, n_layers=3))
        asm.close(_tail(asm), asm.inlet, Bend(radius=0.3, angle=90, n_layers=4, roll=90))
        _full_check(asm)
        _assert_closed_and_conformal(asm)

    def test_twisted_closure(self, gmsh_session):
        """Non-planar loop: closure absorbs the frame mismatch (holonomy)."""
        asm = _chain([60, 0])
        asm.add(Straight(0.6, n_layers=3))
        tail = _tail(asm)
        _, twist = Closure(12).stations(tail.frame, asm.inlet.frame, 4)
        assert abs(math.degrees(twist)) > 10
        asm.close(tail, asm.inlet, Closure(n_layers=12))
        _full_check(asm)
        _assert_closed_and_conformal(asm)

    def test_closure_station_frames(self):
        asm = _chain([60, 0])
        asm.add(Straight(0.6, n_layers=3))
        a, b = _tail(asm).frame, asm.inlet.frame
        frames, _ = Closure(12).stations(a, b, 4)
        assert len(frames) == 13
        for f in frames:
            assert abs(np.dot(f.normal, f.up)) < 1e-12
        # Arrives on the target with zero residual roll (mod 90°)
        assert abs(roll_mismatch(frames[-1].up, b.up, b.normal, 4)) < 1e-9


class TestLoopValidation:
    def test_tight_closure_rejected_before_gmsh(self):
        asm = _chain([90, 0])
        asm.add(Straight(0.6, n_layers=3))
        asm.close(_tail(asm), asm.inlet, Closure(n_layers=12))
        with pytest.raises(AssemblyError, match=r"Closure.*tighter than the pipe"):
            asm.validate()
        assert not gmsh.isInitialized()

    def test_wrong_length_straight_closer_rejected(self):
        asm = _chain([90, 90, 90])
        asm.add(Straight(0.6, n_layers=3))
        asm.add(Bend(radius=0.3, angle=90, n_layers=4, roll=90))
        asm.close(_tail(asm), asm.inlet, Straight(0.5, n_layers=3))
        with pytest.raises(AssemblyError, match="does not match Straight geometry"):
            asm.validate()

    def test_closure_cannot_be_added(self):
        with pytest.raises(TypeError, match="Assembly.close"):
            Assembly(_one_layer()).add(Closure(n_layers=4))

    def test_close_requires_open_interfaces(self):
        asm = _chain([90])
        inner = asm.interfaces[1]
        with pytest.raises(AssemblyError, match="not an open interface"):
            asm.close(_tail(asm), inner, Closure(n_layers=4))

    def test_close_checks_flow_direction(self):
        asm = _chain([90])
        with pytest.raises(AssemblyError, match="upstream end"):
            asm.close(asm.inlet, _tail(asm), Closure(n_layers=4))

    def test_add_after_closing_tail_needs_source(self):
        asm = _chain([90, 90, 90])
        asm.close(_tail(asm), asm.inlet, Closure(n_layers=8))
        with pytest.raises(AssemblyError, match="tail was closed"):
            asm.add(Straight(0.2, n_layers=2))
