"""
Declarative pipe and bundle specifications.

LayerSpec
    Parameters for one concentric material layer (shell or annulus).
    Does NOT include the innermost core; that is described by the Shape
    passed to PipeSpec.core().

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
    must end in a square_shell layer so adjacent cells share flat faces.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .grading import progression_for_first_cell
from .shape import CircleShape, RectShape, Shape, oh_core_wall_span
from .region import MaterialGraph

if TYPE_CHECKING:
    pass


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

    Attributes
    ----------
    name : str
        Material label used for Physical groups and MaterialGraph nodes.
    dR : float
        Radial thickness of this layer.
    nrad : int
        Number of mesh node layers across the thickness.
    mprg : float
        Transfinite progression factor for the radial lines (>1 refines
        toward the inner boundary, <1 toward the outer).
    """

    name: str
    dR:   float
    nrad: int
    mprg: float = 1.0

    def __post_init__(self) -> None:
        if self.dR <= 0:
            raise ValueError(f"LayerSpec.dR must be positive, got {self.dR!r}")
        if self.nrad < 1:
            raise ValueError(f"LayerSpec.nrad must be >= 1, got {self.nrad!r}")


@dataclass(frozen=True)
class SquareShellSpec:
    """Square outer shell terminating a circular pipe stack.

    The square outer boundary allows adjacent pipe cells to share flat
    faces, enabling structured tiling in bundles.

    Attributes
    ----------
    name : str
        Material label.
    half_w : float
        Half-width  of the outer square (first  in-plane axis).
    half_h : float
        Half-height of the outer square (second in-plane axis).
        For a true square set half_h == half_w.
    nrad : int
        Radial mesh divisions from circle boundary to square boundary.
    mprg : float
        Radial progression factor.
    """

    name:   str
    half_w: float
    half_h: float
    nrad:   int
    mprg:   float = 1.0

    def __post_init__(self) -> None:
        if self.half_w <= 0 or self.half_h <= 0:
            raise ValueError("half_w and half_h must be positive.")
        if self.nrad < 1:
            raise ValueError(f"SquareShellSpec.nrad must be >= 1, got {self.nrad!r}")


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
        Rotation offset (radians) applied to the OH grid corner angles.
        Use ``rot=-π/4`` to align patch boundaries with horizontal/vertical
        axes (e.g. for half-buried pipes).  Default 0.0.

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

    Bundle cell (circular pipe ending in a square outer shell)::

        cell = (
            PipeSpec(nang=5)
            .core("fluid",      radius=0.3, nrad=5)
            .shell("pipe_wall", dR=0.05, nrad=3)
            .square_shell("shell_fluid", half_w=0.5, half_h=0.5, nrad=4)
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
        self._rot    = rot
        self._core:   tuple[str, Shape] | None = None
        self._shells: list[LayerSpec | SquareShellSpec] = []
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
        self._core = (name, shape)
        # Store core nrad/mprg as a pseudo-LayerSpec for uniform iteration
        self._core_nrad = nrad
        self._core_mprg = 1.0 if mprg is None else mprg
        return self

    def shell(
        self,
        name: str,
        dR:   float,
        nrad: int,
        mprg: float | None = None,
        *,
        first_cell: float | None = None,
    ) -> "PipeSpec":
        """Add a concentric circular shell layer.

        Only valid after a circular ``core()``.  The radial thickness is
        measured from the previous layer's outer boundary.

        Parameters
        ----------
        name : str
            Material label.
        dR : float
            Radial thickness of this layer.
        nrad : int
            Radial mesh divisions across the layer thickness.
        mprg : float
            Radial progression factor (default 1, uniform; > 1 refines
            toward the inner boundary, < 1 toward the outer).
        first_cell : float, optional
            Radial height of the cell at the layer's outer boundary; sets
            ``mprg`` (< 1).  Exact all round, since every radial is ``dR``
            long.  Mutually exclusive with ``mprg``.
        """
        if self._core is None:
            raise RuntimeError("Call PipeSpec.core() before .shell().")
        _, core_shape = self._core
        if self._shells and isinstance(self._shells[-1], SquareShellSpec):
            raise RuntimeError(
                "Cannot add a circular shell after a square_shell layer."
            )
        if first_cell is not None:
            mprg = _wall_progression(mprg, dR, nrad, first_cell)
        self._shells.append(LayerSpec(name=name, dR=dR, nrad=nrad,
                                      mprg=1.0 if mprg is None else mprg))
        return self

    def square_shell(
        self,
        name:   str,
        half_w: float,
        half_h: float,
        nrad:   int,
        mprg:   float = 1.0,
    ) -> "PipeSpec":
        """Add a square outer shell, terminating the concentric stack.

        The square shell transitions the circular outer boundary to a flat
        square, enabling tiling in bundles.  No further ``.shell()`` calls
        are permitted after this.

        Parameters
        ----------
        name : str
            Material label for the square shell region.
        half_w, half_h : float
            Half-dimensions of the outer square.  For a square pitch
            bundle set half_w == half_h == pitch / 2.
        nrad : int
            Radial mesh divisions from circle to square boundary.
        mprg : float
            Radial progression factor.
        """
        if self._core is None:
            raise RuntimeError("Call PipeSpec.core() before .square_shell().")
        _, core_shape = self._core
        if not isinstance(core_shape, CircleShape):
            raise TypeError(
                "square_shell() requires a circular core (CircleShape)."
            )
        self._shells.append(
            SquareShellSpec(
                name=name, half_w=half_w, half_h=half_h, nrad=nrad, mprg=mprg
            )
        )
        return self

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
    def shells(self) -> list[LayerSpec | SquareShellSpec]:
        return list(self._shells)

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
        return self._rot

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
        if isinstance(shape, CircleShape):
            shape_d = {"type": "circle", "radius": shape.radius, "nang": shape.nang}
        elif isinstance(shape, RectShape):
            shape_d = {"type": "rect", "half_w": shape.half_w, "half_h": shape.half_h,
                       "nang_w": shape.nang_w, "nang_h": shape.nang_h}
        else:
            raise TypeError(f"cannot serialise core shape {type(shape).__name__}")
        shells = []
        for sh in self._shells:
            if isinstance(sh, SquareShellSpec):
                shells.append({"type": "square_shell", "name": sh.name,
                               "half_w": sh.half_w, "half_h": sh.half_h,
                               "nrad": sh.nrad, "mprg": sh.mprg})
            else:
                shells.append({"type": "shell", "name": sh.name, "dR": sh.dR,
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
        sd = dict(core["shape"])
        kind = sd.pop("type")
        if kind == "circle":
            shape = CircleShape(**sd)
        elif kind == "rect":
            shape = RectShape(**sd)
        else:
            raise ValueError(f"unknown core shape type {kind!r}")
        spec.core(core["name"], shape, nrad=core["nrad"], mprg=core.get("mprg", 1.0))
        for sh in d.get("shells", []):
            sh = dict(sh)
            kind = sh.pop("type")
            if kind == "shell":
                spec.shell(**sh)
            elif kind == "square_shell":
                spec.square_shell(**sh)
            else:
                raise ValueError(f"unknown shell type {kind!r}")
        return spec

    def __repr__(self) -> str:
        return (
            f"PipeSpec(core={self._core[0] if self._core else None!r}, "
            f"layers={self.layer_names})"
        )


@dataclass
class BundleSpec:
    """Rectangular tiled array of identical pipe cells.

    Each pipe cell must end in a ``SquareShellSpec`` so adjacent cells
    share flat faces, giving a conformal interface between cells without
    any inter-tube meshing.

    Attributes
    ----------
    pipe : PipeSpec
        Specification for one pipe cell.  Must end in a square_shell.
    nx : int
        Number of cells along the first  in-plane axis.
    ny : int
        Number of cells along the second in-plane axis.
    shell_name : str
        The square_shell material label is used as the shared "shell side"
        Physical Volume name across the whole bundle.
    """

    pipe:       PipeSpec
    nx:         int
    ny:         int
    shell_name: str = "shell"

    def __post_init__(self) -> None:
        if not self.pipe.shells:
            raise ValueError("BundleSpec.pipe has no shell layers defined.")
        outermost = self.pipe.shells[-1]
        if not isinstance(outermost, SquareShellSpec):
            raise TypeError(
                "BundleSpec.pipe must end with a square_shell() layer; "
                f"got {type(outermost).__name__}."
            )
        if self.nx < 1 or self.ny < 1:
            raise ValueError("nx and ny must be >= 1.")

    @property
    def pitch_w(self) -> float:
        """Cell width  (2 × square shell half_w)."""
        outer = self.pipe.shells[-1]
        assert isinstance(outer, SquareShellSpec)
        return 2 * outer.half_w

    @property
    def pitch_h(self) -> float:
        """Cell height (2 × square shell half_h)."""
        outer = self.pipe.shells[-1]
        assert isinstance(outer, SquareShellSpec)
        return 2 * outer.half_h

    @property
    def graph(self) -> MaterialGraph:
        """MaterialGraph for the bundle (same as the pipe graph)."""
        return self.pipe.graph
