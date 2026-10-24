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
from .corners import connect_layer, frame_offset
from .interface import Frame, build_face, outer_radius, roll_mismatch


@dataclass
class FillResult:
    """Entities created by one fitting fill."""

    volumes:    dict[str, list[int]] = field(default_factory=dict)
    walls:      list[int]            = field(default_factory=list)
    interfaces: dict[str, list[int]] = field(default_factory=dict)
    curves:     list[tuple[int, int]] = field(default_factory=list)
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
    """

    frames:     list[Frame]
    layers:     list[int]
    axial:      Arc | None = None
    specs:      list[PipeSpec] | None = None
    min_radius: float = math.inf

    def __post_init__(self) -> None:
        if len(self.layers) != len(self.frames) - 1:
            raise ValueError("Path needs one layer count per slab")
        if any(n < 1 for n in self.layers):
            raise ValueError("every slab needs at least one axial layer")

    def spec_at(self, k: int, default: PipeSpec) -> PipeSpec:
        return default if self.specs is None else self.specs[k]

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


def _fill_slab(in_face: LayeredCrossSection, out_face: LayeredCrossSection,
               n_layers: int, offset: int = 0, axial_curve=None,
               planar_radial: bool = True) -> FillResult:
    """Fill all concentric layers between two existing faces.

    *offset* is the corner correspondence from ``frame_offset``.
    """
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
        )
        result.volumes.setdefault(name, []).extend(vols)
        if prev_side is not None:
            result.interfaces.setdefault(names[idx - 1], []).extend(prev_side)
        result.curves.extend((c, n_layers + 1) for c in deferred["curves"])
        result.curves.extend(deferred["arc_curves"])
        result.surfaces.extend(deferred["surfaces"])
        result.mesh_vols.extend(deferred["volumes"])
        prev_axial, prev_side = axial, side
    result.walls.extend(prev_side)
    return result


def sweep_fill(path: Path, faces: list[LayeredCrossSection],
               spec: PipeSpec, lc: float) -> FillResult:
    """Build internal station faces along *path* and fill every slab."""
    stations = [faces[0]]
    for k, fr in enumerate(path.frames[1:-1], start=1):
        stations.append(build_face(path.spec_at(k, spec), fr, lc))
    stations.append(faces[1])
    if len(stations) > 2:
        gmsh.model.occ.synchronize()

    axial_curve = path.axial.builder() if path.axial is not None else None
    planar = path.is_straight
    offsets = path.offsets(spec)
    result = FillResult()
    for k, n in enumerate(path.layers):
        result.merge(_fill_slab(stations[k], stations[k + 1], n, offsets[k],
                                axial_curve=axial_curve, planar_radial=planar))
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

    def path(self, a: Frame, b: Frame, spec: PipeSpec) -> Path:
        raise NotImplementedError

    def check(self, spec: PipeSpec) -> None:
        if self.n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {self.n_layers!r}")

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
        if path.axial is None:
            for k, turn in enumerate(path.turns()):
                if turn > MAX_CHORD_TURN:
                    raise ValueError(
                        f"slab {k} turns {turn:.1f}° (limit {MAX_CHORD_TURN:.0f}° "
                        f"with straight axial edges); use more axial layers"
                    )
        path.offsets(spec)   # raises if any correspondence is undefined

    def fill(self, faces: list[LayeredCrossSection], frames: list[Frame],
             spec: PipeSpec, lc: float) -> FillResult:
        return sweep_fill(self.path(frames[0], frames[1], spec), faces, spec, lc)
