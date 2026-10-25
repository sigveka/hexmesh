"""
Sweeps — every single-path fitting is a sweep (DESIGN.md §6.1).

A sweep fitting describes only its ``Path``: station frames (both port
frames included), axial layers per slab, the kind of axial curve, and
optionally the spec at each station.  ``Sweep`` provides ``validate`` and
``fill`` for all of them; a fitting adds ``path`` and, where needed,
``ports`` and parameter checks in ``check``.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np
import gmsh

from ..core.cross_section import LayeredCrossSection
from ..core.spec import PipeSpec
from .corners import canonical_geom, connect_layer, curve_endpoints, frame_offset
from .interface import Frame, build_face, outer_radius, roll_mismatch


@dataclass(frozen=True)
class CurveMesh:
    """Transfinite constraint of one curve, in its parametric direction.

    *kind* is a GMSH transfinite type ("Progression" or "Bump"); *coef*
    1.0 means uniform.
    """

    tag:   int
    nodes: int
    kind:  str   = "Progression"
    coef:  float = 1.0


UNIFORM = ("Progression", 1.0)


def station_fractions(n: int, ratio: float = 1.0) -> np.ndarray:
    """Positions of ``n + 1`` stations in [0, 1] for *n* cells whose lengths
    grow by *ratio* from one cell to the next, inlet to outlet (pure).

    This is GMSH's transfinite "Progression" law, so a sweep graded by
    station spacing matches a straight slab graded by its axial curves.
    """
    k = np.arange(n + 1, dtype=float)
    if ratio == 1.0:
        return k / n
    return (ratio ** k - 1.0) / (ratio ** n - 1.0)


def face_grading(face: LayeredCrossSection, spec: PipeSpec) -> dict[int, tuple[str, float]]:
    """Grading of the curves of an OH *face* built from *spec*.

    Radial curves carry the layer's ``mprg`` from the inner to the outer
    end (the face-builder convention, ``core.spec.LayerSpec``); angular
    arcs carry ``mbmp`` as a bump.  Orientation comes from endpoint tags
    (``canonical_geom`` signs radials inner → outer), never from distance.
    """
    mprgs = [spec._core_mprg] + [getattr(sh, "mprg", 1.0) for sh in spec.shells]
    out: dict[int, tuple[str, float]] = {}
    for (_, cs), mprg in zip(face.layers, mprgs):
        g = canonical_geom(cs)
        if spec.mbmp != 1.0:
            for c in g['oc'] + g['ic']:
                out[abs(c)] = ("Bump", spec.mbmp)
        if mprg != 1.0:
            for c in g['rc']:
                out[abs(c)] = ("Progression", mprg if c > 0 else 1.0 / mprg)
    return out


def section_cells(spec: PipeSpec) -> int:
    """Quads in one OH cross-section of *spec* (pure; DESIGN P4).

    The core is an ``a × a`` centre patch plus ``n_outer`` ring patches of
    ``a × nrad``, with ``a`` divisions per outer arc; every shell adds
    ``n_outer`` patches of ``a × nrad``.
    """
    a = spec.nang // (spec.n_outer // 4)
    nrads = [spec._core_nrad] + [sh.nrad for sh in spec.shells]
    return a * a + spec.n_outer * a * sum(nrads)


@dataclass
class FillResult:
    """Entities created by one fitting fill."""

    volumes:    dict[str, list[int]] = field(default_factory=dict)
    walls:      list[int]            = field(default_factory=list)
    interfaces: dict[str, list[int]] = field(default_factory=dict)
    curves:     list[CurveMesh]      = field(default_factory=list)
    surfaces:   list[int]            = field(default_factory=list)
    mesh_vols:  list[int]            = field(default_factory=list)

    def merge(self, other: "FillResult") -> None:
        for k, v in other.volumes.items():
            self.volumes.setdefault(k, []).extend(v)
        self.walls.extend(other.walls)
        for k, v in other.interfaces.items():
            self.interfaces.setdefault(k, []).extend(v)
        self.curves.extend(other.curves)
        self.surfaces.extend(other.surfaces)
        self.mesh_vols.extend(other.mesh_vols)


@dataclass(frozen=True)
class Arc:
    """Axial curves are circular arcs about the line (*centre*, *axis*)."""

    axis:   np.ndarray
    centre: np.ndarray

    def builder(self):
        geo = gmsh.model.occ

        def arc(pt_in: int, pt_out: int) -> int:
            p = np.asarray(gmsh.model.getValue(0, pt_in, []))
            c = self.centre + self.axis * np.dot(p - self.centre, self.axis)
            ct = geo.addPoint(*c)
            tag = geo.addCircleArc(pt_in, ct, pt_out)
            geo.remove([(0, ct)])
            return tag

        return arc


@dataclass
class Path:
    """Geometry of a sweep.

    frames
        Station frames, inlet and outlet port frames included.
    layers
        Axial hex layers per slab (``len(frames) - 1`` entries).  Where the
        axis is curved, use one layer per slab so every node lies on an
        exact station face or axial curve (DESIGN.md §6, exactness).
    axial
        ``None`` for straight axial lines, or an ``Arc``.
    specs
        Spec per station, or ``None`` for a constant cross-section.
    min_radius
        Smallest centreline bend radius (``inf`` for a straight path).
    stretch
        Per station, ``None`` or the in-plane stretch ``(b, s)`` of its face
        (``build_face``).  A miter cut is the station face in the bisecting
        plane, stretched by ``1 / cos(half turn)`` along the bend direction.
    prism
        Every slab is a straight prism: its two faces are parallel
        projections of each other along straight axial lines, so radial
        side faces are planar and the chord-turn limit does not apply.
    axial_grading
        Progression ratio of the axial curves inside a slab, inlet to
        outlet.  Only slabs with several layers have such nodes; sweeps
        with one layer per slab grade by station spacing instead
        (``station_fractions``).
    """

    frames:     list[Frame]
    layers:     list[int]
    axial:      Arc | None = None
    specs:      list[PipeSpec] | None = None
    min_radius: float = math.inf
    stretch:    list[tuple | None] | None = None
    prism:      bool = False
    axial_grading: float = 1.0

    def __post_init__(self) -> None:
        if len(self.layers) != len(self.frames) - 1:
            raise ValueError("Path needs one layer count per slab")
        if self.prism and any(n != 1 for n in self.layers):
            raise ValueError("prism slabs need one axial layer each (no interior wall nodes)")
        if any(n < 1 for n in self.layers):
            raise ValueError("every slab needs at least one axial layer")

    def spec_at(self, k: int, default: PipeSpec) -> PipeSpec:
        return default if self.specs is None else self.specs[k]

    def stretch_at(self, k: int) -> tuple | None:
        return None if self.stretch is None else self.stretch[k]

    def offsets(self, spec: PipeSpec) -> list[int]:
        """Corner correspondence of every slab, from frames (pure numpy)."""
        return [frame_offset(self.frames[k], self.frames[k + 1], self.spec_at(k, spec))
                for k in range(len(self.layers))]

    def turns(self) -> list[float]:
        """Normal turn of every slab in degrees."""
        return [math.degrees(math.acos(np.clip(np.dot(a.normal, b.normal), -1, 1)))
                for a, b in zip(self.frames, self.frames[1:])]

    @property
    def is_straight(self) -> bool:
        n0 = self.frames[0].normal
        return self.axial is None and all(
            np.dot(f.normal, n0) > 1 - 1e-12 for f in self.frames
        )


# Largest normal turn per slab when axial curves are straight chords.
MAX_CHORD_TURN = 30.0   # degrees


def _ruled(loop: int) -> int:
    """Side face of a prism slab.

    Its single axial layer leaves no interior nodes, so the surface only has
    to be valid.  OCC plate filling (``addSurfaceFilling``) fails between
    nearly identical B-spline arcs (miter stations less than ~0.2° apart);
    B-spline "Stretch" filling does not.
    """
    return gmsh.model.occ.addBSplineFilling(loop, type="Stretch")


def _fill_slab(in_face: LayeredCrossSection, out_face: LayeredCrossSection,
               n_layers: int, offset: int = 0, axial_curve=None,
               planar_radial: bool = True,
               grading: dict[int, tuple[str, float]] | None = None,
               side_surface=None, axial_grading: float = 1.0) -> FillResult:
    """Fill all concentric layers between two existing faces.

    *offset* is the corner correspondence from ``frame_offset``; *grading*
    maps face-curve tags to their ``face_grading`` (default uniform);
    *axial_grading* is the inlet → outlet progression of the axial curves.
    """
    grading = grading or {}
    result = FillResult()
    names = in_face.interface_names()
    prev_axial = prev_side = None
    for idx, ((name, in_cs), (_, out_cs)) in enumerate(
        zip(in_face.layers, out_face.layers)
    ):
        vols, side, axial, deferred = connect_layer(
            in_cs, out_cs, n_layers, offset,
            prev_outer_axial=prev_axial,
            prev_outer_side_surfs=prev_side,
            planar_radial=planar_radial,
            axial_curve=axial_curve,
            side_surface=side_surface,
        )
        result.volumes.setdefault(name, []).extend(vols)
        if prev_side is not None:
            result.interfaces.setdefault(names[idx - 1], []).extend(prev_side)
        result.curves.extend(_axial_mesh(c, n_layers, axial_grading, in_cs)
                             for c in deferred["curves"])
        result.curves.extend(CurveMesh(c, n, *grading.get(c, UNIFORM))
                             for c, n in deferred["arc_curves"])
        result.surfaces.extend(deferred["surfaces"])
        result.mesh_vols.extend(deferred["volumes"])
        prev_axial, prev_side = axial, side
    result.walls.extend(prev_side)
    return result


def _axial_mesh(curve: int, n_layers: int, ratio: float,
                in_cs) -> CurveMesh:
    """Transfinite record of an axial curve, progression oriented by flow.

    The direction is read from the curve's start point *tag* (on the inlet
    face or not), never from distances (DESIGN §6.1).
    """
    if ratio == 1.0:
        return CurveMesh(curve, n_layers + 1)
    start, _ = curve_endpoints(curve)
    inlet_pts = set(in_cs.inner_points) | set(in_cs.outer_points)
    return CurveMesh(curve, n_layers + 1, "Progression",
                     ratio if start in inlet_pts else 1.0 / ratio)


def sweep_fill(path: Path, faces: list[LayeredCrossSection],
               spec: PipeSpec, lc: float) -> FillResult:
    """Build internal station faces along *path* and fill every slab."""
    stations = [faces[0]]
    for k, fr in enumerate(path.frames[1:-1], start=1):
        stations.append(build_face(path.spec_at(k, spec), fr, lc, path.stretch_at(k)))
    stations.append(faces[1])
    if len(stations) > 2:
        gmsh.model.occ.synchronize()

    axial_curve = path.axial.builder() if path.axial is not None else None
    planar = path.is_straight or path.prism
    offsets = path.offsets(spec)
    grading: dict[int, tuple[str, float]] = {}
    for k, st in enumerate(stations):
        grading.update(face_grading(st, path.spec_at(k, spec)))
    result = FillResult()
    for k, n in enumerate(path.layers):
        result.merge(_fill_slab(stations[k], stations[k + 1], n, offsets[k],
                                axial_curve=axial_curve, planar_radial=planar,
                                grading=grading,
                                side_surface=_ruled if path.prism else None,
                                axial_grading=path.axial_grading))
    return result


class Sweep:
    """Shared ``validate`` / ``fill`` for single-path fittings.

    Subclasses implement ``path(a, b, spec) -> Path`` and may override
    ``check(spec)`` for parameter checks.  Subclasses that place their own
    outlet (``places_outlet = True``) implement ``ports``; ``validate`` then
    also checks that the given outlet frame is where ``ports`` would put it.
    Fittings that only join existing interfaces set ``places_outlet = False``.
    """

    places_outlet = True
    axial_grading = 1.0     # fittings that support grading declare a field

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        raise NotImplementedError

    def fractions(self, n: int) -> np.ndarray:
        """Station positions in [0, 1] for *n* graded layers (rule A5)."""
        return station_fractions(n, self.axial_grading)

    def check(self, spec: PipeSpec) -> None:
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")
        if not self.axial_grading > 0:
            raise ValueError(f"axial_grading must be positive, got {self.axial_grading!r}")

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        self.check(spec)
        a, b = frames
        if self.places_outlet:
            expected = self.ports(a, spec)[0][0]
            scale = max(1.0, float(np.linalg.norm(b.position - a.position)))
            if (np.linalg.norm(expected.position - b.position) > 1e-9 * scale
                    or np.dot(expected.normal, b.normal) < 1 - 1e-9
                    or abs(roll_mismatch(expected.up, b.up, b.normal,
                                         spec.n_outer)) > 1e-9):
                raise ValueError(
                    f"outlet interface does not match {type(self).__name__} geometry"
                )
        path = self.path(a, b, spec)
        R = outer_radius(spec)
        if path.min_radius <= R:
            raise ValueError(
                f"path bends with radius {path.min_radius:.4g}, tighter than "
                f"the pipe outer radius {R}"
            )
        if path.axial is None and not path.prism:
            for k, turn in enumerate(path.turns()):
                if turn > MAX_CHORD_TURN:
                    raise ValueError(
                        f"slab {k} turns {turn:.1f}° (limit {MAX_CHORD_TURN:.0f}° "
                        f"with straight axial edges); use more axial layers"
                    )
        path.offsets(spec)   # raises if any correspondence is undefined

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count, from topology and density alone (DESIGN P4)."""
        return section_cells(spec) * sum(self.path(frames[0], frames[1], spec).layers)

    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        return sweep_fill(self.path(frames[0], frames[1], spec), faces, spec, lc)
