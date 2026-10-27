"""
Corner identity from frames (DESIGN.md §6.1) — corners are named by the
frame, never found by distance.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Closure, Straight, Bend
from hexmesh.assembly.corners import (
    canonical_geom, corner0_angle, curve_endpoints, frame_offset,
)
from hexmesh.assembly.interface import Frame, build_face
from hexmesh.assembly.interface import rotate
from hexmesh.core.shape import CircleShape
from hexmesh.core.spec import PipeSpec


def _spec(n_outer=4, rot=0.0):
    return (PipeSpec(nang=4, n_outer=n_outer, rot=rot)
            .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
            .shell("wall", dR=0.025, nrad=2))


def _rolled(f, degrees):
    return Frame(f.position, f.normal, rotate(f.up, f.normal, math.radians(degrees)))


A = Frame.from_vectors([0, 0, 0], [1, 0, 0], [0, 0, 1])


class TestFrameOffset:
    @pytest.mark.parametrize("k", [0, 1, 2, 3])
    def test_symmetry_rolls(self, k):
        """A positive roll about the normal turns corners clockwise in the
        face's (right, up) coordinates (right × up = −normal), so inlet
        corner 0 meets outlet corner k."""
        b = _rolled(Frame(A.position + [1, 0, 0], A.normal, A.up), 90 * k)
        assert frame_offset(A, b, _spec()) == k

    def test_small_twist_keeps_correspondence(self):
        b = _rolled(Frame(A.position + [1, 0, 0], A.normal, A.up), 20)
        assert frame_offset(A, b, _spec()) == 0

    def test_turned_face(self):
        """Normal turned by 60° about the corner-free axis: still offset 0."""
        b = Frame.from_vectors([1, 1, 0], [math.cos(1.05), math.sin(1.05), 0], [0, 0, 1])
        assert frame_offset(A, b, _spec()) == 0

    def test_half_symmetry_twist_is_ambiguous(self):
        b = _rolled(A, 45)
        with pytest.raises(ValueError, match="ambiguous"):
            frame_offset(A, b, _spec())

    def test_antiparallel_rejected(self):
        b = Frame.from_vectors([1, 0, 0], [-1, 0, 0], [0, 0, 1])
        with pytest.raises(ValueError, match="antiparallel"):
            frame_offset(A, b, _spec())

    def test_n_outer_8_period(self):
        b = _rolled(A, 45)
        assert frame_offset(A, b, _spec(n_outer=8)) == 1


class TestCurveEndpoints:
    def test_start_with_higher_tag(self, gmsh_session):
        """OCC getBoundary lists end points by ascending tag, not start/end."""
        g = gmsh.model.occ
        a, b = g.addPoint(0, 0, 0), g.addPoint(1, 0, 0)
        fwd, back = g.addLine(a, b), g.addLine(b, a)
        arc_c = g.addPoint(0.5, -0.5, 0)
        arc = g.addCircleArc(b, arc_c, a)
        g.synchronize()
        assert curve_endpoints(fwd) == (a, b)
        assert curve_endpoints(back) == (b, a)
        assert curve_endpoints(arc) == (b, a)


class TestCanonicalGeom:
    @pytest.mark.parametrize("rot", [0.0, 17.0])   # degrees
    def test_builder_convention(self, gmsh_session, rot):
        """Corner k at corner0 + k·90° from right; curves run k → k+1."""
        spec = _spec(rot=rot)
        frame = Frame.from_vectors([0.2, -0.1, 0.4], [0, 1, 1], [1, 0, 0])
        face = build_face(spec, frame, 0.1)
        gmsh.model.occ.synchronize()
        for _, cs in face.layers:
            g = canonical_geom(cs)
            r = cs.shape.radius
            for k in range(4):
                ang = corner0_angle(spec) + k * math.pi / 2
                want = frame.position + r * (math.cos(ang) * frame.right
                                             + math.sin(ang) * frame.up)
                got = gmsh.model.getValue(0, g['op'][k], [])
                np.testing.assert_allclose(got, want, atol=1e-12)
                for key, a, b in [('oc', g['op'][k], g['op'][(k + 1) % 4]),
                                  ('ic', g['ip'][k], g['ip'][(k + 1) % 4]),
                                  ('rc', g['ip'][k], g['op'][k])]:
                    c = g[key][k]
                    t0, t1 = curve_endpoints(abs(c))
                    assert (t0, t1) == ((a, b) if c > 0 else (b, a))


class TestValidationBeforeGmsh:
    def _hairpin(self, n):
        spec = PipeSpec(nang=4).core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
        asm = Assembly(spec, up=[0, 0, 1])
        for r in (45, 225, 45):
            asm.add(Straight(0.6, n_layers=3))
            asm.add(Bend(0.3, 90, n_layers=4, roll=r))
        asm.add(Straight(0.6, n_layers=3))
        asm.close(asm.interfaces[-1], asm.inlet, Closure(n_layers=n))
        return asm

    def test_coarse_hairpin_closure_rejected(self):
        with pytest.raises(AssemblyError, match=r"slab \d+ turns .* use more axial layers"):
            self._hairpin(12).validate()
        assert not gmsh.isInitialized()

    def test_refined_hairpin_closure_accepted(self):
        self._hairpin(20).validate()

    def test_n_outer_8_rejected(self):
        asm = Assembly(_spec(n_outer=8))
        asm.add(Straight(0.3, n_layers=2))
        with pytest.raises(AssemblyError, match="n_outer=4 only"):
            asm.validate()
