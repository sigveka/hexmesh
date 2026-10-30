"""
Duct tap prototype (task 0069, decision 0033 B): a tap narrower than its
face, hole on the wall, the branch's ring layer continued as a dome.

Accept (for a prototype): a rectangular and a round tap on a 2:1 duct,
wide face, ratio 0.6, mesh all-hex with meshed = predicted, class-0 ports
(standard O-H faces) and every wall node on its analytic surface.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight
from hexmesh.assembly.duct_tap import DuctTap
from hexmesh.core.spec import PipeSpec

B = 0.05
A = 2 * B           # 2:1 duct, the tap on a wide face (half-width A)


def _spec(n=4):
    return PipeSpec(nang_w=n, nang_h=n).core("fluid", half_w=A, half_h=B, nrad=3)


def _asm(tap, n=4):
    asm = Assembly(_spec(n), direction=[1, 0, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=n))
    main, branch = asm.add(tap)
    asm.add(main, Straight(0.2, n_layers=n))
    asm.add(branch, Straight(0.1, n_layers=n))
    return asm


def _tap(shape):
    geo = dict(along=0.6 * A, across=0.6 * A) if shape == "rect" else dict(radius=0.6 * A)
    return DuctTap(run_length=3 * A + 2 * B, branch_length=B + 2 * A, n_run=4, n_branch=4, **geo)


def _wall_deviation(asm, shape):
    """Largest distance of a wall node of the tap from the duct's planes or
    the branch's walls (planes, or the cylinder of a round tap)."""
    e = asm.edges[1]
    tap = e.fitting
    o, ex, ey, ez, a, b, _ = tap._basis(e.ports[0].frame, e.ports[0].spec)
    p, q = tap._hole()
    worst = 0.0
    for dim, tag in gmsh.model.getPhysicalGroups(2):
        if not gmsh.model.getPhysicalName(dim, tag).endswith("_wall"):
            continue
        for s in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            _, xyz, _ = gmsh.model.mesh.getNodes(2, s, includeBoundary=True)
            for P in xyz.reshape(-1, 3):
                X, Y, Z = (P - o) @ ex, (P - o) @ ey, (P - o) @ ez
                if abs(X) > tap.run_length + 1e-9:
                    continue
                if Z > b + 1e-9:
                    if shape == "rect":
                        d = min(abs(abs(X) - p) if abs(Y) <= q + 1e-9 else 9,
                                abs(abs(Y) - q) if abs(X) <= p + 1e-9 else 9)
                    else:
                        d = abs(math.hypot(X, Y) - tap.radius)
                else:
                    d = min(abs(abs(Y) - a), abs(abs(Z) - b))
                worst = max(worst, d)
    return worst


@pytest.mark.parametrize("shape", ["rect", "round"])
def test_tap_meshes_all_hex_and_exact(gmsh_session, shape):
    asm = _asm(_tap(shape))
    asm.validate()                         # class-0 ports: standard O-H faces
    tap = asm.edges[1].fitting
    assert None not in (tap.margin, tap.dome, tap.sheet)      # resolved in add()
    frames = [p.frame for p in asm.edges[1].ports]
    predicted_sj = tap.predicted_sj(frames, asm.edges[1].ports[0].spec)
    assert predicted_sj > 0.3
    asm.mesh()
    types = gmsh.model.mesh.getElements(3)[0]
    assert [gmsh.model.mesh.getElementProperties(t)[0] for t in types] == ["Hexahedron 8"]
    assert sum(len(t) for t in gmsh.model.mesh.getElements(3)[1]) == asm.cell_count()
    report = asm.check_quality()
    assert report.ok, str(report)
    assert _wall_deviation(asm, shape) < 1e-12


def test_layout_is_valid_on_every_face():
    """Pure: wide and narrow face, both sides, 1:1 to 3:1."""
    from hexmesh.assembly.interface import Frame
    inlet = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    for asp in (1, 2, 3):
        spec = PipeSpec(nang_w=4, nang_h=4).core("fluid", half_w=asp * B, half_h=B, nrad=3)
        for face in ("wide", "narrow"):
            fw, depth = (asp * B, B) if face == "wide" else (B, asp * B)
            for side in (1, -1):
                tap = DuctTap(run_length=3 * fw + 2 * depth, branch_length=depth + 2 * fw,
                              along=0.5 * fw, across=0.5 * fw, face=face, side=side,
                              margin=1.0, dome=0.35, sheet=0.35)
                frames = [inlet] + [f for f, _ in tap.ports(inlet, spec)]
                assert tap.layout(frames, spec).validate()["min_corner_sj"] > 0.05


def test_full_width_tap_rejected():
    """q = a puts the hole's corners on the creases: the pillow needs room on
    every side of the hole (task 0069 step 4)."""
    tap = DuctTap(run_length=3 * A, branch_length=B + 2 * A, along=0.3 * A, across=A,
                  margin=1.0, dome=0.35, sheet=0.35)
    with pytest.raises(AssemblyError, match="does not fit"):
        _asm(tap).validate()
