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
The O-H ↔ H switch (decision 0036, task 0085).  The kit
(``test_fitting_conformance``, ``switch-*``) covers all-hex, meshed =
predicted, untouched ports and exact walls both ways; here the checks
before GMSH, the cell count, the predicted quality, resolution, JSON and
refinement, and the H end's own grading.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh import (Assembly, AssemblyError, Bend, Closure, Session, Straight, Switch,
                     Transition)
from hexmesh.assembly import intent, limits
from hexmesh.assembly.interface import Frame
from hexmesh.assembly.signature import check_port_pairs
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import LayoutNotSupported, PipeSpec
from hexmesh.sections import h, oh

B = 0.05
INLET = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))


def _oh(aspect=2, n=4, nrad=3, **kw):
    return PipeSpec(nang_w=aspect * n, nang_h=n).core(
        "air", RectShape(aspect * B, B, aspect * n, n), nrad=nrad, **kw)


def _h(aspect=2, n=4, **kw):
    return PipeSpec(nang_w=aspect * n, nang_h=n).core(
        "air", RectShape(aspect * B, B, aspect * n, n), layout="h", **kw)


def _asm(first, switch, axial_cell=None):
    asm = Assembly(first, direction=[1, 0, 0], up=[0, 0, 1], axial_cell=axial_cell)
    asm.add(Straight(0.2, n_layers=2))
    asm.add(switch)
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _frames(switch, spec):
    return [INLET] + [f for f, _ in switch.ports(INLET, spec)]


# ---------------------------------------------------------------------------
# Checks before GMSH
# ---------------------------------------------------------------------------

def test_direct_oh_to_h_is_rejected_naming_the_switch():
    """A loop that switches to H once and closes back onto its O-H inlet
    with no switch: rejected by validate(), before GMSH."""
    asm = Assembly(_oh(), direction=[1, 0, 0], up=[0, 0, 1])
    first = asm.interfaces[0]
    for _ in range(2):
        asm.add(Straight(0.6, n_layers=3))
        asm.add(Bend(0.3, 90, n_layers=4))
    asm.add(Switch(0.1, n_layers=2))
    asm.add(Straight(0.5, n_layers=3))
    asm.add(Bend(0.3, 90, n_layers=4))
    asm.close(asm.open_interfaces()[-1], first, Closure(n_layers=12))
    with pytest.raises(AssemblyError, match=r"class 1, a pillow.*put a Switch"):
        asm.validate()


def test_switch_bridges_class_1_only():
    check_port_pairs(Switch(0.1, n_layers=2), [_oh(), _h()])
    check_port_pairs(Switch(0.1, n_layers=2), [_h(), _oh()])
    with pytest.raises(ValueError, match="class 3"):
        check_port_pairs(Switch(0.1, n_layers=2), [_oh(), _h(n=6)])


@pytest.mark.parametrize("make, match", [
    (lambda: (Switch(0.1, n_layers=2), _h()), "needs outlet="),
    (lambda: (Switch(0.1, n_layers=2, outlet=_oh(nrad=2)), _oh()), "joins an O-H and an H"),
    (lambda: (Switch(0.1, n_layers=2, outlet=_h()), _h()), "joins an O-H and an H"),
    (lambda: (Switch(0.1, n_layers=2, outlet=PipeSpec(nang_w=8, nang_h=4).core(
        "air", RectShape(0.12, B, 8, 4), layout="h")), _oh()), "keeps the rectangle"),
    (lambda: (Switch(0.02, n_layers=2), _oh()), "ring thicknesses"),
    (lambda: (Switch(0.1, n_layers=0), _oh()), "at least 1"),
])
def test_checks(make, match):
    sw, spec = make()
    with pytest.raises(ValueError, match=match):
        sw.check(spec)


def test_shells_wait_for_0086():
    lagged = PipeSpec(nang=4).core("air", RectShape(2 * B, B, 4, 4), nrad=3).shell(
        "lagging", dR=0.01, nrad=2)
    with pytest.raises(LayoutNotSupported, match="0086"):
        Switch(0.1, n_layers=2).check(lagged)


def test_length_rule_is_in_ring_thicknesses():
    t = oh.ring_thickness(2 * B, B)
    Switch(limits.SWITCH_MIN_LENGTH * t, n_layers=2).check(_oh())
    with pytest.raises(ValueError, match="ring thicknesses"):
        Switch(0.99 * limits.SWITCH_MIN_LENGTH * t, n_layers=2).check(_oh())


# ---------------------------------------------------------------------------
# Counts and predicted quality (pure)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("aspect, nrad, n", [(1, 1, 2), (2, 3, 3), (4, 6, 5)])
def test_cell_count_is_exact_before_gmsh(aspect, nrad, n):
    spec = _oh(aspect, 4, nrad)
    sw = Switch(0.1, n_layers=n)
    nw, nh = 4 * aspect, 4
    want = nw * nh * (n + nrad) + 2 * (nw + nh) * nrad * n
    assert sw.cell_count(_frames(sw, spec), spec) == want


@pytest.mark.parametrize("aspect", [1, 2, 4])
@pytest.mark.parametrize("nrad", [1, 3, 6])
def test_predicted_sj_is_a_cube_corner(aspect, nrad):
    """The cap's three 45° slants: 1/√3 at any aspect ratio and nrad."""
    spec = _oh(aspect, 4, nrad)
    for sw in (Switch(0.1, n_layers=3), Switch(0.3, n_layers=3)):
        assert sw.predicted_sj(_frames(sw, spec), spec) == pytest.approx(1 / math.sqrt(3))


def test_n_layers_resolves_from_axial_cell():
    t = oh.ring_thickness(2 * B, B)
    asm = _asm(_oh(), Switch(0.1), axial_cell=0.01)
    assert asm.edges[1].fitting.n_layers == math.ceil((0.1 - t) / 0.01 - 1e-9)
    with pytest.raises(AssemblyError, match="axial_cell"):
        _asm(_oh(), Switch(0.1))


def test_default_outlet_is_the_uniform_h_face():
    asm = _asm(_oh(), Switch(0.1, n_layers=2))
    out = asm.edges[1].fitting.outlet           # resolved, stored in the JSON
    assert out.layout == "h" and out.wall_grading is None
    assert out.side_counts == _oh().side_counts


def test_json_round_trip_and_refinement():
    asm = _asm(_h(first_cell=0.004), Switch(0.1, n_layers=3, outlet=_oh()))
    d = intent.to_dict(asm)
    back = Assembly.from_dict(d)
    assert (intent.fitting_to_dict(back.edges[1].fitting)
            == intent.fitting_to_dict(asm.edges[1].fitting))
    assert back.cell_count() == asm.cell_count()
    fine = Assembly.from_dict(intent.refined_dict(d, 2))
    assert fine.edges[1].fitting.n_layers == 6
    assert fine.cell_count() == 8 * asm.cell_count()


# ---------------------------------------------------------------------------
# Meshed
# ---------------------------------------------------------------------------

def test_graded_h_end_keeps_its_own_grid():
    """The H face's wall grading starts inside the switch (BlockLayout's
    own_grading): its port nodes are the H face's own, though the O-H
    port opposite is uniform."""
    hs = _h(aspect=2, n=6, first_cell=0.004)
    with Session("switch-grid"):
        asm = _asm(_oh(2, 6, 3), Switch(0.1, n_layers=3, outlet=hs))
        asm.mesh()
        _, xyz, _ = gmsh.model.mesh.getNodes()
        xyz = xyz.reshape(-1, 3)
    x_h = 0.2 + 0.1
    top = xyz[(np.abs(xyz[:, 0] - x_h) < 1e-9) & (np.abs(xyz[:, 2] - B) < 1e-9)]
    want = h.node_grid(hs)[:, 0, 0]
    np.testing.assert_allclose(np.sort(top[:, 1]), np.sort(want), atol=1e-8)


# ---------------------------------------------------------------------------
# Transition with an H rectangular end
# ---------------------------------------------------------------------------

def _circle(n=4, nrad=3):
    return PipeSpec(nang=n).core("air", CircleShape(radius=0.1, nang=n), nrad=nrad)


def _hrect(half_w=0.14, half_h=0.07, n=4, **kw):
    return PipeSpec(nang_w=n, nang_h=n).core("air", RectShape(half_w, half_h, n, n),
                                             layout="h", **kw)


def test_transition_to_h_embeds_a_switch():
    """The cells: the blend's, then the switch's over the last m layers."""
    tr = Transition(_hrect(), 0.3, 6)
    spec = _circle()
    frames = [INLET] + [f for f, _ in tr.ports(INLET, spec)]
    (blend, _, _), (sw, (mid, _), s1) = tr._parts(frames, spec)
    assert isinstance(sw, Switch) and s1.layout == "oh" and s1.core_shape == _hrect().core_shape
    m = sw.n_layers
    t = oh.ring_thickness(0.14, 0.07)
    assert m == math.ceil(limits.SWITCH_MIN_LENGTH * t * 6 / 0.3 - 1e-9) and blend.n_layers == 6 - m
    assert mid.position[0] == pytest.approx(0.3 * (6 - m) / 6)
    assert tr.cell_count(frames, spec) == (blend.cell_count([INLET, mid], spec)
                                           + sw.cell_count([mid, frames[1]], s1))


@pytest.mark.parametrize("make, match, exc", [
    (lambda: (Transition(_hrect(), 0.3, 6), PipeSpec(nang=4).core(
        "air", CircleShape(radius=0.1, nang=4), nrad=3).shell("wall", dR=0.01, nrad=2)),
     "0086", LayoutNotSupported),
    (lambda: (Transition(_hrect(0.1, 0.1), 0.3, 6), _hrect()), "both ends", ValueError),
    (lambda: (Transition(_hrect(), 0.3, 6), PipeSpec(nang=4).core(
        "air", RectShape(0.14, 0.07, 4, 4), nrad=3)), "use Switch", ValueError),
    (lambda: (Transition(_hrect(), 0.05, 2), _circle()), "n_layers >=", ValueError),
    (lambda: (Transition(_hrect(n=6), 0.3, 6), _circle()), "equal counts", ValueError),
])
def test_transition_h_end_checks(make, match, exc):
    tr, spec = make()
    with pytest.raises(exc, match=match):
        tr.check(spec)


def test_transition_still_rejects_layer_termination():
    """Class 1 is declared for the H end's pillow; a layer that ends is not
    a transition's."""
    two = _circle().shell("wall", dR=0.01, nrad=2)
    with pytest.raises(ValueError, match="present only at the inlet.*keeps the layers"):
        Transition(PipeSpec(nang=4).core("air", RectShape(0.14, 0.07, 4, 4), nrad=3),
                   0.3, 4).check(two)


def test_transition_h_end_json_and_refinement():
    asm = Assembly(_circle(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.2, n_layers=2))
    asm.add(Transition(_hrect(first_cell=0.01), 0.3, 6))
    asm.add(Straight(0.2, n_layers=2))
    d = intent.to_dict(asm)
    assert Assembly.from_dict(d).cell_count() == asm.cell_count()
    assert Assembly.from_dict(intent.refined_dict(d, 2)).cell_count() == 8 * asm.cell_count()
