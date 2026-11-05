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
Duct tap: the block layout of a ``Tee`` on a rectangular main (decision
0033 B; prototyped in task 0069, merged in task 0070): a perpendicular
branch on a flat face, narrower than the face, with the hole on the wall
and the branch's ring layer continued into the main as a dome.

``DuctTap`` is the layout engine, not a fitting.  ``TapTemplate`` is the
front end: ``Tee`` on a rectangular main picks it and delegates its
resolve, checks, ports, layout, quality and fill (task 0060's design note,
DESIGN §6: a fitting variant is a template).

Canonical frame
---------------
x the main axis, z out of the tapped face, y = z × x.  The duct is
|y| ≤ a, |z| ≤ b; the hole is |x| ≤ p, |y| ≤ q on the wall z = b (a
rectangle, or the O-H outline of a circle of radius r).  The main face's
inner rectangle is (±iw, ±ih), iw = a − t, ih = b − t, t =
``core.shape.oh.ring_thickness(a, b)`` (the O-H layout, ``sections.oh``).

Blocks
------
* Port slabs A → Sa and Sd → B, the stations at x = ∓s: standard.
* Between the stations the side rings S± and the bottom ring are unchanged
  (every crease is a block edge); the top ring and the core are re-blocked
  with all their outer faces single patches, so the ports stay standard:
  - top ring: a column K_r under the hole down to the core top, in an O-grid
    tube of 4 blocks; K_r carries the branch's O-H face (5 columns);
  - core: K_c hangs from K_r's footprint, the core minus K_c is 5 blocks
    (pillow); inside K_c the branch's ring layer continues as a dome sheet
    around a dome core (6 blocks).
* Branch run: the hole → port E (5 blocks).

Vertex ids: stations ``(X, lvl, (sy, sz))``; hole and below
``(Y, ring, (sx, sy))`` with Y ∈ {"W" (z = b), "C" (z = ih), "D" (dome
bottom)} and ring 0 the branch's inner square, 1 its outline.

Counts: opposite block edges share counts, so the branch has the main's
counts per side (a class-0 port): its frame is turned so that its count
across the main is the main's across count; along the main it carries the
junction's axial count.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, replace

import numpy as np

from .errors import AssemblyError
from ..core.shape import CircleShape, RectShape
from ..core.spec import PipeSpec
from ..sections import h, oh
from . import limits
from .blocks import ArcAbout, BlockLayout, LayoutError, bind_face, face_patches, face_vertices
from .interface import Frame
from .limits import PREDICTED_SJ_MIN, PREDICTED_SJ_WARN

_LABS = ((1, 1), (-1, 1), (-1, -1), (1, -1))       # CCW in the (first, second) plane


def _label_map(lay, prefix, o, e1, e2) -> dict:
    """(sign along e1, sign along e2) → corner index k of face *prefix*."""
    out = {}
    for k in range(4):
        d = lay.coords[(prefix, 1, k)] - o
        out[(int(np.sign(d @ e1)), int(np.sign(d @ e2)))] = k
    if len(out) != 4:
        raise LayoutError(f"face {prefix}: corners not one per quadrant",
                          code="layout_corners_invalid", where={"part": f"face {prefix}"})
    return out


@dataclass(frozen=True)
class DuctTap:
    """Duct-tap layout engine (``Tee`` on a rectangular main).

    ``along`` and ``across`` are the hole's half-extents along the main
    axis and across the face; ``radius`` instead makes a round tap.
    ``face`` "wide" or "narrow"; ``side`` ±1 picks which of the two.
    ``margin`` is the station distance beyond the hole, in units of the
    ring thickness t; ``dome`` the core fraction K_c reaches down;
    ``sheet`` the dome sheet's thickness as a fraction of K_c's depth.
    ``tuned`` fills the unset ones with the three that maximise the
    predicted min corner SJ over ``TUNING`` (pure)."""

    run_length:    float
    branch_length: float
    along:  float | None = None
    across: float | None = None
    radius: float | None = None
    face:   str = "wide"
    side:   int = 1
    n_run:    int = 3
    n_branch: int = 3
    n_turn:   int = 2       # FullWidthTap's turn blocks
    margin: float | None = None
    dome:   float | None = None
    sheet:  float | None = None
    n_wall: int | None = None     # O-grid cells from a station to the hole

    TUNING = {"margin": (0.5, 1.0, 2.0, 3.0), "dome": (0.2, 0.35, 0.6, 0.85),
              "sheet": (0.2, 0.35, 0.5)}

    def tuned(self, inlet: Frame, spec: PipeSpec) -> "DuctTap":
        """Fill unset tunables with the best predicted min corner SJ."""
        import itertools
        from dataclasses import replace
        free = [k for k in self.TUNING if getattr(self, k) is None]
        if not free:
            return self
        best = None
        for values in itertools.product(*(self.TUNING[k] for k in free)):
            tap = replace(self, **dict(zip(free, values)))
            try:
                frames = [inlet] + [f for f, _ in tap.ports(inlet, spec)]
                sj = tap.predicted_sj(frames, spec)
            except (LayoutError, ValueError):
                continue
            if best is None or sj > best[0]:
                best = (sj, tap)
        if best is None:
            raise AssemblyError("no layout fits: the tap is too long for run_length",
                                code="tap_does_not_fit", where={"field": "run_length"})
        return best[1]

    # -- geometry -------------------------------------------------------

    def _basis(self, inlet: Frame, spec: PipeSpec):
        sh = spec.core_shape
        R, U = inlet.right, inlet.up
        wide_is_U = sh.half_w >= sh.half_h          # the ±U faces are hw wide
        on_U = wide_is_U == (self.face == "wide")
        ez = self.side * (U if on_U else R)
        a, b = (sh.half_w, sh.half_h) if on_U else (sh.half_h, sh.half_w)
        ex = inlet.normal
        ey = np.cross(ez, ex)
        o = inlet.position + self.run_length * ex
        return o, ex, ey, ez, a, b, on_U

    def _hole(self):
        if self.radius is not None:
            r = self.radius / math.sqrt(2)
            return r, r
        return self.along, self.across

    def branch(self, inlet: Frame, spec: PipeSpec):
        """(frame, spec) of the branch port: the main's counts per side."""
        o, ex, ey, ez, a, b, on_U = self._basis(inlet, spec)
        sh = spec.core_shape
        # across ∥ R (main nang_w) when the tap is on a U face
        up = ex if on_U else ey
        frame = Frame(o + self.branch_length * ez, ez, up)
        if self.radius is not None:
            shape = CircleShape(radius=self.radius, nang=sh.nang_w)
            out = PipeSpec(nang=sh.nang_w)
        else:
            hw, hh = (self.across, self.along) if on_U else (self.along, self.across)
            shape = RectShape(hw, hh, sh.nang_w, sh.nang_h)
            out = PipeSpec(nang_w=sh.nang_w, nang_h=sh.nang_h)
        return frame, out.core(spec.layer_names[0], shape, nrad=spec._core_nrad, layout="oh",
                               mprg=spec._core_mprg)

    def ports(self, inlet: Frame, spec: PipeSpec):
        o, ex, *_ = self._basis(inlet, spec)
        main = Frame(o + self.run_length * ex, ex, inlet.up)
        return [(main, spec), self.branch(inlet, spec)]

    # -- layout ---------------------------------------------------------

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        o, ex, ey, ez, a, b, on_U = self._basis(frames[0], spec)
        p, q = self._hole()
        sh = spec.core_shape
        t = oh.ring_thickness(a, b)
        iw, ih = a - t, b - t
        extent = self.radius if self.radius is not None else p   # the hole's reach along x
        s = extent + self.margin * t
        name = spec.layer_names[0]
        bframe, bspec = self.branch(frames[0], spec)

        def P(x, y, z):
            return o + x * ex + y * ey + z * ez

        reach = self.radius if self.radius is not None else q     # across
        if not (0 < reach < a and s < self.run_length):
            raise LayoutError(f"tap does not fit: q {q:.4g} vs a {a:.4g}, s {s:.4g}",
                              code="tap_does_not_fit", value=float(q), limit={"max": float(a)})

        lay = BlockLayout()
        face_vertices(lay, "A", frames[0], spec)
        face_vertices(lay, "B", frames[1], spec)
        face_vertices(lay, "E", frames[2], bspec)
        mapA = _label_map(lay, "A", frames[0].position, ey, ez)
        mapB = _label_map(lay, "B", frames[1].position, ey, ez)
        mapE = _label_map(lay, "E", frames[2].position, ex, ey)
        # counts by canonical direction: across (y) and deep (z)
        n_y = sh.nang_w if on_U else sh.nang_h
        n_z = sh.nang_h if on_U else sh.nang_w
        n_j = n_z if self.radius is None else n_y      # the branch's count along x
        nrad = spec._core_nrad

        # Stations: ids by canonical (sy, sz).
        for X, x in (("Sa", -s), ("Sd", s)):
            for (sy, sz) in _LABS:
                lay.vertex((X, 0, (sy, sz)), P(x, sy * iw, sz * ih))
                lay.vertex((X, 1, (sy, sz)), P(x, sy * a, sz * b))
            for i, l0 in enumerate(_LABS):
                l1 = _LABS[(i + 1) % 4]
                n = n_y if l0[1] == l1[1] else n_z
                for lvl in (0, 1):
                    lay.edge((X, lvl, l0), (X, lvl, l1), divisions=n)
                lay.edge((X, 0, l0), (X, 1, l0), divisions=nrad,
                         grading=("Progression", spec._core_mprg))
        # Port slabs.
        for port, X, m in (("A", "Sa", mapA), ("B", "Sd", mapB)):
            inv = {k: lab for lab, k in m.items()}
            for k in range(4):
                for lvl in (0, 1):
                    lay.edge((port, lvl, k), (X, lvl, inv[k]), divisions=self.n_run)
            for material, cyc in face_patches(port, spec):
                lay.block(list(cyc) + [(X, l, inv[k]) for (_, l, k) in cyc], material)
        for lab in _LABS:
            for lvl in (0, 1):
                lay.edge(("Sa", lvl, lab), ("Sd", lvl, lab), divisions=n_j)

        sa = lambda l, sy, sz: ("Sa", l, (sy, sz))
        sd = lambda l, sy, sz: ("Sd", l, (sy, sz))
        # Unchanged rings: S+, S−, bottom.
        for cyc in (((0, 1, -1), (0, 1, 1), (1, 1, 1), (1, 1, -1)),
                    ((0, -1, 1), (0, -1, -1), (1, -1, -1), (1, -1, 1)),
                    ((0, -1, -1), (0, 1, -1), (1, 1, -1), (1, -1, -1))):
            lay.block([sa(*c) for c in cyc] + [sd(*c) for c in cyc], name)

        # Hole levels.  W at z = b; C at z = ih (y scaled by iw/a); D the
        # dome bottom.  Ring 0 the branch's inner square, 1 its outline.
        tb = oh.ring_thickness(p, q)
        if self.radius is not None:
            inner = oh.inner_half_side(self.radius)
            pc, qc = inner, inner
        else:
            pc, qc = p - tb, q - tb
        f = iw / a
        zd = ih - self.dome * 2 * ih                 # K_c's bottom
        zdc = ih - (1 - self.sheet) * (ih - zd)      # the dome core's bottom
        # a round hole's footprint at the core top is a circle (r·f): arc to
        # arc, else the face from the wall's arc to a chord bulges and folds
        fc = f if self.radius is not None else 1.0
        lev = {"W": (b, 1.0, 1.0), "C": (ih, fc, f), "D": (zd, 0.85 * fc, 0.85 * f)}
        for Y, (z, fx, fy) in lev.items():
            for (sx, sy) in _LABS:
                lay.vertex((Y, 1, (sx, sy)), P(sx * p * fx, sy * q * fy, z))
                zz = zdc if Y == "D" else z
                lay.vertex((Y, 0, (sx, sy)), P(sx * pc * fx, sy * qc * fy, zz))
        if self.radius is not None:       # hole outline arcs on the wall and at the core top
            for Y, z in (("W", b), ("C", ih)):
                for i, l0 in enumerate(_LABS):
                    lay.edge((Y, 1, l0), (Y, 1, _LABS[(i + 1) % 4]), ArcAbout(tuple(P(0, 0, z))))
                    lay.edge((Y, 0, l0), (Y, 0, _LABS[(i + 1) % 4]))

        W = lambda r, sx, sy: ("W", r, (sx, sy))
        C = lambda r, sx, sy: ("C", r, (sx, sy))
        D = lambda r, sx, sy: ("D", r, (sx, sy))
        # Top ring: the tube (4 blocks) around K_r.
        lay.block([sa(0, -1, 1), sa(0, 1, 1), sa(1, 1, 1), sa(1, -1, 1),
                   C(1, -1, -1), C(1, -1, 1), W(1, -1, 1), W(1, -1, -1)], name)      # −x
        lay.block([sd(0, -1, 1), sd(0, 1, 1), sd(1, 1, 1), sd(1, -1, 1),
                   C(1, 1, -1), C(1, 1, 1), W(1, 1, 1), W(1, 1, -1)], name)          # +x
        lay.block([sa(0, 1, 1), sd(0, 1, 1), sd(1, 1, 1), sa(1, 1, 1),
                   C(1, -1, 1), C(1, 1, 1), W(1, 1, 1), W(1, -1, 1)], name)          # +y
        lay.block([sa(0, -1, 1), sd(0, -1, 1), sd(1, -1, 1), sa(1, -1, 1),
                   C(1, -1, -1), C(1, 1, -1), W(1, 1, -1), W(1, -1, -1)], name)      # −y
        # K_r: the branch's O-H columns, and K_c's dome core and sheet.
        loop = [(sx, sy) for sx, sy in _LABS]
        lay.block([W(0, *l) for l in loop] + [C(0, *l) for l in loop], name)
        lay.block([C(0, *l) for l in loop] + [D(0, *l) for l in loop], name)
        lay.block([D(0, *l) for l in loop] + [D(1, *l) for l in loop], name)        # dome bottom
        for i, l0 in enumerate(loop):
            l1 = loop[(i + 1) % 4]
            lay.block([W(0, *l0), W(0, *l1), W(1, *l1), W(1, *l0),
                       C(0, *l0), C(0, *l1), C(1, *l1), C(1, *l0)], name)
            lay.block([C(0, *l0), C(0, *l1), C(1, *l1), C(1, *l0),
                       D(0, *l0), D(0, *l1), D(1, *l1), D(1, *l0)], name)
        for lab in loop:
            lay.edge(W(1, *lab), C(1, *lab), divisions=nrad)
        # The O-grid's radial count: station corners → hole corners.
        n_wall = self.n_wall or self.wall_cells(spec)
        for X, sx in (("Sa", -1), ("Sd", 1)):
            for sy in (-1, 1):
                lay.edge((X, 1, (sy, 1)), W(1, sx, sy), divisions=n_wall)
                lay.edge((X, 0, (sy, 1)), C(1, sx, sy), divisions=n_wall)
                lay.edge((X, 0, (sy, -1)), D(1, sx, sy), divisions=n_wall)
        # Core minus K_c: 4 sides and the bottom.
        lay.block([sa(0, -1, -1), sa(0, 1, -1), sa(0, 1, 1), sa(0, -1, 1),
                   D(1, -1, -1), D(1, -1, 1), C(1, -1, 1), C(1, -1, -1)], name)      # −x
        lay.block([sd(0, -1, -1), sd(0, 1, -1), sd(0, 1, 1), sd(0, -1, 1),
                   D(1, 1, -1), D(1, 1, 1), C(1, 1, 1), C(1, 1, -1)], name)          # +x
        lay.block([sa(0, 1, -1), sd(0, 1, -1), sd(0, 1, 1), sa(0, 1, 1),
                   D(1, -1, 1), D(1, 1, 1), C(1, 1, 1), C(1, -1, 1)], name)          # +y
        lay.block([sa(0, -1, -1), sd(0, -1, -1), sd(0, -1, 1), sa(0, -1, 1),
                   D(1, -1, -1), D(1, 1, -1), C(1, 1, -1), C(1, -1, -1)], name)      # −y
        lay.block([sa(0, -1, -1), sd(0, -1, -1), sd(0, 1, -1), sa(0, 1, -1),
                   D(1, -1, -1), D(1, 1, -1), D(1, 1, 1), D(1, -1, 1)], name)        # bottom

        # Branch run: the hole (W) → port E.
        inv = {k: lab for lab, k in mapE.items()}
        for k in range(4):
            for lvl in (0, 1):
                lay.edge(("E", lvl, k), ("W", lvl, inv[k]), divisions=self.n_branch)
        for material, cyc in face_patches("E", bspec):
            lay.block([("W", l, inv[k]) for (_, l, k) in cyc] + list(cyc), material)
        return lay

    def wall_cells(self, spec: PipeSpec) -> int:
        """The O-grid's default radial count, station corners → hole
        corners: cells about as long as the branch's along the main.  Not
        linear in the counts (a ceiling), so ``Tee`` stores it resolved and
        refinement scales it (task 0070)."""
        sh = spec.core_shape
        on_U = (sh.half_w >= sh.half_h) == (self.face == "wide")
        a, b = (sh.half_w, sh.half_h) if on_U else (sh.half_h, sh.half_w)
        t = oh.ring_thickness(a, b)
        p, _ = self._hole()
        extent = self.radius if self.radius is not None else p
        n_y, n_z = (sh.nang_w, sh.nang_h) if on_U else (sh.nang_h, sh.nang_w)
        n_j = n_z if self.radius is None else n_y
        return max(2, math.ceil(n_j * (extent + self.margin * t - p) / (2 * p) - 1e-9))

    def predicted_sj(self, frames: list[Frame], spec: PipeSpec) -> float:
        return float(self.layout(frames, spec).corner_jacobians().min())


@dataclass(frozen=True)
class FullWidthTap(DuctTap):
    """Full-width duct tap (task 0057, decision 0027 amended): the hole
    spans its face across (q = a), so its corners lie on the duct's
    creases and the pipe tee's layout ports with straight edges (DESIGN
    §7.1): stations at x = ±p, a core, side and bottom rings, the branch
    core and four turn blocks up to a turning station at height
    ``turning_height``.  Every wall face is a plane.  No tunables."""


    def tuned(self, inlet: Frame, spec: PipeSpec) -> "FullWidthTap":
        return self

    def turning_height(self, b: float) -> float:
        """Above the axis: the face plus half the branch's smaller
        half-extent (the pipe tee's R + r/2)."""
        p, q = self._hole()
        return b + 0.5 * min(p, q)

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        o, ex, ey, ez, a, b, on_U = self._basis(frames[0], spec)
        p, _ = self._hole()
        sh = spec.core_shape
        t = oh.ring_thickness(a, b)
        iw, ih = a - t, b - t
        # The stations' level-0 corners: the main's inner rectangle across,
        # inset min(t, p/2) from the hole along; the branch core tapers from
        # there to the branch's own inner rectangle at Z.  The branch's inset
        # instead (as the pipe tee) gives min SJ 0.06 for short taps, task 0057.
        cx = p - min(t, p / 2)
        z1 = self.turning_height(b)
        name = spec.layer_names[0]
        bframe, bspec = self.branch(frames[0], spec)
        if not (p < self.run_length and z1 < self.branch_length):
            raise LayoutError(f"tap does not fit: p {p:.4g} vs run {self.run_length:.4g}, "
                              f"turning height {z1:.4g} vs branch {self.branch_length:.4g}",
                              code="tap_does_not_fit", value=float(p),
                              limit={"max": float(self.run_length)})

        def P(x, y, z):
            return o + x * ex + y * ey + z * ez

        lay = BlockLayout()
        face_vertices(lay, "A", frames[0], spec)
        face_vertices(lay, "B", frames[1], spec)
        face_vertices(lay, "E", frames[2], bspec)
        Z = Frame(o + z1 * ez, ez, bframe.up)
        face_vertices(lay, "Z", Z, bspec, port=False)
        mapA = _label_map(lay, "A", frames[0].position, ey, ez)
        mapB = _label_map(lay, "B", frames[1].position, ey, ez)
        mapE = _label_map(lay, "E", frames[2].position, ex, ey)
        mapZ = _label_map(lay, "Z", Z.position, ex, ey)
        n_y = sh.nang_w if on_U else sh.nang_h
        n_z = sh.nang_h if on_U else sh.nang_w       # also the branch's count along x
        nrad = spec._core_nrad

        # Stations at x = ∓p: ids by canonical (sy, sz).
        for X, sx in (("Sa", -1), ("Sd", 1)):
            for (sy, sz) in _LABS:
                lay.vertex((X, 0, (sy, sz)), P(sx * cx, sy * iw, sz * ih))
                lay.vertex((X, 1, (sy, sz)), P(sx * p, sy * a, sz * b))
            for i, l0 in enumerate(_LABS):
                l1 = _LABS[(i + 1) % 4]
                n = n_y if l0[1] == l1[1] else n_z
                for lvl in (0, 1):
                    lay.edge((X, lvl, l0), (X, lvl, l1), divisions=n)
                lay.edge((X, 0, l0), (X, 1, l0), divisions=nrad,
                         grading=("Progression", spec._core_mprg))
        for port, X, m in (("A", "Sa", mapA), ("B", "Sd", mapB)):
            inv = {k: lab for lab, k in m.items()}
            for k in range(4):
                for lvl in (0, 1):
                    lay.edge((port, lvl, k), (X, lvl, inv[k]), divisions=self.n_run)
            for material, cyc in face_patches(port, spec):
                lay.block(list(cyc) + [(X, l, inv[k]) for (_, l, k) in cyc], material)
        for lab in _LABS:
            for lvl in (0, 1):
                lay.edge(("Sa", lvl, lab), ("Sd", lvl, lab), divisions=n_z)

        sa = lambda l, sy, sz: ("Sa", l, (sy, sz))
        sd = lambda l, sy, sz: ("Sd", l, (sy, sz))
        lay.block([sa(0, -1, -1), sd(0, -1, -1), sd(0, 1, -1), sa(0, 1, -1),
                   sa(0, -1, 1), sd(0, -1, 1), sd(0, 1, 1), sa(0, 1, 1)], name)      # core
        lay.block([sa(0, 1, -1), sd(0, 1, -1), sd(1, 1, -1), sa(1, 1, -1),
                   sa(0, 1, 1), sd(0, 1, 1), sd(1, 1, 1), sa(1, 1, 1)], name)        # S+
        lay.block([sa(0, -1, -1), sd(0, -1, -1), sd(1, -1, -1), sa(1, -1, -1),
                   sa(0, -1, 1), sd(0, -1, 1), sd(1, -1, 1), sa(1, -1, 1)], name)    # S−
        lay.block([sa(0, -1, -1), sd(0, -1, -1), sd(0, 1, -1), sa(0, 1, -1),
                   sa(1, -1, -1), sd(1, -1, -1), sd(1, 1, -1), sa(1, 1, -1)], name)  # bottom

        # Branch: corners by (sx, sy), in the pipe tee's branch order.
        quads = ((1, 1), (1, -1), (-1, -1), (-1, 1))
        top = lambda l, sx, sy: ("Sd" if sx > 0 else "Sa", l, (sy, 1))
        z = lambda l, sx, sy: ("Z", l, mapZ[(sx, sy)])
        for q in quads:
            for lvl in (0, 1):
                lay.edge(top(lvl, *q), z(lvl, *q), divisions=self.n_turn)
        lay.block([top(0, *q) for q in quads] + [z(0, *q) for q in quads], name)  # branch core
        for k in range(4):
            qk, qj = quads[k], quads[(k + 1) % 4]
            lay.block([top(0, *qk), top(0, *qj), top(1, *qj), top(1, *qk),
                       z(0, *qk), z(0, *qj), z(1, *qj), z(1, *qk)], name)        # turn
        inv = {k: lab for lab, k in mapE.items()}
        for k in range(4):
            for lvl in (0, 1):
                lay.edge(("Z", lvl, mapZ[inv[k]]), ("E", lvl, k), divisions=self.n_branch)
        for material, cyc in face_patches("E", bspec):
            lay.block([("Z", l, mapZ[inv[k]]) for (_, l, k) in cyc] + list(cyc), material)
        return lay


# ---------------------------------------------------------------------------
# The front end: Tee on a rectangular main (task 0060's design note)
# ---------------------------------------------------------------------------

# Default full-width duct-tap run: the tap's half-length plus this many
# times the duct's smaller half-extent (task 0057; the pipe tee's R/2).
FULL_WIDTH_RUN = 0.5

# a frame for what doesn't depend on the placement (an H main's branch spec)
_ORIGIN = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))

_TUNABLES = ("margin", "dome", "sheet", "n_wall")


@dataclass(frozen=True)
class TapTemplate:
    """A ``Tee`` on a rectangular main: its resolve, checks, ports,
    layout, quality and fill (decision 0033; ``Tee`` picks this template
    and delegates).  *tee* is the ``Tee`` with the user's fields; the
    branch is a circle or a rectangle, read through the shape protocol.

    **H ports** (decision 0036 item 5, task 0086).  On an H main the
    junction keeps its O-H blocks: the O-H face the H main pillows into
    (``sections.h.pillowed``, with the tee's ``nrad`` and ``mprg``,
    derived and stored when the tee is added).  A ``Switch`` leg of
    ``limits.SWITCH_MIN_LENGTH`` ring thicknesses at each H port (both
    main ports, and a rectangular branch, which is H too) joins it to the
    port; the legs come out of ``run_length`` and ``branch_length``, so
    the ports stay where the tee puts them.  A round branch stays O-H."""

    tee: object

    def geometry(self, spec: PipeSpec):
        """(on_U, a, b, along, across, reach_x, reach_y): the face's
        half-width a and depth b, the branch's half-extents along the main
        and across the face, and the hole's reach along and across."""
        face = self.tee.face or "wide"
        w, h = (float(x) for x in spec.core_shape.corner(0))
        on_U = (w >= h) == (face == "wide")
        a, b = (w, h) if on_U else (h, w)
        br = self.tee.branch
        if br.is_round:
            r = br.max_extent
            return on_U, a, b, None, None, r, r
        bw, bh = (float(x) for x in br.corner(0))
        along, across = (bh, bw) if on_U else (bw, bh)
        return on_U, a, b, along, across, along, across

    def full_width(self, spec: PipeSpec) -> bool:
        """A rectangular tap as wide as its face across (task 0057)."""
        _, a, _, _, _, _, reach_y = self.geometry(spec)
        return not self.tee.branch.is_round and abs(reach_y / a - 1) < 1e-9

    def tap(self, inlet: Frame, spec: PipeSpec, **tuning) -> DuctTap:
        """The layout engine with the tee's fields (``FullWidthTap`` for a
        full-width tap)."""
        tee = self.tee
        _, _, _, along, across, _, _ = self.geometry(spec)
        side = 1 if abs(math.remainder(tee.roll, 360.0)) < 1e-9 else -1
        if self.full_width(spec):
            return FullWidthTap(run_length=tee.run_length, branch_length=tee.branch_length,
                                along=along, across=across, face=tee.face or "wide",
                                side=side, n_run=tee.n_run, n_branch=tee.n_branch,
                                n_turn=tee.n_turn)
        kw = {k: getattr(tee, k) for k in _TUNABLES}
        kw.update(tuning)
        return DuctTap(run_length=tee.run_length, branch_length=tee.branch_length,
                       along=along, across=across,
                       radius=tee.branch.max_extent if tee.branch.is_round else None,
                       face=tee.face or "wide", side=side, n_run=tee.n_run,
                       n_branch=tee.n_branch, **kw)

    def meshed_sj_check(self) -> bool:
        """Round taps: their prediction (from straight block edges)
        overestimates by up to 0.11 (task 0069)."""
        return self.tee.branch is not None and self.tee.branch.is_round

    # -- resolve and check ---------------------------------------------

    def resolve(self, inlet: Frame, spec: PipeSpec):
        """The ``Tee`` with ``face``, ``run_length`` and the tunables set."""
        tee = self.tee
        if tee.toward is not None:
            raise AssemblyError("Tee: toward= is for pipe tees; a duct tap takes face= "
                                "and roll= (0 or 180)",
                                code="toward_on_duct_tap", where={"field": "toward"},
                                hint="use face= and roll= (0 or 180)")
        if tee.branch is None:
            raise AssemblyError("Tee: a rectangular main needs branch=RectShape(…) or "
                                "CircleShape(…); branch_radius= is the shorthand for pipes",
                                code="duct_tap_needs_branch_shape", where={"field": "branch"},
                                hint="branch=RectShape(…) or CircleShape(…)")
        tee = replace(tee, face=tee.face or "wide")
        me = TapTemplate(tee)
        if spec.layout == "h":
            return me._resolve_h(inlet, spec)
        if tee.nrad is not None or tee.mprg is not None:
            raise AssemblyError("Tee: nrad= and mprg= are for a duct tap on an H main (its "
                                "O-H blocks inside); an O-H main's ring is its own",
                                code="tap_ring_override_on_oh_main", where={"field": "nrad"})
        if me.full_width(spec):
            tuning = [n for n in _TUNABLES if getattr(tee, n) is not None]
            if tuning:
                raise AssemblyError(f"Tee: a full-width tap has no {', '.join(tuning)} "
                                    f"(pillowed taps only)",
                                    code="full_width_tap_tunables", where={"field": tuning[0]})
            if tee.run_length is None:
                _, a, b, along, *_ = me.geometry(spec)
                tee = replace(tee, run_length=along + FULL_WIDTH_RUN * min(a, b))
            TapTemplate(tee).check(spec)
            return tee
        if tee.run_length is None:
            on_U, a, b, *_, reach_x, _ = me.geometry(spec)
            t = oh.ring_thickness(a, b)
            run = reach_x + (max(DuctTap.TUNING["margin"]) + 1) * t
            tee = replace(tee, run_length=run)
        me = TapTemplate(tee)
        me.check(spec, tuned=False)
        tap = me.tap(inlet, spec).tuned(inlet, spec)
        return replace(tee, margin=tap.margin, dome=tap.dome, sheet=tap.sheet,
                       n_wall=tee.n_wall or tap.wall_cells(spec))

    def check(self, spec: PipeSpec, tuned: bool = True) -> None:
        tee = self.tee
        if spec.layout == "h":
            return self._check_h(spec, tuned)
        if tee.nrad is not None or tee.mprg is not None:
            raise AssemblyError("Tee: nrad= and mprg= are for a duct tap on an H main (its "
                                "O-H blocks inside); an O-H main's ring is its own",
                                code="tap_ring_override_on_oh_main", where={"field": "nrad"})
        sh = spec.core_shape
        full = tee.branch is not None and self.full_width(spec)
        tunables = () if full else tuple(getattr(tee, k) for k in _TUNABLES)
        if tee.run_length is None or (tuned and None in tunables):
            raise AssemblyError("Tee: run_length and the duct-tap tunables are resolved "
                                "by Assembly.add(); add the fitting to an assembly",
                                code="fitting_not_resolved", where={"field": "run_length"},
                                hint="add the fitting to an assembly")
        if spec.shells:
            raise AssemblyError("Tee: duct taps are single-layer; shelled duct taps are "
                                "not supported yet (decisions 0026, 0028)",
                                code="junction_shells_unsupported")
        if spec.rot != 0 or spec.n_outer != 4:
            raise AssemblyError("Tee: a duct tap requires rot = 0 and n_outer = 4",
                                code="junction_needs_rot_0_n_outer_4", where={"field": "rot"})
        if tee.branch is None:
            raise AssemblyError("Tee: a rectangular main needs branch=RectShape(…) or "
                                "CircleShape(…); branch_radius= is the shorthand for pipes",
                                code="duct_tap_needs_branch_shape", where={"field": "branch"},
                                hint="branch=RectShape(…) or CircleShape(…)")
        if tee.face not in (None, "wide", "narrow"):
            raise AssemblyError(f"Tee: face must be 'wide' or 'narrow', got {tee.face!r}",
                                code="option_invalid", where={"field": "face"}, value=tee.face,
                                limit=["wide", "narrow"])
        if min(abs(math.remainder(tee.roll - r, 360.0)) for r in (0, 180)) > 1e-9:
            raise AssemblyError(f"Tee: a duct tap's roll is 0 or 180 (the side of the "
                                f"face), got {tee.roll:g}; face= picks wide or narrow",
                                code="duct_tap_roll_invalid", where={"field": "roll"},
                                value=tee.roll, limit=[0, 180])
        br = tee.branch
        (mw, mh), (bw, bh) = sh.counts, br.counts
        if br.is_round:
            if not (mw == mh == bw):
                raise AssemblyError(
                    f"Tee: a round duct tap needs equal counts per side: main "
                    f"(nang_w, nang_h) = ({mw}, {mh}), branch nang {bw}",
                    code="counts_mismatch", where={"field": "branch"}, value=bw, limit=(mw, mh))
        elif (bw, bh) != (mw, mh):
            raise AssemblyError(
                f"Tee: branch counts (nang_w, nang_h) = ({bw}, {bh}) must "
                f"be the main's ({mw}, {mh}): the branch keeps the main's "
                f"counts per side (module notes)",
                code="counts_mismatch", where={"field": "branch"}, value=(bw, bh), limit=(mw, mh))
        on_U, a, b, along, across, reach_x, reach_y = self.geometry(spec)
        face = tee.face or "wide"
        ratio = reach_y / a
        t = oh.ring_thickness(a, b)
        if full:
            z1 = b + 0.5 * min(along, across)
            if tee.run_length <= along:
                raise AssemblyError(f"Tee: run_length must exceed the full-width tap's "
                                    f"half-length along the main, {along:.4g}",
                                    code="run_length_too_short", where={"field": "run_length"},
                                    value=tee.run_length, limit={"min_exclusive": float(along)})
            if tee.branch_length <= z1:
                raise AssemblyError(f"Tee: branch_length must exceed the turning station's "
                                    f"height {z1:.4g} (the {face} face at {b:.4g} plus half "
                                    f"the branch's smaller half-extent)",
                                    code="branch_length_too_short",
                                    where={"field": "branch_length"}, value=tee.branch_length,
                                    limit={"min_exclusive": float(z1)})
            for n in (tee.n_run, tee.n_branch, tee.n_turn):
                if n < 1:
                    raise AssemblyError("layer counts must be >= 1",
                                        code="count_below_minimum",
                                        where={"field": "n_run, n_branch, n_turn"}, value=n,
                                        limit={"min": 1})
            return
        if ratio > limits.DUCT_TAP_MAX_RATIO:
            raise AssemblyError(
                f"Tee: the tap reaches {reach_y:.4g} across the {face} face of "
                f"half-width {a:.4g}: ratio {ratio:.3g} exceeds DUCT_TAP_MAX_RATIO "
                f"{limits.DUCT_TAP_MAX_RATIO:g}; a tap up to "
                f"{limits.DUCT_TAP_MAX_RATIO * a:.4g}, or a full-width tap (across "
                f"{a:.4g})",
                code="duct_tap_too_wide", where={"field": "branch"}, value=float(ratio),
                limit="DUCT_TAP_MAX_RATIO", hint="a smaller tap, or a full-width tap")
        need = reach_x + (tee.margin or min(DuctTap.TUNING["margin"])) * t
        if tee.run_length <= need:
            raise AssemblyError(f"Tee: run_length must exceed {need:.4g}: the tap's reach "
                                f"along the main {reach_x:.4g} plus the station margin",
                                code="run_length_too_short", where={"field": "run_length"},
                                value=tee.run_length, limit={"min_exclusive": float(need)})
        if tee.branch_length <= b:
            raise AssemblyError(f"Tee: branch_length must exceed the {face} face's "
                                f"distance from the axis, {b:.4g}",
                                code="branch_length_too_short", where={"field": "branch_length"},
                                value=tee.branch_length, limit={"min_exclusive": float(b)})
        for n in (tee.n_run, tee.n_branch, tee.n_wall or 1):
            if n < 1:
                raise AssemblyError("layer counts must be >= 1",
                                    code="count_below_minimum",
                                    where={"field": "n_run, n_branch, n_wall"}, value=n,
                                    limit={"min": 1})

    # -- the fitting contract (delegated by Tee) ------------------------

    def ports(self, inlet: Frame, spec: PipeSpec):
        if spec.layout == "h":
            return self._h_ports(inlet, spec)
        return self.tap(inlet, spec).ports(inlet, spec)

    def layout(self, frames: list[Frame], spec: PipeSpec) -> BlockLayout:
        """The junction's blocks; on an H main the O-H junction's (the
        switch legs are their own layouts, ``_parts``)."""
        if spec.layout == "h":
            _, (inner, fr, s), *_ = self._parts(frames, spec)
            return inner.layout(fr, s)
        return self.tap(frames[0], spec).layout(frames, spec)

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """Quality tiers and the block layouts (raise or warn); on an H
        main also each switch leg's."""
        if spec.layout != "h":
            found = self.quality(frames, spec)
            _validate_layout(self.layout(frames, spec))
            return found
        found = []
        for part, fr, s in self._parts(frames, spec):
            if isinstance(part, TapTemplate):
                ring = (f" (H main: the O-H ring inside has nrad {s._core_nrad}, "
                        f"mprg {s._core_mprg:.4g})")
                found += [m + ring for m in part.quality(fr, s)]
                _validate_layout(part.layout(fr, s))
            else:
                found += part.validate(fr, s)
        return found

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        if spec.layout != "h":
            return self.layout(frames, spec).cell_count()
        return sum(part.layout(fr, s).cell_count() if isinstance(part, TapTemplate)
                   else part.cell_count(fr, s) for part, fr, s in self._parts(frames, spec))

    def quality(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        """The predicted-SJ tiers (task 0052) for a duct tap, and the
        narrow-face warning on deep ducts (decision 0033)."""
        tee = self.tee
        sj = self.tap(frames[0], spec).predicted_sj(frames, spec)
        on_U, a, b, *_ = self.geometry(spec)
        face = tee.face or "wide"
        full = self.full_width(spec)
        if full:            # the predicted SJ depends on its length alone, task 0057
            hint = ("a full-width tap's quality is set by its length along the main "
                    "(run_length has no effect): a longer tap does better")
        else:
            hint = ("on the wide face it is better" if face == "narrow"
                    else "a smaller tap, or a longer tap along the main, may do better")
        found = []
        for tier, name in ((PREDICTED_SJ_MIN, "PREDICTED_SJ_MIN"),
                           (PREDICTED_SJ_WARN, "PREDICTED_SJ_WARN")):
            if sj >= tier:
                continue
            kind = "full-width duct tap" if full else "duct tap"
            msg = (f"predicted corner scaled Jacobian {sj:.3f} is below {name} "
                   f"{tier:g} ({kind}, {face} face); {hint}")
            if tier == PREDICTED_SJ_MIN:
                raise AssemblyError(msg,
                                    code="predicted_sj_below_minimum", value=float(sj),
                                    limit="PREDICTED_SJ_MIN", hint=hint)
            # a round tap's prediction overestimates: its warning tier is
            # the meshed check in Assembly.mesh() (task 0057's note)
            if not self.meshed_sj_check():
                found.append(msg)
            break
        if not full and face == "narrow" and b / a >= limits.DUCT_TAP_NARROW_ASPECT_WARN:
            found.append(
                f"a tap on the narrow face of a duct of aspect {b / a:.3g} (≥ "
                f"DUCT_TAP_NARROW_ASPECT_WARN {limits.DUCT_TAP_NARROW_ASPECT_WARN:g}): "
                f"the dome reaches into a deep, thin core (min corner SJ about 0.13, "
                f"non-orthogonality to 82°, task 0069); the wide face is better")
        return found

    def fill(self, faces, frames, spec, lc):
        """Bind the three port faces (declared in the ports' own frames).
        On an H main: the O-H faces at the legs' inner ends, then each
        part's fill on its faces."""
        if spec.layout == "h":
            return self._fill_h(faces, frames, spec, lc)
        lay = self.layout(frames, spec)
        for prefix, face in zip("ABE", faces):
            bind_face(lay, prefix, face)
        return lay.realise(spec.layer_names)

    # -- H ports (task 0086): O-H blocks inside, a switch leg at each port

    def inner_spec(self, spec: PipeSpec) -> PipeSpec:
        """The junction's own section: *spec*, or on an H main the O-H face
        it pillows into (``sections.h.pillowed``; the tee's ``nrad`` and
        ``mprg`` when set, else derived)."""
        if spec.layout != "h":
            return spec
        return h.pillowed(spec, self.tee.nrad, self.tee.mprg)

    def legs(self, spec: PipeSpec) -> tuple[float, float]:
        """(main leg, branch leg): the switch lengths at the main ports and
        at a rectangular branch port, each the switch's shortest
        (``switch.min_length``, task 0086's Q2); 0 where the port stays
        O-H (an O-H main, a round branch)."""
        from .switch import min_length
        if spec.layout != "h":
            return 0.0, 0.0
        s_oh = self.inner_spec(spec)
        main, _, _ = min_length(s_oh, spec)
        br = self.tee.branch
        if br is None or br.is_round:
            return main, 0.0
        b_oh = self._branch_oh(spec)
        return main, min_length(b_oh, self._h_branch(b_oh, spec))[0]

    def _branch_oh(self, spec: PipeSpec) -> PipeSpec:
        """The inner junction's branch spec on an H main: its shape and
        counts don't depend on the lengths (any run length places it)."""
        s_oh = self.inner_spec(spec)
        tpl = TapTemplate(replace(self.tee, nrad=None, mprg=None,
                                  run_length=self.tee.run_length or 1.0))
        return tpl.tap(_ORIGIN, s_oh).branch(_ORIGIN, s_oh)[1]

    def graded_legs(self, spec: PipeSpec) -> bool:
        """An H main with a graded wall: its switch legs' prediction is an
        empirical bound, so the meshed cells are checked (task 0086)."""
        return spec.layout == "h" and spec.wall_grading is not None

    def inner(self, spec: PipeSpec) -> "TapTemplate":
        """The O-H junction inside: the tee with the legs taken off its
        lengths, and no ``nrad``/``mprg`` (its main is O-H)."""
        lm, lb = self.legs(spec)
        tee = self.tee
        run = None if tee.run_length is None else tee.run_length - lm
        return TapTemplate(replace(tee, run_length=run, branch_length=tee.branch_length - lb,
                                   nrad=None, mprg=None))

    def _h_branch(self, bspec: PipeSpec, spec: PipeSpec) -> PipeSpec:
        """A rectangular branch's H port: the inner branch spec's
        rectangle, graded as the main (the same ``Bump`` per side count,
        as the branch keeps the main's counts per side)."""
        sh = bspec.core_shape
        wall = spec.wall_grading
        return PipeSpec(nang_w=sh.nang_w, nang_h=sh.nang_h, mbmp=bspec.mbmp,
                        rot=bspec.rot).core(bspec.layer_names[0], sh, layout="h",
                                            wall_bump=None if wall is None else wall[1])

    def _parts(self, frames: list[Frame], spec: PipeSpec):
        """[(fitting or template, frames, inlet spec), …] on an H main: the
        inlet leg, the O-H junction, the outlet leg and (a rectangular
        branch) the branch leg; *frames* the tee's three ports."""
        from .switch import Switch
        A, B, E = frames
        lm, lb = self.legs(spec)
        s_oh = self.inner_spec(spec)
        A1 = Frame(A.position + lm * A.normal, A.normal, A.up)
        B1 = Frame(B.position - lm * B.normal, B.normal, B.up)
        E1 = Frame(E.position - lb * E.normal, E.normal, E.up)
        inner = self.inner(spec)
        b_oh = self._branch_oh(spec)
        # the legs' layers are the run's and the branch's counts, so they
        # refine with them (intent.refined_dict)
        n_run, n_br = self.tee.n_run, self.tee.n_branch
        parts = [(Switch(lm, n_layers=n_run, outlet=s_oh), [A, A1], spec),
                 (inner, [A1, B1, E1], s_oh),
                 (Switch(lm, n_layers=n_run, outlet=spec), [B1, B], s_oh)]
        if lb:
            parts.append((Switch(lb, n_layers=n_br, outlet=self._h_branch(b_oh, spec)),
                          [E1, E], b_oh))
        return parts

    def _h_ports(self, inlet: Frame, spec: PipeSpec):
        lm, lb = self.legs(spec)
        s_oh = self.inner_spec(spec)
        A1 = Frame(inlet.position + lm * inlet.normal, inlet.normal, inlet.up)
        (b1, _), (e1, b_oh) = self.inner(spec).ports(A1, s_oh)
        main = Frame(b1.position + lm * b1.normal, b1.normal, b1.up)
        if not lb:
            return [(main, spec), (e1, b_oh)]
        branch = Frame(e1.position + lb * e1.normal, e1.normal, e1.up)
        return [(main, spec), (branch, self._h_branch(b_oh, spec))]

    def _check_override(self) -> None:
        tee = self.tee
        if tee.nrad is not None and (isinstance(tee.nrad, bool) or not isinstance(tee.nrad, int)
                                     or tee.nrad < 1):
            raise AssemblyError(f"Tee: nrad must be an integer >= 1, got {tee.nrad!r}",
                                code="count_below_minimum", where={"field": "nrad"},
                                value=tee.nrad, limit={"min": 1, "integer": True})
        if tee.mprg is not None and not tee.mprg > 0:
            raise AssemblyError(f"Tee: mprg must be positive, got {tee.mprg!r}",
                                code="value_not_positive", where={"field": "mprg"}, value=tee.mprg,
                                limit={"min_exclusive": 0})

    def _room(self, e: ValueError, spec: PipeSpec) -> AssemblyError:
        """*e* from the O-H junction inside, naming the legs on top."""
        lm, lb = self.legs(spec)
        legs = f"{lm:.4g} at each main port" + (f" and {lb:.4g} at the branch" if lb else "")
        return AssemblyError.wrap(e, f"{e} (for the O-H junction inside: with H ports a switch "
                                  f"leg of {legs} comes on top, task 0086)",
                                  code="tap_does_not_fit")

    def _check_h(self, spec: PipeSpec, tuned: bool) -> None:
        """An H main: the override, then the O-H junction inside, its room
        checks naming the legs."""
        self._check_override()
        try:
            self.inner(spec).check(self.inner_spec(spec), tuned)
        except ValueError as e:
            raise self._room(e, spec) from None

    def _resolve_h(self, inlet: Frame, spec: PipeSpec):
        """The tee on an H main, resolved: ``nrad`` and ``mprg`` (the
        override, else derived), the O-H junction's resolve with the legs
        off, and the legs back on ``run_length``."""
        self._check_override()
        tee = self.tee
        if tee.nrad is None or tee.mprg is None:
            dn, dm = h.pillow_ring(spec, tee.nrad)
            tee = replace(tee, nrad=dn, mprg=dm if tee.mprg is None else tee.mprg)
        me = TapTemplate(tee)
        lm, lb = me.legs(spec)
        inner_inlet = Frame(inlet.position + lm * inlet.normal, inlet.normal, inlet.up)
        try:
            inner = me.inner(spec).resolve(inner_inlet, me.inner_spec(spec))
        except ValueError as e:
            raise me._room(e, spec) from None
        return replace(inner, run_length=inner.run_length + lm, branch_length=tee.branch_length,
                       nrad=tee.nrad, mprg=tee.mprg)

    def _fill_h(self, faces, frames, spec, lc):
        from .interface import build_face
        parts = self._parts(frames, spec)
        (_, fr_in, s_oh), branch_leg = parts[1], parts[3] if len(parts) == 4 else None
        inner_faces = [build_face(s_oh, fr_in[0], lc), build_face(s_oh, fr_in[1], lc),
                       faces[2] if branch_leg is None else build_face(branch_leg[2], fr_in[2], lc)]
        legs = [parts[0][0].fill([faces[0], inner_faces[0]], parts[0][1], parts[0][2], lc),
                parts[2][0].fill([inner_faces[1], faces[1]], parts[2][1], parts[2][2], lc)]
        if branch_leg is not None:
            legs.append(branch_leg[0].fill([inner_faces[2], faces[2]], branch_leg[1],
                                           branch_leg[2], lc))
        result = parts[1][0].fill(inner_faces, fr_in, s_oh, lc)
        for leg in legs:
            result.merge(leg)
        # the meshed checks measure the legs; a round tap's, the whole tee
        if not self.meshed_sj_check():
            result.checked_volumes = [v for leg in legs for vs in leg.volumes.values() for v in vs]
        return result


def _validate_layout(lay: BlockLayout) -> None:
    try:
        lay.validate()
    except LayoutError as e:
        raise AssemblyError.wrap(e, f"block layout invalid: {e}",
                                 code="block_layout_invalid") from None
