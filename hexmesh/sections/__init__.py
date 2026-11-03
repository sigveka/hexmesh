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
Cross-section layouts (DESIGN §6.1 "Sections"; decision 0037, item 1;
task 0082).  One layout today, the 5-patch O-H face:

- ``sections.oh``: its pure description (corner levels, edges, patches,
  corner order, signature kinds), used by the block layouts;
- ``sections.oh_gmsh``: its GMSH faces.

The interface every layout shares is derived when the second one (the H
face, decision 0036) exists.  ``sections`` sits between ``core`` and
``assembly`` (DESIGN §3.1): it imports ``core``, never ``assembly``.
"""

from __future__ import annotations

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.shape import BlendShape, RectShape
from . import oh
from ._gmsh_helpers import add_physical_group
from .oh_gmsh import (build_annulus, build_oh_blend, build_oh_circle, build_oh_circle8,
                      build_oh_rect, build_ring)

__all__ = ["oh", "build_face", "add_physical_group", "build_oh_circle", "build_oh_circle8",
           "build_oh_rect", "build_oh_blend", "build_ring", "build_annulus"]


def build_face(spec, position, h_axis, v_axis, lc: float,
               stretch: tuple | None = None) -> LayeredCrossSection:
    """Build *spec*'s whole face in GMSH: the core, then a ring per shell.

    Centred at *position*, in the plane of the unit vectors *h_axis* and
    *v_axis*; *stretch* ``(b, s)`` scales it by ``s`` along the in-plane
    direction ``b`` (miter cut faces).
    """
    cx, cy, cz = (float(c) for c in position)
    core_name, core_shape = spec._core
    if isinstance(core_shape, RectShape):
        builder = build_oh_rect
    elif isinstance(core_shape, BlendShape):    # a Transition's stations
        builder = build_oh_blend
    else:
        builder = build_oh_circle8 if spec.n_outer == 8 else build_oh_circle
    cs: CrossSection = builder(
        cx=cx, cy=cy, cz=cz,
        shape=core_shape, h_axis=h_axis, v_axis=v_axis, lc=lc,
        nrad=spec._core_nrad, mprg=spec._core_mprg,
        mbmp=spec.mbmp, rot=spec.rot_rad,
        **({'stretch': stretch} if stretch is not None else {}),
    )
    layers = [(core_name, cs)]
    for shell, outline in zip(spec.shells, spec.outlines[1:]):
        cs = build_ring(
            inner=cs, outer=outline, lc=lc,
            nrad=shell.nrad, mprg=shell.mprg, mbmp=spec.mbmp, rot=spec.rot_rad,
            stretch=stretch,
        )
        layers.append((shell.name, cs))
    return LayeredCrossSection(layers)
