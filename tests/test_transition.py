"""
Transition: circle ↔ rectangle and rectangle ↔ rectangle sweeps
(decision 0009 option B, task 0029).  Meshing in both fill orders is
covered by the kit (tests/test_fitting_conformance.py); these tests cover
the rules and the station geometry.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Transition
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.shape import BlendShape, CircleShape, RectShape, outline
from hexmesh.core.spec import PipeSpec


def _circle(r=0.1, nang=6, nrad=3, name="fluid", **kw):
    return PipeSpec(nang=nang, **kw).core(name, radius=r, nrad=nrad)


def _rect(hw=0.14, hh=0.07, nang_w=6, nang_h=6, nrad=3, name="fluid", **kw):
    return PipeSpec(nang_w=nang_w, nang_h=nang_h, **kw).core(
        name, half_w=hw, half_h=hh, nrad=nrad)


def _asm(inlet, outlet, n_layers=4, length=0.3):
    asm = Assembly(inlet, direction=[1, 0, 0], up=[0, 0, 1])
    asm.add(Transition(outlet, length, n_layers))
    return asm


class TestRules:
    @pytest.mark.parametrize("a, b", [(_circle(), _rect()), (_rect(), _circle()),
                                      (_rect(), _rect(0.1, 0.1))])
    def test_class_0(self, a, b):
        assert int(classify(signature(a), signature(b))) == 0
        asm = _asm(a, b)
        asm.validate()
        assert not gmsh.isInitialized()

    def test_cell_count(self):
        asm = _asm(_circle(), _rect(), n_layers=5)
        assert asm.cell_count() == 5 * (6 * 6 + 4 * 6 * 3)

    def test_corners_untwisted(self):
        """Stations keep the inlet frame, so corner k meets corner k."""
        asm = _asm(_circle(), _rect())
        e = asm.edges[0]
        path = e.fitting.path(*[p.frame for p in e.ports], asm.inlet.spec)
        assert path.offsets(asm.inlet.spec) == [0] * 4

    @pytest.mark.parametrize("outlet, message", [
        (_rect(nang_w=6, nang_h=4), r"equal counts per side: inlet nang 6 vs outlet "
                                    r"nang_w 6, nang_h 4"),
        (_circle(0.06), "for circle → circle use Reducer"),
        (_rect(nrad=4), "core nrad"),
        (_rect(name="air"), "core: layer 0 is `fluid`"),
        (_rect(rot=0.3), "rot"),
    ])
    def test_rejected(self, outlet, message):
        with pytest.raises(AssemblyError, match=message):
            _asm(_circle(), outlet).validate()
        assert not gmsh.isInitialized()

    def test_multi_layer_rejected(self):
        inlet = _circle().shell("wall", dR=0.01, nrad=2)
        with pytest.raises(AssemblyError, match="single-layer"):
            _asm(inlet, _rect()).validate()

    def test_save_load_round_trip(self, tmp_path):
        asm = _asm(_circle(), _rect())
        asm.add(Straight(0.2, n_layers=2))
        path = tmp_path / "t.json"
        asm.save(path)
        again = Assembly.load(path)
        assert again.to_dict() == asm.to_dict()
        assert again.cell_count() == asm.cell_count()
        assert again.edges[0].fitting.outlet.core_shape == RectShape(0.14, 0.07, 6, 6)


class TestStationShape:
    def test_ends_are_the_end_outlines(self):
        c, r = CircleShape(0.1, 6), RectShape(0.14, 0.07, 6, 6)
        s = np.linspace(0, 1, 7)
        for k in range(4):
            for inner in (False, True):
                np.testing.assert_allclose(BlendShape(c, r, 0.0).outline(k, s, inner),
                                           outline(c, k, s, inner), atol=1e-15)
                np.testing.assert_allclose(BlendShape(c, r, 1.0).outline(k, s, inner),
                                           outline(r, k, s, inner), atol=1e-15)

    def test_outlines_match_face_builders(self, gmsh_session):
        """The outline functions describe the faces the builders make."""
        from hexmesh.faces.oh_circle import build_oh_circle
        from hexmesh.faces.oh_rect import build_oh_rect
        h, v = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
        for shape, build in ((CircleShape(0.1, 6), build_oh_circle),
                             (RectShape(0.14, 0.07, 6, 6), build_oh_rect)):
            cs = build(0, 0, 0, shape, h, v, 0.1, 3)
            gmsh.model.occ.synchronize()
            for k in range(4):
                for pts, inner in ((cs.outer_points, False), (cs.inner_points, True)):
                    x = gmsh.model.getValue(0, pts[k], [])[:2]
                    np.testing.assert_allclose(x, outline(shape, k, 0.0, inner), atol=1e-12)
                # the curve's midpoint by arc length
                for curve, inner in ((cs.outer_curves[k], False), (cs.inner_curves[k], True)):
                    lo, hi = gmsh.model.getParametrizationBounds(1, abs(curve))
                    t = np.linspace(lo[0], hi[0], 2001)
                    x = np.asarray(gmsh.model.getValue(1, abs(curve), t)).reshape(-1, 3)[:, :2]
                    if curve < 0:
                        x = x[::-1]
                    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(x, axis=0), axis=1))])
                    m = [np.interp(arc[-1] / 2, arc, x[:, j]) for j in (0, 1)]
                    np.testing.assert_allclose(m, outline(shape, k, 0.5, inner), atol=1e-6)

    def test_end_walls_exact(self, gmsh_session):
        """Inlet wall nodes on the circle, outlet wall nodes on the rectangle."""
        asm = _asm(_circle(), _rect())
        asm.mesh()
        _, x, _ = gmsh.model.mesh.getNodes()
        x = x.reshape(-1, 3)
        wall = x[np.isclose(np.abs(x[:, 1]), 0.14, atol=1e-12)
                 | np.isclose(np.abs(x[:, 2]), 0.07, atol=1e-12)]
        assert np.allclose(wall[:, 0], 0.3)            # flat walls only at the outlet
        inlet = x[np.isclose(x[:, 0], 0.0)]
        rho = np.hypot(inlet[:, 1], inlet[:, 2])
        assert np.isclose(rho.max(), 0.1) and np.sum(np.isclose(rho, 0.1)) == 4 * 6
