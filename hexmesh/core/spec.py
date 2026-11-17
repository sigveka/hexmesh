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
            PipeSpec(n_arc=5, arc_bump=1.0)
            .core("fluid",       shape=CircleShape(0.3, n_arc=5), n_radial=5)
            .shell("pipe_wall",  dR=0.05, n_radial=3)
            .shell("insulation", dR=0.10, n_radial=4)
        )

    The conformality constraint — all layers share the same angular
    division counts — is enforced at ``.shell()`` time.

BundleSpec
    Tiled array of identical pipes on a rectangular grid.  Each pipe
    must end in a rectangular shell so adjacent cells share flat faces.
"""

from __future__ import annotations
import copy
import math
import re
import warnings
from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING

from ..errors import SpecError, SpecTypeError, SpecUsageError
from .grading import bump_for_first_cell, bump_for_ratio, progression_for_first_cell
from .params import describe
from .shape import (LAYOUTS, CircleShape, RectShape, Shape, longest_radial, core_wall_span,
                    ring_corners, shape_from_dict)
from .region import MaterialGraph

if TYPE_CHECKING:
    pass


def _n_arc_hint(n_arc: int, divisor: int) -> str:
    """The nearest ``n_arc`` values divisible by *divisor*."""
    lo = n_arc // divisor * divisor
    near = [n for n in (lo, lo + divisor) if n > 0]
    return " or ".join(f"n_arc={n}" for n in near) + f" (a multiple of {divisor})"


def _check_layer_name(name) -> None:
    """Layer names become group names (``fluid_inlet``,
    ``interface_fluid_steel``), so keep them to ``[A-Za-z0-9_]``."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SpecError(f"layer name {name!r} must be letters, digits and _ only "
                         "(it becomes part of physical group names)",
                        code="layer_name_invalid", where={"field": "name"}, value=name,
                        hint=(f"e.g. {re.sub(r'[^A-Za-z0-9_]', '_', name)!r}"
                              if isinstance(name, str) and name else None))


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


def _wall_progression(radial_grading: float | None, thickness: float, n_radial: int,
                      first_cell: float) -> float:
    """``radial_grading`` giving a cell of *first_cell* at the outer end of a layer.

    Radial curves run inner → outer and ``radial_grading`` grows cells outward, so a
    small wall cell needs the reciprocal of the first-cell ratio.
    """
    if radial_grading is not None:
        raise SpecTypeError("pass either radial_grading= or first_cell=, not both",
                            code="grading_args_conflict", hint="pass radial_grading= or first_cell=")
    return 1.0 / progression_for_first_cell(thickness, n_radial, first_cell)


#: the saved section kind (decision 0053): a core with layers around it.
#: Decision 0035 stage B adds others (pipe-in-pipe, multi-core).
SECTION_KIND = "concentric"

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
    n_radial : int
        Number of mesh node layers across the thickness.
    radial_grading : float
        Transfinite progression factor for the radial lines (>1 refines
        toward the inner boundary, <1 toward the outer).
    outer : Shape or None
        The layer's own outline (``CircleShape`` or ``RectShape``).
    """

    name: str
    _: KW_ONLY
    dR:   float | None
    n_radial: int
    radial_grading: float = 1.0
    outer: Shape | None = None

    def __post_init__(self) -> None:
        if (self.dR is None) == (self.outer is None):
            raise SpecError(f"shell `{self.name}`: give exactly one of dR and outer",
                            code="shell_outline_args", where={"label": self.name},
                            hint="dR= for a shell of even thickness, or outer= (a shape) for "
                                 "its own outline")
        if self.dR is not None and self.dR <= 0:
            raise SpecError(f"LayerSpec.dR must be positive, got {self.dR!r}",
                            code="size_not_positive", where={"label": self.name, "field": "dR"},
                            value=self.dR, limit={"min_exclusive": 0})
        if self.n_radial is None or self.n_radial < 1:
            raise SpecError(f"LayerSpec.n_radial must be >= 1, got {self.n_radial!r}",
                            code="count_below_minimum",
                            where={"label": self.name, "field": "n_radial"}, value=self.n_radial,
                            limit={"min": 1})

    def outline(self, inner: Shape) -> Shape:
        """This layer's outline, around *inner* (the previous one)."""
        return self.outer if self.outer is not None else inner.grown(self.dR)


class PipeSpec:
    """Builder for a concentric-layer pipe cross-section.

    Parameters
    ----------
    n_arc : int, optional
        Angular divisions per quadrant arc.  Required for circular cores
        and all shells.  Shared across the entire stack.
    n_width : int, optional
        Angular divisions along width edges.  Required for rectangular cores.
    n_height : int, optional
        Angular divisions along height edges.  Required for rectangular cores.
    arc_bump : float
        Angular bump factor for Transfinite Line.  Default 1.0 (uniform).
    rot : float
        Rotation offset in degrees applied to the OH grid corner angles,
        like every other angle (decision 0024).  Use ``rot=-45`` to align
        patch boundaries with horizontal/vertical axes (e.g. for
        half-buried pipes).  Default 0.0.

    Examples
    --------
    Circular insulated pipe (shorthand — no repeated n_arc)::

        pipe = (
            PipeSpec(n_arc=5)
            .core("fluid",       radius=0.3,  n_radial=5)
            .shell("pipe_wall",  dR=0.05, n_radial=3)
            .shell("insulation", dR=0.10, n_radial=4)
        )

    Rectangular duct (shorthand; an H face, walls graded, since 0.4.0)::

        duct = (
            PipeSpec(n_width=6, n_height=6)
            .core("air", half_w=0.2, half_h=0.1, first_cell=0.02)
            .shell("duct_wall", dR=0.01, n_radial=3)
        )

    Circular conductor in a square insulation block (decision 0026)::

        bar = (
            PipeSpec(n_arc=4)
            .core("copper", radius=0.01, n_radial=4)
            .shell("insulation", outer=RectShape(0.02, 0.02, n_width=4, n_height=4), n_radial=3)
        )
    """

    #: the section kind it saves (decision 0053; decision 0035 stage B adds others)
    KIND = SECTION_KIND

    #: the constructor's arguments (task 0095): saved as they are
    PARAMS = {
        "n_arc": describe("cells", "divisions per quadrant arc; circles and shells",
                         minimum=1),
        "n_width": describe("cells", "divisions along width edges; rectangular cores",
                           minimum=1),
        "n_height": describe("cells", "divisions along height edges; rectangular cores",
                           minimum=1),
        "arc_bump": describe("1", "angular bump factor of the transfinite arcs (1 = uniform)",
                         exclusiveMinimum=0),
        "rot": describe("deg", "rotation of the outer corner frame (decision 0024)"),
        "n_outer": describe("1", "outer structural corners: a positive multiple of 4",
                            minimum=4),
    }

    def __init__(
        self,
        *, n_arc:    int | None = None,
        n_width:  int | None = None,
        n_height:  int | None = None,
        arc_bump:    float = 1.0,
        rot:     float = 0.0,
        n_outer: int   = 4,
    ) -> None:
        if n_outer < 4 or n_outer % 4 != 0:
            raise SpecError(
                f"PipeSpec n_outer must be a positive multiple of 4, got {n_outer!r}.",
                code="n_outer_invalid", where={"field": "n_outer"}, value=n_outer,
                limit="a positive multiple of 4", hint="use n_outer=4, the default")
        if not arc_bump > 0:
            raise SpecError(f"PipeSpec arc_bump must be positive, got {arc_bump!r}.",
                            code="value_not_positive", where={"field": "arc_bump"}, value=arc_bump,
                            limit={"min_exclusive": 0})
        self._n_outer = n_outer
        self._n_arc   = n_arc
        self._n_width = n_width
        self._n_height = n_height
        self._arc_bump   = arc_bump
        self._rot    = float(rot)    # degrees
        self._core:   tuple[str, Shape] | None = None
        self._shells: list[LayerSpec] = []
        self._layout = "oh"
        self._core_wall_bump: tuple[float, float] | None = None   # an H core's (c_w, c_h)
        # Validate n_arc / n_outer constraint if n_arc is already known at init time.
        if n_arc is not None:
            divisor = n_outer // 4
            if n_arc % divisor != 0:
                raise SpecError(
                    f"PipeSpec n_arc={n_arc} must be divisible by n_outer//4={divisor} "
                    f"(n_outer={n_outer}).",
                    code="n_arc_not_divisible", where={"field": "n_arc"}, value=n_arc,
                    limit={"multiple_of": divisor}, hint=_n_arc_hint(n_arc, divisor))

    # ------------------------------------------------------------------
    # Builder methods: each returns a new spec and leaves its own
    # unchanged (copy-on-write, decision 0053), so a spec is safe to share
    # ------------------------------------------------------------------

    def _copy(self) -> "PipeSpec":
        out = copy.copy(self)
        out._shells = list(self._shells)
        return out

    #: :meth:`core`'s arguments (task 0095).  ``name``, ``shape``,
    #: ``layout``, ``n_radial``, ``radial_grading`` and ``wall_bump`` are saved; the
    #: others are inputs, resolved into those.
    CORE_PARAMS = {
        "name": describe("-", "material label of the core"),
        "shape": describe("-", "the core outline: a circle or a rectangle"),
        "n_radial": describe("cells", "O-H radial cells, inner square to wall (0 on an H core)",
                         minimum=0),
        "radial_grading": describe("1", "radial progression (> 1 refines inward); H: wall growth ratio",
                         exclusiveMinimum=0),
        "radius": describe("length", "input: a circular core's radius", exclusiveMinimum=0),
        "half_w": describe("length", "input: a rectangular core's half-width",
                           exclusiveMinimum=0),
        "half_h": describe("length", "input: a rectangular core's half-height",
                           exclusiveMinimum=0),
        "first_cell": describe("length", "input: the wall cell height; resolves to radial_grading or "
                               "wall_bump", exclusiveMinimum=0),
        "layout": describe("-", "section layout (decision 0036)", enum=sorted(LAYOUTS)),
        "wall_bump": describe("1", "an H core's Bump coefficients (c_w, c_h); < 1 refines "
                              "toward the walls", exclusiveMinimum=0),
    }

    def core(
        self,
        name:   str,
        *, shape:  Shape | None = None,
        n_radial:   int = 0,
        radial_grading:   float | None = None,
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

        - Circular core: pass ``radius=<float>`` — requires ``PipeSpec(n_arc=…)``
        - Rectangular core: pass ``half_w=<float>, half_h=<float>`` —
          requires ``PipeSpec(n_width=…, n_height=…)``

        Both forms are equivalent::

            # explicit shape (old form — still valid):
            PipeSpec(n_arc=5).core("fluid", shape=CircleShape(0.3, n_arc=5), n_radial=4)

            # shorthand (no repeated n_arc):
            PipeSpec(n_arc=5).core("fluid", radius=0.3, n_radial=4)

        Parameters
        ----------
        name : str
            Material label for the core region.
        shape : Shape, optional
            ``CircleShape`` or ``RectShape`` describing the
            core outer boundary.  Mutually exclusive with ``radius`` /
            ``half_w`` / ``half_h``.
        n_radial : int
            Radial mesh layers (from inner square to outer boundary).
        radial_grading : float
            Radial progression factor (default 1, uniform; > 1 refines
            toward the inner square, < 1 toward the outer wall).
        radius : float, optional
            Radius of a circular core.  Requires ``n_arc`` to be set on the
            ``PipeSpec``.  Mutually exclusive with ``shape``.
        half_w : float, optional
            Half-width of a rectangular core.  Must be paired with
            ``half_h``.  Requires ``n_width`` and ``n_height`` to be set.
            Mutually exclusive with ``shape`` and ``radius``.
        half_h : float, optional
            Half-height of a rectangular core.  See ``half_w``.
        first_cell : float, optional
            Largest radial height of a cell at the core's outer wall (the
            circle); sets ``radial_grading`` (< 1).  The core ring is thickest at
            mid-arc (``core_wall_span``), where the wall cell equals
            *first_cell*; at the corners it is about 0.81 of it.  Circular,
            ``n_outer`` 4 or 8 cores only (8 is the 4-corner mesh, cut;
            task 0088); mutually exclusive with ``radial_grading``
            (docs/tasks/0002).  On an H core: the end cell of every side,
            at all four walls, resolved here to ``wall_bump`` (task 0084).
        layout : str, optional
            The section layout (decision 0036): ``"h"``, one Cartesian
            patch, the default for a rectangular core (since 0.4.0, task
            0087); or ``"oh"``, the 5-patch O-H face, the default for a
            circle and the opt-in for a rectangle.  An H
            core has no ring, so no ``n_radial``; ``radial_grading`` is then the wall
            growth ratio, the second cell from each wall over the first
            (> 1 refines toward the walls), and ``first_cell`` its end
            cell.  Both resolve here to ``wall_bump``.
        wall_bump : (float, float), optional
            An H core's ``Bump`` coefficients, ``(c_w, c_h)``: the sides
            of ``n_width`` and of ``n_height`` divisions (< 1 refines toward
            both walls; gmsh's two-sided law).  What ``first_cell=``
            resolves to, and what ``to_dict`` stores, as O-H stores
            ``radial_grading``: a k× refinement keeps them, so its nodes nest.
            ``first_cell=`` and ``radial_grading=`` resolve to it.
        """
        self = self._copy()                  # copy-on-write (decision 0053)
        if self._core is not None:
            raise SpecUsageError("PipeSpec.core() may only be called once.", code="spec_core_twice",
                                 hint="add further layers with .shell(); start a new PipeSpec "
                                      "for another core")
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
                if self._n_arc is None:
                    raise SpecTypeError(
                        "PipeSpec.core(radius=…) requires n_arc to be set on "
                        "the PipeSpec, e.g. PipeSpec(n_arc=5).core(…, radius=0.3)."
                    , code="n_arc_missing", where={"field": "n_arc"})
                shape = CircleShape(radius=radius, n_arc=self._n_arc)
            else:
                # Rectangular shorthand
                if half_w is None or half_h is None:
                    raise SpecTypeError(
                        "PipeSpec.core(): half_w and half_h must both be "
                        "provided for a rectangular core."
                    , code="shape_args_missing")
                if self._n_width is None or self._n_height is None:
                    raise SpecTypeError(
                        "PipeSpec.core(half_w=…, half_h=…) requires n_width "
                        "and n_height to be set on the PipeSpec, e.g. "
                        "PipeSpec(n_width=6, n_height=4).core(…, half_w=0.2, half_h=0.1)."
                    , code="n_arc_missing", where={"field": "n_width"})
                shape = RectShape(
                    half_w=half_w, half_h=half_h,
                    n_width=self._n_width, n_height=self._n_height,
                )

        self._validate_shape_n_arc(shape)
        default = layout is None
        if default:                    # H for a rectangle (0.4.0, decision 0036 item 1)
            layout = "oh" if shape.is_round or shape.is_station else "h"
        if layout == "h":
            if n_radial:
                how = ("a rectangular core is H by default since 0.4.0" if default
                       else "an H core")
                raise SpecError(
                    f"n_radial={n_radial!r} on {how}: it has no ring, so its "
                    "near-wall cells come from wall grading.  Drop n_radial and grade "
                    "the walls (first_cell= or radial_grading=), or pass layout='oh' to keep "
                    "the O-H face (decision 0036)",
                    code="n_radial_on_h_core", where={"label": name, "field": "n_radial"},
                    value=n_radial,
                    hint="drop n_radial and grade the walls (first_cell= or radial_grading=), "
                         "or pass layout='oh'")
        elif n_radial < 1:
            raise SpecError(f"n_radial must be >= 1, got {n_radial!r}",
                            code="count_below_minimum", where={"label": name, "field": "n_radial"},
                            value=n_radial, limit={"min": 1})
        if layout == "h":
            if shape.is_round or shape.is_station:
                raise SpecError(f"layout='h' needs a rectangular core, got a {shape.label}",
                                code="h_layout_needs_rectangle",
                                where={"label": name, "field": "layout"},
                                hint=f"a {shape.label} takes layout='oh', the default")
            if self._n_outer != 4:
                raise SpecError("layout='h' needs n_outer = 4",
                                code="h_layout_needs_n_outer_4",
                                where={"label": name, "field": "n_outer"}, value=self._n_outer,
                                limit=4, hint="use PipeSpec(n_outer=4)")
            if sum(x is not None for x in (radial_grading, first_cell, wall_bump)) > 1:
                raise SpecTypeError("pass one of radial_grading=, first_cell= or wall_bump=",
                                    code="grading_args_conflict", where={"label": name})
            if first_cell is not None:             # each side's coefficient
                wall_bump = tuple(
                    bump_for_first_cell(math.dist(shape.corner(k), shape.corner(k + 1)),
                                        shape.side_count(k, 4), first_cell)
                    for k in (0, 1))
            elif radial_grading is not None and radial_grading != 1.0:   # a wall ratio, per side
                wall_bump = tuple(bump_for_ratio(shape.side_count(k, 4), radial_grading) for k in (0, 1))
            radial_grading = None                            # the grading is wall_bump, or uniform
            if wall_bump is not None:
                wall_bump = tuple(float(c) for c in wall_bump)
                if len(wall_bump) != 2 or not all(c > 0 for c in wall_bump):
                    raise SpecError(f"wall_bump must be two positive coefficients, "
                                     f"got {wall_bump!r}",
                                    code="wall_bump_invalid",
                                    where={"label": name, "field": "wall_bump"}, value=wall_bump)
            self._layout = "h"
            self._core_wall_bump = wall_bump
            first_cell = None                      # the wall grading, not radial_grading
        elif wall_bump is not None:
            raise SpecTypeError("wall_bump= is an H core's grading (layout='h')",
                                code="wall_bump_needs_h_layout",
                                where={"label": name, "field": "wall_bump"},
                                hint="pass layout='h' with it, or grade an O-H core with radial_grading= "
                                     "or first_cell=")
        if first_cell is not None:
            if not shape.is_round:
                raise SpecTypeError("first_cell= supports circular cores only",
                                    code="first_cell_unsupported",
                                    where={"label": name, "field": "first_cell"})
            if self._n_outer not in (4, 8):
                raise SpecTypeError("first_cell= supports n_outer=4 or 8 cores only",
                                    code="first_cell_unsupported",
                                    where={"label": name, "field": "first_cell"})
            # Solved on the thickest span (mid-arc), so first_cell is the
            # largest wall cell; at the corners it is 0.4/0.491 ≈ 0.81 of it.
            radial_grading = _wall_progression(radial_grading, core_wall_span(shape.max_extent),
                                     n_radial, first_cell)
        _check_layer_name(name)
        self._core = (name, shape)
        # Store core n_radial/radial_grading as a pseudo-LayerSpec for uniform iteration
        self._core_n_radial = n_radial
        self._core_radial_grading = 1.0 if radial_grading is None else radial_grading
        return self

    #: :meth:`shell`'s arguments (task 0095).  ``first_cell`` is an
    #: input, resolved into ``radial_grading``; the others are saved.
    SHELL_PARAMS = {
        "name": describe("-", "material label of the shell"),
        "dR": describe("length", "thickness: the previous outline grown by dR (or outer)",
                       exclusiveMinimum=0, limit="OUTLINE_MIN_GAP"),
        "n_radial": describe("cells", "radial cells across the shell", minimum=1),
        "radial_grading": describe("1", "radial progression (> 1 refines toward the inner boundary)",
                         exclusiveMinimum=0),
        "outer": describe("-", "the shell's outline, instead of dR",
                          limit=("OUTLINE_MIN_GAP", "OUTLINE_NONORTH_WARN",
                                 "OUTLINE_NONORTH_MAX")),
        "first_cell": describe("length", "input: the outer-boundary cell height; resolves to "
                               "radial_grading", exclusiveMinimum=0),
    }

    def shell(
        self,
        name: str,
        *, dR:   float | None = None,
        n_radial: int | None = None,
        radial_grading: float | None = None,
        outer: Shape | None = None,
        first_cell: float | None = None,
    ) -> "PipeSpec":
        """Add a shell: the region between the previous outline and this
        layer's (decision 0026).

        Give exactly one of *dR* (the previous outline grown by *dR*) and
        *outer* (a new outline, ``CircleShape`` or ``RectShape``).  In a
        stack of rectangles every outline takes the core's ``(n_width,
        n_height)``, which may differ (decision 0041, option B).  A stack
        with a rectangle and a circle has equal counts on every side of
        every outline (``n_arc = n_width = n_height``): a circle carries one
        count.  Any stack with a rectangle has ``n_outer`` 4 or 8 (8 cuts
        the 4-corner face, task 0088).  Checked here.
        That each outline lies inside the next is checked by the
        assembly's validation.

        Parameters
        ----------
        name : str
            Material label.
        dR : float, optional
            Thickness of this layer.
        n_radial : int
            Radial mesh divisions across the layer.
        radial_grading : float
            Radial progression factor (default 1, uniform; > 1 refines
            toward the inner boundary, < 1 toward the outer).
        outer : CircleShape or RectShape, optional
            This layer's outline.
        first_cell : float, optional
            Largest radial height of a cell at the layer's outer boundary;
            sets ``radial_grading`` (< 1).  Solved on the ring's longest radial, so no
            wall cell exceeds it: every radial of a circle grown by ``dR``
            (exact all round); the corner lines of a rectangle grown by
            ``dR`` (``√2·dR``); for a shell that changes shape, the longest
            line between corresponding points of the two outlines.
            Mutually exclusive with ``radial_grading``.
        """
        self = self._copy()                  # copy-on-write (decision 0053)
        if self._core is None:
            raise SpecUsageError("Call PipeSpec.core() before .shell().",
                                 code="spec_shell_before_core",
                                 hint="PipeSpec(n_arc=…).core(name, shape, n_radial=…).shell(…)")
        if n_radial is None:
            raise SpecTypeError(f"shell `{name}`: n_radial is required",
                                code="shell_n_radial_missing", where={"label": name, "field": "n_radial"},
                                hint="pass n_radial=, the cells across the shell (e.g. n_radial=2)")
        _check_layer_name(name)
        layer = LayerSpec(name=name, dR=dR, n_radial=n_radial, radial_grading=1.0, outer=outer)
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
            radial_grading = _wall_progression(radial_grading, span, n_radial, first_cell)
        self._shells.append(LayerSpec(name=name, dR=dR, n_radial=n_radial,
                                      radial_grading=1.0 if radial_grading is None else radial_grading, outer=outer))
        return self

    def _check_arc_counts(self, names, outlines) -> None:
        """A stack with a circle of unequal arcs (task 0147): every outline
        has the core's count on each side, ``(a, b, a, b)``."""
        want = tuple(outlines[0].side_count(k, 4) for k in range(4))
        for lname, o in zip(names, outlines):
            have = tuple(o.side_count(k, 4) for k in range(4))
            if have != want:
                raise SpecError(
                    f"layer `{lname}`: a stack with a circle of unequal arcs takes the core's "
                    f"count on every side, {list(want)} (corner k → k + 1, NE→NW first); "
                    f"`{lname}` has {list(have)}",
                    code="counts_mismatch", where={"label": lname}, value=list(have),
                    limit=list(want),
                    hint=f"give a circle arcs={list(want)}, a rectangle n_width={want[0]}, "
                         f"n_height={want[1]}")

    def with_radii(self, radii: list[float], radial_gradings: list[float] | None = None) -> "PipeSpec":
        """This spec with core radius ``radii[0]`` and shell thicknesses
        ``radii[1:]``, and, if given, radial gradings *radial_gradings* (core first).
        Circular stacks of ``dR`` shells only."""
        name, shape = self._core
        if any(sh.dR is None for sh in self.shells):
            raise SpecError("PipeSpec.with_radii needs dR shells",
                            code="with_radii_needs_dr_shells")
        if radial_gradings is None:
            radial_gradings = [self._core_radial_grading] + [sh.radial_grading for sh in self.shells]
        out = (PipeSpec(n_arc=self.n_arc, n_width=self.n_width, n_height=self.n_height,
                        n_outer=self.n_outer, rot=self.rot, arc_bump=self.arc_bump)
               .core(name, shape=shape.resized(radii[0]),
                     n_radial=self._core_n_radial, radial_grading=radial_gradings[0]))
        for sh, dR, m in zip(self.shells, radii[1:], radial_gradings[1:]):
            out = out.shell(sh.name, dR=dR, n_radial=sh.n_radial, radial_grading=m)
        return out

    def _check_counts(self, name: str, outline: Shape) -> None:
        """The counts through a stack with a rectangle (decision 0026 item
        3, as amended by decision 0041): every outline the core's
        ``(n_width, n_height)`` in a stack of rectangles; equal counts per
        side once a circle is in it, since a circle carries one count."""
        outlines = self.outlines + [outline]
        names = self.layer_names + [name]
        if any(getattr(o, "arcs", None) is not None for o in outlines):
            self._check_arc_counts(names, outlines)
            return
        if all(type(o).side_curve == "arc" for o in outlines):
            return                              # circles: n_arc already shared
        if self._n_outer not in (4, 8):     # 8: the 4-corner face, cut (task 0088)
            raise SpecError(f"shell `{name}`: a stack with a rectangular outline "
                             f"needs n_outer = 4 or 8, got {self._n_outer}",
                            code="rect_stack_needs_n_outer_4",
                            where={"label": name, "field": "n_outer"}, value=self._n_outer,
                            limit=4, hint="use PipeSpec(n_outer=4)")
        core = outlines[0].counts
        if all(type(o).side_curve != "arc" for o in outlines):
            for lname, o in zip(names, outlines):
                if o.counts != core:
                    raise SpecError(
                        f"shell `{name}`: every outline in a stack of rectangles takes "
                        f"the core's counts; layer `{lname}` has {o.counts} "
                        f"(n_width, n_height), the core {core}",
                        code="rect_stack_counts_unequal", where={"label": name},
                        value=o.counts, limit=core,
                        hint=f"give layer `{lname}` n_width={core[0]}, n_height={core[1]}")
            return
        want = core[0]
        for lname, o in zip(names, outlines):
            if o.counts != (want, want):
                raise SpecError(
                    f"shell `{name}`: a stack with a rectangle and a circle needs equal "
                    f"counts per side, since a circle carries one count (decision "
                    f"0041); layer `{lname}` has {o.counts} (n_width, n_height), the core "
                    f"{want} per side",
                    code="rect_stack_counts_unequal", where={"label": name},
                    value=o.counts, limit=(want, want),
                    hint=f"give layer `{lname}` n_width={want}, n_height={want}")

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
            raise SpecUsageError("PipeSpec has no core defined.", code="spec_no_core",
                                 hint="call .core(name, shape, n_radial=…) first")
        return self._core[1]

    @property
    def shells(self) -> list[LayerSpec]:
        return list(self._shells)

    @property
    def outlines(self) -> list[Shape]:
        """Every layer's outline, core first (decision 0026)."""
        if self._core is None:
            raise SpecUsageError("PipeSpec has no core defined.", code="spec_no_core",
                                 hint="call .core(name, shape, n_radial=…) first")
        out = [self._core[1]]
        for sh in self._shells:
            out.append(sh.outline(out[-1]))
        return out

    def corners(self) -> list[list]:
        """Corner points ``(u, v)`` of every layer's outer boundary, before
        ``rot``: the core's O-H corners, then each ring's (its corner lines
        run from the previous layer's corners; ``ring_corners``).  The four
        structural corners for every ``n_outer``: a partitioned face only
        cuts between them (decision 0005, task 0088)."""
        outlines = self.outlines
        out = [[outlines[0].corner(k) for k in range(4)]]
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
        (uniform); ``None`` on an O-H core, whose grading is ``radial_grading``."""
        if self._layout != "h" or self._core_wall_bump is None:
            return None
        return ("bump", self._core_wall_bump)

    @property
    def n_arc(self) -> int | None:
        return self._n_arc

    @property
    def n_width(self) -> int | None:
        return self._n_width

    @property
    def n_height(self) -> int | None:
        return self._n_height

    @property
    def arc_bump(self) -> float:
        return self._arc_bump

    @property
    def rot(self) -> float:
        """Corner-frame rotation in degrees."""
        return self._rot

    @property
    def rot_rad(self) -> float:
        """Deprecated (task 0150): ``math.radians(spec.rot)``.  Public
        members are in degrees (decision 0047)."""
        warnings.warn("PipeSpec.rot_rad is deprecated: use math.radians(spec.rot); "
                      "public members are in degrees", DeprecationWarning, stacklevel=2)
        return math.radians(self._rot)

    @property
    def side_counts(self) -> tuple[int, ...]:
        """Divisions of each outer curve of the core, corner *k* → *k* + 1
        (NE→NW first): ``n_arc // (n_outer // 4)`` per arc of a circle;
        ``(n_width, n_height, n_width, n_height)`` for a rectangle."""
        shape = self.core_shape
        return tuple(shape.side_count(k, self._n_outer) for k in range(self._n_outer))

    @property
    def period_deg(self) -> float:
        """Geometric symmetry period P in degrees: the smallest roll that
        maps the section onto itself (DESIGN §6.1, decision 0010).
        90 for a circle and a square, for every ``n_outer`` (decision
        0010 as amended: a partition doesn't change the mesh), 180 for any
        other rectangle; for a stack, the largest over its outlines."""
        return math.degrees(max(o.period(self._n_outer) for o in self.outlines))

    @property
    def period(self) -> float:
        """Deprecated (task 0150): P in radians; use :attr:`period_deg`."""
        warnings.warn("PipeSpec.period (radians) is deprecated: use PipeSpec.period_deg",
                      DeprecationWarning, stacklevel=2)
        return math.radians(self.period_deg)

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

    def _check_arcs(self, arcs: tuple) -> None:
        """What today's layouts mesh of a circle's arcs (decision 0041's note
        of 2026-11-13): opposite arcs equal, on ``n_outer = 4``."""
        if arcs[0] != arcs[2] or arcs[1] != arcs[3]:
            raise SpecError(
                f"a circle's opposite arcs must have equal counts, got arcs={list(arcs)}: "
                f"the O-H and H layouts mesh (a, b, a, b) only",
                code="arc_counts_not_opposite", where={"field": "arcs"}, value=list(arcs),
                limit="arcs[0] == arcs[2] and arcs[1] == arcs[3]",
                hint=f"use arcs=[{arcs[0]}, {arcs[1]}, {arcs[0]}, {arcs[1]}]")
        if self._n_arc is not None:
            raise SpecError(
                f"PipeSpec(n_arc={self._n_arc}) and a circle with arcs={list(arcs)}: the arcs "
                f"set the spec's n_width and n_height", code="shape_counts_mismatch",
                where={"field": "n_arc"}, value=self._n_arc, limit=None,
                hint=f"leave out the PipeSpec's n_arc, or give n_width={arcs[0]}, "
                     f"n_height={arcs[1]}")
        if self._n_outer != 4:
            raise SpecError(
                f"a circle with unequal arc counts needs n_outer = 4, got {self._n_outer}",
                code="arc_counts_need_n_outer_4", where={"field": "n_outer"},
                value=self._n_outer, limit=4, hint="use PipeSpec(n_outer=4), the default")

    def _validate_shape_n_arc(self, shape: Shape) -> None:
        """Check that shape angular divisions match PipeSpec-level values.
        A ``Transition`` station's come from its two ends, checked there."""
        if shape.is_station:
            return
        arcs = getattr(shape, "arcs", None)
        if arcs is not None:
            self._check_arcs(arcs)
        counts = shape.angular_counts
        for name, n in counts.items():
            mine = getattr(self, f"_{name}")
            if mine is not None and n != mine:
                raise SpecError(
                    f"{type(shape).__name__}.{name}={n} does not match "
                    f"PipeSpec({name}={mine})."
                , code="shape_counts_mismatch", where={"field": name}, value=n, limit=mine,
                hint=f"give the shape {name}={mine}, or leave the PipeSpec's {name} unset")
        for name, n in counts.items():
            if getattr(self, f"_{name}") is None:
                setattr(self, f"_{name}", n)
        if "n_arc" in counts:
            # Enforce n_arc % (n_outer // 4) == 0 once n_arc is resolved.
            divisor = self._n_outer // 4
            if self._n_arc % divisor != 0:
                raise SpecError(
                    f"PipeSpec n_arc={self._n_arc} must be divisible by "
                    f"n_outer//4={divisor} (n_outer={self._n_outer}).",
                    code="n_arc_not_divisible", where={"field": "n_arc"},
                    value=self._n_arc, limit={"multiple_of": divisor},
                    hint=_n_arc_hint(self._n_arc, divisor))

    # ------------------------------------------------------------------
    # Serialisation (docs/tasks/0006)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Plain JSON-serialisable description of this spec.

        Lengths are stored in the user's unit, unconverted.  ``radial_grading`` is
        stored as resolved, so a spec built with ``first_cell=`` reloads
        with the same progression.
        """
        if self._core is None:
            raise SpecUsageError("PipeSpec has no core defined.", code="spec_no_core",
                                 hint="call .core(name, shape, n_radial=…) first")
        name, shape = self._core
        if not hasattr(shape, "to_dict"):
            raise SpecTypeError(f"cannot serialise core shape {type(shape).__name__}",
                                code="shape_not_serialisable")
        shape_d = shape.to_dict()
        shells = []
        for sh in self._shells:
            if sh.outer is None:
                shells.append({"type": "shell", "name": sh.name, "dR": sh.dR,
                               "n_radial": sh.n_radial, "radial_grading": sh.radial_grading})
            else:
                shells.append({"type": "shell", "name": sh.name,
                               "outer": sh.outer.to_dict(),
                               "n_radial": sh.n_radial, "radial_grading": sh.radial_grading})
        return {
            "kind": SECTION_KIND,
            "n_arc": self._n_arc, "n_width": self._n_width, "n_height": self._n_height,
            "arc_bump": self._arc_bump, "rot": self._rot, "n_outer": self._n_outer,
            "core": {"name": name, "shape": shape_d, "layout": self._layout,
                     "n_radial": self._core_n_radial, "radial_grading": self._core_radial_grading,
                     **({"wall_bump": list(self._core_wall_bump)}
                        if self._core_wall_bump is not None else {})},
            "shells": shells,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipeSpec":
        """Rebuild a spec from :meth:`to_dict` output."""
        kind = d.get("kind", SECTION_KIND)      # saved before decision 0053: concentric
        if kind != SECTION_KIND:
            raise SpecError(f"section kind {kind!r} is not supported; hexmesh meshes "
                            f"{SECTION_KIND!r} sections (layers around one core).  Other kinds "
                            f"come with decision 0035 stage B",
                            code="section_kind_unsupported", where={"field": "kind"},
                            value=kind, limit=[SECTION_KIND])
        spec = cls(n_arc=d.get("n_arc"), n_width=d.get("n_width"), n_height=d.get("n_height"),
                   arc_bump=d.get("arc_bump", 1.0), rot=d.get("rot", 0.0),
                   n_outer=d.get("n_outer", 4))
        core = d["core"]
        shape = shape_from_dict(core["shape"])
        layout = core.get("layout", "oh")       # saved before task 0084: O-H
        if layout == "h":
            wb = core.get("wall_bump")
            # an H ratio saved as radial_grading (e0e88dc) resolves to wall_bump here
            spec = spec.core(core["name"], shape=shape, layout="h",
                             wall_bump=None if wb is None else tuple(wb),
                             radial_grading=None if wb is not None else core.get("radial_grading", 1.0))
        else:
            spec = spec.core(core["name"], shape=shape, n_radial=core["n_radial"],
                             radial_grading=core.get("radial_grading", 1.0), layout="oh")
        for sh in d.get("shells", []):
            sh = dict(sh)
            kind = sh.pop("type")
            if kind == "square_shell":          # removed (decision 0026): same ring
                n = spec.n_arc
                sh = {"name": sh["name"], "n_radial": sh["n_radial"], "radial_grading": sh.get("radial_grading", 1.0),
                      "outer": {"type": "rect", "half_w": sh["half_w"],
                                "half_h": sh["half_h"], "n_width": n, "n_height": n}}
            elif kind != "shell":
                raise SpecError(f"unknown shell type {kind!r}",
                                code="shell_type_unknown", value=kind)
            if "outer" in sh:
                sh["outer"] = shape_from_dict(sh["outer"])
            spec = spec.shell(**sh)
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
    _: KW_ONLY
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
