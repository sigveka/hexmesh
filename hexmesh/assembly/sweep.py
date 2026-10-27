"""
Sweeps — every single-path fitting is a sweep (DESIGN.md §6.1).

A sweep fitting describes only its ``Path``: station frames (both port
frames included), axial layers per slab, the kind of axial curve, and
optionally the spec at each station.  ``Sweep`` provides ``validate`` and
``fill`` for all of them; a fitting adds ``path`` and, where needed,
``ports`` and parameter checks in ``check``.
"""

from __future__ import annotations
import copy
import math
from dataclasses import dataclass, field

import numpy as np
import gmsh

from ..core.cross_section import LayeredCrossSection
from ..core.shape import CircleShape
from ..core.spec import PipeSpec
from .corners import canonical_geom, connect_layer, curve_endpoints, frame_offset
from .interface import Frame, build_face, outer_radius, roll_mismatch
from .signature import check_port_pairs, classify, signature


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

    With ``c = spec.side_counts`` (divisions per outer curve), the core is
    a ``c[0] × c[1]`` centre patch plus one ring patch of ``c[k] × nrad``
    per side; every shell adds the same ring again with its own ``nrad``.
    A circle has ``c[k] = nang // (n_outer // 4)``; a rectangle
    ``nang_w, nang_h, nang_w, nang_h``.
    """
    c = spec.side_counts
    nrads = [spec._core_nrad] + [sh.nrad for sh in spec.shells]
    return c[0] * c[1] + sum(c) * sum(nrads)


def trim_spec(spec: PipeSpec, n: int) -> PipeSpec:
    """*spec* keeping only its innermost *n* layers (core included)."""
    if n >= len(spec.layer_names):
        return spec
    out = copy.copy(spec)
    out._shells = list(spec.shells[:n - 1])
    return out


@dataclass
class FillResult:
    """Entities created by one fitting fill.

    *walls* holds every wall surface; *wall_groups* names the group of
    those a fill knows (``{layer}_wall`` for side walls, ``{layer}_end``
    for the end annuli of a terminated layer).  Walls it leaves out belong
    to ``{outer}_wall`` of the fitting's inlet stack.
    """

    volumes:    dict[str, list[int]] = field(default_factory=dict)
    walls:      list[int]            = field(default_factory=list)
    wall_groups: dict[int, str]      = field(default_factory=dict)
    interfaces: dict[str, list[int]] = field(default_factory=dict)
    curves:     list[CurveMesh]      = field(default_factory=list)
    surfaces:   list[int]            = field(default_factory=list)
    mesh_vols:  list[int]            = field(default_factory=list)

    def merge(self, other: "FillResult") -> None:
        for k, v in other.volumes.items():
            self.volumes.setdefault(k, []).extend(v)
        self.walls.extend(other.walls)
        self.wall_groups.update(other.wall_groups)
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
    fill
        Layers filled per slab, innermost first, or ``None`` for all of
        them.  A slab with fewer layers than a station face leaves the
        rest of that face as end walls (layer termination, decision 0006).
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
    fill:       list[int] | None = None

    def __post_init__(self) -> None:
        if len(self.layers) != len(self.frames) - 1:
            raise ValueError("Path needs one layer count per slab")
        if self.fill is not None and len(self.fill) != len(self.layers):
            raise ValueError("Path needs one fill count per slab")
        if self.prism and any(n != 1 for n in self.layers):
            raise ValueError("prism slabs need one axial layer each (no interior wall nodes)")
        if any(n < 1 for n in self.layers):
            raise ValueError("every slab needs at least one axial layer")

    def spec_at(self, k: int, default: PipeSpec) -> PipeSpec:
        return default if self.specs is None else self.specs[k]

    def slab_spec(self, k: int, default: PipeSpec) -> PipeSpec:
        """Spec of the layers slab *k* fills."""
        spec = self.spec_at(k, default)
        return spec if self.fill is None else trim_spec(spec, self.fill[k])

    def cells(self, spec: PipeSpec) -> int:
        """Exact hex count (DESIGN P4): each layer only where it is filled."""
        return sum(section_cells(self.slab_spec(k, spec)) * n
                   for k, n in enumerate(self.layers))

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
    """Ruled side face of a straight or prism slab.

    Between two coaxial arcs at the same angles, joined by straight axial
    lines, the ruled surface is the exact cylinder (or, for a reducer, the
    exact cone).  So a straight slab with several axial layers keeps its
    interior wall nodes on the true surface; OCC plate filling
    (``addSurfaceFilling``) sags up to 1.08 % of R there (DESIGN §6, task
    0025).  Plate filling also fails between nearly identical B-spline arcs
    (miter stations less than ~0.2° apart); B-spline "Stretch" filling does
    not.
    """
    return gmsh.model.occ.addBSplineFilling(loop, type="Stretch")


def _fill_slab(in_face: LayeredCrossSection, out_face: LayeredCrossSection,
               n_layers: int, offset: int = 0, axial_curve=None,
               planar_radial: bool = True,
               grading: dict[int, tuple[str, float]] | None = None,
               side_surface=None, axial_grading: float = 1.0,
               n_fill: int | None = None) -> FillResult:
    """Fill the innermost *n_fill* concentric layers (default: all) between
    two existing faces.

    Layers are paired by name; faces may carry further outer layers, which
    this slab leaves alone (layer termination).  *offset* is the corner
    correspondence from ``frame_offset``; *grading* maps face-curve tags to
    their ``face_grading`` (default uniform); *axial_grading* is the inlet →
    outlet progression of the axial curves.
    """
    grading = grading or {}
    result = FillResult()
    names = in_face.interface_names()
    if n_fill is None:
        n_fill = len(in_face.layers)
    pairs = list(zip(in_face.layers[:n_fill], out_face.layers[:n_fill]))
    if len(pairs) != n_fill:
        raise ValueError(f"slab fills {n_fill} layers but a face has fewer")
    for (a, _), (b, _) in pairs:
        if a != b:
            raise ValueError(f"slab would join layer `{a}` to layer `{b}`")
    prev_axial = prev_side = None
    for idx, ((name, in_cs), (_, out_cs)) in enumerate(pairs):
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
    result.wall_groups.update((w, f"{pairs[-1][0][0]}_wall") for w in prev_side)
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
                                # exact surfaces wherever slabs are straight
                                # (DESIGN §6); plate filling elsewhere
                                side_surface=_ruled if path.prism or planar else None,
                                axial_grading=path.axial_grading,
                                n_fill=None if path.fill is None else path.fill[k]))
    if path.fill is not None:
        # End walls: internal-station layers filled on one side only.
        for k in range(1, len(stations) - 1):
            up, down = path.fill[k - 1], path.fill[k]
            for i, (name, cs) in enumerate(stations[k].layers):
                if (i < up) != (i < down):
                    result.walls.extend(cs.surfaces)
                    result.wall_groups.update((t, f"{name}_end") for t in cs.surfaces)
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
        if self.stack_changes:
            self.check_stack_changes(spec)

    def validate(self, frames: list[Frame], spec: PipeSpec) -> None:
        self.check(spec)
        a, b = frames
        if self.places_outlet:
            # Port pairs this fitting declares (DESIGN A4, decision 0011);
            # Assembly.validate checks the pairs as actually connected.
            check_port_pairs(self, [spec] + [s for _, s in self.ports(a, spec)])
            expected = self.ports(a, spec)[0][0]
            scale = max(1.0, float(np.linalg.norm(b.position - a.position)))
            if (np.linalg.norm(expected.position - b.position) > 1e-9 * scale
                    or np.dot(expected.normal, b.normal) < 1 - 1e-9
                    or abs(roll_mismatch(expected.up, b.up, b.normal,
                                         spec.period)) > 1e-9):
                raise ValueError(
                    f"outlet interface does not match {type(self).__name__} geometry"
                )
        path = self.path(a, b, spec)
        R = self.clearance(spec)
        if path.min_radius <= R:
            what = ("the pipe outer radius" if isinstance(spec.core_shape, CircleShape)
                    else f"the duct's half-extent {self.clearance_note}")
            raise ValueError(
                f"path bends with radius {path.min_radius:.4g}, tighter than "
                f"{what} {R:.4g}"
            )
        if path.axial is None and not path.prism:
            for k, turn in enumerate(path.turns()):
                if turn > MAX_CHORD_TURN:
                    raise ValueError(
                        f"slab {k} turns {turn:.1f}° (limit {MAX_CHORD_TURN:.0f}° "
                        f"with straight axial edges); use more axial layers"
                    )
        path.offsets(spec)   # raises if any correspondence is undefined

    # Smallest centreline radius a path may have: the section's extent
    # toward the centre of curvature.  Where the bend plane is not fixed
    # (splines, closures) a rectangle is checked on its half-diagonal.
    clearance_note = "(half-diagonal: the bend plane varies)"

    def clearance(self, spec: PipeSpec) -> float:
        return outer_radius(spec)

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count, from topology and density alone (DESIGN P4)."""
        return self.path(frames[0], frames[1], spec).cells(spec)

    # -- layer termination (decision 0006) -----------------------------

    stack_changes: tuple = ()

    def cell_specs(self, spec: PipeSpec) -> list[PipeSpec]:
        """Layer stack of each axial cell: *spec*, changed by every
        ``(i, spec)`` in ``stack_changes`` from cell *i* on."""
        out, cur = [], spec
        changes = dict(self.stack_changes)
        for j in range(self.n_layers):
            cur = changes.get(j, cur)
            out.append(cur)
        return out

    def outlet_spec(self, spec: PipeSpec) -> PipeSpec:
        return self.cell_specs(spec)[-1] if self.stack_changes else spec

    def check_stack_changes(self, spec: PipeSpec) -> None:
        """Termination rules (decision 0006), pure Python.

        Changes sit at cell boundaries inside the fitting (never at a
        port), and each one adds or removes whole outermost layers while
        every remaining layer keeps its name, radius, ``nrad`` and grading.
        """
        name = type(self).__name__
        idx = [i for i, _ in self.stack_changes]
        if idx != sorted(set(idx)) or any(not 1 <= i < self.n_layers for i in idx):
            raise ValueError(
                f"{name}: stack_changes must be at increasing cell boundaries "
                f"1 … {self.n_layers - 1} (layers end inside the fitting, never "
                f"at a port), got {idx}")
        prev = spec
        for i, nxt in self.stack_changes:
            _check_termination(name, i, prev, nxt)
            prev = nxt

    def stacked(self, path: Path, spec: PipeSpec) -> Path:
        """*path* with station specs and per-slab fill counts from
        ``stack_changes``.  Every change must sit at a slab boundary of
        *path*; each internal station face carries the fuller adjacent
        stack, so the ending layer's annulus exists there."""
        if not self.stack_changes:
            return path
        cells = self.cell_specs(spec)
        bounds = np.cumsum([0] + list(path.layers))
        slab = [cells[b] for b in bounds[:-1]]
        for k, (lo, hi) in enumerate(zip(bounds[:-1], bounds[1:])):
            if any(c is not slab[k] for c in cells[lo:hi]):
                raise ValueError(f"{type(self).__name__}: a stack change falls "
                                 f"inside slab {k}")
        n = [len(s.layer_names) for s in slab]
        specs = [slab[0]] + [slab[k - 1] if n[k - 1] >= n[k] else slab[k]
                             for k in range(1, len(slab))] + [slab[-1]]
        path.specs = specs if path.specs is None else path.specs
        path.fill = n
        return path


    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        return sweep_fill(self.path(frames[0], frames[1], spec), faces, spec, lc)


def _radii(spec: PipeSpec) -> list[float]:
    return [spec.core_shape.radius] + [sh.dR for sh in spec.shells]


def _check_termination(fitting: str, i: int, a: PipeSpec, b: PipeSpec) -> None:
    """Raise unless *a* → *b* only adds or removes whole outermost layers."""
    la, lb = a.layer_names, b.layer_names
    short, long_ = (la, lb) if len(la) <= len(lb) else (lb, la)
    where = f"{fitting}: stack change at cell {i}"
    if la == lb:
        raise ValueError(f"{where} keeps the layers {la}; a stack change must "
                         f"end or start a layer")
    if long_[:len(short)] != short:
        gone = [x for x in long_ if x not in short]
        if set(short) <= set(long_):
            raise ValueError(
                f"{where}: only outermost layers may stop or start; "
                f"{', '.join(f'`{x}`' for x in gone)} is not outermost")
        raise ValueError(f"{where}: layers {la} → {lb} are not the same stack "
                         f"with outer layers removed or added")
    c = classify(signature(a), signature(b))
    if c.cls != 1:
        what = "; ".join(str(d) for d in c.differences if d.field != "shells")
        raise ValueError(f"{where}: the remaining layers must match ({what}); "
                         f"use a Reducer to change them")
    n = len(short)
    for lname, ra, rb in zip(short, _radii(a)[:n], _radii(b)[:n]):
        if ra != rb:
            raise ValueError(f"{where}: the remaining layers must match "
                             f"(`{lname}` radius {ra} vs {rb}); use a Reducer")
    if a.rot != b.rot:
        raise ValueError(f"{where}: the remaining layers must match "
                         f"(rot {a.rot} vs {b.rot})")
