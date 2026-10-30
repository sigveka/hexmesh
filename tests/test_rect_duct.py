"""
Rectangular cores in the assembly (decisions 0009, 0010; task 0028).
Meshing and wall exactness are covered by the kit's duct cases
(tests/test_fitting_conformance.py); these tests cover the rules.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import (
    Assembly, AssemblyError, Bend, Closure, Elbow, MiterBend, Reducer, Straight, Tee, Wye,
)
from hexmesh.assembly.corners import frame_offset
from hexmesh.assembly.interface import Frame, hydraulic_diameter, rotate
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.spec import PipeSpec


def _duct(half_w=0.1, half_h=0.05, nang_w=4, nang_h=2, nrad=2, **kw):
    return PipeSpec(nang_w=nang_w, nang_h=nang_h, **kw).core(
        "air", half_w=half_w, half_h=half_h, nrad=nrad)


def _circle(nang=4, nrad=2):
    return PipeSpec(nang=nang).core("air", radius=0.1, nrad=nrad)


def _square():
    return _duct(0.07, 0.07, 3, 3)


A = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])


def _rolled(frame, degrees, shift=1.0):
    return Frame(frame.position + shift * frame.normal, frame.normal,
                 rotate(frame.up, frame.normal, math.radians(degrees)))


class TestPeriod:
    def test_geometric_period(self):
        assert _duct().period == pytest.approx(math.pi)
        assert _square().period == pytest.approx(math.pi / 2)
        assert _circle().period == pytest.approx(math.pi / 2)
        # equal sides but unequal counts: the mesh repeats only every π
        assert _duct(0.07, 0.07, 4, 2).period == pytest.approx(math.pi)

    def test_side_counts(self):
        assert _duct().side_counts == (4, 2, 4, 2)
        assert _circle(5).side_counts == (5, 5, 5, 5)

    @pytest.mark.parametrize("roll, offset", [(0, 0), (180, 2), (-180, 2), (40, 0), (-170, 2)])
    def test_duct_offsets_in_half_turns(self, roll, offset):
        assert frame_offset(A, _rolled(A, roll), _duct()) == offset

    @pytest.mark.parametrize("roll", [90, -90])
    def test_duct_quarter_turn_is_ambiguous(self, roll):
        with pytest.raises(ValueError, match="ambiguous"):
            frame_offset(A, _rolled(A, roll), _duct())

    @pytest.mark.parametrize("roll, offset", [(90, 1), (180, 2), (-90, 3)])
    def test_square_offsets_in_quarter_turns(self, roll, offset):
        assert frame_offset(A, _rolled(A, roll), _square()) == offset

    def test_closure_quarter_turn(self):
        """A 90° roll mismatch is half a 2:1 duct's period, so ambiguous; a
        square has it modulo P = 90° (nothing to absorb)."""
        b = _rolled(A, 90, shift=1.0)
        with pytest.raises(ValueError, match="ambiguous which way to twist"):
            Closure(n_layers=4).validate([A, b], _duct())
        Closure(n_layers=4).validate([A, b], _square())
        _, twist = Closure(n_layers=4).stations(A, b, _square().period)
        assert abs(twist) < 1e-9

    def test_duct_rolled_outlet_quarter_turn_rejected(self):
        """A Straight's outlet rolled by 90° does not match a 2:1 duct."""
        asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
        out = asm.add(Straight(0.3, n_layers=2))
        out.frame = _rolled(out.frame, 90, shift=0.0)
        with pytest.raises(AssemblyError, match="does not match"):
            asm.validate()


class TestSignature:
    def test_square_duct_matches_circle(self):
        """Shape is geometry (decision 0009): equal counts, equal signature."""
        assert signature(_square()) == signature(_circle(3))

    def test_duct_contents(self):
        sig = signature(_duct())
        assert (sig.n_outer, sig.period, sig.nang_w, sig.nang_h) == (4, 180.0, 4, 2)
        assert [(l.name, l.kind, l.nrad) for l in sig.layers] == [("air", "oh_core", 2)]

    def test_circle_to_flat_duct_is_class_3(self):
        """Unequal counts change the combinatorial period: no sweep bridges it."""
        c = classify(signature(_circle()), signature(_duct()))
        assert int(c) == 3 and {d.field for d in c.differences} == {"period"}

    def test_duct_density_change_is_class_2(self):
        c = classify(signature(_duct()), signature(_duct(nang_w=8, nang_h=4)))
        assert int(c) == 2
        assert {d.field for d in c.differences} == {"nang_w", "nang_h"}


class TestSizes:
    def test_cell_count_closed_form(self):
        asm = Assembly(_duct(nrad=3), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=5))
        assert asm.cell_count() == 5 * (4 * 2 + 2 * (4 + 2) * 3)

    @pytest.mark.parametrize("roll, ok", [(0, True), (90, False), (180, True), (-90, False)])
    def test_bend_checked_in_its_plane(self, roll, ok):
        """R = 0.08 clears the half-height 0.05 (easy way), not the
        half-width 0.1 (hard way)."""
        asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Bend(0.08, 90, n_layers=4, roll=roll))
        if ok:
            asm.validate()
        else:
            with pytest.raises(AssemblyError, match="half-extent in the bend plane 0.1"):
                asm.validate()

    def test_miter_bend_checked_in_its_plane(self):
        asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(MiterBend(0.08, 90, roll=90))
        with pytest.raises(AssemblyError, match="in the bend plane"):
            asm.validate()

    def test_hydraulic_diameter(self):
        assert hydraulic_diameter(_duct()) == pytest.approx(4 * 0.1 * 0.05 / 0.15)
        assert hydraulic_diameter(_square()) == pytest.approx(0.14)
        assert hydraulic_diameter(_circle()) == pytest.approx(0.2)

    def test_extend_open_ends_in_hydraulic_diameters(self):
        asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=2))
        asm.extend_open_ends(upstream=2, downstream=3, cells_per_diameter=2)
        lengths = sorted(e.fitting.length for e in asm.edges)
        dh = 4 * 0.1 * 0.05 / 0.15
        assert lengths == pytest.approx(sorted([0.3, 2 * dh, 3 * dh]))


class TestRejections:
    @pytest.mark.parametrize("fitting, message", [
        (Elbow(90), "use Bend"),
        # sizes may change (decision 0026), shapes may not
        (Reducer(_circle(), 0.2, n_layers=2), "Transition"),
        (Tee(0.2, 0.2, 0.03), "needs branch=RectShape"),   # a duct tap takes branch= (task 0070)
        (Wye(60, 0.3, 0.5), "circular cores only"),
    ])
    def test_unsupported_fittings(self, fitting, message):
        asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
        # a tee on a duct needs branch=, so it fails in add()
        with pytest.raises((AssemblyError, ValueError), match=message):
            asm.add(fitting)
            asm.validate()
        assert not gmsh.isInitialized()

    def test_first_cell(self):
        with pytest.raises(TypeError, match="circular cores only"):
            PipeSpec(nang_w=4, nang_h=2).core("air", half_w=0.1, half_h=0.05, nrad=3,
                                               first_cell=0.001)

    def test_shells_need_equal_counts(self):
        """Shells around a rectangle exist (decision 0026), with one count
        per side; the 2:1 duct has 4 × 2."""
        with pytest.raises(ValueError, match=r"shell `wall`: .*equal counts per side; "
                                             r"layer `air` has \(4, 2\)"):
            _duct().shell("wall", dR=0.01, nrad=2)


def test_rot_turns_the_duct(gmsh_session):
    """``rot`` rotates the rectangle in its frame: a 2:1 duct at rot = 90°
    stands on its short side, and its outer nodes lie on that rectangle."""
    spec = _duct(rot=90)
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=2))
    asm.mesh()
    _, x, _ = gmsh.model.mesh.getNodes()
    x = x.reshape(-1, 3)
    # frame.right is −y here, up is z: the width now runs along z
    assert np.abs(x[:, 1]).max() == pytest.approx(0.05)
    assert np.abs(x[:, 2]).max() == pytest.approx(0.1)


def test_save_load_round_trip(tmp_path):
    asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=2))
    asm.add(Bend(0.3, 90, n_layers=4, roll=90))
    path = tmp_path / "duct.json"
    asm.save(path)
    again = Assembly.load(path)
    assert again.to_dict() == asm.to_dict()
    assert again.cell_count() == asm.cell_count()
    assert again.inlet.spec.core_shape == asm.inlet.spec.core_shape


def test_refined_doubles_both_counts():
    asm = Assembly(_duct(), direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Straight(0.3, n_layers=2))
    fine = asm.refined(2)
    assert fine.inlet.spec.side_counts == (8, 4, 8, 4)
    assert fine.cell_count() == 8 * asm.cell_count()
