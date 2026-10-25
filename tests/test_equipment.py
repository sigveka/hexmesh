"""
Equipment nozzles as network boundaries (decision 0002, docs/tasks/0010).

Frames and validation are pure Python; one realisation test meshes a
network that starts at a drum nozzle.
"""

import json
import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import (
    Assembly, AssemblyError, Bend, Drum, EquipmentError, Nozzle, OnHead, OnShell, Straight,
)
from hexmesh.core.spec import PipeSpec

S2 = math.sqrt(0.5)


def _spec(r=0.1):
    return PipeSpec(nang=4).core("fluid", radius=r, nrad=3)


def _horizontal(*nozzles, **kw):
    """D = 2, tangent length 6, along +x from the origin, up +z."""
    return Drum("D101", 2.0, 6.0, nozzles=nozzles, **kw)


def _vertical(*nozzles, **kw):
    """D = 3, tangent length 8, from (1, 2, 3) up +z, angles from +x."""
    return Drum("V201", 3.0, 8.0, position=(1, 2, 3), axis=(0, 0, 1), up=(1, 0, 0),
                nozzles=nozzles, **kw)


def _close(f, position, normal, up):
    for got, want in ((f.position, position), (f.normal, normal), (f.up, up)):
        np.testing.assert_allclose(got, want, atol=1e-12, rtol=0)


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

class TestHorizontalDrum:
    def test_top_shell_nozzle(self):
        d = _horizontal(Nozzle("N1", _spec(), OnShell(axial=1.5, angle=0, projection=1.4)))
        _close(d.frame("N1"), [1.5, 0, 1.4], [0, 0, 1], [1, 0, 0])

    def test_side_shell_nozzle(self):
        # +90° about +x from +z is -y (right-handed: x × z = -y)
        d = _horizontal(Nozzle("N2", _spec(), OnShell(4.0, 90, 1.25)))
        _close(d.frame("N2"), [4.0, -1.25, 0], [0, -1, 0], [1, 0, 0])

    def test_oblique_shell_nozzle(self):
        d = _horizontal(Nozzle("N3", _spec(), OnShell(3.0, 225, 1.5)))
        _close(d.frame("N3"), [3.0, 1.5 * S2, -1.5 * S2], [0, S2, -S2], [1, 0, 0])

    def test_head_nozzles(self):
        d = _horizontal(Nozzle("H1", _spec(), OnHead("first", 0.0, 0, 0.8)),
                        Nozzle("H2", _spec(), OnHead("second", 0.5, 180, 0.6)))
        _close(d.frame("H1"), [-0.8, 0, 0], [-1, 0, 0], [0, 0, 1])     # centred: drum up
        _close(d.frame("H2"), [6.6, 0, -0.5], [1, 0, 0], [0, 0, -1])   # radial direction


class TestVerticalDrum:
    def test_shell_nozzle(self):
        d = _vertical(Nozzle("N1", _spec(), OnShell(2.0, 90, 2.0)))
        # +90° about +z from +x is +y
        _close(d.frame("N1"), [1, 4, 5], [0, 1, 0], [0, 0, 1])

    def test_top_and_bottom_head(self):
        d = _vertical(Nozzle("T", _spec(), OnHead("second", 0.6, 0, 1.0)),
                      Nozzle("B", _spec(), OnHead("first", 0.0, 0, 1.2)))
        _close(d.frame("T"), [1.6, 2, 12], [0, 0, 1], [1, 0, 0])
        _close(d.frame("B"), [1, 2, 1.8], [0, 0, -1], [1, 0, 0])

    @pytest.mark.parametrize("angle", [0, 37, 90, 151, 270, 333])
    def test_shell_face_at_projection_from_axis(self, angle):
        d = _vertical(Nozzle("N", _spec(), OnShell(3.3, angle, 1.9)))
        f = d.frame("N")
        rel = f.position - np.array([1, 2, 3])
        radial = rel - np.dot(rel, [0, 0, 1]) * np.array([0, 0, 1])
        assert np.linalg.norm(radial) == pytest.approx(1.9, abs=1e-12)
        assert np.dot(f.normal, f.up) == pytest.approx(0, abs=1e-15)
        np.testing.assert_allclose(f.normal, radial / 1.9, atol=1e-12)


def test_up_made_perpendicular_to_axis():
    d = Drum("D", 2.0, 4.0, axis=(0, 0, 2), up=(1, 0, 1),
             nozzles=[Nozzle("N", _spec(), OnShell(1.0, 0, 1.5))])
    _close(d.frame("N"), [1.5, 0, 1.0], [1, 0, 0], [0, 0, 1])


# ---------------------------------------------------------------------------
# Heads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("head, kw, depth", [
    ("ellipsoidal_2_1", {}, 0.5),                     # D/4
    ("hemispherical", {}, 1.0),                       # D/2
    ("torispherical", dict(crown_radius=2.0, knuckle_radius=0.2),
     2.0 - math.sqrt(1.8 ** 2 - 0.8 ** 2)),
])
def test_head_depth_and_edge(head, kw, depth):
    d = Drum("D", 2.0, 4.0, head=head, **kw)
    assert d.head_height(0.0) == pytest.approx(depth, abs=1e-12)
    assert d.head_height(1.0) == pytest.approx(0.0, abs=1e-6)


def test_torispherical_junction_is_smooth():
    d = Drum("D", 2.0, 4.0, head="torispherical", crown_radius=2.0, knuckle_radius=0.2)
    j, e = d.crown_limit, 1e-6
    assert d.head_height(j - 1e-12) == pytest.approx(d.head_height(j + 1e-12), abs=1e-9)
    slope_in = (d.head_height(j) - d.head_height(j - e)) / e
    slope_out = (d.head_height(j + e) - d.head_height(j)) / e
    assert slope_in == pytest.approx(slope_out, abs=1e-4)


def test_torispherical_needs_both_radii():
    with pytest.raises(EquipmentError, match="no default"):
        Drum("D", 2.0, 4.0, head="torispherical", crown_radius=2.0)
    with pytest.raises(EquipmentError, match="knuckle_radius < D/2 < crown_radius"):
        Drum("D", 2.0, 4.0, head="torispherical", crown_radius=0.9, knuckle_radius=0.2)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_valid_drum_passes():
    _horizontal(Nozzle("N1", _spec(), OnShell(1.0, 0, 1.2)),
                Nozzle("N2", _spec(), OnShell(1.0, 180, 1.2)),
                Nozzle("N3", _spec(), OnShell(1.25, 0, 1.2)),   # 0.25 apart > 0.2: clear
                Nozzle("H1", _spec(), OnHead("first", 0.0, 0, 0.6)),
                Nozzle("H2", _spec(), OnHead("first", 0.5, 90, 0.5))).validate()


@pytest.mark.parametrize("nozzle, message", [
    (Nozzle("N1", _spec(), OnShell(2.0, 0, 1.0)), "N1: projection"),        # face on the shell
    (Nozzle("N1", _spec(), OnShell(2.0, 0, 0.9)), "N1: projection"),        # inside
    (Nozzle("N1", _spec(1.0), OnShell(2.0, 0, 2.0)), "N1: outer radius"),   # oversized
    (Nozzle("N1", _spec(), OnShell(0.05, 0, 1.5)), "N1: footprint"),        # over a tangent line
    (Nozzle("H1", _spec(), OnHead("first", 0.0, 0, 0.5)), "H1: projection"),  # at crown height
    (Nozzle("H1", _spec(), OnHead("first", 0.95, 0, 1.0)), "H1: footprint"),  # off the head
    (Nozzle("H1", _spec(), OnHead("third", 0.0, 0, 1.0)), "H1: head must be"),
])
def test_invalid_nozzle_named(nozzle, message):
    with pytest.raises(EquipmentError, match=f"drum D101, nozzle {message}"):
        _horizontal(nozzle).validate()


def test_head_face_checked_over_the_whole_footprint():
    """An off-centre face clears the head at its centre but not at its inner edge."""
    d = _horizontal(Nozzle("H1", _spec(0.2), OnHead("first", 0.5, 0, 0.45)))
    assert d.head_height(0.5) < 0.45 < d.head_height(0.3)
    with pytest.raises(EquipmentError, match="H1: projection"):
        d.validate()


def test_torispherical_nozzle_must_stay_in_the_crown():
    kw = dict(head="torispherical", crown_radius=2.0, knuckle_radius=0.2)
    _horizontal(Nozzle("H1", _spec(), OnHead("second", 0.75, 0, 0.6)), **kw).validate()
    with pytest.raises(EquipmentError, match="leaves the crown region"):
        _horizontal(Nozzle("H1", _spec(), OnHead("second", 0.82, 0, 0.6)), **kw).validate()


@pytest.mark.parametrize("a, b", [
    (OnShell(2.0, 0, 1.5), OnShell(2.15, 0, 1.5)),       # axial neighbours
    (OnShell(2.0, 0, 1.5), OnShell(2.0, 10, 1.5)),       # around the shell
    (OnShell(2.0, 355, 1.5), OnShell(2.0, 5, 1.5)),      # across 0°
    (OnShell(2.0, 0, 1.5), OnShell(2.0, 0, 1.8)),        # same spot
])
def test_overlapping_shell_nozzles(a, b):
    with pytest.raises(EquipmentError, match="nozzles N1 and N2 overlap"):
        _horizontal(Nozzle("N1", _spec(), a), Nozzle("N2", _spec(), b)).validate()


def test_overlapping_head_nozzles():
    with pytest.raises(EquipmentError, match="nozzles H1 and H2 overlap"):
        _horizontal(Nozzle("H1", _spec(), OnHead("first", 0.0, 0, 0.8)),
                    Nozzle("H2", _spec(), OnHead("first", 0.15, 0, 0.8))).validate()
    # the same spot on the other head is fine
    _horizontal(Nozzle("H1", _spec(), OnHead("first", 0.0, 0, 0.8)),
                Nozzle("H2", _spec(), OnHead("second", 0.0, 0, 0.8))).validate()


def test_names_checked():
    with pytest.raises(EquipmentError, match="duplicate nozzle names"):
        _horizontal(Nozzle("N1", _spec(), OnShell(1, 0, 1.5)),
                    Nozzle("N1", _spec(), OnShell(4, 0, 1.5)))
    with pytest.raises(EquipmentError, match="letters, digits"):
        Drum("D-101", 2.0, 6.0)
    with pytest.raises(EquipmentError, match="has no nozzle"):
        _horizontal().frame("N9")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def _from_top_nozzle():
    drum = _horizontal(Nozzle("N1", _spec(), OnShell(1.5, 0, 1.4)))
    asm = Assembly.from_nozzle(drum, "N1", lc=0.05)
    asm.add(Straight(0.4, n_layers=3))
    asm.add(Bend(0.3, 90, n_layers=4))
    asm.add(Straight(0.4, n_layers=3))
    return asm


def test_from_nozzle_pose_and_name():
    asm = _from_top_nozzle()
    assert asm.inlet.name == "D101_N1"
    _close(asm.inlet.frame, [1.5, 0, 1.4], [0, 0, 1], [1, 0, 0])
    asm.validate()


def test_from_nozzle_validates_the_drum():
    drum = _horizontal(Nozzle("N1", _spec(), OnShell(1.5, 0, 0.9)))
    with pytest.raises(EquipmentError, match="N1: projection"):
        Assembly.from_nozzle(drum, "N1")


def test_nothing_upstream_of_a_nozzle():
    asm = _from_top_nozzle()
    with pytest.raises(AssemblyError, match="drum nozzle"):
        asm.prepend(Straight(0.3, n_layers=2))
    n = len(asm.edges)
    asm.extend_open_ends(upstream=5, downstream=2)
    assert len(asm.edges) == n + 1                      # the outlet only
    assert asm.inlet.name == "D101_N1"


def test_nozzle_start_round_trips_and_follows_the_drum():
    asm = _from_top_nozzle()
    d = json.loads(json.dumps(asm.to_dict()))
    assert d["inlet"]["nozzle"]["name"] == "N1"
    again = Assembly.from_dict(d)
    assert again.to_dict() == asm.to_dict()
    # the drum is the authority: moving it moves the network
    d["inlet"]["nozzle"]["drum"]["position"] = [0.0, 0.0, 1.0]
    moved = Assembly.from_dict(d)
    _close(moved.inlet.frame, [1.5, 0, 2.4], [0, 0, 1], [1, 0, 0])


def test_network_from_nozzle_meshes(gmsh_session):
    asm = _from_top_nozzle()
    asm.mesh()
    names = {gmsh.model.getPhysicalName(d, t) for d, t in gmsh.model.getPhysicalGroups(2)}
    assert "fluid_D101_N1" in names and "fluid_outlet" in names
    n_hex = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
    assert n_hex == asm.cell_count()
    assert asm.check_quality().ok
