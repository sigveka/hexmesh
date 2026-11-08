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
                get exactly one count) and corner Jacobians.  A class has
                one grading, except on edges declared ``own_grading``,
                which keep theirs (GMSH's transfinite volumes need equal
                node counts on opposite edges, not equal grading).
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

from .._gmsh import gmsh
from ..errors import HexmeshError
from .. import _occ
from ..sections import layout_of
from ..core.cross_section import interface_group_name
from ..quality_hex import corner_scaled_jacobians, shared_face_angles
from .corners import curve_endpoints
from .sweep import CurveMesh, FillResult, _ruled

_EDGES = {  # direction → the four parallel edges
    'i': [(0, 1), (3, 2), (4, 5), (7, 6)],
    'j': [(0, 3), (1, 2), (4, 7), (5, 6)],
    'k': [(0, 4), (1, 5), (2, 6), (3, 7)],
}
# Wall surfaces (``BlockLayout._wall_surface``): grid points per direction
# (boundary included), plate tolerance relative to the face size, and the
# plate's polynomial limits.
_WALL_SAMPLES = 9
_WALL_TOL = 1e-6
_WALL_DEGREE = 8
_WALL_SEGMENTS = 9


_FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


class LayoutError(HexmeshError):
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


def _show(k) -> str:
    """An edge or face key for messages, its vertices sorted, so the text
    doesn't depend on the hash seed (the agent SDK, decision 0019)."""
    return "{" + ", ".join(sorted(map(repr, k))) + "}"


def _ordered(keys):
    """*keys* (edge or face keys) in a hash-seed-independent order."""
    return sorted(keys, key=_show)


def _level(cyc):
    """The common level of a face's vertices ``(prefix, level, k)``, or None."""
    if all(isinstance(v, tuple) and len(v) == 3 for v in cyc):
        levels = {v[1] for v in cyc}
        if len(levels) == 1:
            return levels.pop()
    return None


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
    own_grading: bool = False       # keeps *grading* inside its class


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
        # Level → projector onto that level's intended surface (the wall, or
        # a shell boundary; ``projection``).  Every face whose four vertices
        # ``(prefix, level, k)`` share a level listed here has its mesh
        # nodes moved onto that surface by ``Assembly.mesh()`` (decision
        # 0029).  With *pin_walls*, its curved faces are also plates through
        # points on the surface (``_wall_surface``, task 0051).
        self.walls: dict[int, object] = {}
        self.pin_walls = True
        self._classes: dict[frozenset, tuple[int, tuple]] | None = None

    # -- construction -----------------------------------------------------

    def vertex(self, vid, coord, point: int | None = None):
        """Declare vertex *vid* at *coord*; *point* binds an existing tag."""
        self.coords[vid] = np.asarray(coord, dtype=float)
        if point is not None:
            self.points[vid] = point
        return vid

    def edge(self, a, b, geom=None, curve: int | None = None,
             divisions: int | None = None, grading: tuple | None = None,
             own_grading: bool = False) -> None:
        """Declare the edge *a*–*b* (straight by default).

        *curve* binds an existing curve tag; *divisions* fixes the edge's
        division class; *grading* is a ``(kind, coef)`` transfinite grading
        oriented from *a* to *b* (default uniform).  With *own_grading*
        the edge keeps *grading* although its class (its parallel edges)
        has another: a port face whose sides are graded unlike the face
        opposite (the O-H ↔ H switch, task 0085).
        """
        e = _Edge(a, b, geom or Line(), grading=grading or ("Progression", 1.0),
                  own_grading=own_grading)
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
            raise LayoutError(f"block needs 8 distinct vertices, got {ids}",
                              code="block_vertices_not_distinct")
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

    def _edge_starts(self) -> dict[frozenset, object]:
        """Orientation of every edge: the declared a → b, else the first
        traversal in block order — the order in which ``realise`` creates
        undeclared edges, so both agree.  Edge key → its start vertex."""
        start: dict[frozenset, object] = {k: e.a for k, e in self.edges.items()}
        for ids, _ in self.blocks:
            for group in _EDGES.values():
                for a, b in group:
                    start.setdefault(_key(ids[a], ids[b]), ids[a])
        return start

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

        start = self._edge_starts()

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
                    f"division conflict: edge {_show(k)} needs {n} but parallel "
                    f"edge {_show(other)} needs {root_count[r][0]}",
                    code="block_division_conflict"
                )
            root_count[r] = (n, k)

        def to_root(grading, p):
            kind, coef = grading
            return (kind, 1.0 / coef) if p and kind == "Progression" else (kind, coef)

        root_grading: dict[frozenset, tuple[tuple, frozenset]] = {}
        for k, e in self.edges.items():
            if e.grading == ("Progression", 1.0) or k not in parent or e.own_grading:
                continue
            r = find(k)
            g = to_root(e.grading, parity[k])
            if r in root_grading and not _same_grading(root_grading[r][0], g):
                other = root_grading[r][1]
                raise LayoutError(
                    f"grading conflict: edge {_show(k)} is graded {e.grading} but "
                    f"parallel edge {_show(other)} is graded "
                    f"{self.edges[other].grading} (directions compared along the class)",
                    code="block_grading_conflict"
                )
            root_grading[r] = (g, k)

        result = {}
        for k in list(parent):
            r = find(k)
            if r not in root_count:
                raise LayoutError(
                    f"edge {_show(k)} has no division count (its parallel class "
                    f"reaches no edge with a fixed count)",
                    code="block_division_missing"
                )
            e = self.edges.get(k)
            if e is not None and e.own_grading:
                result[k] = (root_count[r][0], e.grading)
                continue
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

    def _fractions(self, a, b, n: int, start: dict) -> np.ndarray:
        """Node fractions along edge *a* → *b*: its grading is oriented from
        ``start`` (``_edge_starts``)."""
        from ..core.grading import bump, progression
        kind, coef = self._classes[_key(a, b)][1]
        f = np.asarray(bump(n, coef) if kind == "Bump" else progression(n, coef))
        return f if start[_key(a, b)] == a else 1.0 - f[::-1]

    def _edge_nodes(self, a, b, f: np.ndarray) -> np.ndarray:
        """Points at fractions *f* of the length of edge *a* → *b*, along
        its declared geometry (straight if undeclared)."""
        pa, pb = self.coords[a], self.coords[b]
        e = self.edges.get(_key(a, b))
        if e is None or isinstance(e.geom, Line):
            return pa + np.outer(f, pb - pa)
        if isinstance(e.geom, Spline):         # its control polyline: no scipy
            pts = np.vstack([self.coords[e.a], np.asarray(e.geom.points, dtype=float),
                             self.coords[e.b]])          # in validate (task 0107)
            pts = pts if e.a == a else pts[::-1]
        else:
            pts = self._edge_points(a, b, 129)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        return np.column_stack([np.interp(f * s[-1], s, pts[:, i]) for i in range(3)])

    def cells(self):
        """The hexes of the blocks (pure, approximate): each block cut by
        its division counts at its edges' grading fractions, along its
        edges' declared curves, and filled by transfinite interpolation
        (Coons faces, a Gordon–Hall volume), as GMSH's transfinite meshing
        does.  Wall faces are not projected (``walls``): on the conformance
        kit's junctions that moved the worst angle by under 0.1° and cost
        more than the rest (task 0104).  Returns ``(verts (N, 8, 3), conn
        (N, 8), block (N,))``, nodes shared across blocks by position."""
        if self._classes is None:
            self._classes = self._division_classes()
        start = self._edge_starts()
        memo: dict = {}

        def nodes_along(a, b, n):
            """Edge a → b's n + 1 nodes, each edge computed once."""
            k = (_key(a, b), n)
            if k not in memo:
                s = start[k[0]]
                e = b if s == a else a
                memo[k] = (s, self._edge_nodes(s, e, self._fractions(s, e, n, start)))
            s, pts = memo[k]
            return pts if s == a else pts[::-1]

        verts, block = [], []
        for bi, (ids, _) in enumerate(self.blocks):
            n = {d: self._classes[_key(ids[g[0][0]], ids[g[0][1]])][0]
                 for d, g in _EDGES.items()}
            frac = {d: [self._fractions(ids[x], ids[y], n[d], start) for x, y in g]
                    for d, g in _EDGES.items()}
            # the edges' nodes, indexed like _EDGES: i-edges at (j, k) and
            # j-edges at (i, k) = (0,0), (1,0), (0,1), (1,1); k-edges at
            # (i, j) = (0,0), (1,0), (1,1), (0,1)
            E = {d: [nodes_along(ids[x], ids[y], n[d]) for x, y in g] for d, g in _EDGES.items()}
            # blending parameters: the mean of each direction's fractions
            u, v, w = (np.mean(frac[d], axis=0) for d in "ijk")
            I, J, K = len(u), len(v), len(w)
            U, V, W = np.meshgrid(u, v, w, indexing="ij")
            U, V, W = U[..., None], V[..., None], W[..., None]
            ei = [e[:, None, None, :] for e in E["i"]]       # (I, 1, 1, 3)
            ej = [e[None, :, None, :] for e in E["j"]]       # (1, J, 1, 3)
            ek = [e[None, None, :, :] for e in E["k"]]       # (1, 1, K, 3)
            c = np.array([self.coords[x] for x in ids])
            # Gordon–Hall from the 12 edges: sum of the edge interpolants
            # in each pair of directions minus twice the trilinear corners
            edges_i = ((1 - V) * (1 - W) * ei[0] + V * (1 - W) * ei[1]
                       + (1 - V) * W * ei[2] + V * W * ei[3])
            edges_j = ((1 - U) * (1 - W) * ej[0] + U * (1 - W) * ej[1]
                       + (1 - U) * W * ej[2] + U * W * ej[3])
            edges_k = ((1 - U) * (1 - V) * ek[0] + U * (1 - V) * ek[1]
                       + U * V * ek[2] + (1 - U) * V * ek[3])
            tri = ((1 - U) * (1 - V) * (1 - W) * c[0] + U * (1 - V) * (1 - W) * c[1]
                   + U * V * (1 - W) * c[2] + (1 - U) * V * (1 - W) * c[3]
                   + (1 - U) * (1 - V) * W * c[4] + U * (1 - V) * W * c[5]
                   + U * V * W * c[6] + (1 - U) * V * W * c[7])
            g = edges_i + edges_j + edges_k - 2 * tri
            hexes = np.stack([g[:-1, :-1, :-1], g[1:, :-1, :-1], g[1:, 1:, :-1], g[:-1, 1:, :-1],
                              g[:-1, :-1, 1:], g[1:, :-1, 1:], g[1:, 1:, 1:], g[:-1, 1:, 1:]],
                             axis=3).reshape(-1, 8, 3)
            verts.append(hexes)
            block.append(np.full(len(hexes), bi))
        verts = np.concatenate(verts)
        scale = float(np.ptp(verts.reshape(-1, 3), axis=0).max()) or 1.0
        _, conn = np.unique(np.round(verts.reshape(-1, 3) / scale, 9), axis=0,
                            return_inverse=True)
        return verts, conn.reshape(-1, 8), np.concatenate(block)

    def predicted_nonorth(self) -> tuple[float, int]:
        """Largest non-orthogonality of :meth:`cells`, degrees, by
        OpenFOAM's definition (``quality_hex.shared_face_angles``, as the
        meshed check), and the block it is in (the worse of a face's two
        cells' blocks; pure)."""
        verts, conn, block = self.cells()
        angles, a, b = shared_face_angles(verts, conn)
        if not len(angles):
            return 0.0, 0
        i = int(np.argmax(angles))
        return float(angles[i]), int(block[a[i]])

    def validate(self) -> dict:
        """Check topology, densities and corner Jacobians; return a report."""
        if not self.blocks:
            raise LayoutError("layout has no blocks", code="block_layout_empty")
        for ids, _ in self.blocks:
            for v in ids:
                if v not in self.coords:
                    raise LayoutError(f"vertex {v!r} has no coordinates",
                                      code="block_vertex_unplaced")
        use = self.face_use()
        for k, users in use.items():
            if len(users) > 2:
                raise LayoutError(f"face {_show(k)} is shared by {len(users)} blocks",
                                  code="block_face_shared")
        for k in _ordered(self.port_faces):
            if k not in use:
                raise LayoutError(f"port face {_show(k)} is not used by any block",
                                  code="block_port_face_unused")
            if len(use[k]) != 1:
                raise LayoutError(f"port face {_show(k)} is interior to the layout",
                                  code="block_port_face_interior")
        self._classes = self._division_classes()
        sj = self.corner_jacobians()
        if sj.min() <= 0:
            bad = int(np.argmin(sj)) // 8
            raise LayoutError(
                f"block {bad} {self.blocks[bad][0]} is inverted or degenerate "
                f"at a corner (scaled Jacobian {sj.min():.3f})",
                code="block_inverted", value=float(sj.min()), limit={"min_exclusive": 0}
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
            elif self.pin_walls and (wall := self.walls.get(_level(cyc))) is not None:
                self.faces[k] = self._wall_surface(cyc, loop, wall)
            elif self.filling is not None:
                self.faces[k] = geo.addBSplineFilling(loop, type=self.filling)
            else:
                self.faces[k] = geo.addSurfaceFilling(loop)
        return self.faces[k]

    def edge_lengths(self) -> dict[frozenset, tuple[float, int]]:
        """Edge key → (length along its declared geometry, divisions), for
        every edge of every block (pure)."""
        out = {}
        for k, (n, _) in self._division_classes().items():
            a, b = tuple(k)
            if k in self.edges:
                pts = self._edge_points(a, b, 65)
                L = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
            else:
                L = float(np.linalg.norm(self.coords[b] - self.coords[a]))
            out[k] = (L, n)
        return out

    def _edge_points(self, a, b, n: int) -> np.ndarray:
        """*n* points along edge a → b, from its declared geometry."""
        e = self.edges[_key(a, b)]
        pa, pb = self.coords[e.a], self.coords[e.b]
        t = np.linspace(0.0, 1.0, n)
        if isinstance(e.geom, ArcAbout):
            c = np.asarray(e.geom.centre, dtype=float)
            va, vb = pa - c, pb - c
            th = math.acos(np.clip(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)), -1, 1))
            pts = c + (np.outer(np.sin((1 - t) * th), va)
                       + np.outer(np.sin(t * th), vb)) / math.sin(th)
        elif isinstance(e.geom, (Spline, Polyline)):
            ctl = np.vstack([pa, np.asarray(e.geom.points, dtype=float), pb])
            s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(ctl, axis=0), axis=1))])
            if isinstance(e.geom, Spline):
                from scipy.interpolate import CubicSpline   # 0.14 s: build only (task 0107)
                pts = CubicSpline(s / s[-1], ctl, axis=0)(t)
            else:
                pts = np.column_stack([np.interp(t, s / s[-1], ctl[:, i]) for i in range(3)])
        else:
            pts = pa + np.outer(t, pb - pa)
        return pts if e.a == a else pts[::-1]

    def _wall_surface(self, cyc, loop: int, wall) -> int:
        """A wall surface bounded by *loop* that passes through the wall
        (task 0051): a plate filling of the loop's own curves, constrained
        to a Coons grid between them projected onto the wall by *wall*.  Without the points a plate or B-spline filling only
        knows the boundary and sags 0.4–16 % of R off a junction wall.
        """
        n = _WALL_SAMPLES
        v0, v1, v2, v3 = cyc
        bottom, right = self._edge_points(v0, v1, n), self._edge_points(v1, v2, n)
        top, left = self._edge_points(v3, v2, n), self._edge_points(v0, v3, n)
        u = np.linspace(0.0, 1.0, n)[:, None, None]
        v = np.linspace(0.0, 1.0, n)[None, :, None]
        grid = ((1 - v) * bottom[:, None] + v * top[:, None]
                + (1 - u) * left[None, :] + u * right[None, :]
                - ((1 - u) * (1 - v) * bottom[0] + u * (1 - v) * bottom[-1]
                   + (1 - u) * v * top[0] + u * v * top[-1]))
        geo = gmsh.model.occ
        scale = max(np.ptp(grid.reshape(-1, 3), axis=0))
        tags = [geo.addPoint(*q) for q in wall(grid[1:-1, 1:-1].reshape(-1, 3))]
        tag = geo.addSurfaceFilling(loop, pointTags=tags, tol3d=_WALL_TOL * scale,
                                    maxDegree=_WALL_DEGREE, maxSegments=_WALL_SEGMENTS)
        for t_ in tags:
            _occ.discard(t_)
        return tag

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

        unbound = [_show(k) for k in _ordered(self.port_faces) if k not in self.faces]
        if unbound:
            raise LayoutError(f"port faces not bound before realise: {', '.join(unbound[:2])}",
                              code="block_port_faces_unbound")
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
        on_level: dict[int, list[int]] = {}
        for k, users in use.items():
            level = _level(users[0][1])
            if level in self.walls:
                on_level.setdefault(level, []).append(surf_of[k])
        result.projections = [(self.walls[l], s) for l, s in sorted(on_level.items())]
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
# Port faces: the section layout declared into a BlockLayout
# ---------------------------------------------------------------------------
#
# Vertex ids of a port face are (prefix, level, k): the layout's
# (level, k) corners (``sections.oh``), placed at the frame.


def face_vertices(layout: BlockLayout, prefix, frame, spec, port: bool = True,
                  own_grading: bool = False) -> None:
    """Declare the corners and edges of *spec*'s face at *frame* (pure),
    from the layout's ``levels`` (``sections.layout_of``).

    With ``port=False`` the face is an internal station: its patches are
    shared by two blocks and are not declared as port faces.  With
    *own_grading* the face's edges keep their grading against their
    parallel edges' (``BlockLayout.edge``).
    """
    for lvl, level in enumerate(layout_of(spec).levels(spec)):
        for k, (u, v) in enumerate(level.corners):
            if level.polar:                       # bit-identical round stacks (Level)
                r, a = level.polar[0], level.polar[1][k]
                p = frame.position + r * (np.cos(a) * frame.right + np.sin(a) * frame.up)
            else:
                p = frame.position + u * frame.right + v * frame.up
            layout.vertex((prefix, lvl, k), p)
        for e in level.edges:
            layout.edge((prefix, *e.a), (prefix, *e.b), divisions=e.divisions,
                        grading=e.grading, own_grading=own_grading)
    if port:
        for _, cyc in face_patches(prefix, spec):
            layout.port_face(cyc)


def face_patches(prefix, spec) -> list[tuple[str, tuple]]:
    """(material, cyclic vertex ids) of every patch of the port face
    (the layout's ``patches``)."""
    return [(name, tuple((prefix, *c) for c in cyc)) for name, cyc in layout_of(spec).patches(spec)]


def corner_shift(layout_frame, frame, spec) -> int:
    """Index shift *s* between two frames of one face rolled by a multiple
    of the section's period: corner *k* declared at *layout_frame* is
    corner ``(k + s) % n_outer`` of the face built at *frame* (pure)."""
    n = spec.n_outer
    a0 = layout_of(spec).corner0_angle(spec)
    w = np.cos(a0) * layout_frame.right + np.sin(a0) * layout_frame.up
    a = math.atan2(np.dot(w, frame.up), np.dot(w, frame.right))
    steps = (a - a0) / (2 * math.pi / n)
    s = round(steps)
    if abs(steps - s) > 1e-9:
        raise LayoutError(f"frames differ by a roll of {math.degrees(a - a0):.6g}°, "
                          f"not a multiple of {360 / n:g}°",
                          code="port_roll_not_a_period", value=math.degrees(a - a0),
                          limit={"multiple_of": 360 / n})
    return s % n


def bind_face(layout: BlockLayout, prefix, face, shift: int = 0) -> None:
    """Bind the realised port *face* (LayeredCrossSection) into *layout*.

    Declared corner *k* binds the face's corner ``(k + shift) % n``: a
    layout declared in a frame rolled by a multiple of the period
    (:func:`corner_shift`).
    """
    from .corners import canonical_geom
    h_core = False
    for i, (_, cs) in enumerate(face.layers):
        n = cs.n_outer
        g = canonical_geom(cs)
        # an H face's rings run from level i - 1 (its core has one level, task 0086)
        lvl = i - 1 if h_core else i
        if "ip" not in g:              # an H face: one patch on the outer corners
            if i:
                raise LayoutError("bind_face: an H core inside a ring",
                                  code="block_h_core_in_ring")
            h_core = True
            at = lambda k: (k + shift) % n
            for k in range(n):
                layout.bind_point((prefix, 0, k), g['op'][at(k)])
            for k in range(n):
                layout.bind_edge((prefix, 0, k), (prefix, 0, (k + 1) % n), g['oc'][at(k)])
            layout.port_face(tuple((prefix, 0, k) for k in range(n)), cs.surfaces[0])
            continue
        at = lambda k: (k + shift) % n
        for k in range(n):
            layout.bind_point((prefix, lvl, k), g['ip'][at(k)])
            layout.bind_point((prefix, lvl + 1, k), g['op'][at(k)])
        for k in range(n):
            j = (k + 1) % n
            if i == 0:
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
