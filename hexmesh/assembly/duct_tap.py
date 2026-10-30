"""
Duct tap: the block layout of a ``Tee`` on a rectangular main (decision
0033 B; prototyped in task 0069, merged in task 0070): a perpendicular
branch on a flat face, narrower than the face, with the hole on the wall
and the branch's ring layer continued into the main as a dome.

``DuctTap`` is the layout engine, not a fitting: ``Tee`` builds it from its
own fields and checks (``Tee._tap``).

Canonical frame
---------------
x the main axis, z out of the tapped face, y = z × x.  The duct is
|y| ≤ a, |z| ≤ b; the hole is |x| ≤ p, |y| ≤ q on the wall z = b (a
rectangle, or the O-H outline of a circle of radius r).  The main face's
inner rectangle is (±iw, ±ih), iw = a − t, ih = b − t, t = (1 − OH_RATIO)
min(a, b) (``build_oh_rect``).

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
from dataclasses import dataclass

import numpy as np

from ..core.shape import CircleShape, OH_RATIO, RectShape
from ..core.spec import PipeSpec
from .blocks import ArcAbout, BlockLayout, LayoutError, face_patches, face_vertices
from .interface import Frame

_LABS = ((1, 1), (-1, 1), (-1, -1), (1, -1))       # CCW in the (first, second) plane


def _label_map(lay, prefix, o, e1, e2) -> dict:
    """(sign along e1, sign along e2) → corner index k of face *prefix*."""
    out = {}
    for k in range(4):
        d = lay.coords[(prefix, 1, k)] - o
        out[(int(np.sign(d @ e1)), int(np.sign(d @ e2)))] = k
    if len(out) != 4:
        raise LayoutError(f"face {prefix}: corners not one per quadrant")
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
            raise ValueError("no layout fits: the tap is too long for run_length")
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
        return frame, out.core(spec.layer_names[0], shape, nrad=spec._core_nrad,
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
        t = (1 - OH_RATIO) * min(a, b)
        iw, ih = a - t, b - t
        extent = self.radius if self.radius is not None else p   # the hole's reach along x
        s = extent + self.margin * t
        name = spec.layer_names[0]
        bframe, bspec = self.branch(frames[0], spec)

        def P(x, y, z):
            return o + x * ex + y * ey + z * ez

        reach = self.radius if self.radius is not None else q     # across
        if not (0 < reach < a and s < self.run_length):
            raise LayoutError(f"tap does not fit: q {q:.4g} vs a {a:.4g}, s {s:.4g}")

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
        tb = (1 - OH_RATIO) * min(p, q)
        if self.radius is not None:
            inner = OH_RATIO * self.radius / math.sqrt(2)
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
        t = (1 - OH_RATIO) * min(a, b)
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
        t = (1 - OH_RATIO) * min(a, b)
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
                              f"turning height {z1:.4g} vs branch {self.branch_length:.4g}")

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
