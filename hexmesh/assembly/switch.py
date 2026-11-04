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
Switch: the O-H ↔ H change on a rectangular duct (decision 0036 items 5–6,
task 0085; DESIGN A4 class 1, ``ends="pillow"``).

A rectangular O-H face is an H face with ``nrad`` ring layers pillowed in
(RESEARCH §7.11).  The switch ends those ring sheets: each closes as a cup
across the duct, open toward the O-H port (the capped construction; task
0085 step 1 measured it).

Blocks, along the axis from the O-H port (O) to the H port (H), length L
and ring thickness t (``sections.oh.ring_thickness``):

* core: O's inner rectangle → level C at L − t (the same rectangle);
* cap: C → H's whole face (a frustum, ``nrad`` cells along the axis);
* four side blocks: O's ring patches → the wall from O to H, closed by the
  slants C → H.

The three slants meet at 45° at each corner of C, a cube O-grid's corner:
min corner scaled Jacobian 1/√3 at any aspect ratio, ``nrad`` and length.
The H face's side grading (``wall_bump``) starts at C, so the core block
carries the change from O's uniform sides (``BlockLayout.edge``'s
``own_grading``); in the cap it costs about 0.15 of min SJ (task 0085).

Counts: the cap and core share the H face's ``nang_w`` × ``nang_h``; the
side blocks have ``nrad`` across, ``n_layers`` along.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, replace

import numpy as np

from ..core.spec import LayoutNotSupported, PipeSpec
from ..sections import layout_of, oh
from . import limits
from .blocks import BlockLayout, LayoutError, bind_face, face_vertices
from .interface import Frame
from .signature import check_port_pairs


@dataclass(frozen=True)
class Switch:
    """Change a rectangular duct between the O-H and H sections.

    Parameters
    ----------
    length : float
        Axial length; at least ``limits.SWITCH_MIN_LENGTH`` ring
        thicknesses (the cap is one ring thickness deep).
    n_layers : int, optional
        Cells along the core block (and along the wall).  ``None`` resolves
        from ``Assembly(axial_cell=…)`` over ``length`` minus the cap.
    outlet : PipeSpec, optional
        The outlet spec: the same rectangle and counts, the other layout.
        From an O-H inlet the default is the H face, ungraded; give it to
        grade the H walls (``first_cell=``, ``wall_bump=``).  From an H
        inlet it is required (it carries ``nrad`` and the ring's ``mprg``).
    """

    strategies = frozenset({1})   # class 1, a pillow: O-H ↔ H (DESIGN A4)
    pillows = True

    length:   float
    n_layers: int | None = None
    outlet:   PipeSpec | None = field(default=None, metadata={"input": True})

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell: float | None = None,
                outlet: Frame | None = None) -> "Switch":
        out = self.outlet_spec(spec)
        sw = self if self.outlet is out else replace(self, outlet=out)
        if sw.n_layers is not None:
            return sw
        if axial_cell is None:
            raise ValueError("n_layers=None needs Assembly(axial_cell=...)")
        core = self.length - self.cap_depth(spec)
        return replace(sw, n_layers=max(1, math.ceil(core / axial_cell - 1e-9)))

    # -- specs ----------------------------------------------------------

    def outlet_spec(self, spec: PipeSpec) -> PipeSpec:
        """The H face of an O-H *spec* (ungraded), unless ``outlet`` is given."""
        if self.outlet is not None:
            return self.outlet
        if spec.layout != "oh":
            raise ValueError("Switch from an H inlet needs outlet= (the O-H spec, "
                             "with its nrad)")
        sh = spec.core_shape
        return PipeSpec(nang_w=sh.nang_w, nang_h=sh.nang_h, mbmp=spec.mbmp,
                        rot=spec.rot).core(spec.layer_names[0], sh, layout="h")

    @staticmethod
    def _ends(spec: PipeSpec, out: PipeSpec) -> tuple[PipeSpec, PipeSpec]:
        """(O-H spec, H spec)."""
        return (spec, out) if spec.layout == "oh" else (out, spec)

    def cap_depth(self, spec: PipeSpec) -> float:
        sh = spec.core_shape
        return oh.ring_thickness(sh.half_w, sh.half_h)

    # -- checks (pure) --------------------------------------------------

    def check(self, spec: PipeSpec) -> None:
        if self.length <= 0:
            raise ValueError(f"length must be positive, got {self.length!r}")
        if self.n_layers is not None and self.n_layers < 1:
            raise ValueError(f"n_layers must be at least 1, got {self.n_layers!r}")
        out = self.outlet_spec(spec)
        for end, s in (("inlet", spec), ("outlet", out)):
            if s.core_shape.side_curve != "line":
                raise ValueError(f"Switch changes a rectangular duct's section; the {end} "
                                 f"core is a {s.core_shape.label}")
            if s.shells:
                raise LayoutNotSupported(f"Switch: the {end} spec has shells", "h", "0086",
                                         "a switch inside shells (an H core with shells "
                                         "around it) is task 0086's")
        if {spec.layout, out.layout} != {"oh", "h"}:
            raise ValueError(f"Switch joins an O-H and an H face; got layout "
                             f"{spec.layout!r} at the inlet and {out.layout!r} at the outlet")
        a, b = spec.core_shape, out.core_shape
        if (a.half_w, a.half_h) != (b.half_w, b.half_h) or spec.rot != out.rot:
            raise ValueError("Switch keeps the rectangle: the outlet's half_w, half_h and rot "
                             "must be the inlet's (use Reducer or Transition to change them)")
        t = self.cap_depth(spec)
        if self.length < limits.SWITCH_MIN_LENGTH * t - 1e-12:
            raise ValueError(
                f"Switch length {self.length:.6g} is below {limits.SWITCH_MIN_LENGTH:g} ring "
                f"thicknesses ({limits.SWITCH_MIN_LENGTH * t:.6g}): the cap is one ring "
                f"thickness (t = {t:.6g}) deep")
        check_port_pairs(self, [spec, out])     # counts, mbmp, name: class 1 only

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal, inlet.normal, inlet.up)
        return [(out, self.outlet_spec(spec))]

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """Raise ValueError if invalid; nothing to warn about (the corner
        SJ is 1/√3 throughout, task 0085)."""
        self.check(spec)
        if self.n_layers is None:
            raise ValueError("n_layers unresolved (add the switch to an Assembly)")
        (want, _), = self.ports(frames[0], spec)
        got = frames[1]
        if (np.linalg.norm(want.position - got.position) > 1e-9 * self.length
                or np.dot(want.normal, got.normal) < 1 - 1e-9
                or np.dot(want.up, got.up) < 1 - 1e-9):
            raise ValueError("port interface does not match Switch geometry")
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise ValueError(f"block layout invalid: {e}") from None
        return []

    # -- layout ---------------------------------------------------------

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        """The six blocks (pure).  Vertex ids: the O-H face ``("O", lvl,
        k)``, the H face ``("H", 0, k)``, the cap's inner corners ``("C",
        0, k)``; k as on both faces (the rectangle's corners, ``rot``
        applied)."""
        out = self.outlet_spec(spec)
        s_oh, s_h = self._ends(spec, out)
        f_oh, f_h = frames if spec.layout == "oh" else frames[::-1]
        lay = BlockLayout()
        face_vertices(lay, "O", f_oh, s_oh)
        face_vertices(lay, "H", f_h, s_h, own_grading=True)
        axis = (f_h.position - f_oh.position) / self.length
        x_c = self.length - self.cap_depth(spec)
        (level,) = layout_of(s_h).levels(s_h)
        for k in range(4):
            lay.vertex(("C", 0, k), lay.coords[("O", 0, k)] + x_c * axis)
            lay.edge(("O", 0, k), ("C", 0, k), divisions=self.n_layers)
        for e in level.edges:            # the H side grading starts at C
            lay.edge(("C", *e.a), ("C", *e.b), grading=e.grading, own_grading=True)
        name = spec.layer_names[0]
        O0 = [("O", 0, k) for k in range(4)]
        C0 = [("C", 0, k) for k in range(4)]
        H0 = [("H", 0, k) for k in range(4)]
        lay.block(O0 + C0, name)                                  # core
        lay.block(C0 + H0, name)                                  # cap
        for k in range(4):                                        # sides
            j = (k + 1) % 4
            lay.block([("O", 0, k), ("O", 0, j), ("O", 1, j), ("O", 1, k),
                       ("C", 0, k), ("C", 0, j), ("H", 0, j), ("H", 0, k)], name)
        return lay

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count (pure; DESIGN P4)."""
        return self.layout(frames, spec).cell_count()

    def predicted_sj(self, frames: list[Frame], spec: PipeSpec) -> float:
        return float(self.layout(frames, spec).corner_jacobians().min())

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        prefixes = ("O", "H") if spec.layout == "oh" else ("H", "O")
        for prefix, face in zip(prefixes, faces):
            bind_face(lay, prefix, face)
        return lay.realise(spec.layer_names)
