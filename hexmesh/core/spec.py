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
Declarative pipe and bundle specifications.

LayerSpec
    Parameters for one shell: the region between the previous layer's
    outline and its own (decision 0026).  The innermost core is described
    by the Shape passed to PipeSpec.core().

PipeSpec
    Builder for a single-pipe cross-section stack.  Fluent API::

        pipe = (
            PipeSpec(nang=5, mbmp=1.0)
            .core("fluid",       shape=CircleShape(0.3, nang=5), nrad=5)
            .shell("pipe_wall",  dR=0.05, nrad=3)
            .shell("insulation", dR=0.10, nrad=4)
        )

    The conformality constraint — all layers share the same angular
    division counts — is enforced at ``.shell()`` time.

BundleSpec
    Tiled array of identical pipes on a rectangular grid.  Each pipe
    must end in a rectangular shell so adjacent cells share flat faces.
"""

from __future__ import annotations
import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..errors import SpecError, SpecTypeError
from .grading import bump_for_first_cell, bump_for_ratio, progression_for_first_cell
from .params import describe
from .shape import (LAYOUTS, CircleShape, RectShape, Shape, longest_radial, core_wall_span,
                    ring_corners, shape_from_dict)
from .region import MaterialGraph

if TYPE_CHECKING:
    pass


def _check_layer_name(name) -> None:
    """Layer names become group names (``fluid_inlet``,
    ``interface_fluid_steel``), so keep them to ``[A-Za-z0-9_]``."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SpecError(f"layer name {name!r} must be letters, digits and _ only "
                         "(it becomes part of physical group names)",
                        code="layer_name_invalid", where={"field": "name"}, value=name)


class LayoutNotSupported(SpecError):
    """A section layout used where it isn't built yet (task 0084): names
    *where* (a fitting or option), the *layout* and the *task* that adds
    it, so a script or agent can act on it.  ``where`` is the structured
    location (``{"part": …}``); ``site`` keeps the text."""

    def __init__(self, where: str, layout: str, task: str, hint: str = ""):
        self.site, self.layout, self.task = where, layout, task
        super().__init__(f"{where}: layout {layout!r} is not supported yet (task {task})"
                         + (f"; {hint}" if hint else ""),
                         code="layout_not_supported", where={"part": where}, value=layout,
                         hint=hint or None)


def _wall_progression(mprg: float | None, thickness: float, nrad: int,
                      first_cell: float) -> float:
    """``mprg`` giving a cell of *first_cell* at the outer end of a layer.

    Radial curves run inner → outer and ``mprg`` grows cells outward, so a
    small wall cell needs the reciprocal of the first-cell ratio.
    """
    if mprg is not None:
        raise SpecTypeError("pass either mprg= or first_cell=, not both",
                            code="grading_args_conflict", hint="pass mprg= or first_cell=")
    return 1.0 / progression_for_first_cell(thickness, nrad, first_cell)


@dataclass(frozen=True)
class LayerSpec:
    """One shell layer in a pipe cross-section stack.

    The shell fills the region between the previous layer's outline and
    its own (decision 0026), given by exactly one of *dR* and *outer*.

    Attributes
    ----------
    name : str
        Material label used for Physical groups and MaterialGraph nodes.
    dR : float or None
        Thickness: the previous outline grown by *dR* (a circle's radius +
        dR; a rectangle's half_w and half_h + dR).
    nrad : int
        Number of mesh node layers across the thickness.
    mprg : float
        Transfinite progression factor for the radial lines (>1 refines
        toward the inner boundary, <1 toward the outer).
    outer : Shape or None
        The layer's own outline (``CircleShape`` or ``RectShape``).
    """

    name: str
    dR:   float | None
    nrad: int
    mprg: float = 1.0
    outer: Shape | None = None

    def __post_init__(self) -> None:
        if (self.dR is None) == (self.outer is None):
            raise SpecError(f"shell `{self.name}`: give exactly one of dR and outer",
                            code="shell_outline_args", where={"label": self.name})
        if self.dR is not None and self.dR <= 0:
            raise SpecError(f"LayerSpec.dR must be positive, got {self.dR!r}",
                            code="size_not_positive", where={"label": self.name, "field": "dR"},
                            value=self.dR, limit={"min_exclusive": 0})
        if self.nrad is None or self.nrad < 1:
            raise SpecError(f"LayerSpec.nrad must be >= 1, got {self.nrad!r}",
                            code="count_below_minimum",
                            where={"label": self.name, "field": "nrad"}, value=self.nrad,
                            limit={"min": 1})

    def outline(self, inner: Shape) -> Shape:
        """This layer's outline, around *inner* (the previous one)."""
        return self.outer if self.outer is not None else inner.grown(self.dR)


class PipeSpec:
    """Builder for a concentric-layer pipe cross-section.

    Parameters
    ----------
    nang : int, optional
        Angular divisions per quadrant arc.  Required for circular cores
        and all shells.  Shared across the entire stack.
    nang_w : int, optional
        Angular divisions along width edges.  Required for rectangular cores.
    nang_h : int, optional
        Angular divisions along height edges.  Required for rectangular cores.
    mbmp : float
        Angular bump factor for Transfinite Line.  Default 1.0 (uniform).
    rot : float
        Rotation offset in degrees applied to the OH grid corner angles,
        like every other angle (decision 0024).  Use ``rot=-45`` to align
        patch boundaries with horizontal/vertical axes (e.g. for
        half-buried pipes).  Default 0.0.

    Examples
    --------
    Circular insulated pipe (shorthand — no repeated nang)::

        pipe = (
            PipeSpec(nang=5)
            .core("fluid",       radius=0.3,  nrad=5)
            .shell("pipe_wall",  dR=0.05, nrad=3)
            .shell("insulation", dR=0.10, nrad=4)
        )

    Rectangular duct (shorthand; an H face, walls graded, since 0.4.0)::

        duct = (
            PipeSpec(nang_w=6, nang_h=6)
            .core("air", half_w=0.2, half_h=0.1, first_cell=0.02)
            .shell("duct_wall", dR=0.01, nrad=3)
        )

    Circular conductor in a square insulation block (decision 0026)::

        bar = (
            PipeSpec(nang=4)
            .core("copper", radius=0.01, nrad=4)
            .shell("insulation", outer=RectShape(0.02, 0.02, 4, 4), nrad=3)
        )
    """

    #: the constructor's arguments (task 0095): saved as they are
    PARAMS = {
        "nang": describe("cells", "divisions per quadrant arc; circles and shells",
                         minimum=1),
        "nang_w": describe("cells", "divisions along width edges; rectangular cores",
                           minimum=1),
        "nang_h": describe("cells", "divisions along height edges; rectangular cores",
                           minimum=1),
        "mbmp": describe("1", "angular bump factor of the transfinite arcs (1 = uniform)",
                         exclusiveMinimum=0),
        "rot": describe("deg", "rotation of the outer corner frame (decision 0024)"),
        "n_outer": describe("1", "outer structural corners: a positive multiple of 4",
                            minimum=4),
    }

    def __init__(
        self,
        nang:    int | None = None,
        nang_w:  int | None = None,
        nang_h:  int | None = None,
        mbmp:    float = 1.0,
        rot:     float = 0.0,
        n_outer: int   = 4,
    ) -> None:
        if n_outer < 4 or n_outer % 4 != 0:
            raise SpecError(
                f"PipeSpec n_outer must be a positive multiple of 4, got {n_outer!r}.",
                code="n_outer_invalid", where={"field": "n_outer"}, value=n_outer,
                limit="a positive multiple of 4")
        self._n_outer = n_outer
        self._nang   = nang
        self._nang_w = nang_w
        self._nang_h = nang_h
        self._mbmp   = mbmp
        self._rot    = float(rot)    # degrees
        self._core:   tuple[str, Shape] | None = None
        self._shells: list[LayerSpec] = []
        self._layout = "oh"
        self._core_wall_bump: tuple[float, float] | None = None   # an H core's (c_w, c_h)
        # Validate nang / n_outer constraint if nang is already known at init time.
        if nang is not None:
            divisor = n_outer // 4
            if nang % divisor != 0:
                raise SpecError(
                    f"PipeSpec nang={nang} must be divisible by n_outer//4={divisor} "
                    f"(n_outer={n_outer}).",
                    code="nang_not_divisible", where={"field": "nang"}, value=nang,
                    limit={"multiple_of": divisor})

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------

    #: :meth:`core`'s arguments (task 0095).  ``name``, ``shape``,
    #: ``layout``, ``nrad``, ``mprg`` and ``wall_bump`` are saved; the
    #: others are inputs, resolved into those.
    CORE_PARAMS = {
        "name": describe("-", "material label of the core"),
        "shape": describe("-", "the core outline: a circle or a rectangle"),
        "nrad": describe("cells", "O-H radial cells, inner square to wall (0 on an H core)",
                         minimum=0),
        "mprg": describe("1", "radial progression (> 1 refines inward); H: wall growth ratio",
                         exclusiveMinimum=0),
        "radius": describe("length", "input: a circular core's radius", exclusiveMinimum=0),
        "half_w": describe("length", "input: a rectangular core's half-width",
                           exclusiveMinimum=0),
        "half_h": describe("length", "input: a rectangular core's half-height",
                           exclusiveMinimum=0),
        "first_cell": describe("length", "input: the wall cell height; resolves to mprg or "
                               "wall_bump", exclusiveMinimum=0),
        "layout": describe("-", "section layout (decision 0036)", enum=sorted(LAYOUTS)),
        "wall_bump": describe("1", "an H core's Bump coefficients (c_w, c_h); < 1 refines "
                              "toward the walls", exclusiveMinimum=0),
    }

    def core(
        self,
        name:   str,
        shape:  Shape | None = None,
        nrad:   int = 0,
        mprg:   float | None = None,
        *,
        radius: float | None = None,
        half_w: float | None = None,
        half_h: float | None = None,
        first_cell: float | None = None,
        layout: str | None = None,
        wall_bump: tuple[float, float] | None = None,
    ) -> "PipeSpec":
        """Set the innermost (core) layer.

        The shape can be specified either by passing a ``shape`` object
        directly, or by passing geometry keyword arguments so that the shape
        is built automatically from the PipeSpec-level division counts:

        - Circular core: pass ``radius=<float>`` — requires ``PipeSpec(nang=…)``
        - Rectangular core: pass ``half_w=<float>, half_h=<float>`` —
          requires ``PipeSpec(nang_w=…, nang_h=…)``

        Both forms are equivalent::

            # explicit shape (old form — still valid):
            PipeSpec(nang=5).core("fluid", shape=CircleShape(0.3, nang=5), nrad=4)

            # shorthand (no repeated nang):
            PipeSpec(nang=5).core("fluid", radius=0.3, nrad=4)

        Parameters
        ----------
        name : str
            Material label for the core region.
        shape : Shape, optional
            ``CircleShape`` or ``RectShape`` describing the
            core outer boundary.  Mutually exclusive with ``radius`` /
            ``half_w`` / ``half_h``.
        nrad : int
            Radial mesh layers (from inner square to outer boundary).
        mprg : float
            Radial progression factor (default 1, uniform; > 1 refines
            toward the inner square, < 1 toward the outer wall).
        radius : float, optional
            Radius of a circular core.  Requires ``nang`` to be set on the
            ``PipeSpec``.  Mutually exclusive with ``shape``.
        half_w : float, optional
            Half-width of a rectangular core.  Must be paired with
            ``half_h``.  Requires ``nang_w`` and ``nang_h`` to be set.
            Mutually exclusive with ``shape`` and ``radius``.
        half_h : float, optional
            Half-height of a rectangular core.  See ``half_w``.
        first_cell : float, optional
            Largest radial height of a cell at the core's outer wall (the
            circle); sets ``mprg`` (< 1).  The core ring is thickest at
            mid-arc (``core_wall_span``), where the wall cell equals
            *first_cell*; at the corners it is about 0.81 of it.  Circular,
            ``n_outer = 4`` cores only; mutually exclusive with ``mprg``
            (docs/tasks/0002).  On an H core: the end cell of every side,
            at all four walls, resolved here to ``wall_bump`` (task 0084).
        layout : str, optional
            The section layout (decision 0036): ``"h"``, one Cartesian
            patch, the default for a rectangular core (since 0.4.0, task
            0087); or ``"oh"``, the 5-patch O-H face, the default for a
            circle and the opt-in for a rectangle.  An H
            core has no ring, so no ``nrad``; ``mprg`` is then the wall
            growth ratio, the second cell from each wall over the first
            (> 1 refines toward the walls), and ``first_cell`` its end
            cell.  Both resolve here to ``wall_bump``.
        wall_bump : (float, float), optional
            An H core's ``Bump`` coefficients, ``(c_w, c_h)``: the sides
            of ``nang_w`` and of ``nang_h`` divisions (< 1 refines toward
            both walls; gmsh's two-sided law).  What ``first_cell=``
            resolves to, and what ``to_dict`` stores, as O-H stores
            ``mprg``: a k× refinement keeps them, so its nodes nest.
            ``first_cell=`` and ``mprg=`` resolve to it.
        """
        if self._core is not None:
            raise RuntimeError("PipeSpec.core() may only be called once.")
        if layout is not None and layout not in LAYOUTS:
            raise SpecError(f"layout must be one of {sorted(LAYOUTS)}, got {layout!r}",
                            code="layout_unknown", where={"field": "layout"}, value=layout,
                            limit=sorted(LAYOUTS))

        # Resolve shape from shorthand geometry keywords
        geo_given = radius is not None or half_w is not None or half_h is not None
        if shape is not None and geo_given:
            raise SpecTypeError(
                "PipeSpec.core(): pass either shape= or geometry keywords "
                "(radius / half_w / half_h), not both."
            , code="shape_args_conflict")
        if shape is None and not geo_given:
            raise SpecTypeError(
                "PipeSpec.core(): provide either shape= or one of the "
                "geometry keywords (radius=, half_w= + half_h=)."
            , code="shape_args_missing")

        if geo_given:
            if radius is not None:
                # Circular shorthand
                if half_w is not None or half_h is not None:
                    raise SpecTypeError(
                        "PipeSpec.core(): radius and half_w/half_h are "
                        "mutually exclusive."
                    , code="shape_args_conflict")
                if self._nang is None:
                    raise SpecTypeError(
                        "PipeSpec.core(radius=…) requires nang to be set on "
                        "the PipeSpec, e.g. PipeSpec(nang=5).core(…, radius=0.3)."
                    , code="nang_missing", where={"field": "nang"})
                shape = CircleShape(radius=radius, nang=self._nang)
            else:
                # Rectangular shorthand
                if half_w is None or half_h is None:
                    raise SpecTypeError(
                        "PipeSpec.core(): half_w and half_h must both be "
                        "provided for a rectangular core."
                    , code="shape_args_missing")
                if self._nang_w is None or self._nang_h is None:
                    raise SpecTypeError(
                        "PipeSpec.core(half_w=…, half_h=…) requires nang_w "
                        "and nang_h to be set on the PipeSpec, e.g. "
                        "PipeSpec(nang_w=6, nang_h=4).core(…, half_w=0.2, half_h=0.1)."
                    , code="nang_missing", where={"field": "nang_w"})
                shape = RectShape(
                    half_w=half_w, half_h=half_h,
                    nang_w=self._nang_w, nang_h=self._nang_h,
                )

        self._validate_shape_nang(shape)
        default = layout is None
        if default:                    # H for a rectangle (0.4.0, decision 0036 item 1)
            layout = "oh" if shape.is_round or shape.is_station else "h"
        if layout == "h":
            if nrad:
                how = ("a rectangular core is H by default since 0.4.0" if default
                       else "an H core")
                raise SpecError(
                    f"nrad={nrad!r} on {how}: it has no ring, so its "
                    "near-wall cells come from wall grading.  Drop nrad and grade "
                    "the walls (first_cell= or mprg=), or pass layout='oh' to keep "
                    "the O-H face (decision 0036)",
                    code="nrad_on_h_core", where={"label": name, "field": "nrad"},
                    value=nrad,
                    hint="drop nrad and grade the walls (first_cell= or mprg=), "
                         "or pass layout='oh'")
        elif nrad < 1:
            raise SpecError(f"nrad must be >= 1, got {nrad!r}",
                            code="count_below_minimum", where={"label": name, "field": "nrad"},
                            value=nrad, limit={"min": 1})
        if layout == "h":
            if shape.is_round or shape.is_station:
                raise SpecError(f"layout='h' needs a rectangular core, got a {shape.label}",
                                code="h_layout_needs_rectangle",
                                where={"label": name, "field": "layout"})
            if self._n_outer != 4:
                raise SpecError("layout='h' needs n_outer = 4",
                                code="h_layout_needs_n_outer_4",
                                where={"label": name, "field": "n_outer"}, value=self._n_outer,
                                limit=4)
            if sum(x is not None for x in (mprg, first_cell, wall_bump)) > 1:
                raise SpecTypeError("pass one of mprg=, first_cell= or wall_bump=",
                                    code="grading_args_conflict", where={"label": name})
            if first_cell is not None:             # each side's coefficient
                wall_bump = tuple(
                    bump_for_first_cell(math.dist(shape.corner(k), shape.corner(k + 1)),
                                        shape.side_count(k, 4), first_cell)
                    for k in (0, 1))
            elif mprg is not None and mprg != 1.0:   # a wall ratio, per side
                wall_bump = tuple(bump_for_ratio(shape.side_count(k, 4), mprg) for k in (0, 1))
            mprg = None                            # the grading is wall_bump, or uniform
            if wall_bump is not None:
                wall_bump = tuple(float(c) for c in wall_bump)
                if len(wall_bump) != 2 or not all(c > 0 for c in wall_bump):
                    raise SpecError(f"wall_bump must be two positive coefficients, "
                                     f"got {wall_bump!r}",
                                    code="wall_bump_invalid",
                                    where={"label": name, "field": "wall_bump"}, value=wall_bump)
            self._layout = "h"
            self._core_wall_bump = wall_bump
            first_cell = None                      # the wall grading, not mprg
        elif wall_bump is not None:
            raise SpecTypeError("wall_bump= is an H core's grading (layout='h')",
                                code="wall_bump_needs_h_layout",
                                where={"label": name, "field": "wall_bump"})
        if first_cell is not None:
            if not shape.is_round:
                raise SpecTypeError("first_cell= supports circular cores only",
                                    code="first_cell_unsupported",
                                    where={"label": name, "field": "first_cell"})
            if self._n_outer != 4:
                raise SpecTypeError("first_cell= supports n_outer=4 cores only",
                                    code="first_cell_unsupported",
                                    where={"label": name, "field": "first_cell"})
            # Solved on the thickest span (mid-arc), so first_cell is the
            # largest wall cell; at the corners it is 0.4/0.491 ≈ 0.81 of it.
            mprg = _wall_progression(mprg, core_wall_span(shape.max_extent),
                                     nrad, first_cell)
        _check_layer_name(name)
        self._core = (name, shape)
        # Store core nrad/mprg as a pseudo-LayerSpec for uniform iteration
        self._core_nrad = nrad
        self._core_mprg = 1.0 if mprg is None else mprg
        return self

    #: :meth:`shell`'s arguments (task 0095).  ``first_cell`` is an
    #: input, resolved into ``mprg``; the others are saved.
    SHELL_PARAMS = {
        "name": describe("-", "material label of the shell"),
        "dR": describe("length", "thickness: the previous outline grown by dR (or outer)",
                       exclusiveMinimum=0, limit="OUTLINE_MIN_GAP"),
        "nrad": describe("cells", "radial cells across the shell", minimum=1),
        "mprg": describe("1", "radial progression (> 1 refines toward the inner boundary)",
                         exclusiveMinimum=0),
        "outer": describe("-", "the shell's outline, instead of dR",
                          limit=("OUTLINE_MIN_GAP", "OUTLINE_NONORTH_WARN",
                                 "OUTLINE_NONORTH_MAX")),
        "first_cell": describe("length", "input: the outer-boundary cell height; resolves to "
                               "mprg", exclusiveMinimum=0),
    }

    def shell(
        self,
        name: str,
        dR:   float | None = None,
        nrad: int | None = None,
        mprg: float | None = None,
        *,
        outer: Shape | None = None,
        first_cell: float | None = None,
    ) -> "PipeSpec":
        """Add a shell: the region between the previous outline and this
        layer's (decision 0026).

        Give exactly one of *dR* (the previous outline grown by *dR*) and
        *outer* (a new outline, ``CircleShape`` or ``RectShape``).  A stack
        with any rectangle has equal counts on every side of every outline
        (``nang = nang_w = nang_h``) and ``n_outer = 4``, checked here.
        That each outline lies inside the next is checked by the
        assembly's validation.

        Parameters
        ----------
        name : str
            Material label.
        dR : float, optional
            Thickness of this layer.
        nrad : int
            Radial mesh divisions across the layer.
        mprg : float
            Radial progression factor (default 1, uniform; > 1 refines
            toward the inner boundary, < 1 toward the outer).
        outer : CircleShape or RectShape, optional
            This layer's outline.
        first_cell : float, optional
            Largest radial height of a cell at the layer's outer boundary;
            sets ``mprg`` (< 1).  Solved on the ring's longest radial, so no
            wall cell exceeds it: every radial of a circle grown by ``dR``
            (exact all round); the corner lines of a rectangle grown by
            ``dR`` (``√2·dR``); for a shell that changes shape, the longest
            line between corresponding points of the two outlines.
            Mutually exclusive with ``mprg``.
        """
        if self._core is None:
            raise RuntimeError("Call PipeSpec.core() before .shell().")
        if nrad is None:
            raise SpecTypeError(f"shell `{name}`: nrad is required",
                                code="shell_nrad_missing", where={"label": name, "field": "nrad"})
        _check_layer_name(name)
        layer = LayerSpec(name=name, dR=dR, nrad=nrad, mprg=1.0, outer=outer)
        inner = self.outlines[-1]
        outline = layer.outline(inner)
        self._check_counts(name, outline)
        if first_cell is not None:
            if outer is None and type(inner).side_curve == "arc":
                span = dR                       # every radial is dR long
            else:
                corners = self.corners()[-1]
                span = longest_radial(inner, corners, outline,
                                      ring_corners(corners, outline))
            mprg = _wall_progression(mprg, span, nrad, first_cell)
        self._shells.append(LayerSpec(name=name, dR=dR, nrad=nrad,
                                      mprg=1.0 if mprg is None else mprg, outer=outer))
        return self

    def with_radii(self, radii: list[float], mprgs: list[float] | None = None) -> "PipeSpec":
        """This spec with core radius ``radii[0]`` and shell thicknesses
        ``radii[1:]``, and, if given, radial gradings *mprgs* (core first).
        Circular stacks of ``dR`` shells only."""
        name, shape = self._core
        if any(sh.dR is None for sh in self.shells):
            raise SpecError("PipeSpec.with_radii needs dR shells",
                            code="with_radii_needs_dr_shells")
        if mprgs is None:
            mprgs = [self._core_mprg] + [sh.mprg for sh in self.shells]
        out = (PipeSpec(nang=self.nang, n_outer=self.n_outer, rot=self.rot, mbmp=self.mbmp)
               .core(name, CircleShape(radius=radii[0], nang=shape.nang),
                     nrad=self._core_nrad, mprg=mprgs[0]))
        for sh, dR, m in zip(self.shells, radii[1:], mprgs[1:]):
            out = out.shell(sh.name, dR=dR, nrad=sh.nrad, mprg=m)
        return out

    def _check_counts(self, name: str, outline: Shape) -> None:
        """Equal counts per side through a stack with a rectangle
        (decision 0026, item 3)."""
        outlines = self.outlines + [outline]
        if all(type(o).side_curve == "arc" for o in outlines):
            return                              # circles: nang already shared
        if self._n_outer != 4:
            raise SpecError(f"shell `{name}`: a stack with a rectangular outline "
                             f"needs n_outer = 4, got {self._n_outer}",
                            code="rect_stack_needs_n_outer_4",
                            where={"label": name, "field": "n_outer"}, value=self._n_outer,
                            limit=4)
        names = self.layer_names + [name]
        want = outlines[0].counts[0]
        for lname, o in zip(names, outlines):
            if o.counts != (want, want):
                raise SpecError(
                    f"shell `{name}`: every outline in a stack with a rectangle needs "
                    f"equal counts per side; layer `{lname}` has {o.counts} "
                    f"(nang_w, nang_h), the core {want} per side",
                    code="rect_stack_counts_unequal", where={"label": name},
                    value=o.counts)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def layer_names(self) -> list[str]:
        """Ordered material names, innermost first."""
        if self._core is None:
            return []
        return [self._core[0]] + [s.name for s in self._shells]

    @property
    def core_shape(self) -> Shape:
        if self._core is None:
            raise RuntimeError("PipeSpec has no core defined.")
        return self._core[1]

    @property
    def shells(self) -> list[LayerSpec]:
        return list(self._shells)

    @property
    def outlines(self) -> list[Shape]:
        """Every layer's outline, core first (decision 0026)."""
        if self._core is None:
            raise RuntimeError("PipeSpec has no core defined.")
        out = [self._core[1]]
        for sh in self._shells:
            out.append(sh.outline(out[-1]))
        return out

    def corners(self) -> list[list]:
        """Corner points ``(u, v)`` of every layer's outer boundary, before
        ``rot``: the core's O-H corners, then each ring's (its corner lines
        run from the previous layer's corners; ``ring_corners``)."""
        outlines = self.outlines
        n = self._n_outer if type(outlines[0]).side_curve == "arc" else 4
        out = [[outlines[0].corner(k * 4 // n) if n == 4 else
                outlines[0].ring_corner(math.pi / 4 + 2 * math.pi * k / n)
                for k in range(n)]]
        for o in outlines[1:]:
            out.append(ring_corners(out[-1], o))
        return out

    @property
    def n_outer(self) -> int:
        return self._n_outer

    @property
    def layout(self) -> str:
        """The core's section layout, ``"oh"`` or ``"h"`` (decision 0036)."""
        return self._layout

    @property
    def wall_grading(self) -> tuple | None:
        """An H core's wall grading: ``("bump", (c_w, c_h))``, or ``None``
        (uniform); ``None`` on an O-H core, whose grading is ``mprg``."""
        if self._layout != "h" or self._core_wall_bump is None:
            return None
        return ("bump", self._core_wall_bump)

    @property
    def nang(self) -> int | None:
        return self._nang

    @property
    def nang_w(self) -> int | None:
        return self._nang_w

    @property
    def nang_h(self) -> int | None:
        return self._nang_h

    @property
    def mbmp(self) -> float:
        return self._mbmp

    @property
    def rot(self) -> float:
        """Corner-frame rotation in degrees."""
        return self._rot

    @property
    def rot_rad(self) -> float:
        """``rot`` in radians, for the face builders."""
        return math.radians(self._rot)

    @property
    def side_counts(self) -> tuple[int, ...]:
        """Divisions of each outer curve of the core, corner *k* → *k* + 1
        (NE→NW first): ``nang // (n_outer // 4)`` per arc of a circle;
        ``(nang_w, nang_h, nang_w, nang_h)`` for a rectangle."""
        shape = self.core_shape
        n = self._n_outer if shape.is_round else 4
        return tuple(shape.side_count(k, n) for k in range(n))

    @property
    def period(self) -> float:
        """Geometric symmetry period P in radians: the smallest roll that
        maps the section onto itself (DESIGN §6.1, decision 0010).
        ``2π / n_outer`` for a circle, π/2 for a square, π for any other
        rectangle; for a stack, the largest over its outlines (they are
        all of the form 2π/m with m dividing 4)."""
        return max(o.period(self._n_outer) for o in self.outlines)

    @property
    def graph(self) -> MaterialGraph:
        """MaterialGraph derived from the layer order."""
        g = MaterialGraph()
        names = self.layer_names
        for name in names:
            g.add_material(name)
        for i in range(len(names) - 1):
            g.add_interface(names[i], names[i + 1])
        return g

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_shape_nang(self, shape: Shape) -> None:
        """Check that shape angular divisions match PipeSpec-level values.
        A ``Transition`` station's come from its two ends, checked there."""
        if shape.is_station:
            return
        counts = shape.angular_counts
        for name, n in counts.items():
            mine = getattr(self, f"_{name}")
            if mine is not None and n != mine:
                raise SpecError(
                    f"{type(shape).__name__}.{name}={n} does not match "
                    f"PipeSpec({name}={mine})."
                , code="shape_counts_mismatch", where={"field": name}, value=n, limit=mine)
        for name, n in counts.items():
            if getattr(self, f"_{name}") is None:
                setattr(self, f"_{name}", n)
        if "nang" in counts:
            # Enforce nang % (n_outer // 4) == 0 once nang is resolved.
            divisor = self._n_outer // 4
            if self._nang % divisor != 0:
                raise SpecError(
                    f"PipeSpec nang={self._nang} must be divisible by "
                    f"n_outer//4={divisor} (n_outer={self._n_outer}).",
                    code="nang_not_divisible", where={"field": "nang"},
                    value=self._nang, limit={"multiple_of": divisor})

    # ------------------------------------------------------------------
    # Serialisation (docs/tasks/0006)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Plain JSON-serialisable description of this spec.

        Lengths are stored in the user's unit, unconverted.  ``mprg`` is
        stored as resolved, so a spec built with ``first_cell=`` reloads
        with the same progression.
        """
        if self._core is None:
            raise RuntimeError("PipeSpec has no core defined.")
        name, shape = self._core
        if not hasattr(shape, "to_dict"):
            raise SpecTypeError(f"cannot serialise core shape {type(shape).__name__}",
                                code="shape_not_serialisable")
        shape_d = shape.to_dict()
        shells = []
        for sh in self._shells:
            if sh.outer is None:
                shells.append({"type": "shell", "name": sh.name, "dR": sh.dR,
                               "nrad": sh.nrad, "mprg": sh.mprg})
            else:
                shells.append({"type": "shell", "name": sh.name,
                               "outer": sh.outer.to_dict(),
                               "nrad": sh.nrad, "mprg": sh.mprg})
        return {
            "nang": self._nang, "nang_w": self._nang_w, "nang_h": self._nang_h,
            "mbmp": self._mbmp, "rot": self._rot, "n_outer": self._n_outer,
            "core": {"name": name, "shape": shape_d, "layout": self._layout,
                     "nrad": self._core_nrad, "mprg": self._core_mprg,
                     **({"wall_bump": list(self._core_wall_bump)}
                        if self._core_wall_bump is not None else {})},
            "shells": shells,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipeSpec":
        """Rebuild a spec from :meth:`to_dict` output."""
        spec = cls(nang=d.get("nang"), nang_w=d.get("nang_w"), nang_h=d.get("nang_h"),
                   mbmp=d.get("mbmp", 1.0), rot=d.get("rot", 0.0),
                   n_outer=d.get("n_outer", 4))
        core = d["core"]
        shape = shape_from_dict(core["shape"])
        layout = core.get("layout", "oh")       # saved before task 0084: O-H
        if layout == "h":
            wb = core.get("wall_bump")
            # an H ratio saved as mprg (e0e88dc) resolves to wall_bump here
            spec.core(core["name"], shape, layout="h",
                      wall_bump=None if wb is None else tuple(wb),
                      mprg=None if wb is not None else core.get("mprg", 1.0))
        else:
            spec.core(core["name"], shape, nrad=core["nrad"], mprg=core.get("mprg", 1.0),
                      layout="oh")
        for sh in d.get("shells", []):
            sh = dict(sh)
            kind = sh.pop("type")
            if kind == "square_shell":          # removed (decision 0026): same ring
                n = spec.nang
                sh = {"name": sh["name"], "nrad": sh["nrad"], "mprg": sh.get("mprg", 1.0),
                      "outer": {"type": "rect", "half_w": sh["half_w"],
                                "half_h": sh["half_h"], "nang_w": n, "nang_h": n}}
            elif kind != "shell":
                raise SpecError(f"unknown shell type {kind!r}",
                                code="shell_type_unknown", value=kind)
            if "outer" in sh:
                sh["outer"] = shape_from_dict(sh["outer"])
            spec.shell(**sh)
        return spec

    def __repr__(self) -> str:
        return (
            f"PipeSpec(core={self._core[0] if self._core else None!r}, "
            f"layers={self.layer_names})"
        )


@dataclass
class BundleSpec:
    """Rectangular tiled array of identical pipe cells.

    Each pipe cell must end in a rectangular shell (``outer=RectShape``) so
    adjacent cells share flat faces, giving a conformal interface between
    cells without any inter-tube meshing.

    Attributes
    ----------
    pipe : PipeSpec
        Specification for one pipe cell.  Must end in a rectangular shell.
    nx : int
        Number of cells along the first  in-plane axis.
    ny : int
        Number of cells along the second in-plane axis.
    shell_name : str
        The outer shell's material label is used as the shared "shell side"
        Physical Volume name across the whole bundle.
    """

    pipe:       PipeSpec
    nx:         int
    ny:         int
    shell_name: str = "shell"

    def __post_init__(self) -> None:
        if not self.pipe.shells:
            raise SpecError("BundleSpec.pipe has no shell layers defined.",
                            code="bundle_pipe_has_no_shells")
        outermost = self.pipe.outlines[-1]
        if outermost.side_curve != "line":           # cells tile on flat sides
            raise SpecTypeError(
                "BundleSpec.pipe must end with a rectangular shell "
                f"(outer=RectShape); got {type(outermost).__name__}."
            , code="bundle_pipe_outer_not_rectangle")
        if self.nx < 1 or self.ny < 1:
            raise SpecError("nx and ny must be >= 1.",
                            code="count_below_minimum", where={"field": "nx, ny"},
                            value=(self.nx, self.ny), limit={"min": 1})

    @property
    def pitch_w(self) -> float:
        """Cell width  (2 × the outer shell's half_w)."""
        return 2 * self.pipe.outlines[-1].half_w

    @property
    def pitch_h(self) -> float:
        """Cell height (2 × the outer shell's half_h)."""
        return 2 * self.pipe.outlines[-1].half_h

    @property
    def graph(self) -> MaterialGraph:
        """MaterialGraph for the bundle (same as the pipe graph)."""
        return self.pipe.graph
