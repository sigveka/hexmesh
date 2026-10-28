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

from .grading import progression_for_first_cell
from .shape import (CircleShape, RectShape, Shape, longest_radial, oh_core_wall_span,
                    ring_corners, shape_from_dict)
from .region import MaterialGraph

if TYPE_CHECKING:
    pass


def _check_layer_name(name) -> None:
    """Layer names become group names (``fluid_inlet``,
    ``interface_fluid_steel``), so keep them to ``[A-Za-z0-9_]``."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"layer name {name!r} must be letters, digits and _ only "
                         "(it becomes part of physical group names)")


def _wall_progression(mprg: float | None, thickness: float, nrad: int,
                      first_cell: float) -> float:
    """``mprg`` giving a cell of *first_cell* at the outer end of a layer.

    Radial curves run inner → outer and ``mprg`` grows cells outward, so a
    small wall cell needs the reciprocal of the first-cell ratio.
    """
    if mprg is not None:
        raise TypeError("pass either mprg= or first_cell=, not both")
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
            raise ValueError(f"shell `{self.name}`: give exactly one of dR and outer")
        if self.dR is not None and self.dR <= 0:
            raise ValueError(f"LayerSpec.dR must be positive, got {self.dR!r}")
        if self.nrad is None or self.nrad < 1:
            raise ValueError(f"LayerSpec.nrad must be >= 1, got {self.nrad!r}")

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

    Rectangular duct (shorthand)::

        duct = (
            PipeSpec(nang_w=6, nang_h=4)
            .core("air", half_w=0.2, half_h=0.1, nrad=5)
            .shell("duct_wall", dR=0.01, nrad=3)
        )

    Circular conductor in a square insulation block (decision 0026)::

        bar = (
            PipeSpec(nang=4)
            .core("copper", radius=0.01, nrad=4)
            .shell("insulation", outer=RectShape(0.02, 0.02, 4, 4), nrad=3)
        )
    """

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
            raise ValueError(
                f"PipeSpec n_outer must be a positive multiple of 4, got {n_outer!r}."
            )
        self._n_outer = n_outer
        self._nang   = nang
        self._nang_w = nang_w
        self._nang_h = nang_h
        self._mbmp   = mbmp
        self._rot    = float(rot)    # degrees
        self._core:   tuple[str, Shape] | None = None
        self._shells: list[LayerSpec] = []
        # Validate nang / n_outer constraint if nang is already known at init time.
        if nang is not None:
            divisor = n_outer // 4
            if nang % divisor != 0:
                raise ValueError(
                    f"PipeSpec nang={nang} must be divisible by n_outer//4={divisor} "
                    f"(n_outer={n_outer})."
                )

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------

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
            mid-arc (``oh_core_wall_span``), where the wall cell equals
            *first_cell*; at the corners it is about 0.81 of it.  Circular,
            ``n_outer = 4`` cores only; mutually exclusive with ``mprg``
            (docs/tasks/0002).
        """
        if self._core is not None:
            raise RuntimeError("PipeSpec.core() may only be called once.")
        if nrad < 1:
            raise ValueError(f"nrad must be >= 1, got {nrad!r}")

        # Resolve shape from shorthand geometry keywords
        geo_given = radius is not None or half_w is not None or half_h is not None
        if shape is not None and geo_given:
            raise TypeError(
                "PipeSpec.core(): pass either shape= or geometry keywords "
                "(radius / half_w / half_h), not both."
            )
        if shape is None and not geo_given:
            raise TypeError(
                "PipeSpec.core(): provide either shape= or one of the "
                "geometry keywords (radius=, half_w= + half_h=)."
            )

        if geo_given:
            if radius is not None:
                # Circular shorthand
                if half_w is not None or half_h is not None:
                    raise TypeError(
                        "PipeSpec.core(): radius and half_w/half_h are "
                        "mutually exclusive."
                    )
                if self._nang is None:
                    raise TypeError(
                        "PipeSpec.core(radius=…) requires nang to be set on "
                        "the PipeSpec, e.g. PipeSpec(nang=5).core(…, radius=0.3)."
                    )
                shape = CircleShape(radius=radius, nang=self._nang)
            else:
                # Rectangular shorthand
                if half_w is None or half_h is None:
                    raise TypeError(
                        "PipeSpec.core(): half_w and half_h must both be "
                        "provided for a rectangular core."
                    )
                if self._nang_w is None or self._nang_h is None:
                    raise TypeError(
                        "PipeSpec.core(half_w=…, half_h=…) requires nang_w "
                        "and nang_h to be set on the PipeSpec, e.g. "
                        "PipeSpec(nang_w=6, nang_h=4).core(…, half_w=0.2, half_h=0.1)."
                    )
                shape = RectShape(
                    half_w=half_w, half_h=half_h,
                    nang_w=self._nang_w, nang_h=self._nang_h,
                )

        self._validate_shape_nang(shape)
        if first_cell is not None:
            if not isinstance(shape, CircleShape):
                raise TypeError("first_cell= supports circular cores only")
            if self._n_outer != 4:
                raise TypeError("first_cell= supports n_outer=4 cores only")
            # Solved on the thickest span (mid-arc), so first_cell is the
            # largest wall cell; at the corners it is 0.4/0.491 ≈ 0.81 of it.
            mprg = _wall_progression(mprg, oh_core_wall_span(shape.radius),
                                     nrad, first_cell)
        _check_layer_name(name)
        self._core = (name, shape)
        # Store core nrad/mprg as a pseudo-LayerSpec for uniform iteration
        self._core_nrad = nrad
        self._core_mprg = 1.0 if mprg is None else mprg
        return self

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
            raise TypeError(f"shell `{name}`: nrad is required")
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

    def _check_counts(self, name: str, outline: Shape) -> None:
        """Equal counts per side through a stack with a rectangle
        (decision 0026, item 3)."""
        outlines = self.outlines + [outline]
        if all(type(o).side_curve == "arc" for o in outlines):
            return                              # circles: nang already shared
        if self._n_outer != 4:
            raise ValueError(f"shell `{name}`: a stack with a rectangular outline "
                             f"needs n_outer = 4, got {self._n_outer}")
        names = self.layer_names + [name]
        want = outlines[0].counts[0]
        for lname, o in zip(names, outlines):
            if o.counts != (want, want):
                raise ValueError(
                    f"shell `{name}`: every outline in a stack with a rectangle needs "
                    f"equal counts per side; layer `{lname}` has {o.counts} "
                    f"(nang_w, nang_h), the core {want} per side")

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
        if isinstance(shape, CircleShape):
            return (shape.nang // (self._n_outer // 4),) * self._n_outer
        return (shape.nang_w, shape.nang_h) * 2

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
        """Check that shape angular divisions match PipeSpec-level values."""
        if isinstance(shape, CircleShape):
            if self._nang is not None and shape.nang != self._nang:
                raise ValueError(
                    f"CircleShape.nang={shape.nang} does not match "
                    f"PipeSpec(nang={self._nang})."
                )
            if self._nang is None:
                self._nang = shape.nang
            # Enforce nang % (n_outer // 4) == 0 once nang is resolved.
            divisor = self._n_outer // 4
            if self._nang % divisor != 0:
                raise ValueError(
                    f"PipeSpec nang={self._nang} must be divisible by "
                    f"n_outer//4={divisor} (n_outer={self._n_outer})."
                )
        elif isinstance(shape, RectShape):
            if self._nang_w is not None and shape.nang_w != self._nang_w:
                raise ValueError(
                    f"{type(shape).__name__}.nang_w={shape.nang_w} does not match "
                    f"PipeSpec(nang_w={self._nang_w})."
                )
            if self._nang_h is not None and shape.nang_h != self._nang_h:
                raise ValueError(
                    f"{type(shape).__name__}.nang_h={shape.nang_h} does not match "
                    f"PipeSpec(nang_h={self._nang_h})."
                )
            if self._nang_w is None:
                self._nang_w = shape.nang_w
            if self._nang_h is None:
                self._nang_h = shape.nang_h

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
            raise TypeError(f"cannot serialise core shape {type(shape).__name__}")
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
            "core": {"name": name, "shape": shape_d,
                     "nrad": self._core_nrad, "mprg": self._core_mprg},
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
        spec.core(core["name"], shape, nrad=core["nrad"], mprg=core.get("mprg", 1.0))
        for sh in d.get("shells", []):
            sh = dict(sh)
            kind = sh.pop("type")
            if kind == "square_shell":          # removed (decision 0026): same ring
                n = spec.nang
                sh = {"name": sh["name"], "nrad": sh["nrad"], "mprg": sh.get("mprg", 1.0),
                      "outer": {"type": "rect", "half_w": sh["half_w"],
                                "half_h": sh["half_h"], "nang_w": n, "nang_h": n}}
            elif kind != "shell":
                raise ValueError(f"unknown shell type {kind!r}")
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
            raise ValueError("BundleSpec.pipe has no shell layers defined.")
        outermost = self.pipe.outlines[-1]
        if not isinstance(outermost, RectShape):
            raise TypeError(
                "BundleSpec.pipe must end with a rectangular shell "
                f"(outer=RectShape); got {type(outermost).__name__}."
            )
        if self.nx < 1 or self.ny < 1:
            raise ValueError("nx and ny must be >= 1.")

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
