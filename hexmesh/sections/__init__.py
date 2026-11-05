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
tasks 0082, 0084).  Two layouts, chosen on the core
(``PipeSpec.core(layout=)``, decision 0036):

- ``sections.oh``: the 5-patch O-H face, pure (corner levels, edges,
  patches, corner order, signature kinds), used by the block layouts;
  ``sections.oh_gmsh``: its GMSH faces;
- ``sections.h``: one Cartesian patch for a rectangular core, pure and
  GMSH.

``layout_of(spec)`` gives a spec's layout module; both implement
``SectionLayout``, what the assembly asks of a layout (task 0084).
``build_face`` builds any layout's GMSH face.  ``sections`` sits between
``core`` and ``assembly`` (DESIGN §3.1): it imports ``core``, never
``assembly``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.shape import BlendShape, RectShape
from . import h, oh
from ._gmsh_helpers import add_physical_group, add_point
from .oh_gmsh import (build_annulus, build_oh_blend, build_oh_circle, build_oh_circle8,
                      build_oh_rect, build_ring)

__all__ = ["oh", "h", "SectionLayout", "LAYOUT_MODULES", "layout_of", "build_face", "add_physical_group", "build_oh_circle", "build_oh_circle8",
           "build_oh_rect", "build_oh_blend", "build_ring", "build_annulus"]


@runtime_checkable
class SectionLayout(Protocol):
    """What fittings, the assembler and the block layouts ask of a section
    layout (task 0084).  A layout is a module (``sections.oh``,
    ``sections.h``); decision 0035's multi-core sections implement the
    same members.  Each member, and who needs it:

    - ``NAME``: the ``PipeSpec.core(layout=)`` value.
    - ``CORE_KIND``: the core layer's kind in the port signature
      (``assembly.signature``): faces of different kinds never share
      nodes.
    - ``levels(spec)``: corner levels, each corner's in-plane position and
      each edge's divisions and grading.  The block layouts place a face
      from it (``assembly.blocks.face_vertices``), and it is the
      declaration the GMSH face is checked against (``tests/test_sections``).
    - ``patches(spec)``: (material, corners) of each patch: the block
      layouts' port faces and cell zones.
    - ``corner0_angle(spec)``: the angle of corner 0, for corner matching
      between frames (``assembly.blocks.corner_shift``).
    - ``side_counts(shape, n_outer)``: divisions of outer side *k*, which
      every sweep connection and the face grading need.
    - ``section_cells(spec)``: quads per section, for the exact cell count
      before GMSH (``Assembly.cell_count``).
    - ``node_grids(spec)``: (layer, node grid) per patch, for the
      predicted quality before GMSH (``assembly.section_quality``).

    The GMSH face is ``build_face(spec, …)``, which every layout's builder
    sits behind.  What isn't here, and why, is in task 0084's notes: the
    slab connection and the face grading still branch on the layout in
    ``assembly`` (they build GMSH entities from a face, below the layout).
    """

    NAME: str
    CORE_KIND: str

    def levels(self, spec) -> list: ...
    def patches(self, spec) -> list[tuple[str, tuple[tuple[int, int], ...]]]: ...
    def corner0_angle(self, spec) -> float: ...
    def side_counts(self, shape, n_outer: int = 4) -> tuple[int, ...]: ...
    def section_cells(self, spec) -> int: ...
    def node_grids(self, spec) -> list[tuple[int, np.ndarray]]: ...


#: the layouts, by ``PipeSpec.layout``
LAYOUT_MODULES: dict[str, SectionLayout] = {oh.NAME: oh, h.NAME: h}


def layout_of(spec) -> SectionLayout:
    """*spec*'s section layout module (``LAYOUT_MODULES``)."""
    return LAYOUT_MODULES[spec.layout]


def build_face(spec, position, h_axis, v_axis, lc: float,
               stretch: tuple | None = None) -> LayeredCrossSection:
    """Build *spec*'s whole face in GMSH: the core, then a ring per shell.

    Centred at *position*, in the plane of the unit vectors *h_axis* and
    *v_axis*; *stretch* ``(b, s)`` scales it by ``s`` along the in-plane
    direction ``b`` (miter cut faces).
    """
    if spec.layout == "h":
        cs = h.build_h_rect(spec, position, h_axis, v_axis, lc, stretch)
        layers = [(spec.layer_names[0], cs)]
        if spec.shells:     # rings on the core's corners (task 0086); a centre for arcs
            center = add_point(*(float(c) for c in position), lc)
            rot = spec.rot_rad
            cs.corner_angles = [rot + float(np.arctan2(p[1], p[0]))
                                for p in (spec.core_shape.corner(k) for k in range(4))]
            grading = [h.side_grading(spec, k) for k in range(4)]
            for shell, outline in zip(spec.shells, spec.outlines[1:]):
                cs = build_ring(inner=cs, outer=outline, lc=lc, nrad=shell.nrad,
                                mprg=shell.mprg, rot=rot, stretch=stretch, center=center,
                                side_grading=grading)
                layers.append((shell.name, cs))
        return LayeredCrossSection(layers)
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
