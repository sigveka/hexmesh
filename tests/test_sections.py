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
Each layout described once (tasks 0082, 0084): the pure declaration
(``levels`` and ``patches`` of ``sections.oh`` / ``sections.h``, what
block layouts use) and the GMSH face (``sections.build_face``) agree
corner for corner and edge for edge.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh import Session
from hexmesh.assembly.corners import canonical_geom
from hexmesh.assembly.interface import Frame
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import PipeSpec
from hexmesh import sections
from hexmesh.sections import h, layout_of, oh


def _rect(a, b, n=4, **kw):
    return PipeSpec(nang=n, **kw).core("fluid", RectShape(a, b, n, n), nrad=3)


def _h(a, b, nw, nh, rot=0.0, **kw):
    return PipeSpec(nang_w=nw, nang_h=nh, rot=rot).core(
        "fluid", RectShape(a, b, nw, nh), layout="h", **kw)


SPECS = {
    "circle": lambda: PipeSpec(nang=6).core("fluid", radius=0.05, nrad=3),
    "rect-1": lambda: _rect(0.06, 0.06),
    "rect-2": lambda: _rect(0.10, 0.05),
    "rect-4": lambda: _rect(0.20, 0.05),
    "rect-unequal-counts": lambda: PipeSpec(nang_w=6, nang_h=3).core(
        "fluid", RectShape(0.10, 0.05, 6, 3), nrad=3),
    "circle-3layer": lambda: (PipeSpec(nang=4).core("fluid", radius=0.05, nrad=3, mprg=0.9)
                              .shell("wall", dR=0.004, nrad=2, mprg=1.1)
                              .shell("lagging", dR=0.02, nrad=3)),
    "rect-3layer": lambda: (_rect(0.10, 0.05).shell("wall", dR=0.01, nrad=2)
                            .shell("lagging", dR=0.03, nrad=2)),
    "circle-in-rect": lambda: (PipeSpec(nang=4).core("fluid", radius=0.05, nrad=3)
                               .shell("block", outer=RectShape(0.25, 0.125, 4, 4), nrad=3)),
    "circle-square-circle": lambda: (
        PipeSpec(nang=4).core("fluid", radius=0.05, nrad=3)
        .shell("filler", outer=RectShape(0.08, 0.08, 4, 4), nrad=2)
        .shell("sheath", outer=CircleShape(0.14, 4), nrad=2)),
    "rect-in-circle": lambda: (_rect(0.10, 0.05)
                               .shell("casing", outer=CircleShape(0.16, 4), nrad=3)),
    "circle-rot": lambda: (PipeSpec(nang=4, rot=30).core("fluid", radius=0.05, nrad=3)
                           .shell("wall", dR=0.01, nrad=2)),
    "rect-rot-bump": lambda: (_rect(0.10, 0.05, rot=-17, mbmp=0.7)
                              .shell("wall", dR=0.01, nrad=2)),
    "circle8": lambda: PipeSpec(nang=4, n_outer=8).core("fluid", radius=0.05, nrad=3),
    # the H layout (task 0084): one patch, graded to the walls
    "h-1": lambda: _h(0.06, 0.06, 5, 5),
    "h-2": lambda: _h(0.10, 0.05, 8, 4),
    "h-4-first-cell": lambda: _h(0.20, 0.05, 16, 4, first_cell=0.003),
    "h-2-ratio": lambda: _h(0.10, 0.05, 8, 4, mprg=1.25),
    "h-rot-bump": lambda: _h(0.10, 0.05, 8, 4, first_cell=0.004, rot=-17),
}

#: an oblique frame, so no coordinate is trivially zero
FRAME = Frame.from_vectors(position=[0.3, -1.2, 2.5], normal=[1.0, 2.0, -0.5], up=[0.2, 0.1, 1.0])


def _realised(spec):
    """Per level, the GMSH corner points; per (a, b), the curve."""
    face = sections.build_face(spec, FRAME.position, FRAME.right, FRAME.up, lc=0.1)
    gmsh.model.occ.synchronize()
    points, curves = {}, {}
    if spec.layout == "h":                  # one level: the boundary
        (_, cs), = face.layers
        g = canonical_geom(cs)
        for k in range(4):
            points[(0, k)] = g["op"][k]
            curves[((0, k), (0, (k + 1) % 4))] = g["oc"][k]
        return face, points, curves
    for lvl, (_, cs) in enumerate(face.layers):
        g = canonical_geom(cs)
        n = cs.n_outer
        for k in range(n):
            j = (k + 1) % n
            points[(lvl, k)], points[(lvl + 1, k)] = g["ip"][k], g["op"][k]
            if lvl == 0:
                curves[((0, k), (0, j))] = g["ic"][k]
            curves[((lvl + 1, k), (lvl + 1, j))] = g["oc"][k]
            curves[((lvl, k), (lvl + 1, k))] = g["rc"][k]
    return face, points, curves


@pytest.mark.parametrize("name", SPECS)
def test_declared_corners_and_edges_are_the_gmsh_face(name):
    spec = SPECS[name]()
    with Session(f"sections-{name}"):
        face, points, curves = _realised(spec)
        levels = layout_of(spec).levels(spec)
        scale = max(o.max_extent for o in spec.outlines)
        declared = set()
        for lvl, level in enumerate(levels):
            for k, (u, v) in enumerate(level.corners):
                want = FRAME.position + u * FRAME.right + v * FRAME.up
                got = np.array(gmsh.model.getValue(0, points[(lvl, k)], []))
                assert np.linalg.norm(got - want) <= 1e-12 * scale, (lvl, k, got, want)
            for e in level.edges:
                declared.add((e.a, e.b))
                tag = abs(curves[(e.a, e.b)])
                grading, n = _transfinite(tag)
                assert n == e.divisions + 1, (e, n)
                assert grading == _uniform(e.grading), (e, grading)
        assert declared == set(curves)                          # every curve declared once
        assert len(levels) == len(spec.layer_names) + (spec.layout == "oh")


def _uniform(grading):
    """A grading with any kind and coefficient 1 is uniform: None."""
    return None if grading is None or grading[1] == 1.0 else tuple(grading)


def _transfinite(curve):
    """(grading, nodes) of a curve's transfinite setting: the grading as
    the builder set it (gmsh has no getter), the nodes from a 1-D mesh."""
    gmsh.model.mesh.generate(1)
    return (_uniform(_SET.get(curve, ("unset", 0.0))),
            len(gmsh.model.mesh.getNodes(1, curve, includeBoundary=True)[0]))


_SET: dict[int, tuple] = {}


@pytest.fixture(autouse=True)
def _record_transfinite(monkeypatch):
    """Record each curve's transfinite grading as the builders set it."""
    _SET.clear()
    real = gmsh.model.mesh.setTransfiniteCurve

    def record(tag, n, kind="Progression", coef=1.0):
        _SET[tag] = (kind, coef)
        return real(tag, n, kind, coef)
    monkeypatch.setattr(gmsh.model.mesh, "setTransfiniteCurve", record)


@pytest.mark.parametrize("name", SPECS)
def test_patches_name_the_faces_surfaces(name):
    """Each declared patch's corners are the corners of the surface the
    face builds there, with the patch's material."""
    spec = SPECS[name]()
    with Session(f"patches-{name}"):
        face, points, _ = _realised(spec)
        surfaces = [(mat, s) for mat, cs in face.layers for s in cs.surfaces]
        for (mat, cyc), (smat, s) in zip(layout_of(spec).patches(spec), surfaces, strict=True):
            assert mat == smat
            corners = {abs(t) for _, t in gmsh.model.getBoundary([(2, s)], recursive=True)}
            assert corners == {points[c] for c in cyc}, (mat, cyc)


def test_corner0_and_signature_kinds_come_from_the_layout():
    from hexmesh.assembly.signature import signature
    sig = signature(SPECS["rect-3layer"]())
    assert [l.kind for l in sig.layers] == [oh.CORE_KIND, oh.RING_KIND, oh.RING_KIND]
    assert oh.corner0_angle(SPECS["rect-2"]()) == pytest.approx(math.atan2(0.05, 0.10))
    assert oh.corner0_angle(SPECS["circle-rot"]()) == pytest.approx(math.pi / 4 + math.radians(30))


def test_h_corner0_and_signature_kind():
    from hexmesh.assembly.signature import signature
    assert [l.kind for l in signature(SPECS["h-2"]()).layers] == [h.CORE_KIND]
    assert h.corner0_angle(SPECS["h-rot-bump"]()) == pytest.approx(
        math.atan2(0.05, 0.10) - math.radians(17))


def test_every_layout_row_has_its_geometry():
    """``core.shape.LAYOUTS`` holds the scalars ``core`` needs per layout
    (task 0084): each row's layout exists in ``sections`` and its numbers
    are the layout's geometry.  The O-H wall span itself is checked on
    the built face in ``test_first_cell``."""
    from hexmesh.core.shape import LAYOUTS
    assert set(LAYOUTS) == {"oh", "h"}
    assert oh.OH_RATIO == LAYOUTS["oh"]["ratio"]
    centre = oh.levels(SPECS["circle"]())[0].corners
    assert np.hypot(*np.transpose(centre)) == pytest.approx(LAYOUTS["oh"]["ratio"] * 0.05)
    assert LAYOUTS["h"] == {}                    # the wall span is the side itself
    assert len(h.levels(SPECS["h-2"]())) == 1
