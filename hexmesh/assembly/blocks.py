"""
Blocks — every multi-port fitting is a layout of hex blocks (DESIGN.md §6.1).

A ``BlockLayout`` describes hex blocks by their 8 corner vertices.  Shared
corners, edges and faces are keyed by *topological identity* (vertex ids),
never by coordinates, so blocks that share a face share its entities by
construction.  Port faces are bound to existing interface entities.

Pipeline (mirrors the assembly)
-------------------------------
``validate()``  Pure numpy.  Face sharing, port binding, edge division
                classes (opposite edges of a block must have equal
                divisions; classes are solved by union-find and must each
                get exactly one count) and corner Jacobians.
``realise()``   GMSH.  Points, curves, surfaces, volumes and transfinite
                constraints; bound entities are reused, never recreated.

Hex corner order (GMSH convention)::

        7-------6        k
       /|      /|        |  j
      4-------5 |        | /
      | 3-----|-2        |/
      |/      |/         +----- i
      0-------1
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np
import gmsh

from .. import _occ
from ..core.shape import OH_RATIO   # re-exported: inner-square scale of the OH face
from ..core.cross_section import interface_group_name
from ..quality_hex import corner_scaled_jacobians
from .corners import curve_endpoints
from .sweep import CurveMesh, FillResult, _ruled

_EDGES = {  # direction → the four parallel edges
    'i': [(0, 1), (3, 2), (4, 5), (7, 6)],
    'j': [(0, 3), (1, 2), (4, 7), (5, 6)],
    'k': [(0, 4), (1, 5), (2, 6), (3, 7)],
}
_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


class LayoutError(ValueError):
    """Raised by ``BlockLayout.validate``."""


# ---------------------------------------------------------------------------
# Edge geometry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Line:
    pass


@dataclass(frozen=True)
class ArcAbout:
    """Circular arc about *centre* (must be equidistant from both ends)."""
    centre: tuple


@dataclass(frozen=True)
class Spline:
    """Spline through interior points (endpoints excluded)."""
    points: tuple


@dataclass(frozen=True)
class Polyline:
    """Straight segments through interior points (endpoints excluded): a
    C0 curve, for an edge that crosses a crease of the wall (a wye's
    crotch, task 0030), where a spline would overshoot."""
    points: tuple


def _key(*ids) -> frozenset:
    return frozenset(ids)


def _same_grading(g, h) -> bool:
    return g[0] == h[0] and math.isclose(g[1], h[1], rel_tol=1e-12)


@dataclass
class _Edge:
    a: object
    b: object
    geom: object = field(default_factory=Line)
    tag: int | None = None          # bound or realised curve tag (unsigned)
    start: object = None            # vertex id at the curve's parametric start
    grading: tuple = ("Progression", 1.0)   # oriented a → b


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class BlockLayout:
    """Hex blocks with shared, topologically keyed entities."""

    def __init__(self) -> None:
        self.coords:  dict[object, np.ndarray] = {}
        self.points:  dict[object, int] = {}           # vertex id → point tag
        self.edges:   dict[frozenset, _Edge] = {}
        self.faces:   dict[frozenset, int] = {}        # bound/realised surfaces
        self.port_faces: set[frozenset] = set()
        self.blocks:  list[tuple[tuple, str]] = []
        self.counts:  dict[frozenset, int] = {}        # fixed edge divisions
        # OCC filling for curved faces that are neither planar nor a ruled
        # cylinder: None for a plate (``addSurfaceFilling``), or a
        # ``addBSplineFilling`` type ("Stretch", "Curved")
        self.filling: str | None = None
        self._classes: dict[frozenset, tuple[int, tuple]] | None = None

    # -- construction -----------------------------------------------------

    def vertex(self, vid, coord, point: int | None = None):
        """Declare vertex *vid* at *coord*; *point* binds an existing tag."""
        self.coords[vid] = np.asarray(coord, dtype=float)
        if point is not None:
            self.points[vid] = point
        return vid

    def edge(self, a, b, geom=None, curve: int | None = None,
             divisions: int | None = None, grading: tuple | None = None) -> None:
        """Declare the edge *a*–*b* (straight by default).

        *curve* binds an existing curve tag; *divisions* fixes the edge's
        division class; *grading* is a ``(kind, coef)`` transfinite grading
        oriented from *a* to *b* (default uniform).
        """
        e = _Edge(a, b, geom or Line(), grading=grading or ("Progression", 1.0))
        if curve is not None:
            e.tag = abs(curve)
            t0, _ = curve_endpoints(abs(curve))
            e.start = a if self.points.get(a) == t0 else b
        self.edges[_key(a, b)] = e
        if divisions is not None:
            self.counts[_key(a, b)] = divisions

    def bind_point(self, vid, point: int) -> None:
        self.points[vid] = point

    def bind_edge(self, a, b, curve: int) -> None:
        """Bind declared edge *a*–*b* to an existing curve (points bound first)."""
        e = self.edges.setdefault(_key(a, b), _Edge(a, b))
        e.tag = abs(curve)
        t0, _ = curve_endpoints(abs(curve))
        e.start = a if self.points.get(a) == t0 else b

    def port_face(self, ids, surface: int | None = None) -> None:
        """Declare face *ids* (4 vertex ids, cyclic) as a port face.

        Declared in the pure phase so validation can check that blocks tile
        every port exactly; *surface* binds the realised surface later.
        """
        k = _key(*ids)
        self.port_faces.add(k)
        if surface is not None:
            self.faces[k] = surface

    def block(self, ids, material: str) -> None:
        """Add a hex block with corners *ids* in GMSH order.

        A left-handed corner order is mirrored (bottom and top faces
        reversed) so callers need not care about handedness.
        """
        ids = tuple(ids)
        if len(ids) != 8 or len(set(ids)) != 8:
            raise LayoutError(f"block needs 8 distinct vertices, got {ids}")
        p = [self.coords[v] for v in ids]
        if np.dot(np.cross(p[1] - p[0], p[3] - p[0]), p[4] - p[0]) < 0:
            ids = (ids[0], ids[3], ids[2], ids[1], ids[4], ids[7], ids[6], ids[5])
        self.blocks.append((ids, material))

    # -- validation (pure) ------------------------------------------------

    def face_use(self) -> dict[frozenset, list[tuple[int, tuple]]]:
        """Face key → list of (block index, cyclic vertex ids)."""
        use: dict[frozenset, list] = {}
        for bi, (ids, _) in enumerate(self.blocks):
            for f in _FACES:
                cyc = tuple(ids[i] for i in f)
                use.setdefault(_key(*cyc), []).append((bi, cyc))
        return use

    def _division_classes(self) -> dict[frozenset, tuple[int, tuple]]:
        """Edge key → (divisions, grading oriented edge.a → edge.b).

        Parallel edges of a block form one class (union-find).  Each class
        node also tracks its *parity*: whether the edge's a → b runs with or
        against the class root, so a progression keeps its direction across
        the class.  Every edge of a class gets the class grading; declared
        gradings that disagree (in kind, coefficient or direction) raise.
        """
        parent: dict[frozenset, frozenset] = {}
        parity: dict[frozenset, int] = {}       # 1: a → b runs against parent

        def find(x):
            if x not in parent:
                parent[x], parity[x] = x, 0
            path = []
            while parent[x] != x:
                path.append(x)
                x = parent[x]
            acc = 0
            for y in reversed(path):            # compress, accumulating parity
                acc ^= parity[y]
                parent[y], parity[y] = x, acc
            return x

        # Orientation of every edge: the declared a → b, else the first
        # traversal in block order — the order in which ``realise`` creates
        # undeclared edges, so both agree.
        start: dict[frozenset, object] = {k: e.a for k, e in self.edges.items()}
        for ids, _ in self.blocks:
            for group in _EDGES.values():
                for a, b in group:
                    start.setdefault(_key(ids[a], ids[b]), ids[a])

        def flip(k, a) -> int:
            """1 if the block traverses edge *k* against its orientation."""
            return 0 if start[k] == a else 1

        for ids, _ in self.blocks:
            for group in _EDGES.values():
                (a0, b0), *rest = group
                k0 = _key(ids[a0], ids[b0])
                f0 = flip(k0, ids[a0])
                for a, b in rest:
                    k = _key(ids[a], ids[b])
                    rel = flip(k, ids[a]) ^ f0  # k against k0
                    r0, r = find(k0), find(k)
                    if r0 != r:
                        parent[r] = r0
                        parity[r] = parity[k] ^ rel ^ parity[k0]

        root_count: dict[frozenset, tuple[int, frozenset]] = {}
        for k, n in self.counts.items():
            r = find(k)
            if r in root_count and root_count[r][0] != n:
                other = root_count[r][1]
                raise LayoutError(
                    f"division conflict: edge {set(k)} needs {n} but parallel "
                    f"edge {set(other)} needs {root_count[r][0]}"
                )
            root_count[r] = (n, k)

        def to_root(grading, p):
            kind, coef = grading
            return (kind, 1.0 / coef) if p and kind == "Progression" else (kind, coef)

        root_grading: dict[frozenset, tuple[tuple, frozenset]] = {}
        for k, e in self.edges.items():
            if e.grading == ("Progression", 1.0) or k not in parent:
                continue
            r = find(k)
            g = to_root(e.grading, parity[k])
            if r in root_grading and not _same_grading(root_grading[r][0], g):
                other = root_grading[r][1]
                raise LayoutError(
                    f"grading conflict: edge {set(k)} is graded {e.grading} but "
                    f"parallel edge {set(other)} is graded "
                    f"{self.edges[other].grading} (directions compared along the class)"
                )
            root_grading[r] = (g, k)

        result = {}
        for k in list(parent):
            r = find(k)
            if r not in root_count:
                raise LayoutError(
                    f"edge {set(k)} has no division count (its parallel class "
                    f"reaches no edge with a fixed count)"
                )
            g = root_grading.get(r, (("Progression", 1.0), None))[0]
            result[k] = (root_count[r][0], to_root(g, parity[k]))
        return result

    def corner_jacobians(self) -> np.ndarray:
        """Scaled Jacobian at every block corner (straight-edge estimate),
        8 per block, by the same formula as the mesh metric
        (``quality_hex.corner_scaled_jacobians``)."""
        return np.concatenate([
            corner_scaled_jacobians(np.array([self.coords[v] for v in ids]))
            for ids, _ in self.blocks
        ])

    def validate(self) -> dict:
        """Check topology, densities and corner Jacobians; return a report."""
        if not self.blocks:
            raise LayoutError("layout has no blocks")
        for ids, _ in self.blocks:
            for v in ids:
                if v not in self.coords:
                    raise LayoutError(f"vertex {v!r} has no coordinates")
        use = self.face_use()
        for k, users in use.items():
            if len(users) > 2:
                raise LayoutError(f"face {set(k)} is shared by {len(users)} blocks")
        for k in self.port_faces:
            if k not in use:
                raise LayoutError(f"port face {set(k)} is not used by any block")
            if len(use[k]) != 1:
                raise LayoutError(f"port face {set(k)} is interior to the layout")
        self._classes = self._division_classes()
        sj = self.corner_jacobians()
        if sj.min() <= 0:
            bad = int(np.argmin(sj)) // 8
            raise LayoutError(
                f"block {bad} {self.blocks[bad][0]} is inverted or degenerate "
                f"at a corner (scaled Jacobian {sj.min():.3f})"
            )
        boundary = [k for k, u in use.items() if len(u) == 1 and k not in self.port_faces]
        return {"blocks": len(self.blocks), "faces": len(use),
                "wall_faces": len(boundary), "min_corner_sj": float(sj.min())}

    def cell_count(self) -> int:
        """Exact hex count: per block, the product of its three division
        counts (pure; solves the division classes if needed)."""
        if self._classes is None:
            self._classes = self._division_classes()
        total = 0
        for ids, _ in self.blocks:
            n = 1
            for group in _EDGES.values():
                a, b = group[0]
                n *= self._classes[_key(ids[a], ids[b])][0]
            total += n
        return total

    # -- realisation (GMSH) ----------------------------------------------

    def _point(self, vid) -> int:
        if vid not in self.points:
            self.points[vid] = gmsh.model.occ.addPoint(*self.coords[vid])
        return self.points[vid]

    def _curve(self, a, b) -> int:
        """Signed curve tag running a → b."""
        k = _key(a, b)
        e = self.edges.get(k)
        if e is None:
            e = self.edges[k] = _Edge(a, b)
        if e.tag is None:
            geo = gmsh.model.occ
            pa, pb = self._point(e.a), self._point(e.b)
            if isinstance(e.geom, ArcAbout):
                c = geo.addPoint(*e.geom.centre)
                e.tag = _occ.circle_arc(pa, c, pb)
                _occ.discard(c)
            elif isinstance(e.geom, Spline):
                mids = [geo.addPoint(*p) for p in e.geom.points]
                e.tag = _occ.spline([pa, *mids, pb])
            elif isinstance(e.geom, Polyline):
                mids = [geo.addPoint(*p) for p in e.geom.points]
                e.tag = _occ.bspline([pa, *mids, pb], degree=1)
            else:
                e.tag = _occ.line(pa, pb)
            e.start = e.a
        return e.tag if e.start == a else -e.tag

    def _surface(self, cyc) -> int:
        """Bound surface, or a new one (plane if straight and coplanar)."""
        k = _key(*cyc)
        if k not in self.faces:
            geo = gmsh.model.occ
            curves = [self._curve(cyc[i], cyc[(i + 1) % 4]) for i in range(4)]
            loop = geo.addCurveLoop(curves)
            types = [_occ.kind(c) for c in curves]
            straight = all(t == "Line" for t in types)
            if straight and self._coplanar(cyc):
                self.faces[k] = geo.addPlaneSurface([loop])
            elif self._ruled_cylinder(types):
                # two opposite straight lines between two arcs: the ruled
                # surface is the exact cylinder (DESIGN §6, task 0025), as
                # in a sweep's straight slab
                self.faces[k] = _ruled(loop)
            elif self.filling is not None:
                self.faces[k] = geo.addBSplineFilling(loop, type=self.filling)
            else:
                self.faces[k] = geo.addSurfaceFilling(loop)
        return self.faces[k]

    @staticmethod
    def _ruled_cylinder(types) -> bool:
        """Arcs on one pair of opposite sides, lines on the other."""
        for i in (0, 1):
            if (types[i] == types[i + 2] == "Circle"
                    and types[i + 1] == types[(i + 3) % 4] == "Line"):
                return True
        return False

    def _coplanar(self, cyc) -> bool:
        p = [self.coords[v] for v in cyc]
        n = np.cross(p[1] - p[0], p[3] - p[0])
        scale = max(np.linalg.norm(p[2] - p[0]), 1e-30)
        return abs(np.dot(n / max(np.linalg.norm(n), 1e-30), p[2] - p[0])) < 1e-9 * scale

    def realise(self, layer_order: list[str] | None = None) -> FillResult:
        """Build every entity in GMSH and return the fill result.

        *layer_order* (the spec's ``layer_names``, inner → outer) orders
        each material pair in its interface group name, so a pair gets the
        same name here as in a sweep.
        """
        if self._classes is None:
            self.validate()
        geo = gmsh.model.occ
        use = self.face_use()

        for ids, _ in self.blocks:              # curves first (lines only need points)
            for group in _EDGES.values():
                for a, b in group:
                    self._curve(ids[a], ids[b])

        unbound = [set(k) for k in self.port_faces if k not in self.faces]
        if unbound:
            raise LayoutError(f"port faces not bound before realise: {unbound[:2]}")
        result = FillResult()
        surf_of: dict[frozenset, int] = {}
        for k, users in use.items():
            surf_of[k] = self._surface(users[0][1])

        for ids, material in self.blocks:
            sl = geo.addSurfaceLoop([surf_of[_key(*(ids[i] for i in f))] for f in _FACES])
            vol = geo.addVolume([sl])
            result.volumes.setdefault(material, []).append(vol)
            result.mesh_vols.append(vol)

        for k, (n, (kind, coef)) in self._classes.items():
            e = self.edges[k]
            if kind == "Progression" and e.start != e.a:
                coef = 1.0 / coef
            result.curves.append(CurveMesh(e.tag, n + 1, kind, coef))
        materials = {}
        for bi, (ids, material) in enumerate(self.blocks):
            for f in _FACES:
                materials.setdefault(_key(*(ids[i] for i in f)), []).append(material)
        for k, users in use.items():
            result.surfaces.append(surf_of[k])
            if len(users) == 1 and k not in self.port_faces:
                result.walls.append(surf_of[k])
            elif len(users) == 2:
                m0, m1 = materials[k]
                if m0 != m1:
                    if layer_order is not None:
                        m0, m1 = sorted((m0, m1), key=layer_order.index)
                    result.interfaces.setdefault(
                        interface_group_name(m0, m1), []).append(surf_of[k])
        return result


# ---------------------------------------------------------------------------
# OH port faces
# ---------------------------------------------------------------------------
#
# Vertex ids of a port face are (prefix, level, k): level 0 is the core's
# inner square, level l ≥ 1 the outer boundary of layer l-1; corner k is
# named by the frame (corners.corner0_angle + k·2π/n_outer).



def face_levels(spec) -> list[float]:
    """Radius of every corner level of *spec* (level 0 = inner square)."""
    r = [spec.core_shape.radius]
    for sh in spec.shells:
        r.append(r[-1] + sh.dR)
    return [OH_RATIO * r[0], *r]


def face_vertices(layout: BlockLayout, prefix, frame, spec, port: bool = True) -> None:
    """Declare the corners and edges of the OH face at *frame* (pure).

    With ``port=False`` the face is an internal station: its patches are
    shared by two blocks and are not declared as port faces.
    """
    from .corners import corner0_angle
    n = spec.n_outer
    a0 = corner0_angle(spec)
    nang = spec.nang // (n // 4)
    nrads = [spec._core_nrad] + [sh.nrad for sh in spec.shells]
    mprgs = [spec._core_mprg] + [sh.mprg for sh in spec.shells]
    bump = ("Bump", spec.mbmp) if spec.mbmp != 1.0 else None
    for lvl, rad in enumerate(face_levels(spec)):
        for k in range(n):
            ang = a0 + 2 * np.pi * k / n
            layout.vertex((prefix, lvl, k), frame.position
                          + rad * (np.cos(ang) * frame.right + np.sin(ang) * frame.up))
        for k in range(n):
            layout.edge((prefix, lvl, k), (prefix, lvl, (k + 1) % n),
                        divisions=nang, grading=bump)
            if lvl:
                layout.edge((prefix, lvl - 1, k), (prefix, lvl, k),
                            divisions=nrads[lvl - 1],
                            grading=("Progression", mprgs[lvl - 1]))
    if port:
        for _, cyc in face_patches(prefix, spec):
            layout.port_face(cyc)


def face_patches(prefix, spec) -> list[tuple[str, tuple]]:
    """(material, cyclic vertex ids) of every patch of the OH port face."""
    n = spec.n_outer
    names = spec.layer_names
    out = [(names[0], tuple((prefix, 0, k) for k in range(n)))]
    for lvl, name in enumerate(names):
        for k in range(n):
            j = (k + 1) % n
            out.append((name, ((prefix, lvl, k), (prefix, lvl, j),
                               (prefix, lvl + 1, j), (prefix, lvl + 1, k))))
    return out


def corner_shift(layout_frame, frame, spec) -> int:
    """Index shift *s* between two frames of one face rolled by a multiple
    of the section's period: corner *k* declared at *layout_frame* is
    corner ``(k + s) % n_outer`` of the face built at *frame* (pure)."""
    from .corners import corner0_angle
    n = spec.n_outer
    a0 = corner0_angle(spec)
    w = np.cos(a0) * layout_frame.right + np.sin(a0) * layout_frame.up
    a = math.atan2(np.dot(w, frame.up), np.dot(w, frame.right))
    steps = (a - a0) / (2 * math.pi / n)
    s = round(steps)
    if abs(steps - s) > 1e-9:
        raise LayoutError(f"frames differ by a roll of {math.degrees(a - a0):.6g}°, "
                          f"not a multiple of {360 / n:g}°")
    return s % n


def bind_face(layout: BlockLayout, prefix, face, shift: int = 0) -> None:
    """Bind the realised port *face* (LayeredCrossSection) into *layout*.

    Declared corner *k* binds the face's corner ``(k + shift) % n``: a
    layout declared in a frame rolled by a multiple of the period
    (:func:`corner_shift`).
    """
    from .corners import canonical_geom
    for lvl, (_, cs) in enumerate(face.layers):
        n = cs.n_outer
        g = canonical_geom(cs)
        at = lambda k: (k + shift) % n
        for k in range(n):
            layout.bind_point((prefix, lvl, k), g['ip'][at(k)])
            layout.bind_point((prefix, lvl + 1, k), g['op'][at(k)])
        for k in range(n):
            j = (k + 1) % n
            if lvl == 0:
                layout.bind_edge((prefix, 0, k), (prefix, 0, j), g['ic'][at(k)])
            layout.bind_edge((prefix, lvl + 1, k), (prefix, lvl + 1, j), g['oc'][at(k)])
            layout.bind_edge((prefix, lvl, k), (prefix, lvl + 1, k), g['rc'][at(k)])
        off = 1 if len(cs.surfaces) == n + 1 else 0
        if off:
            layout.port_face(tuple((prefix, 0, k) for k in range(n)), cs.surfaces[0])
        for k in range(n):
            j = (k + 1) % n
            layout.port_face(((prefix, lvl, k), (prefix, lvl, j),
                              (prefix, lvl + 1, j), (prefix, lvl + 1, k)),
                             cs.surfaces[off + at(k)])
