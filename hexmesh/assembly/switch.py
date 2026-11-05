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
min corner scaled Jacobian 1/√3 at any aspect ratio, ``nrad`` and length,
with a uniform H face.

**A graded H face** (task 0086, design answer to Q2).  The side blocks'
wall edges go from the O-H face's node spacing to the H face's over the
length, so their cells shear by about Δ/L, Δ the largest shift of a side
node between the two faces (:func:`wall_shift`).  The length rule is
therefore ``L ≥ max(SWITCH_MIN_LENGTH · t, Δ / SWITCH_MAX_SHEAR,
t + Δ / SWITCH_MAX_CORE_SHEAR)``, the last for the core block, L − t long,
which carries the same change (:func:`min_length`); the predicted SJ is the empirical bound measured
for that shear (``limits.SWITCH_SHEAR_SJ``), and the meshed cells are
checked after meshing.
The H face's side grading (``wall_bump``) starts at C, so the core block
carries the change from O's uniform sides (``BlockLayout.edge``'s
``own_grading``); in the cap it costs about 0.15 of min SJ (task 0085).

Counts: the cap and core share the H face's ``nang_w`` × ``nang_h``; the
side blocks have ``nrad`` across, ``n_layers`` along.

Shells (task 0086): both faces' first shell starts at the rectangle's
corners (O-H level 1, H level 0), so each shell's four ring blocks run
straight from one face to the other.  The shells must be the same at
both ends.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, replace

import numpy as np

from .errors import AssemblyError
from ..core.grading import bump
from ..core.spec import PipeSpec
from ..sections import h, layout_of, oh
from . import limits
from .blocks import BlockLayout, LayoutError, bind_face, face_vertices
from .interface import Frame
from .signature import check_port_pairs


def wall_shift(o_spec: PipeSpec, h_spec: PipeSpec) -> float:
    """Δ_max (pure): the largest distance between a side node of the O-H
    face and the same node of the H face, over every layer's sides (the
    O-H sides at ``mbmp``, the H sides at the wall grading)."""
    corners = h_spec.corners()
    out = 0.0
    for k in range(4):
        n = h_spec.core_shape.side_count(k, 4)
        fo, fh = bump(n, o_spec.mbmp), h.side_fractions(h_spec, k)
        for o, c in zip(h_spec.outlines, corners):
            a, b = c[k], c[(k + 1) % 4]
            d = o.side(a, b, fo) - o.side(a, b, fh)
            out = max(out, float(np.max(np.linalg.norm(d, axis=-1))))
    return out


def min_length(o_spec: PipeSpec, h_spec: PipeSpec) -> tuple[float, float, float]:
    """(shortest switch length, ring thickness t, Δ_max) between the two
    faces (pure): ``max(SWITCH_MIN_LENGTH · t, Δ_max / SWITCH_MAX_SHEAR,
    t + Δ_max / SWITCH_MAX_CORE_SHEAR)``."""
    sh = h_spec.core_shape
    t = oh.ring_thickness(sh.half_w, sh.half_h)
    d = wall_shift(o_spec, h_spec)
    if not d:
        return limits.SWITCH_MIN_LENGTH * t, t, d
    return max(limits.SWITCH_MIN_LENGTH * t, d / limits.SWITCH_MAX_SHEAR,
               t + d / limits.SWITCH_MAX_CORE_SHEAR), t, d


def length_rule(o_spec: PipeSpec, h_spec: PipeSpec) -> str:
    """The length rule in words, with its numbers, for error messages."""
    need, t, d = min_length(o_spec, h_spec)
    return (f"{need:.6g}: the largest of {limits.SWITCH_MIN_LENGTH:g} ring thicknesses "
            f"(t = {t:.6g}; the cap is one t deep), the H face's wall-node shift "
            f"Δ_max = {d:.6g} over SWITCH_MAX_SHEAR {limits.SWITCH_MAX_SHEAR:g}, and t plus "
            f"Δ_max over SWITCH_MAX_CORE_SHEAR {limits.SWITCH_MAX_CORE_SHEAR:g} (the core block)")


def shear_sj(shear: float) -> float:
    """The empirical min corner SJ bound for a switch at wall shear
    Δ_max/L (``limits.SWITCH_SHEAR_SJ``, task 0086's table): the row at
    the smallest tabulated shear not below *shear*."""
    for s, sj in limits.SWITCH_SHEAR_SJ:
        if shear <= s + 1e-12:
            return sj
    return 0.0


@dataclass(frozen=True)
class Switch:
    """Change a rectangular duct between the O-H and H sections.

    Parameters
    ----------
    length : float
        Axial length; at least ``limits.SWITCH_MIN_LENGTH`` ring
        thicknesses (the cap is one ring thickness deep), and on a graded
        H face at least Δ_max / ``limits.SWITCH_MAX_SHEAR``
        (:func:`min_length`).
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
            raise AssemblyError("n_layers=None needs Assembly(axial_cell=...)",
                                code="n_layers_unresolved", where={"field": "n_layers"},
                                hint="Assembly(axial_cell=...)")
        core = self.length - self.cap_depth(spec)
        return replace(sw, n_layers=max(1, math.ceil(core / axial_cell - 1e-9)))

    # -- specs ----------------------------------------------------------

    def outlet_spec(self, spec: PipeSpec) -> PipeSpec:
        """The H face of an O-H *spec* (ungraded), unless ``outlet`` is given."""
        if self.outlet is not None:
            return self.outlet
        if spec.layout != "oh":
            raise AssemblyError("Switch from an H inlet needs outlet= (the O-H spec, "
                                "with its nrad)",
                                code="switch_needs_outlet", where={"field": "outlet"})
        sh = spec.core_shape
        out = PipeSpec(nang_w=sh.nang_w, nang_h=sh.nang_h, mbmp=spec.mbmp,
                       rot=spec.rot).core(spec.layer_names[0], sh, layout="h")
        for s in spec.shells:
            out = out.shell(s.name, dR=s.dR, nrad=s.nrad, mprg=s.mprg, outer=s.outer)
        return out

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
            raise AssemblyError(f"length must be positive, got {self.length!r}",
                                code="size_not_positive", where={"field": "length"},
                                value=self.length, limit={"min_exclusive": 0})
        if self.n_layers is not None and self.n_layers < 1:
            raise AssemblyError(f"n_layers must be at least 1, got {self.n_layers!r}",
                                code="count_below_minimum", where={"field": "n_layers"},
                                value=self.n_layers, limit={"min": 1})
        out = self.outlet_spec(spec)
        for end, s in (("inlet", spec), ("outlet", out)):
            if s.core_shape.side_curve != "line":
                raise AssemblyError(f"Switch changes a rectangular duct's section; the {end} "
                                    f"core is a {s.core_shape.label}",
                                    code="switch_needs_rectangle", where={"field": end})
        if {spec.layout, out.layout} != {"oh", "h"}:
            raise AssemblyError(f"Switch joins an O-H and an H face; got layout "
                                f"{spec.layout!r} at the inlet and {out.layout!r} at the outlet",
                                code="switch_needs_oh_and_h", where={"field": "outlet"},
                                value=out.layout, limit="the other layout")
        a, b = spec.core_shape, out.core_shape
        if (a.half_w, a.half_h) != (b.half_w, b.half_h) or spec.rot != out.rot:
            raise AssemblyError("Switch keeps the rectangle: the outlet's half_w, half_h and rot "
                                "must be the inlet's (use Reducer or Transition to change them)",
                                code="switch_changes_rectangle", where={"field": "outlet"},
                                hint="use Reducer or Transition")
        shells = lambda s: [(x.name, x.nrad, x.mprg, o.to_dict())
                            for x, o in zip(s.shells, s.outlines[1:])]
        if shells(spec) != shells(out):
            raise AssemblyError("Switch keeps the shells: the outlet's shells (names, outlines, "
                                "nrad, mprg) must be the inlet's",
                                code="switch_changes_shells", where={"field": "outlet"})
        s_oh, s_h = self._ends(spec, out)
        need, _, _ = min_length(s_oh, s_h)
        if self.length < need - 1e-12:
            raise AssemblyError(f"Switch length {self.length:.6g} is below "
                                f"{length_rule(s_oh, s_h)}",
                                code="switch_too_short", where={"field": "length"},
                                value=self.length, limit={"min": float(need)})
        check_port_pairs(self, [spec, out])     # counts, mbmp, name: class 1 only

    def ports(self, inlet: Frame, spec: PipeSpec) -> list[tuple[Frame, PipeSpec]]:
        out = Frame(inlet.position + self.length * inlet.normal, inlet.normal, inlet.up)
        return [(out, self.outlet_spec(spec))]

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """Raise ValueError if invalid; the predicted-SJ tiers on
        :meth:`predicted_sj` (with the length rule kept, never below
        0.5)."""
        self.check(spec)
        if self.n_layers is None:
            raise AssemblyError("n_layers unresolved (add the switch to an Assembly)",
                                code="n_layers_unresolved", where={"field": "n_layers"},
                                hint="add the switch to an Assembly")
        (want, _), = self.ports(frames[0], spec)
        got = frames[1]
        if (np.linalg.norm(want.position - got.position) > 1e-9 * self.length
                or np.dot(want.normal, got.normal) < 1 - 1e-9
                or np.dot(want.up, got.up) < 1 - 1e-9):
            raise AssemblyError("port interface does not match Switch geometry",
                                code="outlet_frame_mismatch")
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise AssemblyError.wrap(e, f"block layout invalid: {e}",
                                     code="block_layout_invalid") from None
        sj = self.predicted_sj(frames, spec)
        what = f"predicted corner scaled Jacobian {sj:.3f}"
        if self.wall_shift(spec):
            what += " (the empirical bound at this wall shear, limits.SWITCH_SHEAR_SJ)"
        if sj < limits.PREDICTED_SJ_MIN:
            raise AssemblyError(f"{what} is below PREDICTED_SJ_MIN {limits.PREDICTED_SJ_MIN:g}",
                                code="predicted_sj_below_minimum", value=float(sj),
                                limit="PREDICTED_SJ_MIN", hint=self.meshed_sj_hint)
        if sj < limits.PREDICTED_SJ_WARN:
            return [f"{what} is below PREDICTED_SJ_WARN {limits.PREDICTED_SJ_WARN:g}"]
        return []

    def wall_shift(self, spec: PipeSpec) -> float:
        """Δ_max between this switch's two faces (:func:`wall_shift`)."""
        return wall_shift(*self._ends(spec, self.outlet_spec(spec)))

    def meshed_sj_check(self, spec: PipeSpec) -> bool:
        """A graded H face: the prediction is an empirical bound, so the
        meshed cells are checked too (task 0086)."""
        return self.wall_shift(spec) > 0

    def meshed_nonorth_check(self, spec: PipeSpec) -> bool:
        """A graded H face: up to 70–77° at the steepest gradings at any
        length (task 0086's table), so the meshed cells are checked."""
        return self.meshed_sj_check(spec)

    meshed_sj_hint = "a longer switch shears its cells less"

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
        level = layout_of(s_h).levels(s_h)[0]
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
        for i, shell in enumerate(s_h.layer_names[1:], start=1):       # shells: O i+1 ↔ H i
            for k in range(4):
                j = (k + 1) % 4
                lay.block([("O", i, k), ("O", i, j), ("O", i + 1, j), ("O", i + 1, k),
                           ("H", i - 1, k), ("H", i - 1, j), ("H", i, j), ("H", i, k)], shell)
        return lay

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        """Exact hex count (pure; DESIGN P4)."""
        return self.layout(frames, spec).cell_count()

    def predicted_sj(self, frames: list[Frame], spec: PipeSpec) -> float:
        """The blocks' corner SJ from straight edges (1/√3), or on a graded
        H face the empirical bound at the wall shear Δ_max/L if lower."""
        sj = float(self.layout(frames, spec).corner_jacobians().min())
        d = self.wall_shift(spec)
        return min(sj, shear_sj(d / self.length)) if d else sj

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        prefixes = ("O", "H") if spec.layout == "oh" else ("H", "O")
        for prefix, face in zip(prefixes, faces):
            bind_face(lay, prefix, face)
        return lay.realise(spec.layer_names)
