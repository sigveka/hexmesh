"""
Duct tap — PROTOTYPE (task 0069, decision 0033 B): a perpendicular branch
on a flat face of a rectangular duct, narrower than the face, with the hole
on the wall and the branch's ring layer continued into the main as a dome.

Not wired into ``Tee``; the layout is chosen on this prototype's numbers.

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
from .blocks import ArcAbout, BlockLayout, LayoutError, bind_face, face_patches, face_vertices
from .interface import Frame
from .signature import check_port_pairs

_LABS = ((1, 1), (-1, 1), (-1, -1), (1, -1))       # CCW in the (first, second) plane


def rect_face_vertices(lay: BlockLayout, prefix, frame: Frame, spec: PipeSpec,
                       port: bool = True) -> None:
    """``face_vertices`` for a single-layer rectangular O-H face: corners
    at (±hw, ±hh) and the uniform-ring inner rectangle, counts per side."""
    sh = spec.core_shape
    hw, hh = sh.half_w, sh.half_h
    t = (1 - OH_RATIO) * min(hw, hh)
    R, U = frame.right, frame.up
    for lvl, (w, h) in enumerate(((hw - t, hh - t), (hw, hh))):
        for k, (su, sv) in enumerate(_LABS):
            lay.vertex((prefix, lvl, k), frame.position + su * w * R + sv * h * U)
    counts = spec.side_counts
    grading = ("Progression", spec._core_mprg)
    for k in range(4):
        j = (k + 1) % 4
        for lvl in (0, 1):
            lay.edge((prefix, lvl, k), (prefix, lvl, j), divisions=counts[k])
        lay.edge((prefix, 0, k), (prefix, 1, k), divisions=spec._core_nrad, grading=grading)
    if port:
        for _, cyc in face_patches(prefix, spec):
            lay.port_face(cyc)


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
    """Prototype duct tap (task 0069).

    ``along`` and ``across`` are the hole's half-extents along the main
    axis and across the face; ``radius`` instead makes a round tap.
    ``face`` "wide" or "narrow"; ``side`` ±1 picks which of the two.
    ``margin`` is the station distance beyond the hole, in units of the
    ring thickness t; ``dome`` the core fraction K_c reaches down;
    ``sheet`` the dome sheet's thickness as a fraction of K_c's depth.
    Left as None, ``resolve`` (in ``Assembly.add``) picks the three that
    maximise the predicted min corner SJ over ``TUNING`` (pure)."""

    strategies = frozenset({0})
    port_names = ("main", "branch")

    run_length:    float
    branch_length: float
    along:  float | None = None
    across: float | None = None
    radius: float | None = None
    face:   str = "wide"
    side:   int = 1
    n_run:    int = 3
    n_branch: int = 3
    margin: float | None = None
    dome:   float | None = None
    sheet:  float | None = None
    n_wall: int | None = None     # O-grid cells from a station to the hole

    TUNING = {"margin": (0.5, 1.0, 2.0, 3.0), "dome": (0.2, 0.35, 0.6, 0.85),
              "sheet": (0.2, 0.35, 0.5)}

    def resolve(self, inlet: Frame, spec: PipeSpec, axial_cell=None, outlet=None) -> "DuctTap":
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
            raise ValueError("DuctTap: no tuning fits (the tap or the run is too large)")
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

    def check(self, spec: PipeSpec) -> None:
        sh = spec.core_shape
        if not isinstance(sh, RectShape) or spec.shells or spec.rot != 0:
            raise ValueError("DuctTap prototype: single-layer rectangular main, rot 0")
        if self.radius is not None and sh.nang_w != sh.nang_h:
            raise ValueError("DuctTap: a round tap needs a main with equal counts per side")
        if (self.radius is None) == (self.along is None or self.across is None):
            raise ValueError("DuctTap: give along and across, or radius")

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
        rect_face_vertices(lay, "A", frames[0], spec)
        rect_face_vertices(lay, "B", frames[1], spec)
        if self.radius is None:
            rect_face_vertices(lay, "E", frames[2], bspec)
        else:
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
        n_wall = self.n_wall or max(2, math.ceil(n_j * (s - p) / (2 * p) - 1e-9))
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

    # -- contract -------------------------------------------------------

    def validate(self, frames: list[Frame], spec: PipeSpec) -> list[str]:
        self.check(spec)
        check_port_pairs(self, [spec] + [s for _, s in self.ports(frames[0], spec)])
        try:
            self.layout(frames, spec).validate()
        except LayoutError as e:
            raise ValueError(f"block layout invalid: {e}") from None
        return []

    def cell_count(self, frames: list[Frame], spec: PipeSpec) -> int:
        return self.layout(frames, spec).cell_count()

    def predicted_sj(self, frames: list[Frame], spec: PipeSpec) -> float:
        return float(self.layout(frames, spec).corner_jacobians().min())

    def fill(self, faces, frames, spec, lc):
        lay = self.layout(frames, spec)
        for prefix, face in zip("ABE", faces):
            bind_face(lay, prefix, face)
        return lay.realise(spec.layer_names)
