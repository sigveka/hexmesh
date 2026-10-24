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
from dataclasses import dataclass, field

import numpy as np
import gmsh

from .corners import curve_endpoints
from .sweep import CurveMesh, FillResult

# Corner (a, b, c) ∈ {0,1}³ → vertex index
_IDX = {(0, 0, 0): 0, (1, 0, 0): 1, (1, 1, 0): 2, (0, 1, 0): 3,
        (0, 0, 1): 4, (1, 0, 1): 5, (1, 1, 1): 6, (0, 1, 1): 7}
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


def _key(*ids) -> frozenset:
    return frozenset(ids)


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
        self._classes: dict[frozenset, int] | None = None

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

    def _division_classes(self) -> dict[frozenset, int]:
        parent: dict[frozenset, frozenset] = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for ids, _ in self.blocks:
            for group in _EDGES.values():
                keys = [_key(ids[a], ids[b]) for a, b in group]
                for k in keys[1:]:
                    parent[find(k)] = find(keys[0])

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
        result = {}
        for k in list(parent):
            r = find(k)
            if r not in root_count:
                raise LayoutError(
                    f"edge {set(k)} has no division count (its parallel class "
                    f"reaches no edge with a fixed count)"
                )
            result[k] = root_count[r][0]
        return result

    def corner_jacobians(self) -> np.ndarray:
        """Scaled Jacobian at every block corner (straight-edge estimate)."""
        out = []
        for ids, _ in self.blocks:
            p = [self.coords[v] for v in ids]
            for (a, b, c), idx in _IDX.items():
                def nb(da, db, dc):
                    return p[_IDX[(a ^ da, b ^ db, c ^ dc)]] - p[idx]
                ei = nb(1, 0, 0) * (1 if a == 0 else -1)
                ej = nb(0, 1, 0) * (1 if b == 0 else -1)
                ek = nb(0, 0, 1) * (1 if c == 0 else -1)
                n = np.linalg.norm(ei) * np.linalg.norm(ej) * np.linalg.norm(ek)
                out.append(np.dot(np.cross(ei, ej), ek) / n if n > 0 else 0.0)
        return np.array(out)

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
                n *= self._classes[_key(ids[a], ids[b])]
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
                e.tag = geo.addCircleArc(pa, c, pb)
                geo.remove([(0, c)])
            elif isinstance(e.geom, Spline):
                mids = [geo.addPoint(*p) for p in e.geom.points]
                e.tag = geo.addSpline([pa, *mids, pb])
            else:
                e.tag = geo.addLine(pa, pb)
            e.start = e.a
        return e.tag if e.start == a else -e.tag

    def _surface(self, cyc) -> int:
        """Bound surface, or a new one (plane if straight and coplanar)."""
        k = _key(*cyc)
        if k not in self.faces:
            geo = gmsh.model.occ
            curves = [self._curve(cyc[i], cyc[(i + 1) % 4]) for i in range(4)]
            loop = geo.addCurveLoop(curves)
            # Curves are synchronised before any surface is built.
            straight = all(gmsh.model.getType(1, abs(c)) == "Line" for c in curves)
            if straight and self._coplanar(cyc):
                self.faces[k] = geo.addPlaneSurface([loop])
            else:
                self.faces[k] = geo.addSurfaceFilling(loop)
        return self.faces[k]

    def _coplanar(self, cyc) -> bool:
        p = [self.coords[v] for v in cyc]
        n = np.cross(p[1] - p[0], p[3] - p[0])
        scale = max(np.linalg.norm(p[2] - p[0]), 1e-30)
        return abs(np.dot(n / max(np.linalg.norm(n), 1e-30), p[2] - p[0])) < 1e-9 * scale

    def realise(self) -> FillResult:
        """Build every entity in GMSH and return the fill result."""
        if self._classes is None:
            self.validate()
        geo = gmsh.model.occ
        use = self.face_use()

        for ids, _ in self.blocks:              # curves first (lines only need points)
            for group in _EDGES.values():
                for a, b in group:
                    self._curve(ids[a], ids[b])
        geo.synchronize()

        unbound = [set(k) for k in self.port_faces if k not in self.faces]
        if unbound:
            raise LayoutError(f"port faces not bound before realise: {unbound[:2]}")
        result = FillResult()
        surf_of: dict[frozenset, int] = {}
        for k, users in use.items():
            surf_of[k] = self._surface(users[0][1])
        geo.synchronize()

        for ids, material in self.blocks:
            sl = geo.addSurfaceLoop([surf_of[_key(*(ids[i] for i in f))] for f in _FACES])
            vol = geo.addVolume([sl])
            result.volumes.setdefault(material, []).append(vol)
            result.mesh_vols.append(vol)
        geo.synchronize()

        for k, n in self._classes.items():
            e = self.edges[k]
            kind, coef = e.grading
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
                    result.interfaces.setdefault(f"{m0}_to_{m1}", []).append(surf_of[k])
        return result


# ---------------------------------------------------------------------------
# OH port faces
# ---------------------------------------------------------------------------
#
# Vertex ids of a port face are (prefix, level, k): level 0 is the core's
# inner square, level l ≥ 1 the outer boundary of layer l-1; corner k is
# named by the frame (corners.corner0_angle + k·2π/n_outer).

OH_RATIO = 0.6   # inner-square scale used by faces.oh_circle.build_oh_circle


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


def bind_face(layout: BlockLayout, prefix, face) -> None:
    """Bind the realised port *face* (LayeredCrossSection) into *layout*."""
    from .corners import canonical_geom
    for lvl, (_, cs) in enumerate(face.layers):
        n = cs.n_outer
        g = canonical_geom(cs)
        for k in range(n):
            layout.bind_point((prefix, lvl, k), g['ip'][k])
            layout.bind_point((prefix, lvl + 1, k), g['op'][k])
        for k in range(n):
            j = (k + 1) % n
            if lvl == 0:
                layout.bind_edge((prefix, 0, k), (prefix, 0, j), g['ic'][k])
            layout.bind_edge((prefix, lvl + 1, k), (prefix, lvl + 1, j), g['oc'][k])
            layout.bind_edge((prefix, lvl, k), (prefix, lvl + 1, k), g['rc'][k])
        off = 1 if len(cs.surfaces) == n + 1 else 0
        if off:
            layout.port_face(tuple((prefix, 0, k) for k in range(n)), cs.surfaces[0])
        for k in range(n):
            j = (k + 1) % n
            layout.port_face(((prefix, lvl, k), (prefix, lvl, j),
                              (prefix, lvl + 1, j), (prefix, lvl + 1, k)),
                             cs.surfaces[off + k])
