"""
Layer outlines (decision 0026, task 0045): shells of any outline, circle or
rectangle, in any order.  The conformance kit meshes the stacks
(``outline-*`` cases); these are the rules around them.
"""

import math
import warnings

import gmsh
import numpy as np
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
        (lambda: Tee(0.2, 0.3, 0.05), "not circular.*circular only"),
        (lambda: Wye(60, 0.3, 0.5), "single-layer"),
        (lambda: Transition(_core(), 0.3, 3), "layer `block` present only at the inlet"),
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


# ---------------------------------------------------------------------------
# Predicted section quality and its limits (task 0047)
# ---------------------------------------------------------------------------

def _circle_in_rect(aspect, gap, nang=4):
    """Circle r = 0.1 in a rectangle whose thinnest gap is gap · r."""
    hh = 0.1 * (1 + gap)
    return (PipeSpec(nang=nang).core("core", CircleShape(0.1, nang), nrad=4)
            .shell("ring", outer=RectShape(aspect * hh, hh, nang, nang), nrad=4))


def _rect_in_circle(aspect, gap, nang=4):
    """Rectangle of half-diagonal 0.1 in a circle of radius (1 + gap) · 0.1."""
    hh = 0.1 / math.hypot(aspect, 1)
    return (PipeSpec(nang=nang).core("core", RectShape(aspect * hh, hh, nang, nang), nrad=4)
            .shell("ring", outer=CircleShape(0.1 * (1 + gap), nang), nrad=4))


class TestSectionQuality:
    @pytest.mark.parametrize("kind, coef", [("Bump", 0.6), ("Bump", 1.4), ("Bump", 1.0),
                                            ("Progression", 1.3), ("Progression", 0.8)])
    def test_spacing_matches_gmsh(self, gmsh_session, kind, coef):
        from hexmesh.assembly.section_quality import bump, progression
        a = gmsh.model.occ.addPoint(0, 0, 0)
        b = gmsh.model.occ.addPoint(1, 0, 0)
        line = gmsh.model.occ.addLine(a, b)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.setTransfiniteCurve(line, 9, kind, coef)
        gmsh.model.mesh.generate(1)
        x = np.sort(gmsh.model.mesh.getNodes()[1].reshape(-1, 3)[:, 0])
        want = bump(8, coef) if kind == "Bump" else progression(8, coef)
        np.testing.assert_allclose(x, want, atol=1e-6)   # GMSH integrates Bump numerically

    @pytest.mark.parametrize("spec", [
        _circle_in_rect(2.5, 0.3), _circle_in_rect(1.5, 1.0, nang=8),
        _rect_in_circle(2, 0.3), _rect_in_circle(4, 0.1, nang=8),
        _core().shell("wall", dR=0.01, nrad=2, first_cell=0.002),
        PipeSpec(nang=4, mbmp=0.6).core("core", RectShape(0.2, 0.1, 4, 4), nrad=3)
        .shell("ring", outer=CircleShape(0.3, 4), nrad=3, mprg=1.2),
    ], ids=["c-in-2.5to1", "c-in-1.5to1-nang8", "2to1-in-c", "4to1-in-c-nang8", "dR-graded",
            "bumped"])
    def test_corner_sj_matches_the_mesh(self, gmsh_session, spec):
        """A straight's per-layer corner scaled Jacobian is the prediction."""
        from hexmesh.assembly.section_quality import section_quality
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.4, n_layers=4))
        asm.mesh()
        got = {r.name: r.min_quality for r in asm.check_quality("scaled_jacobian").regions}
        for q in section_quality(spec):
            assert got[q.name] == pytest.approx(q.min_sj, abs=0.01), q

    @pytest.mark.parametrize("spec, checkmesh", [
        (_circle_in_rect(4, 0.3), 80.2544), (_rect_in_circle(4, 0.3), 54.1026)])
    def test_non_orthogonality_matches_checkmesh(self, spec, checkmesh):
        """Max over the section against OpenFOAM v1912 ``checkMesh`` on the
        meshed straights (task 0047, docs/integrations/openfoam.md)."""
        from hexmesh.assembly.section_quality import section_quality
        got = max(q.max_non_ortho for q in section_quality(spec))
        assert got == pytest.approx(checkmesh, abs=0.1)


class TestQualityLimits:
    @pytest.mark.parametrize("spec, warns", [
        (_circle_in_rect(1.5, 0.3), []),
        (_circle_in_rect(1.68, 0.1), ["non-orthogonality"]),              # 70.9°, SJ 0.31
        (_circle_in_rect(2, 0.3), ["corner scaled Jacobian"]),            # SJ 0.299, 68.0°
        (_circle_in_rect(2.5, 0.3), ["corner scaled Jacobian", "non-orthogonality"]),
        (_circle_in_rect(2.5, 0.1), ["corner scaled Jacobian", "non-orthogonality"]),  # 79.0°
        (_rect_in_circle(3, 0.3), []),                                    # SJ 0.316
        (_rect_in_circle(8, 0.3), ["corner scaled Jacobian"]),            # SJ 0.124
    ], ids=["c-1.5", "c-1.68-thin", "c-2", "c-2.5", "c-2.5-thin", "r-3", "r-8"])
    def test_soft_limits_warn(self, spec, warns):
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=2))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asm.validate()
        assert [w for m in asm.warnings for w in warns if w in m] == warns
        assert len(asm.warnings) == len(warns)
        assert [str(c.message) for c in caught
                if issubclass(c.category, UserWarning)] == asm.warnings
        for m in asm.warnings:
            assert "layer `ring`" in m and ("PREDICTED_SJ_WARN 0.3" in m
                                            or "OUTLINE_NONORTH_WARN 70°" in m)

    @pytest.mark.parametrize("spec, message", [
        (_circle_in_rect(3, 0.1), r"layer `ring` \(circle in a 3:1 rectangle\): predicted "
                                  r"non-orthogonality 81\.3° is above OUTLINE_NONORTH_MAX 80°"),
        (_rect_in_circle(11, 0.3), r"layer `ring` \(11:1 rectangle in a circle\): predicted "
                                   r"corner scaled Jacobian 0\.091 is below PREDICTED_SJ_MIN 0\.1"),
    ], ids=["non-orth", "sj"])
    def test_hard_limits_reject_before_gmsh(self, spec, message):
        asm = Assembly(spec, direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=2))
        with pytest.raises(AssemblyError, match=message):
            asm.validate()
        assert not gmsh.isInitialized()

    def test_shells_that_keep_their_shape_are_not_checked(self):
        """dR shells (the inner outline grown) and circles round circles."""
        from hexmesh.assembly.section_quality import changes_shape
        duct = (PipeSpec(nang=4).core("air", RectShape(0.6, 0.1, 4, 4), nrad=3)
                .shell("wall", dR=0.01, nrad=2))
        assert not changes_shape(duct, 1)
        assert not changes_shape(_in(CircleShape(0.2, 4)), 1)
        assert changes_shape(_in(RectShape(0.2, 0.2, 4, 4)), 1)

    def test_warnings_reset_on_each_validate(self):
        asm = Assembly(_circle_in_rect(2, 0.3), direction=[1, 0, 0], up=[0, 0, 1])
        asm.add(Straight(0.3, n_layers=2))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            asm.validate()
            asm.validate()
        assert len(asm.warnings) == 1
