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
Realising an assembly in GMSH: faces, fills, the mesh and its
corrections (task 0136).
"""

from __future__ import annotations
import copy
import math
from contextlib import contextmanager
from typing import Iterable

import numpy as np

from .._gmsh import gmsh
from ..errors import HexmeshError
from .errors import AssemblyError
from .. import _occ
from .sweep import Arc
from .corners import transfinite_surface_corners, transfinite_volume_corners
from .fittings import FillResult
from .interface import build_face
from ..sections.oh_gmsh import place_partition_nodes
from . import _checks
from ._checks import _require_session


def curve_constraints(records) -> dict:
    """One transfinite constraint per curve tag; disagreeing records raise.

    A curve shared by two fittings (an interface face curve) is reported by
    both; their records must agree.
    """
    out: dict = {}
    for c in records:
        prev = out.setdefault(c.tag, c)
        if (prev.nodes != c.nodes or prev.kind != c.kind
                or not math.isclose(prev.coef, c.coef, rel_tol=1e-12)):
            raise AssemblyError(
                f"curve {c.tag}: conflicting transfinite constraints {prev} and {c}",
                code="curve_constraint_conflict", where={"part": f"curve {c.tag}"}
            )
    return out


class _Parents(dict):
    """Hex node index → its parent corners (the corners sharing its
    nonzero local coordinates), for the nodes past the 8 corners."""

    def index(self, corners: set) -> int:
        return next(k for k, ps in self.items() if ps == corners)


def _element_parents(element_type: int) -> _Parents:
    local = np.asarray(gmsh.model.mesh.getElementProperties(element_type)[4]).reshape(-1, 3)
    out = _Parents()
    for k in range(8, len(local)):
        fixed = local[k] != 0
        out[k] = frozenset(i for i in range(8) if np.all(local[i][fixed] == local[k][fixed]))
    return out


def _rotation(axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotation matrix by *angle* (radians) about the unit *axis*."""
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * (k @ k)


#: a hex's 12 edges, as gmsh numbers its corners
_HEX_EDGES = np.array([(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                       (0, 4), (1, 5), (2, 6), (3, 7)])


def _quad_edges(quads: np.ndarray, surfs) -> np.ndarray:
    """The shortest edge of each quad of *surfs* (node tags, (n, 4)), at
    the nodes' current positions."""
    msh = gmsh.model.mesh
    ids, xyz = [], []
    for s in surfs:
        nt, nx, _ = msh.getNodes(2, s, includeBoundary=True)
        ids.append(nt.astype(int))
        xyz.append(nx.reshape(-1, 3))
    ids, first = np.unique(np.concatenate(ids), return_index=True)
    q = np.vstack(xyz)[first][np.searchsorted(ids, quads)]
    return np.linalg.norm(q - np.roll(q, -1, axis=1), axis=2).min(axis=1)


def _surface_quads(surfs) -> np.ndarray:
    """The corner node tags (n, 4) of every element of *surfs*."""
    msh = gmsh.model.mesh
    return np.vstack([n.reshape(-1, msh.getElementProperties(int(t))[3])[:, :4]
                      for s in surfs for t, _, n in zip(*msh.getElements(2, s))]).astype(int)


def _wall_edges(surfs, tags: np.ndarray) -> np.ndarray:
    """Per node tag in *tags* (sorted): the shortest edge of the quads of
    *surfs* that hold it (its local edge length)."""
    quads = _surface_quads(surfs)
    h = np.repeat(_quad_edges(quads, surfs), 4)
    flat = quads.ravel()
    pos = np.searchsorted(tags, flat).clip(max=len(tags) - 1)
    hit = tags[pos] == flat
    best = np.full(len(tags), np.inf)
    np.minimum.at(best, pos[hit], h[hit])
    return best


@contextmanager
def _located(edge: "Edge", errors=AssemblyError):
    """Re-raise a fitting's own *errors* raised inside the block with
    *edge*'s ``origin``: the message as ``"<edge>: <message>"`` (the form
    of ``validate()``'s errors) and ``where["source"]``; class, code,
    value, limit and hint unchanged (task 0096).  Without an origin the
    error passes through as it is."""
    try:
        yield
    except errors as e:
        if not edge.origin:
            raise
        located = copy.copy(e)
        located.args = (f"{edge}: {e}",)
        located.where = {**edge.where, **e.where, "source": dict(edge.origin)}
        raise located from e


def build(asm, order: Iterable[int] | None = None) -> None:
    _require_session()
    if asm._fill is not None:
        return
    asm.build_faces()
    asm.fill(order)


def build_faces(asm) -> None:
    _require_session()
    if asm._faces_built:
        return
    asm.validate()
    # Fittings read back nothing from the model: hexmesh records what it
    # needs as it creates curves (hexmesh._occ), and mesh() sets every
    # face constraint.  So there is one synchronize here, so the faces
    # can be inspected, and none per fitting (decision 0020, task 0036).
    _occ.reset()
    with _occ.building():
        for iface in asm._interfaces:
            iface.face = build_face(iface.spec, iface.frame, asm.lc)
    gmsh.model.occ.synchronize()
    asm._faces_built = True


def fill(asm, order: Iterable[int] | None = None) -> None:
    _require_session()
    if asm._fill is not None:
        return
    asm.build_faces()
    edges = (asm._edges if order is None
             else [asm._edges[i] for i in order])
    if sorted(e.index for e in edges) != list(range(len(asm._edges))):
        raise AssemblyError("order must be a permutation of all fittings",
                            code="fill_order_invalid", where={"field": "order"})

    fill = FillResult()
    for edge in edges:
        # No raw OCC or GMSH exception escapes a fill (task 0053): it
        # becomes an AssemblyError naming the fitting.
        try:
            with _occ.building(), _located(edge):
                part = edge.fitting.fill(
                    [p.face for p in edge.ports],
                    [p.frame for p in edge.ports],
                    edge.ports[0].spec, asm.lc,
                )
        except AssemblyError:
            raise
        except Exception as e:
            raise AssemblyError(
                f"{edge}: fill failed ({type(e).__name__}: {e})",
                code="fill_failed", where=edge.where) from e
        asm._fitting_volumes[edge.index] = [v for vs in part.volumes.values() for v in vs]
        if part.checked_volumes is not None:
            asm._checked_volumes[edge.index] = list(part.checked_volumes)
        # Wall group per surface; a fill that names none has its
        # inlet's stack throughout (DESIGN A7, decision 0006).
        default = f"{edge.ports[0].spec.layer_names[-1]}_wall"
        walls: dict[str, list[int]] = {}
        for w in part.walls:
            walls.setdefault(part.wall_groups.get(w, default), []).append(w)
        asm._fitting_walls[edge.index] = walls
        asm._fitting_projections[edge.index] = part.projections
        asm._fitting_partitions[edge.index] = (
            [p.face for p in edge.ports if p.face.layers[0][1].n_outer == 8] + part.partitions)
        fill.merge(part)
    _occ.remove_discarded()
    gmsh.model.occ.synchronize()

    # Face builders leave construction points (arc centres, helpers)
    # that bound nothing; drop them so they do not become stray nodes.
    debris = [(0, p) for _, p in gmsh.model.getEntities(0)
              if not gmsh.model.getAdjacencies(0, p)[0].size]
    if debris:
        gmsh.model.occ.remove(debris)
        gmsh.model.occ.synchronize()
    asm._fill = fill


def _set_constraints(asm) -> None:
    msh = gmsh.model.mesh
    for c in curve_constraints(asm._fill.curves).values():
        msh.setTransfiniteCurve(c.tag, c.nodes, c.kind, c.coef)
    # Corners from tags, not GMSH's geometric choice, so geometry
    # variants of one assembly get identical node numbering (task 0007).
    for tag in dict.fromkeys(asm._fill.surfaces):
        msh.setTransfiniteSurface(tag, cornerTags=transfinite_surface_corners(tag))
        msh.setRecombine(2, tag)
    for tag in asm._fill.mesh_vols:
        msh.setTransfiniteVolume(tag, cornerTags=transfinite_volume_corners(tag))
        msh.setRecombine(3, tag)


def mesh(asm, dim: int = 3, *, order: int = 1, incomplete: bool = False,
         walls_by_fitting: bool = False) -> None:
    if order not in (1, 2):
        raise AssemblyError(f"mesh order must be 1 or 2, got {order!r}",
                            code="mesh_order_invalid", where={"field": "order"},
                            value=order, limit=[1, 2])
    if order == 2:
        if dim != 3:
            raise AssemblyError(f"order=2 needs a volume mesh (dim=3), got dim={dim!r}",
                                code="mesh_order_needs_volume", where={"field": "dim"},
                                value=dim, limit=3)
        for e in asm._edges:
            why = getattr(e.fitting, "second_order_limitation", None)
            if callable(why):                   # depends on the spec (Tee)
                why = why(e.ports[0].spec)
            if why:
                raise AssemblyError(f"{e.name}{e.at}: order=2 is not supported: {why}",
                                    code="second_order_unsupported", where=e.where,
                                    hint="mesh it at order=1")
    asm.build()
    gmsh.model.occ.synchronize()
    asm.write_physical_groups(walls_by_fitting)
    with _occ.building():       # the build's records are still valid
        _set_constraints(asm)
    faces = list({id(f): f for fs in asm._fitting_partitions.values() for f in fs}.values())
    if faces and dim >= 2:
        # n_outer = 8: every node of a partitioned face onto the 4-corner
        # face's, before the wall projection (task 0088)
        gmsh.model.mesh.generate(1)
        split = place_partition_nodes(faces, 1)
        gmsh.model.mesh.generate(2)
        split += place_partition_nodes(faces, 2)
    else:
        gmsh.model.mesh.generate(min(dim, 2))
        split = []
    moved = asm._project_walls() if dim >= 2 else {}
    if dim == 3:
        gmsh.model.mesh.generate(3)
    _checks._check_projection(asm, moved)
    if dim == 3:
        _checks._check_meshed_sj(asm)
    if order == 2:
        placed, arcs, split_ho = _second_order(asm, incomplete, faces)
        split += split_ho
    else:
        placed, arcs = {}, {}
    _checks._record_corrections(asm, moved, placed, arcs, _split_moves(asm, split))
    asm.mesh_order = order
    asm._meshed = True


def _split_moves(asm, split) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per fitting index, the moves of ``place_partition_nodes`` on its
    partitioned faces (ports and stations), as :meth:`_project_walls`'s:
    lengths, the face's radius (its outline's largest extent), the local
    grid edge."""
    by_face: dict[int, list] = {}
    for face, move, edge in split:
        by_face.setdefault(id(face), []).append((face, move, edge))
    out = {}
    for i, faces in asm._fitting_partitions.items():
        parts = [r for f in faces for r in by_face.get(id(f), [])]
        if parts:
            out[i] = tuple(np.concatenate(c) for c in zip(*(
                (m, np.full(len(m), f.layers[-1][1].shape.max_extent), h)
                for f, m, h in parts)))
    return out


def _project_walls(asm) -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Move the nodes of every projected surface, its curves and its
    points onto the fitting's analytic surface, between surface and
    volume meshing (decision 0029).  Returns, per fitting index, the
    move lengths, the local wall radii and the local edge lengths (the
    shortest edge of the node's wall quads, before the move)."""
    msh = gmsh.model.mesh
    moved: dict[int, list] = {}
    for e in asm._edges:
        for project, surfs in asm._fitting_projections.get(e.index, []):
            ents = [(2, s) for s in surfs]
            ents += [(abs(d), abs(t)) for d, t in gmsh.model.getBoundary(
                ents, combined=False, oriented=False, recursive=False)]
            ents += [(0, abs(t)) for _, t in gmsh.model.getBoundary(
                [(2, s) for s in surfs], combined=False, oriented=False, recursive=True)]
            tags, x = [], []
            for d, t in dict.fromkeys(ents):
                nt, nx, _ = msh.getNodes(d, t, includeBoundary=False)
                tags.append(nt)
                x.append(nx.reshape(-1, 3))
            tags, first = np.unique(np.concatenate(tags), return_index=True)
            x = np.vstack(x)[first]
            edge = _wall_edges(surfs, tags)
            with _located(e, HexmeshError):
                y = project(x)
            moved.setdefault(e.index, []).append(
                (np.linalg.norm(y - x, axis=1), project.local_radius(y), edge))
            for t, p in zip(tags, y):
                msh.setNode(int(t), p.tolist(), [])
    return {i: tuple(np.concatenate(c) for c in zip(*v)) for i, v in moved.items()}


def _second_order(asm, incomplete: bool, faces: list) -> tuple[dict, dict, list]:
    """``setOrder(2)`` on the checked linear mesh, the halves' mid-edge
    nodes of partitioned *faces* onto the 4-corner face's (task 0088), a
    bend's high-order nodes onto its arcs, then every high-order node on
    a projected fitting's walls onto that fitting's projector, and the
    validity check (task 0076).  Returns the wall placement's and the arc
    placement's moves per fitting index, as :meth:`_project_walls`, and
    the partition's, as ``place_partition_nodes``."""
    opt = "Mesh.SecondOrderIncomplete"
    was = gmsh.option.getNumber(opt)
    try:
        gmsh.option.setNumber(opt, 1 if incomplete else 0)
        gmsh.model.mesh.setOrder(2)
    finally:
        gmsh.option.setNumber(opt, was)
    split = place_partition_nodes(faces, 3)
    msh = gmsh.model.mesh
    placed: dict[int, list] = {}
    arcs: dict[int, tuple] = {}
    for e in asm._edges:
        if hasattr(e.fitting, "path") and len(e.ports) == 2:
            axial = e.fitting.path(e.ports[0].frame, e.ports[1].frame, e.ports[0].spec).axial
            if isinstance(axial, Arc):
                arcs[e.index] = asm._revolve_high_order(e, axial)
        for project, surfs in asm._fitting_projections.get(e.index, []):
            ho: dict[int, float] = {}         # high-order node → local edge length
            for s in surfs:
                for t, _, n in zip(*msh.getElements(2, s)):
                    k = msh.getElementProperties(int(t))[3]       # nodes per element
                    conn = n.reshape(-1, k).astype(int)
                    for node, h in zip(conn[:, 4:].ravel().tolist(),
                                       np.repeat(_quad_edges(conn[:, :4], [s]), k - 4)):
                        ho[node] = min(ho.get(node, np.inf), float(h))
            if not ho:
                continue
            tags = np.array(sorted(ho))
            x = np.array([msh.getNode(int(t))[0] for t in tags])
            y = project(x)
            for t, p in zip(tags, y):
                msh.setNode(int(t), p.tolist(), [])
            placed.setdefault(e.index, []).append(
                (np.linalg.norm(y - x, axis=1), project.local_radius(y),
                 np.array([ho[int(t)] for t in tags])))
    _checks._check_second_order(asm)
    return ({i: tuple(np.concatenate(c) for c in zip(*v)) for i, v in placed.items()},
            arcs, split)


def _revolve_high_order(asm, e, arc: Arc) -> None:
    """Place every high-order node of a bend's hexes that lies between
    two stations exactly: its counterpart on the hex's first station
    (the corner, edge node or face node with the same in-station
    parents), rotated about the bend axis by half the slab's turn.
    ``setOrder`` keeps interior axial edges straight; in a tight bend
    their sag folds thin shells (task 0076).  Returns each moved node's
    move from gmsh's position, the section's outer radius and the
    shortest edge of the hexes that hold it (task 0130)."""
    msh = gmsh.model.mesh
    radius = max(s.max_extent for s in e.ports[0].spec.outlines)
    start: dict[int, np.ndarray] = {}     # node → gmsh's position
    end: dict[int, np.ndarray] = {}       # node → placed position
    edge: dict[int, float] = {}           # node → shortest edge of its hexes
    axis = np.asarray(arc.axis, float) / np.linalg.norm(arc.axis)
    centre = np.asarray(arc.centre, float)

    def radial(x):
        r = x - centre
        return r - np.outer(r @ axis, axis)

    for v in asm._fitting_volumes.get(e.index, []):
        for t, tags, nodes in zip(*msh.getElements(3, v)):
            parents = _element_parents(int(t))
            conn = nodes.reshape(len(tags), -1).astype(int)
            ids, x, _ = msh.getNodes(3, v, includeBoundary=True)
            at = dict(zip(ids.astype(int).tolist(), x.reshape(-1, 3)))
            for h in conn:
                c = np.array([at[n] for n in h[:8]])
                shortest = float(np.linalg.norm(c[_HEX_EDGES[:, 0]] - c[_HEX_EDGES[:, 1]],
                                                axis=1).min())
                r = radial(c)
                turn = np.arctan2(np.cross(r[0], r) @ axis, (r * r[0]).sum(axis=1))
                first = {i for i in range(8) if abs(turn[i]) < 1e-9}
                half = 0.5 * turn[[i for i in range(8) if i not in first][0]]
                rot = _rotation(axis, half)
                for k, ps in parents.items():
                    on_first = ps & first
                    if on_first and on_first != ps:
                        twin = next(iter(on_first)) if len(on_first) == 1 else\
                            parents.index(on_first)
                        p = at[h[twin]]
                        y = centre + rot @ (p - centre)
                        node = int(h[k])
                        start.setdefault(node, at[node])
                        end[node] = y
                        edge[node] = min(edge.get(node, np.inf), shortest)
                        at[node] = y
                        msh.setNode(node, y.tolist(), [])
    nodes = sorted(end)
    move = np.array([np.linalg.norm(end[n] - start[n]) for n in nodes]).reshape(-1)
    return move, np.full(len(nodes), radius), np.array([edge[n] for n in nodes])
