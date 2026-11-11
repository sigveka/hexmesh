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
Interfaces — first-class shared faces between fittings (DESIGN.md §4, A1/A3/A4).

Frame
    Absolute pose of an interface: position, normal (pipe direction leaving
    the interface) and up (fixes the roll, i.e. where structural corners lie).
    Pure numpy; never touches GMSH.

Interface
    A node of the assembly graph.  Carries a Frame and the PipeSpec that
    types it.  Its GMSH face is created exactly once by the assembler during
    realisation and is never created by a fitting.

port_type
    Hashable type key of a PipeSpec.  Two ports may only meet at an
    interface when their keys are equal (rule A4).
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

import numpy as np

from .errors import AssemblyError
from ..core.cross_section import LayeredCrossSection
from ..core.spec import PipeSpec
from .. import sections
from .limits import OUTLINE_MIN_GAP



def rotate(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotate *v* about the unit *axis* by *angle* radians (Rodrigues)."""
    c, s = math.cos(angle), math.sin(angle)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)


def perpendicular(v: np.ndarray) -> np.ndarray:
    """An arbitrary unit vector perpendicular to *v*."""
    candidate = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(v, candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    w = np.cross(v, candidate)
    return w / np.linalg.norm(w)


@dataclass(frozen=True)
class Frame:
    """Absolute pose of an interface.

    Attributes
    ----------
    position : ndarray, shape (3,)
        Centre of the interface face.
    normal : ndarray, shape (3,)
        Unit pipe direction through the face (downstream).
    up : ndarray, shape (3,)
        Unit in-plane vector fixing the roll of the face.
    """

    position: np.ndarray
    normal:   np.ndarray
    up:       np.ndarray

    @classmethod
    def from_vectors(cls, position=None, normal=None, up=None) -> "Frame":
        p = np.zeros(3) if position is None else np.asarray(position, dtype=float)
        n = np.array([1., 0., 0.]) if normal is None else np.asarray(normal, dtype=float)
        n = n / np.linalg.norm(n)
        if up is None:
            u = np.array([0., 0., 1.]) if abs(n[2]) < 0.9 else perpendicular(n)
        else:
            u = np.asarray(up, dtype=float)
        # Remove any component along the normal so the frame is orthonormal.
        u = u - np.dot(u, n) * n
        u = u / np.linalg.norm(u)
        return cls(position=p, normal=n, up=u)

    @property
    def right(self) -> np.ndarray:
        return np.cross(self.normal, self.up)


def port_type(spec: PipeSpec) -> tuple:
    """Hashable type key of *spec* (rule A4)."""
    core_name, core_shape = spec._core
    return (
        spec.n_outer, spec.rot, spec.nang, spec.nang_w, spec.nang_h, spec.mbmp,
        core_name, repr(core_shape), spec._core_nrad, spec._core_mprg,
        tuple(spec.shells), spec.layout, spec.wall_grading,
    )


def toward_roll(frame: Frame, toward) -> float:
    """Roll in degrees, about ``frame.normal`` from ``frame.up``, of the
    absolute direction *toward* (its component across the pipe):
    ``rotate(up, normal, roll)`` points that way (decision 0024).

    *toward* within ``TOWARD_MIN_ANGLE`` of the normal (either sense) sets
    no direction and raises ``ValueError`` naming the angle.
    """
    from .limits import TOWARD_MIN_ANGLE
    t = np.asarray(toward, dtype=float)
    if t.shape != (3,) or not np.linalg.norm(t) > 0:
        raise AssemblyError(f"toward must be a nonzero 3-vector, got {toward!r}",
                            code="toward_invalid", where={"field": "toward"})
    t = t / np.linalg.norm(t)
    along = float(np.dot(t, frame.normal))
    off = math.degrees(math.acos(min(1.0, abs(along))))
    if off < TOWARD_MIN_ANGLE:
        raise AssemblyError(
            f"toward {tuple(np.round(t, 6))} is {off:.3g}° from the inlet normal "
            f"(minimum {TOWARD_MIN_ANGLE:g}°): it sets no direction across the pipe",
            code="toward_along_axis", where={"field": "toward"}, value=off,
            limit="TOWARD_MIN_ANGLE")
    p = t - along * frame.normal
    return math.degrees(math.atan2(np.dot(p, frame.right), np.dot(p, frame.up)))


def lean(angle: float) -> tuple[float, float]:
    """``(cos α, sin α)`` of a branch angle in degrees, exact at 90°, so a
    perpendicular tee's coordinates are bit-identical to before task 0060."""
    if angle == 90:
        return 0.0, 1.0
    a = math.radians(angle)
    return math.cos(a), math.sin(a)


def rolled(frame: Frame, roll: float) -> Frame:
    """*frame* rolled about its normal by *roll* degrees."""
    return Frame(frame.position, frame.normal,
                 rotate(frame.up, frame.normal, math.radians(roll)))


def junction_roll(fitting, spec: PipeSpec) -> None:
    """A junction's ``roll`` must be a multiple of the section's period:
    only then do its corners land on the inlet face's (decision 0024)."""
    P = math.degrees(spec.period)
    m = fitting.roll / P
    if abs(m - round(m)) > 1e-9:
        raise AssemblyError(
            f"{type(fitting).__name__} roll {fitting.roll:g}° is not a multiple of "
            f"the section's period {P:g}°",
            code="junction_roll_invalid", where={"field": "roll"}, value=fitting.roll,
            limit={"multiple_of": P})


def junction_toward(fitting, inlet: Frame, spec: PipeSpec, offset: float = 0.0):
    """*fitting* with ``toward`` resolved to the nearest allowed roll.

    *offset* is the roll (degrees) of the direction ``toward`` names,
    relative to the junction's ``up``.  A miss above
    ``JUNCTION_TOWARD_TOL`` raises, naming it.
    """
    from dataclasses import replace
    from .limits import JUNCTION_TOWARD_TOL
    if fitting.toward is None:
        return fitting
    name = type(fitting).__name__
    if fitting.roll != 0:
        raise AssemblyError(f"{name}: give roll or toward, not both",
                            code="roll_and_toward_conflict", where={"field": "toward"})
    want = toward_roll(inlet, fitting.toward) - offset
    P = math.degrees(spec.period)
    roll = round(want / P) * P
    miss = abs(math.remainder(want - roll, 360.0))
    if miss > JUNCTION_TOWARD_TOL:
        raise AssemblyError(
            f"{name}: toward is {miss:.3g}° from the nearest allowed direction "
            f"(roll {math.remainder(roll, 360.0):g}°; rolls are multiples of "
            f"{P:g}°, tolerance {JUNCTION_TOWARD_TOL:g}°)",
            code="toward_off_allowed", where={"field": "toward"}, value=miss,
            limit="JUNCTION_TOWARD_TOL")
    return replace(fitting, roll=math.remainder(roll, 360.0) + 0.0, toward=None)


def check_port_frames(fitting, expected: list[Frame], given: list[Frame],
                      scale: float) -> None:
    """``AssemblyError`` (``outlet_frame_mismatch``) unless each *expected*
    port frame of a junction or switch equals the *given* one: position
    within 1e-9 *scale*, normal and up within 1e-9 (task 0135)."""
    for want, got in zip(expected, given):
        if (np.linalg.norm(want.position - got.position) > 1e-9 * scale
                or np.dot(want.normal, got.normal) < 1 - 1e-9
                or np.dot(want.up, got.up) < 1 - 1e-9):
            raise AssemblyError(f"port interface does not match {type(fitting).__name__} "
                                "geometry", code="outlet_frame_mismatch")


def roll_mismatch(up_from: np.ndarray, up_to: np.ndarray, normal: np.ndarray,
                  period: float) -> float:
    """Signed roll (radians, about *normal*) taking *up_from* to *up_to*.

    The section repeats every *period* (``PipeSpec.period``: P of DESIGN
    §6.1), so the result is wrapped into ``(-P/2, P/2]``: only this
    residual twist has to be absorbed by a fitting.
    """
    theta = math.atan2(np.dot(np.cross(up_from, up_to), normal),
                       np.dot(up_from, up_to))
    theta = math.remainder(theta, period)
    return period / 2 if math.isclose(theta, -period / 2) else theta


def outer_radius(spec: PipeSpec) -> float:
    """Radius of the smallest circle about the axis that holds the
    outermost outline: a circular stack's outer radius; a rectangle's
    half-diagonal, which is what clearance checks need when no direction
    is given."""
    return spec.outlines[-1].max_extent


def half_extent(spec: PipeSpec, angle: float) -> float:
    """Distance from the axis to the outer wall's supporting line in the
    in-plane direction at *angle* (radians from ``frame.right`` toward
    ``frame.up``), for the outermost outline (rotated by ``rot``): the
    outer radius of a circle; ``half_w·|cos| + half_h·|sin|`` for a
    rectangle, so the half-height toward ``up`` and the half-width toward
    ``right``."""
    return float(spec.outlines[-1].extent(angle - spec.rot_rad))


def hydraulic_diameter(spec: PipeSpec) -> float:
    """Hydraulic diameter 4A / P_w of the core (the flow passage)."""
    return spec.core_shape.hydraulic_diameter


@dataclass(eq=False)
class Interface:
    """Node of the assembly graph: a typed, posed, shared face.

    ``face`` is ``None`` until the assembler realises it.  ``equipment``
    marks an end attached to equipment (a nozzle; decisions 0002, 0023):
    ``extend_open_ends`` never extends it and nothing is prepended to it.
    """

    index: int
    frame: Frame
    spec:  PipeSpec
    name:  str | None = None
    edges: list = field(default_factory=list)
    face:  LayeredCrossSection | None = None
    equipment: bool = False

    @property
    def is_open(self) -> bool:
        """True when only one fitting touches this interface (network end)."""
        return len(self.edges) == 1

    def __repr__(self) -> str:
        label = self.name or f"#{self.index}"
        return f"Interface({label}, pos={np.round(self.frame.position, 4)})"


def build_face(spec: PipeSpec, frame: Frame, lc: float,
               stretch: tuple | None = None) -> LayeredCrossSection:
    """Build the GMSH face of an interface (realisation layer only).

    Used both by the assembler (interface faces) and by fittings for their
    own *internal* stations.  *stretch* ``(b, s)`` scales an internal
    station by ``s`` along the in-plane direction ``b`` (miter cut faces);
    interfaces are never stretched.  The section layout builds it
    (``sections.build_face``).
    """
    return sections.build_face(spec, frame.position, frame.right, frame.up, lc, stretch)


def check_supported(spec: PipeSpec) -> None:
    """Raise if *spec* uses a cross-section the prototype cannot fill."""
    shape = spec.core_shape
    if shape.is_station:
        raise AssemblyError(
            f"assembly supports circular and rectangular cores, "
            f"got {type(shape).__name__}.",
            code="section_not_supported", value=type(shape).__name__,
            hint="use a CircleShape or RectShape core"
        )
    if spec.n_outer not in (4, 8):
        # n_outer = 12: the core's grid lines at 1/3 and 2/3 are curved, so
        # straight cuts can't carry them (task 0088)
        raise AssemblyError(
            f"n_outer must be 4 or 8, got {spec.n_outer}: a core cut into "
            f"{spec.n_outer // 4} × {spec.n_outer // 4} needs curved cuts",
            code="section_not_supported", where={"field": "n_outer"}, value=spec.n_outer,
            limit=[4, 8], hint="use n_outer=4 or 8"
        )
    check_outlines(spec)


def check_outlines(spec: PipeSpec, samples: int = 720) -> None:
    """Each layer's outline strictly inside the next all round, with a gap
    of at least ``OUTLINE_MIN_GAP`` of the outer one's extent (decision
    0026, item 5).  The outlines are convex and share a centre (a rule
    checked here, not assumed by the data model), so containment is the
    support function of the inner one below the outer one's in every
    direction; the corner directions are sampled exactly."""
    outlines = spec.outlines
    names = spec.layer_names
    angles = np.linspace(0.0, 2 * math.pi, samples, endpoint=False)
    for inner, outer, iname, oname in zip(outlines, outlines[1:], names, names[1:]):
        extra = [math.atan2(p[1], p[0]) for o in (inner, outer)
                 for p in (o.corner(k) for k in range(4))]
        a = np.concatenate([angles, extra])
        gaps = outer.extent(a) - inner.extent(a)
        gap, at = float(gaps.min()), float(a[gaps.argmin()])
        need = OUTLINE_MIN_GAP * outer.max_extent
        if gap < need:
            raise AssemblyError(
                f"layer `{oname}`: its outline must enclose `{iname}`'s with a gap "
                f"of at least {need:.3g} (OUTLINE_MIN_GAP {OUTLINE_MIN_GAP:g} of its "
                f"extent); the gap is {gap:.3g} at {math.degrees(at):.1f}° "
                f"(before rot)",
                code="outline_gap_too_small", where={"label": oname}, value=gap,
                limit="OUTLINE_MIN_GAP")
