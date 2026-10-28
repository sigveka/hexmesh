"""
Layer outlines (decision 0026, task 0045): shells of any outline, circle or
rectangle, in any order.  The conformance kit meshes the stacks
(``outline-*`` cases); these are the rules around them.
"""

import math

import gmsh
import pytest

from hexmesh.assembly import (
    Assembly, AssemblyError, Drum, Elbow, EquipmentError, Nozzle, OnShell, Reducer,
    Straight, Tee, Transition, Wye,
)
from hexmesh.assembly.interface import half_extent, outer_radius
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.grading import progression_for_first_cell
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import BundleSpec, PipeSpec


def _core(r=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(r, 4), nrad=3)


def _in(outline, name="block"):
    return _core().shell(name, outer=outline, nrad=3)


def _validate(spec, fitting=None):
    asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(fitting or Straight(0.3, n_layers=2))
    asm.validate()


class TestSpec:
    def test_outlines(self):
        spec = _in(RectShape(0.25, 0.125, 4, 4)).shell("skin", dR=0.01, nrad=2)
        assert spec.outlines == [CircleShape(0.1, 4), RectShape(0.25, 0.125, 4, 4),
                                 RectShape(0.26, 0.135, 4, 4)]

    def test_period_is_the_stack_s(self):
        """The section's roll symmetry is that of its least symmetric outline."""
        assert _core().period == pytest.approx(math.pi / 2)
        assert _in(RectShape(0.2, 0.2, 4, 4)).period == pytest.approx(math.pi / 2)
        assert _in(RectShape(0.25, 0.125, 4, 4)).period == pytest.approx(math.pi)
        rc = (PipeSpec(nang=4).core("f", RectShape(0.1, 0.05, 4, 4), nrad=3)
              .shell("c", outer=CircleShape(0.2, 4), nrad=2))
        assert rc.period == pytest.approx(math.pi)

    def test_extents_use_the_outermost_outline(self):
        spec = _in(RectShape(0.25, 0.125, 4, 4))
        assert outer_radius(spec) == pytest.approx(math.hypot(0.25, 0.125))
        assert half_extent(spec, 0.0) == pytest.approx(0.25)
        assert half_extent(spec, math.pi / 2) == pytest.approx(0.125)

    def test_counts_name_the_layer(self):
        with pytest.raises(ValueError, match=r"shell `block`: .*layer `block` has \(4, 2\)"):
            _in(RectShape(0.25, 0.125, 4, 2))

    def test_rectangle_needs_n_outer_4(self):
        spec = PipeSpec(nang=8, n_outer=8).core("fluid", CircleShape(0.1, 8), nrad=3)
        with pytest.raises(ValueError, match="n_outer = 4"):
            spec.shell("block", outer=RectShape(0.2, 0.2, 8, 8), nrad=2)

    def test_round_trip(self):
        spec = (_in(RectShape(0.25, 0.125, 4, 4), "filler")
                .shell("wall", dR=0.01, nrad=2)
                .shell("sheath", outer=CircleShape(0.4, 4), nrad=2, first_cell=0.002))
        again = PipeSpec.from_dict(spec.to_dict())
        assert again.to_dict() == spec.to_dict()
        assert again.outlines == spec.outlines
        assert again.shells == spec.shells

    def test_old_square_shell_files_load(self):
        """A spec dict saved with the removed ``square_shell`` loads as the
        same ring: a square outline with the stack's count per side."""
        d = _core().to_dict()
        d["shells"] = [{"type": "square_shell", "name": "box", "half_w": 0.2,
                        "half_h": 0.2, "nrad": 2, "mprg": 1.0}]
        spec = PipeSpec.from_dict(d)
        assert spec.outlines[-1] == RectShape(0.2, 0.2, 4, 4)
        assert spec.layer_names == ["fluid", "box"]

    def test_bundle_cell_ends_in_a_rectangle(self):
        b = BundleSpec(_in(RectShape(0.2, 0.15, 4, 4), "shell"), nx=2, ny=3)
        assert (b.pitch_w, b.pitch_h) == pytest.approx((0.4, 0.3))
        with pytest.raises(TypeError, match="rectangular shell"):
            BundleSpec(_core().shell("wall", dR=0.01, nrad=2), nx=2, ny=2)


class TestFirstCell:
    """``first_cell`` is solved on the ring's longest radial (task 0045, 6)."""

    def _mprg(self, span, nrad, h):
        return 1.0 / progression_for_first_cell(span, nrad, h)

    def test_circle_in_rectangle_at_the_corner_line(self):
        spec = _core().shell("block", outer=RectShape(0.25, 0.125, 4, 4), nrad=4,
                             first_cell=0.01)
        c = 0.1 * math.sqrt(0.5)                    # the O-H corner at 45°
        span = math.hypot(0.25 - c, 0.125 - c)      # to the rectangle's corner
        assert spec.shells[0].mprg == pytest.approx(self._mprg(span, 4, 0.01), rel=1e-9)

    def test_rectangle_grown_by_dR_at_the_corner_line(self):
        spec = (PipeSpec(nang=4).core("f", RectShape(0.1, 0.05, 4, 4), nrad=3)
                .shell("wall", dR=0.02, nrad=4, first_cell=0.002))
        span = 0.02 * math.sqrt(2)
        assert spec.shells[0].mprg == pytest.approx(self._mprg(span, 4, 0.002), rel=1e-9)

    def test_circle_grown_by_dR_unchanged(self):
        spec = _core().shell("wall", dR=0.02, nrad=4, first_cell=0.002)
        assert spec.shells[0].mprg == pytest.approx(self._mprg(0.02, 4, 0.002), rel=1e-12)


class TestSignature:
    def test_circle_in_square_is_class_0_with_circle_in_circle(self):
        """Equal counts and the same layers: the same connectivity, so a
        straight joins them with no switch (task 0045, item 7)."""
        ring = _in(CircleShape(0.15, 4))
        for o in (RectShape(0.15, 0.15, 4, 4), RectShape(0.25, 0.125, 4, 4)):
            assert classify(signature(ring), signature(_in(o))).cls == 0
        assert signature(ring) == signature(_in(RectShape(0.25, 0.125, 4, 4)))


class TestContainment:
    @pytest.mark.parametrize("inner, outer, at", [
        (CircleShape(0.1, 4), RectShape(0.25, 0.1, 4, 4), "90.0°"),       # touches
        (CircleShape(0.1, 4), RectShape(0.25, 0.09, 4, 4), "90.0°"),      # cuts
        (RectShape(0.1, 0.05, 4, 4), CircleShape(0.11, 4), "-?153.4°"),  # corners out
    ])
    def test_outline_must_enclose_the_previous(self, inner, outer, at):
        spec = PipeSpec(nang=4).core("fluid", inner, nrad=3).shell("block", outer=outer,
                                                                    nrad=2)
        with pytest.raises((AssemblyError, ValueError),
                           match=rf"layer `block`: .*enclose `fluid`.*OUTLINE_MIN_GAP.* at {at}"):
            _validate(spec)
        assert not gmsh.isInitialized()

    def test_dR_after_a_rectangle_is_contained(self):
        _validate(_in(RectShape(0.12, 0.11, 4, 4)).shell("skin", dR=0.005, nrad=2))


class TestFittingRules:
    SPEC = staticmethod(lambda: _in(RectShape(0.25, 0.125, 4, 4)))

    @pytest.mark.parametrize("fitting, message", [
        (lambda: Elbow(90), "Elbow schedules .* a section with a rectangle"),
        (lambda: Tee(0.2, 0.3, 0.05), "single-layer"),
        (lambda: Wye(60, 0.3, 0.5), "single-layer"),
        (lambda: Transition(_core(), 0.3, 3), "single-layer"),
        (lambda: Reducer(_in(CircleShape(0.3, 4)), 0.3, n_layers=2),
         r"layer `block` is a RectShape at the inlet and a CircleShape .*Transition"),
    ])
    def test_rejections_name_the_limit(self, fitting, message):
        with pytest.raises((AssemblyError, ValueError), match=message):
            _validate(self.SPEC(), fitting())
        assert not gmsh.isInitialized()

    def test_reducer_changes_sizes(self):
        _validate(self.SPEC(), Reducer(_core(0.08).shell(
            "block", outer=RectShape(0.2, 0.1, 4, 4), nrad=3), 0.3, n_layers=2))

    def test_termination_compares_outlines(self):
        """A stack change may drop whole outer layers; the rest must match."""
        three = self.SPEC().shell("skin", dR=0.01, nrad=2)
        other = _in(RectShape(0.25, 0.12, 4, 4))
        with pytest.raises((AssemblyError, ValueError),
                           match=r"remaining layers must match \(`block` outline"):
            _validate(three, Straight(0.6, n_layers=4, stack_changes=((2, other),)))

    def test_drum_nozzles_are_circular_in_every_layer(self):
        nozzle = Nozzle("N1", _in(RectShape(0.2, 0.2, 4, 4)), OnShell(1.5, 0, 1.4))
        with pytest.raises(EquipmentError, match="layer `block` is a RectShape"):
            Drum("D101", 2.0, 6.0, nozzles=(nozzle,)).validate()
