"""
Fitting conformance kit (DESIGN.md §6.1) — the design rules, checked for
every fitting.

Each case builds a small assembly with the fitting under test placed so
that its ports are shared with neighbours (or closing a loop).  Every case
runs the same checks:

* topology    ``ports`` / ``validate`` / ``cell_count`` run without
              GMSH                                               (P3, P4)
              every port pair's switch class is declared         (A4)
* realisation port faces untouched by ``fill``                   (A1, A2)
              no duplicated surfaces, no coincident hex nodes    (P2)
              interior interfaces shared by exactly two fittings (P2)
              hex mesh valid (minSICN > 0)
              every surface in at most one physical group and
              every boundary face of the mesh in one             (A7)
              cell count predicted before GMSH equals the mesh   (P4)
              per-fitting wall groups keep the above        (A7)
* order       every fill order gives the identical mesh          (A6)
* exactness   wall and interface nodes on their analytic surface (§6)

A new fitting is added by writing one case function and listing it in
``CASES``.  A fitting is not finished until it passes the kit.
"""

import math

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import (
    Assembly, Bend, Closure, Elbow, MiterBend, Reducer, SplinePipe, Straight, Tee,
    Transition, Wye,
)
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import PipeSpec


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def _one(radius=0.1):
    return PipeSpec(nang=4).core("fluid", CircleShape(radius=radius, nang=4), nrad=3)


def _two(radius=0.1, dR=0.025):
    return _one(radius).shell("wall", dR=dR, nrad=2)


def _three(radius=0.1):
    return _two(radius).shell("insulation", dR=0.03, nrad=2)


def _three_thin(radius=0.1):
    """Fluid, wall and insulation, 0.3 R in all: inside the wye's thickness
    limit at 60° (0.40 R, task 0053), which `_three` (0.55 R) is not."""
    return _one(radius).shell("wall", dR=0.01, nrad=2).shell("insulation", dR=0.02, nrad=2)


def _duct(half_w=0.1, half_h=0.05, nang_w=4, nang_h=2, name="air", nrad=2):
    """Single-layer rectangular duct, 2:1 by default (task 0028)."""
    return PipeSpec(nang_w=nang_w, nang_h=nang_h).core(
        name, half_w=half_w, half_h=half_h, nrad=nrad)


def _flat(half_w=0.14, half_h=0.07):
    """A duct with ``_one()``'s counts, name and nrad: a transition's partner."""
    return _duct(half_w, half_h, 4, 4, "fluid", 3)


def _square():
    return _duct(0.07, 0.07, 3, 3)


def _in_rect(half_w=0.25, half_h=0.125):
    """Circular pipe in a rectangular block (decision 0026): skewed corner
    lines when the block is not square."""
    return _one().shell("block", outer=RectShape(half_w, half_h, 4, 4), nrad=3)


def _rect_in_circle():
    """2:1 duct in a circular casing: the casing's arcs are unequal."""
    return PipeSpec(nang=4).core("fluid", RectShape(0.1, 0.05, 4, 4), nrad=3).shell(
        "casing", outer=CircleShape(0.16, 4), nrad=3)


def _rect3(half_w=0.1, half_h=0.05, lagging=True):
    """A duct with a wall and lagging, each grown by dR."""
    spec = (PipeSpec(nang=4).core("fluid", RectShape(half_w, half_h, 4, 4), nrad=3)
            .shell("wall", dR=0.01, nrad=2))
    return spec.shell("lagging", dR=0.03, nrad=2) if lagging else spec


def _cyl_box_cyl():
    """Circle, square, circle: a cable in a square filler in a sheath."""
    return (_one(0.05).shell("filler", outer=RectShape(0.08, 0.08, 4, 4), nrad=2)
            .shell("sheath", outer=CircleShape(0.14, 4), nrad=2))


def _between(spec, fitting, **kw):
    """Straight → fitting → Straight."""
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1, **kw)
    asm.add(Straight(0.2, n_layers=2))
    asm.add(fitting)
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _ring(spec, rolls, closer, extra_straight=False):
    asm = Assembly(spec, up=[0, 0, 1], lc=0.1)
    for r in rolls:
        asm.add(Straight(0.6, n_layers=3))
        asm.add(Bend(radius=0.3, angle=90, n_layers=4, roll=r))
    if extra_straight:
        asm.add(Straight(0.6, n_layers=3))
    asm.close(asm.interfaces[-1], asm.inlet, closer)
    return asm


def _rolled_outlet(spec, fitting, degrees):
    """fitting whose outlet interface is rolled by a symmetry angle.

    Exercises a non-zero corner correspondence: the faces are identical but
    corner 0 of the inlet meets corner k of the outlet.
    """
    from hexmesh.assembly.interface import Frame
    from hexmesh.assembly.interface import rotate
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    out = asm.add(fitting)
    f = out.frame
    out.frame = Frame(f.position, f.normal,
                      rotate(f.up, f.normal, math.radians(degrees)))
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _spline(spec, points, **kw):
    """Straight → SplinePipe (points relative to its inlet) → Straight."""
    asm = Assembly(spec, direction=[0, 1, 0], up=[0, 0, 1], lc=0.1)
    start = asm.add(Straight(0.2, n_layers=2)).frame.position
    asm.add(SplinePipe(tuple(tuple(start + p) for p in points), n_layers=20, **kw))
    asm.add(Straight(0.2, n_layers=2))
    return asm


def _tee(ratio, direction=(0, 1, 0), spec=None):
    """Straight → Tee → Straight on both outlets."""
    asm = Assembly(spec or _one(), direction=list(direction), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    main, branch = asm.add(Tee(run_length=0.2, branch_length=0.25,
                               branch_radius=ratio * 0.1), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=2))
    asm.add(branch, Straight(0.2, n_layers=2))
    return asm


def _duct_tap(branch, aspect=2, face="wide", roll=0, direction=(1, 0, 0)):
    """Straight → duct-tap Tee → Straight on both outlets (task 0070).
    *branch* is "rect" or "round", reaching 0.6 of the face's half-width,
    or "full": as wide as the face, 0.6 of it along the main (task 0057)."""
    B = 0.05
    n = 4
    spec = _duct(half_w=aspect * B, half_h=B, nang_w=n, nang_h=n, name="fluid", nrad=3)
    a = aspect * B if face == "wide" else B
    if branch == "full":
        along_up = face == "wide" or aspect == 1      # the tap on an up/down face
        shape = RectShape(a, 0.6 * a, n, n) if along_up else RectShape(0.6 * a, a, n, n)
    elif branch == "rect":
        shape = RectShape(0.6 * a, 0.6 * a, n, n)
    else:
        shape = CircleShape(radius=0.6 * a, nang=n)
    asm = Assembly(spec, direction=list(direction), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=n))
    main, br = asm.add(Tee(branch_length=2 * aspect * B, branch=shape, face=face, roll=roll,
                           n_run=n, n_branch=n), names=["main", "branch"])
    asm.add(main, Straight(0.2, n_layers=n))
    asm.add(br, Straight(0.1, n_layers=n))
    return asm


def _wye(angle, direction=(0, 1, 0), spec=None):
    """Straight → Wye → Straight on both outlets."""
    asm = Assembly(spec or _one(), direction=list(direction), up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=2))
    left, right = asm.add(Wye(angle, run_length=0.25, branch_length=0.4),
                          names=["left", "right"])
    asm.add(left, Straight(0.2, n_layers=2))
    asm.add(right, Straight(0.2, n_layers=2))
    return asm


CASES = {
    "straight":            lambda: _between(_one(), Straight(0.3, n_layers=3)),
    "straight-2layer":     lambda: _between(_two(), Straight(0.3, n_layers=3)),
    "bend":                lambda: _between(_one(), Bend(0.3, 90, n_layers=6)),
    "bend-rolled-2layer":  lambda: _between(_two(), Bend(0.3, -60, n_layers=4, roll=45)),
    "closure-planar":      lambda: _ring(_one(), [90, 90, 90], Closure(n_layers=8)),
    "closure-twisted":     lambda: _ring(_one(), [60, 0], Closure(n_layers=12),
                                         extra_straight=True),
    "bend-as-closer":      lambda: _ring(_one(), [90, 90, 90],
                                         Bend(0.3, 90, n_layers=4, roll=90),
                                         extra_straight=True),
    "straight-rolled-90":  lambda: _rolled_outlet(_two(), Straight(0.3, n_layers=3), 90),
    "bend-rolled-180":     lambda: _rolled_outlet(_one(), Bend(0.3, 90, n_layers=4), 180),
    "tee-0.5":             lambda: _tee(0.5),
    "tee-0.9-oblique":     lambda: _tee(0.9, direction=(1, 1, 0.2)),
    "tee-0.5-2layer":      lambda: _tee(0.5, spec=_two()),
    "tee-0.9-3layer":      lambda: _tee(0.9, spec=_three()),
    "tee-0.5-3layer-oblique": lambda: _tee(0.5, direction=(1, 1, 0.2), spec=_three()),
    "tee-duct-rect-2-wide":   lambda: _duct_tap("rect"),
    "tee-duct-rect-2-narrow": lambda: _duct_tap("rect", face="narrow", roll=180),
    "tee-duct-rect-3-wide":   lambda: _duct_tap("rect", aspect=3, direction=(1, 1, 0.2)),
    "tee-duct-round-2-wide":  lambda: _duct_tap("round", roll=180),
    "tee-duct-round-2-narrow": lambda: _duct_tap("round", face="narrow"),
    "tee-duct-round-3-wide":  lambda: _duct_tap("round", aspect=3),
    "tee-duct-full-1-wide":   lambda: _duct_tap("full", aspect=1),
    "tee-duct-full-2-wide":   lambda: _duct_tap("full", roll=180, direction=(1, 1, 0.2)),
    "tee-duct-full-2-narrow": lambda: _duct_tap("full", face="narrow"),
    "wye-60":              lambda: _wye(60),
    "wye-90":              lambda: _wye(90),
    "wye-60-oblique":      lambda: _wye(60, direction=(1, 1, 0.2)),
    "wye-60-2layer":       lambda: _wye(60, spec=_two()),
    "wye-90-2layer":       lambda: _wye(90, spec=_two()),
    "wye-60-3layer":       lambda: _wye(60, spec=_three_thin()),
    "wye-90-3layer-oblique": lambda: _wye(90, direction=(1, 1, 0.2), spec=_three_thin()),
    "miter-1cut":          lambda: _between(_one(), MiterBend(0.3, 90, n_cuts=1)),
    "miter-3cut-2layer":   lambda: _between(_two(), MiterBend(0.3, 90, n_cuts=3)),
    "miter-rolled":        lambda: _between(_two(), MiterBend(0.3, -60, n_cuts=2, roll=30)),
    "elbow-short":         lambda: _between(_two(), Elbow(90, "short", n_layers=4, roll=45)),
    "reducer":             lambda: _between(_one(), Reducer(_one(0.06), 0.15, n_layers=3)),
    "expander":            lambda: _between(_one(0.06), Reducer(_one(), 0.15, n_layers=3)),
    "reducer-2layer":      lambda: _between(_two(), Reducer(_two(0.07, 0.015), 0.2, n_layers=4)),
    "spline-s-bend":       lambda: _spline(_one(), ((0, 0, 0), (0.1, 0.4, 0), (0.4, 0.8, 0),
                                                    (0.5, 1.2, 0))),
    "spline-3d-2layer":    lambda: _spline(_two(), ((0, 0, 0), (0.1, 0.4, 0.1), (0.4, 0.7, 0.4),
                                                    (0.5, 0.9, 0.9)), end_tangent=(0, 0, 1)),
    # axial grading (docs/tasks/0001): curve progression or station spacing
    "straight-graded-2layer": lambda: _between(_two(), Straight(0.3, n_layers=4, axial_grading=1.3)),
    "bend-graded-2layer":  lambda: _between(_two(), Bend(0.3, 90, n_layers=6, axial_grading=0.8)),
    "reducer-graded":      lambda: _between(_one(), Reducer(_one(0.06), 0.15, n_layers=4,
                                                            axial_grading=1.2)),
    "closure-graded":      lambda: _ring(_one(), [90, 90, 90], Closure(n_layers=8, axial_grading=1.15)),
    # layer termination (decision 0006): insulation stops and restarts
    "straight-insulation-gap": lambda: _between(_three(), Straight(
        0.6, n_layers=6, stack_changes=((2, _two()), (4, _three())))),
    "bend-insulation-ends": lambda: _between(_three(), Bend(
        0.3, 90, n_layers=6, axial_grading=1.2, stack_changes=((3, _two()),))),
    "spline-graded":       lambda: _spline(_one(), ((0, 0, 0), (0.1, 0.4, 0), (0.4, 0.8, 0),
                                                    (0.5, 1.2, 0)), axial_grading=1.05),
    # rectangular ducts (task 0028): P = π for 2:1, π/2 for a square
    "duct-straight":       lambda: _between(_duct(), Straight(0.3, n_layers=3)),
    "duct-bend-easy":      lambda: _between(_duct(), Bend(0.3, 90, n_layers=6)),
    "duct-bend-hard":      lambda: _between(_duct(), Bend(0.3, 90, n_layers=6, roll=90)),
    "duct-rolled-180":     lambda: _rolled_outlet(_duct(), Bend(0.3, 90, n_layers=4), 180),
    "duct-miter":          lambda: _between(_duct(), MiterBend(0.3, 90, n_cuts=2, roll=30)),
    # absorbs 49.9° of twist: modulo π, where a circle would take −40.1°
    "duct-closure":        lambda: _ring(_duct(), [60, 0, 120], Closure(n_layers=12)),
    "duct-spline":         lambda: _spline(_duct(), ((0, 0, 0), (0.1, 0.4, 0), (0.4, 0.8, 0),
                                                     (0.5, 1.2, 0))),
    "square-bend-rolled":  lambda: _between(_square(), Bend(0.3, -60, n_layers=4, roll=45)),
    "square-rolled-90":    lambda: _rolled_outlet(_square(), Straight(0.3, n_layers=3), 90),
    # profiled reducers (task 0031): stations on R(s), chords within tolerance
    "profile-cosine":      lambda: _between(_one(), Reducer(_one(), 0.4, n_layers=40,
                                                            profile=("cosine", 0.25))),
    "profile-cosine-bulge": lambda: _between(_one(), Reducer(_one(), 0.4, n_layers=50,
                                                             profile=("cosine", -0.5))),
    "profile-venturi":     lambda: _between(_one(), Reducer(_one(), 0.8, n_layers=12,
                                                            profile=("venturi", 0.5, 15))),
    "profile-table-2layer": lambda: _between(_two(), Reducer(
        _two(0.06, 0.015), 0.4, n_layers=16, axial_grading=1.1,
        profile=((0, 1), (0.3, 0.8), (0.6, 0.7), (1, 0.6)))),
    # layer outlines (decision 0026, task 0045); the stacks × straight,
    # easy-way and hard-way bend are added below the dict
    "outline-c-r-c-rolled": lambda: _between(_cyl_box_cyl(), Bend(0.5, -60, n_layers=4,
                                                                  roll=45)),
    "outline-lagging-gap":  lambda: _between(_rect3(), Straight(
        0.6, n_layers=6, stack_changes=((2, _rect3(lagging=False)), (4, _rect3())))),
    "outline-reducer":      lambda: _between(_rect3(), Reducer(_rect3(0.08, 0.04), 0.2,
                                                               n_layers=3)),
    "outline-miter":        lambda: _between(_in_rect(), MiterBend(0.5, 90, n_cuts=2)),
    # transitions (task 0029): equal counts per side, so class 0
    "transition-circle-square": lambda: _between(_one(), Transition(_flat(0.09, 0.09), 0.3, 4)),
    "transition-circle-2to1": lambda: _between(_one(), Transition(_flat(), 0.3, 4)),
    "transition-2to1-circle": lambda: _between(_flat(), Transition(_one(), 0.3, 4)),
    "transition-2to1-1to1": lambda: _between(_flat(), Transition(_flat(0.1, 0.1), 0.2, 3,
                                                                axial_grading=1.2)),
    # multi-layer transitions (task 0046): every outline blends
    "transition-2layer-circle-rect": lambda: _between(_two(), Transition(
        _rect3(0.14, 0.07, lagging=False), 0.3, 4)),
    "transition-square-shell-circle": lambda: _between(_in_rect(0.15, 0.15), Transition(
        _one().shell("block", dR=0.08, nrad=3), 0.3, 4)),
    "transition-3layer-circle-2to1": lambda: _between(_three(), Transition(
        PipeSpec(nang=4).core("fluid", RectShape(0.15, 0.075, 4, 4), nrad=3)
        .shell("wall", dR=0.025, nrad=2).shell("insulation", dR=0.03, nrad=2), 0.4, 6,
        axial_grading=1.1)),
}


OUTLINE_STACKS = {
    "circle-square": lambda: _in_rect(0.15, 0.15),
    "circle-2to1":   _in_rect,
    "2to1-circle":   _rect_in_circle,
    "rrr":           _rect3,
    "c-r-c":         _cyl_box_cyl,
}
OUTLINE_FITTINGS = {
    "straight": lambda: Straight(0.3, n_layers=3),
    "easy":     lambda: Bend(0.5, 90, n_layers=6),            # turns about the long side
    "hard":     lambda: Bend(0.5, 90, n_layers=6, roll=90),   # turns about the short side
}
CASES.update({
    f"outline-{s}-{f}": (lambda s=s, f=f: _between(OUTLINE_STACKS[s](), OUTLINE_FITTINGS[f]()))
    for s in OUTLINE_STACKS for f in OUTLINE_FITTINGS
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(name="kit"):
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add(name)


def _face_snapshot(asm):
    """Port-face entities: surface → (boundary curves, boundary point coords)."""
    snap = {}
    for iface in asm.interfaces:
        for _, cs in iface.face.layers:
            for s in cs.surfaces:
                curves = gmsh.model.getBoundary([(2, s)], oriented=False)
                pts = gmsh.model.getBoundary([(2, s)], recursive=True)
                snap[s] = (
                    sorted(abs(c) for _, c in curves),
                    sorted(tuple(np.round(gmsh.model.getValue(0, p, []), 12))
                           for _, p in pts),
                )
    return snap


def _hex_nodes():
    _, _, enodes = gmsh.model.mesh.getElements(3)
    used = np.unique(np.concatenate(enodes))
    tags, xyz, _ = gmsh.model.mesh.getNodes()
    lookup = dict(zip(tags, xyz.reshape(-1, 3)))
    return np.round(np.array([lookup[t] for t in used]), 9)


def _boundary_faces():
    """Node-sets of hex faces that belong to exactly one hex."""
    faces = gmsh.model.mesh.getElementFaceNodes(5, 4)   # 5 = hex8, quads
    faces = np.sort(faces.reshape(-1, 4), axis=1)
    uniq, counts = np.unique(faces, axis=0, return_counts=True)
    return {tuple(f) for f in uniq[counts == 1]}


def _grouped_quads():
    """Node-sets of quads on surfaces in physical groups, plus group count per surface."""
    quads, owners = set(), {}
    for d, t in gmsh.model.getPhysicalGroups(2):
        for s in gmsh.model.getEntitiesForPhysicalGroup(d, t):
            owners[s] = owners.get(s, 0) + 1
            types, _, nodes = gmsh.model.mesh.getElements(2, s)
            for ty, nd in zip(types, nodes):
                if ty == 3:   # quad4
                    for q in np.sort(nd.reshape(-1, 4), axis=1):
                        quads.add(tuple(q))
    return quads, owners


def _extent(spec):
    """Largest distance of *spec*'s outermost outline from the axis: the
    scale of the deviations."""
    return spec.core_shape.max_extent if not spec.shells else spec.outlines[-1].max_extent


def _outline_dev(u, v, spec0, spec1=None, t=None):
    """Distance-like deviation of in-section points (*u* along the frame's
    right, *v* along up) from the nearest layer boundary of *spec0*: 0 on an
    outline (decision 0026).  With *spec1* and per-point fractions *t*, the
    outlines are interpolated linearly between the two (a reducer's slab:
    its walls are cones and planes)."""
    c, d = math.cos(spec0.rot_rad), math.sin(spec0.rot_rad)
    u, v = c * u + d * v, -d * u + c * v
    o0 = spec0.outlines
    o1 = o0 if spec1 is None else spec1.outlines[:len(o0)]
    t = np.zeros(len(u)) if t is None else t
    devs = []
    for a, b in zip(o0, o1):
        if isinstance(a, CircleShape):
            r = a.radius + (b.radius - a.radius) * t
            devs.append(np.abs(np.hypot(u, v) - r))
        else:
            hw = a.half_w + (b.half_w - a.half_w) * t
            hh = a.half_h + (b.half_h - a.half_h) * t
            devs.append(np.abs(np.maximum(np.abs(u) - hw, np.abs(v) - hh)))
    return np.min(devs, axis=0)


def _tee_deviation(tee, inlet, spec, x) -> float:
    """Largest distance of the points *x* from the nearest of a tee's layer
    boundaries, each the union of a main cylinder and a branch cylinder
    (z ≥ 0 along the branch axis) grown by the shells' cumulative
    thickness (decision 0028), relative to the outer radius."""
    o, ex, _, ez = tee._origin_basis(inlet)
    R, r = spec.core_shape.radius, tee.branch_radius
    v = x - o
    dm = np.linalg.norm(v - np.outer(v @ ex, ex), axis=1)
    db = np.linalg.norm(v - np.outer(np.clip(v @ ez, 0, None), ez), axis=1)
    Ts = [o_.radius - R for o_ in spec.outlines]
    dev = np.min([np.abs(np.minimum(dm - (R + T), db - (r + T))) for T in Ts], axis=0)
    return float(dev.max() / (R + Ts[-1]))


def _duct_tap_deviation(tee, inlet, spec, x) -> float:
    """Largest distance of the points *x* from a duct tap's walls: the
    duct's faces |y| = a, |z| = b, or (z ≥ b) the branch's planes or
    cylinder, relative to the duct's half-diagonal (task 0070)."""
    tap = tee._tap(inlet, spec)
    o, ex, ey, ez, a, b, _ = tap._basis(inlet, spec)
    v = x - o
    X, Y, Z = v @ ex, v @ ey, v @ ez
    main = np.minimum(np.abs(np.abs(Y) - a), np.abs(np.abs(Z) - b))
    if tap.radius is not None:
        br = np.abs(np.hypot(X, Y) - tap.radius)
    else:
        p, q = tap._hole()
        br = np.abs(np.maximum(np.abs(X) - p, np.abs(Y) - q))
    br = np.where(Z >= b - 1e-9, br, np.inf)
    return float(np.minimum(main, br).max() / math.hypot(a, b))


def wall_deviations(asm) -> dict[str, float]:
    """Largest distance, relative to the outer radius, of any node on a
    fitting's wall or material-interface surfaces from its analytic surface
    (DESIGN §6, task 0025).  Pure check on a meshed assembly; reusable for
    new fittings.

    The surface comes from the fitting's own ``Path``:
    * arc axial curves (``Bend``, ``Elbow``): the torus about the arc;
    * straight axial curves (``Straight``, ``Reducer``, ``MiterBend`` legs):
      the distance to the axis line of the slab whose axis segment is
      nearest, with layer radii interpolated linearly between its two
      stations (a cone for a reducer).  A node on a miter cut lies on both
      legs' cylinders;
    * any layer outline (decision 0026): distances are taken to every
      layer's outline in the section frame (``_outline_dev``), so circles
      and rectangles alike;
    * other paths (``SplinePipe``, ``Closure``, and ``Transition``, whose
      stations blend two shapes): no closed form; they must
      have one axial layer per slab, so no surface carries interior nodes
      (asserted), and they are not measured;
    * ``Tee``: the union of the main and branch cylinders, per layer;
      ``Wye``: the level sets ``Skeleton.distance = R + T_l`` (tasks 0051,
      0052, 0053; their nodes are projected, decision 0029).
    """
    fill = asm._fill
    # end annuli of a terminated layer lie on station planes, not cylinders
    ends = {t for t, g in fill.wall_groups.items() if g.endswith("_end")}
    sides = (set(fill.walls) - ends) | {t for ts in fill.interfaces.values() for t in ts}
    out = {}
    for e in asm.edges:
        frames = [p.frame for p in e.ports]
        spec = e.ports[0].spec
        vols = asm.fitting_volumes()[e.index]
        bnd = {abs(t) for _, t in gmsh.model.getBoundary([(3, v) for v in vols],
                                                       combined=False, oriented=False)}
        surfs = sorted(bnd & sides)
        x = np.vstack([gmsh.model.mesh.getNodes(2, t, includeBoundary=True)[1].reshape(-1, 3)
                       for t in surfs])
        if isinstance(e.fitting, Tee) and isinstance(spec.core_shape, RectShape):
            out[e.name] = _duct_tap_deviation(e.fitting, frames[0], spec, x)
            continue
        if isinstance(e.fitting, Tee):
            out[e.name] = _tee_deviation(e.fitting, frames[0], spec, x)
            continue
        if isinstance(e.fitting, Wye):
            R = spec.core_shape.radius
            radii = [o_.radius for o_ in spec.outlines]
            dist = e.fitting.skeleton(frames[0], spec).distance(x)
            dev = np.min([np.abs(dist - rho) for rho in radii], axis=0)
            out[e.name] = float(dev.max() / radii[-1])
            continue
        path = e.fitting.path(frames[0], frames[1], spec)
        scale = max(_extent(path.spec_at(k, spec)) for k in range(len(path.frames)))
        if path.axial is not None:                     # torus about the arc
            a, c = path.axial.axis, path.axial.centre
            rb = np.linalg.norm((path.frames[0].position - c)
                                - np.dot(path.frames[0].position - c, a) * a)
            v = x - c
            h = v @ a
            rho = np.linalg.norm(v - np.outer(h, a), axis=1)
            # the meridian plane's (outward, axis) directions are fixed in
            # the section frame, whatever the angle about the axis
            f0 = path.frames[0]
            er = (f0.position - c) / rb
            u = (rho - rb) * (f0.right @ er) + h * (f0.right @ a)
            v = (rho - rb) * (f0.up @ er) + h * (f0.up @ a)
            dev = _outline_dev(u, v, spec)
        elif (path.is_straight or path.prism) and not path.blend:   # per-slab axis lines
            seg = np.full(len(x), np.inf)               # distance to the nearest axis segment
            dev = np.full(len(x), np.inf)
            for k in range(len(path.layers)):
                p0, p1 = path.frames[k].position, path.frames[k + 1].position
                L = np.linalg.norm(p1 - p0)
                ax = (p1 - p0) / L
                t = (x - p0) @ ax
                u = np.clip(t / L, 0, 1)
                to_seg = np.linalg.norm(x - (p0 + np.outer(u * L, ax)), axis=1)
                w = (x - p0) - np.outer(t, ax)
                if all(isinstance(o, CircleShape) for o in spec.outlines):
                    wu, wv = np.linalg.norm(w, axis=1), np.zeros(len(w))   # any frame
                else:
                    # section frame of this leg: an untilted station on it
                    f = next(f for j, f in enumerate(path.frames)
                             if path.stretch_at(j) is None and f.normal @ ax > 1 - 1e-12)
                    wu, wv = w @ f.right, w @ f.up
                dk = _outline_dev(wu, wv, path.slab_spec(k, spec),
                                  path.spec_at(k + 1, spec), u)
                nearer = to_seg < seg - 1e-12 * scale
                tie = np.abs(to_seg - seg) <= 1e-12 * scale     # on a cut: either leg
                dev = np.where(nearer, dk, np.where(tie, np.minimum(dev, dk), dev))
                seg = np.minimum(seg, to_seg)
        else:
            assert all(n == 1 for n in path.layers), (
                f"{e}: no analytic surface, so every slab needs one axial layer")
            continue
        out[e.name] = float(dev.max() / scale)
    return out


# ---------------------------------------------------------------------------
# The kit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES)
class TestConformance:

    def test_topology_without_gmsh(self, case):
        assert not gmsh.isInitialized()
        asm = CASES[case]()
        asm.validate()
        assert asm.cell_count() > 0
        assert not gmsh.isInitialized()

    def test_switch_classes_declared(self, case):
        """Every port pair's switch class is one the fitting declares (A4)."""
        from hexmesh.assembly.signature import classify, signature, strategies_for
        asm = CASES[case]()
        for edge in asm.edges:
            a = signature(edge.ports[0].spec)
            for k, port in enumerate(edge.ports[1:]):
                c = classify(a, signature(port.spec))
                assert c.cls in strategies_for(edge.fitting, k), (edge, c)
        assert not gmsh.isInitialized()

    def test_realisation(self, case):
        _session()
        try:
            asm = CASES[case]()
            predicted = asm.cell_count()
            asm.build_faces()
            before = _face_snapshot(asm)
            asm.fill()
            assert _face_snapshot(asm) == before, "fill modified a port face"

            # No duplicated surfaces anywhere in the model
            com = [tuple(np.round(gmsh.model.occ.getCenterOfMass(2, s), 9))
                   for _, s in gmsh.model.getEntities(2)]
            assert len(com) == len(set(com)), "coincident surfaces in model"

            # Interior interfaces shared by exactly two fittings
            for iface in asm.interfaces:
                assert len(iface.edges) in (1, 2)

            asm.mesh()
            c = _hex_nodes()
            assert len(c) == len(np.unique(c, axis=0)), "coincident hex nodes"

            report = asm.check_quality()
            assert report.ok, str(report)

            n_hex = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
            assert n_hex == predicted, f"predicted {predicted} cells, meshed {n_hex}"

            quads, owners = _grouped_quads()
            assert all(n == 1 for n in owners.values()), "surface in two groups"
            missing = _boundary_faces() - quads
            assert not missing, f"{len(missing)} boundary faces in no group"
        finally:
            gmsh.finalize()

    def test_walls_by_fitting(self, case):
        """Per-fitting wall groups (docs/tasks/0009) keep rule A7."""
        _session()
        try:
            asm = CASES[case]()
            asm.mesh(walls_by_fitting=True)
            quads, owners = _grouped_quads()
            assert all(n == 1 for n in owners.values()), "surface in two groups"
            missing = _boundary_faces() - quads
            assert not missing, f"{len(missing)} boundary faces in no group"
            roles = asm.group_roles()
            walls = {}
            for d, t in gmsh.model.getPhysicalGroups(2):
                name = gmsh.model.getPhysicalName(d, t)
                if roles[name] == "wall":
                    walls[name] = set(gmsh.model.getEntitiesForPhysicalGroup(d, t))
            assert set().union(*walls.values()) == set(asm._fill.walls)
            # {layer}_wall_{fitting} or {layer}_end_{fitting}, never unsplit
            layers = {n for e in asm.edges for p in e.ports for n in p.spec.layer_names}
            allowed = {f"{l}_{kind}_{e.name}" for l in layers for kind in ("wall", "end")
                       for e in asm.edges}
            assert set(walls) <= allowed, set(walls) - allowed
        finally:
            gmsh.finalize()

    def test_walls_exact(self, case):
        """Every wall and interface node on its analytic surface (DESIGN §6).
        Junction walls are put there by node projection (decision 0029), to
        1e-6 R (task 0051)."""
        _session()
        try:
            asm = CASES[case]()
            asm.mesh()
            dev = wall_deviations(asm)
            tol = 1e-6 if case.startswith(("tee", "wye")) else 1e-9
            bad = {k: v for k, v in dev.items() if v > tol}
            assert not bad, f"wall nodes off the analytic surface (× R): {bad}"
        finally:
            gmsh.finalize()

    def test_order_independence(self, case):
        meshes = []
        for reverse in (False, True):
            _session()
            try:
                asm = CASES[case]()
                order = list(range(len(asm.edges)))
                asm.build(order[::-1] if reverse else order)
                asm.mesh()
                c = _hex_nodes()
                n = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
                meshes.append((n, c[np.lexsort(c.T)]))
            finally:
                gmsh.finalize()
        (n_a, c_a), (n_b, c_b) = meshes
        assert n_a == n_b
        np.testing.assert_allclose(c_a, c_b, atol=1e-9)


# ---------------------------------------------------------------------------
# The kit must catch violations
# ---------------------------------------------------------------------------

class _OwnOutlet(Straight):
    """Violates A1/A2: builds its own outlet face instead of using the port."""

    def fill(self, faces, frames, spec, lc):
        from hexmesh.assembly.sweep import _fill_slab
        from hexmesh.assembly.interface import build_face
        own = build_face(spec, frames[1], lc)
        gmsh.model.occ.synchronize()
        return _fill_slab(faces[0], own, self.n_layers)


class _NoWalls(Straight):
    """Violates A7: does not report its wall surfaces."""

    def fill(self, faces, frames, spec, lc):
        result = super().fill(faces, frames, spec, lc)
        result.walls.clear()
        return result


@pytest.mark.parametrize("bad, message", [
    (_OwnOutlet(0.3, n_layers=3), "coincident surfaces"),
    (_NoWalls(0.3, n_layers=3), "boundary faces in no group"),
])
def test_kit_detects_violations(bad, message):
    CASES["_bad"] = lambda: _between(_one(), bad)
    try:
        with pytest.raises(AssertionError, match=message):
            TestConformance().test_realisation("_bad")
    finally:
        del CASES["_bad"]
