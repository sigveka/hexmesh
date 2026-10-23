"""
Cursor — pipe-axis position and orientation.

The Cursor tracks where the pipe network currently is in 3D space and which
direction it is heading.  Every connector (Straight, Bend, Reducer) consumes
a Cursor and returns an updated one.

Plane
    Canonical orientation enum used by the 2-D face builders (OHCircle,
    OHRect, …).  The plane defines which two axes span the cross-section and
    which axis is the default extrusion direction.

Cursor
    Full 3-D orientation.  The ``direction`` vector is the outward normal of
    the current end-face (i.e. the axis along which the next segment will
    grow).  The ``up`` vector defines the in-plane "vertical" direction and
    is required for bend-plane disambiguation.

    ``from_plane`` is a convenience constructor that initialises a cursor
    aligned with one of the three canonical planes, which covers the common
    case of a straight pipe starting from the origin.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class Plane(Enum):
    """Canonical cross-section plane.

    Value is the index of the extrusion axis (0=X, 1=Y, 2=Z).
    """
    XY = 2   # cross-section in XY, extrude along Z
    XZ = 1   # cross-section in XZ, extrude along Y
    YZ = 0   # cross-section in YZ, extrude along X

    @property
    def extrusion_axis(self) -> np.ndarray:
        """Unit vector along the default extrusion direction."""
        v = np.zeros(3)
        v[self.value] = 1.0
        return v

    @property
    def gmsh_flag(self) -> int:
        """Flag_Plane integer expected by the .geo function library."""
        return {Plane.XY: 0, Plane.XZ: 1, Plane.YZ: 2}[self]


@dataclass
class Cursor:
    """Current position and orientation of the pipe network end-face.

    Attributes
    ----------
    position : ndarray, shape (3,)
        Centre of the current end-face.
    direction : ndarray, shape (3,)
        Unit vector pointing along the pipe axis away from the last segment
        (outward normal of the end-face).
    up : ndarray, shape (3,)
        Unit vector defining the "up" direction in the cross-section plane.
        Used to determine the bend plane for rotational extrusions.
    """

    position:  np.ndarray
    direction: np.ndarray
    up:        np.ndarray

    def __post_init__(self) -> None:
        self.position  = np.asarray(self.position,  dtype=float)
        self.direction = _normalise(np.asarray(self.direction, dtype=float))
        self.up        = _normalise(np.asarray(self.up,        dtype=float))
        if abs(np.dot(self.direction, self.up)) > 1e-6:
            raise ValueError(
                "Cursor 'up' vector must be perpendicular to 'direction'."
            )

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_plane(
        cls,
        plane:    Plane,
        position: np.ndarray | list[float] | None = None,
    ) -> "Cursor":
        """Create a cursor aligned with a canonical plane.

        Parameters
        ----------
        plane : Plane
            The cross-section plane.  The extrusion direction is the
            plane's outward normal.
        position : array-like, optional
            Starting position.  Defaults to the origin.
        """
        pos = np.zeros(3) if position is None else np.asarray(position, dtype=float)
        d   = plane.extrusion_axis
        # Canonical up vectors for each plane (matches world convention):
        #   XY (extrude along Z) → up = +Y
        #   XZ (extrude along Y) → up = +Z
        #   YZ (extrude along X) → up = +Z
        _up_map = {
            Plane.XY: np.array([0., 1., 0.]),
            Plane.XZ: np.array([0., 0., 1.]),
            Plane.YZ: np.array([0., 0., 1.]),
        }
        up = _up_map[plane]
        return cls(position=pos, direction=d, up=up)

    # ------------------------------------------------------------------
    # Derived quantities
    # ------------------------------------------------------------------

    @property
    def right(self) -> np.ndarray:
        """Unit vector completing the right-handed frame (direction × up)."""
        return _normalise(np.cross(self.direction, self.up))

    def advanced(self, length: float) -> "Cursor":
        """Return a new cursor moved *length* along ``direction``."""
        return Cursor(
            position  = self.position + length * self.direction,
            direction = self.direction.copy(),
            up        = self.up.copy(),
        )

    def rotated(
        self,
        axis:  np.ndarray,
        angle: float,
    ) -> "Cursor":
        """Return a new cursor with direction and up rotated about *axis*.

        Uses Rodrigues' rotation formula.

        Parameters
        ----------
        axis : array-like, shape (3,)
            Unit vector of the rotation axis.
        angle : float
            Rotation angle in radians.
        """
        axis = _normalise(np.asarray(axis, dtype=float))
        new_dir = _rodrigues(self.direction, axis, angle)
        new_up  = _rodrigues(self.up,        axis, angle)
        return Cursor(
            position  = self.position.copy(),
            direction = new_dir,
            up        = new_up,
        )

    def __repr__(self) -> str:
        p = np.round(self.position,  4)
        d = np.round(self.direction, 4)
        return f"Cursor(pos={p}, dir={d})"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise ValueError(f"Cannot normalise near-zero vector {v}")
    return v / n


def _perpendicular(v: np.ndarray) -> np.ndarray:
    """Return an arbitrary unit vector perpendicular to v."""
    candidate = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(v, candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    return _normalise(np.cross(v, candidate))


def _rodrigues(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotate vector v around axis by angle (radians) — Rodrigues formula."""
    c, s = np.cos(angle), np.sin(angle)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1 - c)
