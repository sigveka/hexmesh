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

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.cursor import Cursor, _perpendicular
from ..core.shape import CircleShape
from ..core.spec import PipeSpec, SquareShellSpec
from ..faces.oh_circle import build_oh_circle, build_oh_circle8
from ..faces.annulus import build_annulus


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
            u = np.array([0., 0., 1.]) if abs(n[2]) < 0.9 else _perpendicular(n)
        else:
            u = np.asarray(up, dtype=float)
        # Remove any component along the normal so the frame is orthonormal.
        u = u - np.dot(u, n) * n
        u = u / np.linalg.norm(u)
        return cls(position=p, normal=n, up=u)

    @property
    def right(self) -> np.ndarray:
        return np.cross(self.normal, self.up)

    def cursor(self) -> Cursor:
        return Cursor(self.position, self.normal, self.up)


def port_type(spec: PipeSpec) -> tuple:
    """Hashable type key of *spec* (rule A4)."""
    core_name, core_shape = spec._core
    return (
        spec.n_outer, spec.rot, spec.nang, spec.nang_w, spec.nang_h, spec.mbmp,
        core_name, repr(core_shape), spec._core_nrad, spec._core_mprg,
        tuple(spec.shells),
    )


def roll_mismatch(up_from: np.ndarray, up_to: np.ndarray, normal: np.ndarray,
                  n_outer: int) -> float:
    """Signed roll (radians, about *normal*) taking *up_from* to *up_to*.

    The OH cross-section repeats every ``2π / n_outer``, so the result is
    wrapped into ``(-π/n_outer, π/n_outer]``: only this residual twist has
    to be absorbed by a fitting.
    """
    theta = math.atan2(np.dot(np.cross(up_from, up_to), normal),
                       np.dot(up_from, up_to))
    period = 2 * math.pi / n_outer
    theta = math.remainder(theta, period)
    return period / 2 if math.isclose(theta, -period / 2) else theta


def outer_radius(spec: PipeSpec) -> float:
    """Outer radius of a circular layer stack."""
    return spec.core_shape.radius + sum(s.dR for s in spec.shells)


@dataclass(eq=False)
class Interface:
    """Node of the assembly graph: a typed, posed, shared face.

    ``face`` is ``None`` until the assembler realises it.
    """

    index: int
    frame: Frame
    spec:  PipeSpec
    name:  str | None = None
    edges: list = field(default_factory=list)
    face:  LayeredCrossSection | None = None

    @property
    def is_open(self) -> bool:
        """True when only one fitting touches this interface (network end)."""
        return len(self.edges) == 1

    def __repr__(self) -> str:
        label = self.name or f"#{self.index}"
        return f"Interface({label}, pos={np.round(self.frame.position, 4)})"


def build_face(spec: PipeSpec, frame: Frame, lc: float) -> LayeredCrossSection:
    """Build the GMSH face of an interface (realisation layer only).

    Used both by the assembler (interface faces) and by fittings for their
    own *internal* stations.
    """
    cx, cy, cz = (float(c) for c in frame.position)
    h_axis, v_axis = frame.right, frame.up

    core_name, core_shape = spec._core
    builder = build_oh_circle8 if spec.n_outer == 8 else build_oh_circle
    cs: CrossSection = builder(
        cx=cx, cy=cy, cz=cz,
        shape=core_shape, h_axis=h_axis, v_axis=v_axis, lc=lc,
        nrad=spec._core_nrad, mprg=spec._core_mprg,
        mbmp=spec.mbmp, rot=spec.rot,
    )
    layers = [(core_name, cs)]
    for shell in spec.shells:
        cs = build_annulus(
            inner=cs, dR=shell.dR, lc=lc,
            nrad=shell.nrad, mprg=shell.mprg, mbmp=spec.mbmp, rot=spec.rot,
        )
        layers.append((shell.name, cs))
    return LayeredCrossSection(layers)


def check_supported(spec: PipeSpec) -> None:
    """Raise if *spec* uses a cross-section the prototype cannot fill."""
    if not isinstance(spec.core_shape, CircleShape):
        raise NotImplementedError(
            f"assembly prototype supports circular cores only, "
            f"got {type(spec.core_shape).__name__}."
        )
    if spec.n_outer != 4:
        raise NotImplementedError(
            f"assembly prototype supports n_outer=4 only, got {spec.n_outer}: "
            f"the n_outer=8 core centre patch has 8 sides and cannot bound a "
            f"transfinite hex block"
        )
    if any(isinstance(s, SquareShellSpec) for s in spec.shells):
        raise NotImplementedError(
            "assembly prototype does not support square_shell layers."
        )
