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
Idealised aorta: the arch with its three branches, the tapering
descending and abdominal aorta, and the iliac bifurcation.

    python3 -m hexmesh.examples.applications.idealised_aorta # writes idealised_aorta.msh

A lumen-only model built from hexmesh's ordinary fittings: a ``Reducer``
for the ascending aorta, ``SplinePipe`` pieces along a slightly
non-planar arch, three ``Tee``s for the arch branches, ``Reducer``s for
the taper, and a ``Wye`` for the iliac fork.  No patient data.

**Where each number comes from** (metres in the code; the sources'
centimetres here):

- **Thoracic aorta**, Mansouri et al. 2024 (`mansouri_and_kemerli_etal_2024`),
  Table 10, the Normal (Type I) idealised model, weighted averages of
  published cohorts:
  ascending diameter D1 3.17, arch D2 2.65, mid-descending D3 2.5;
  arch width W 7.95 and height H 4.06; transverse curvature R 12.2;
  sinotubular junction (STJ) to the arch's start L 2.6; STJ to the
  brachiocephalic artery a 7.62; brachiocephalic to left common carotid
  d1 1.68; left common carotid to left subclavian d2 3.44; branch
  diameters 1.47 (brachiocephalic), 0.97 (left common carotid), 1.14
  (left subclavian).
- **Abdominal aorta and iliacs**, Minichil et al. 2022
  (`minichil_and_tesfaye_etal_2022`), Table 1, all 136 adults (outer
  diameters on CT, so the lumen is slightly smaller): aortic hiatus 2.13,
  suprarenal 1.91, infrarenal 1.63, common iliac 1.11 (right) and 1.10
  (left), taken here as 1.10 for both.
- **Bifurcation angle**, Góes Junior et al. 2020
  (`goes_and_albuquerque_etal_2020`): about 44° in women at every age and
  45.5° in men aged 20–30; taken as 45°.

**Not from a source** (modelling choices, stated as such):
- the arch's centreline shape: a half-ellipse above the arch's start,
  bowed out of plane by the sagitta of R over the arch's width;
- **the arch is 1.2 × the cited W and H** (9.54 × 4.87).  At the cited
  size it can't carry three branches from straight tees: each needs
  about two branch diameters of straight run, and the spline joining
  two tees then turns tighter than the aorta's own radius, which
  ``SplinePipe`` rejects.  1.2 is the smallest scale tried (in steps of
  0.1) that builds;
- **the left common carotid and left subclavian move downstream** to
  10.96 and 14.14 from the STJ (cited 9.30 and 12.74): a branch's tee
  starts at least half an arch diameter of curved arch after the
  previous one (``GAP``), so the spline between them can turn.  The
  brachiocephalic stays at its cited 7.62.  ``PLACED`` holds the
  positions;
- the descending thoracic (20 cm) and abdominal (13 cm) lengths and the
  common iliac length (5 cm): no normative centreline lengths were found
  with the sources above;
- the branches' outlet extensions (four branch diameters), which let a
  flow case's outlets sit away from the junctions.

**Idealised in hexmesh's terms:**
- the branches leave square to the arch, along its outward normal
  (Mansouri's angles to the arch are 84.8°, 73.3° and 69.8°; a ``Tee``
  leans only downstream, and the arch branches lean toward the head);
- each tee's run is straight, along the arch's tangent at the branch,
  and the pieces between are splines on a smooth (Hermite) curve
  between the tees, not on the ellipse itself;
- the visceral and renal branches are left out;
- the iliacs leave the wye at the infrarenal diameter (a ``Wye``'s
  daughters keep the inlet's section) and narrow to the common iliac
  diameter in a ``Reducer`` each: a stand-in for a fork with unequal
  daughters.

**Quality** (``nang`` 8): the three arch tees warn (predicted min SJ
0.20, 0.14 and 0.15: small branch ratios, r/R 0.37–0.56), the left
common carotid's turn block also on non-orthogonality (70.6°), and the
wye on its crotch's non-orthogonality (79°), as every wye does.  No cell
is inverted.

Inlet ``aortic_root``; outlets ``brachiocephalic``,
``left_common_carotid``, ``left_subclavian``, ``right_common_iliac`` and
``left_common_iliac``, so a flow case can be set up from the patch names.
"""

import numpy as np

from hexmesh import Assembly, PipeSpec, Reducer, SplinePipe, Straight, Tee, Wye

CM = 0.01

# Mansouri et al. 2024, Table 10, Type I.
D_ASC, D_ARCH, D_DESC = 3.17 * CM, 2.65 * CM, 2.5 * CM
ARCH_W, ARCH_H, ARCH_R, ARCH_L = 7.95 * CM, 4.06 * CM, 12.2 * CM, 2.6 * CM
STJ_TO_BA, BA_TO_LCA, LCA_TO_LSA = 7.62 * CM, 1.68 * CM, 3.44 * CM
BRANCHES = (("brachiocephalic", 1.47 * CM), ("left_common_carotid", 0.97 * CM),
            ("left_subclavian", 1.14 * CM))
# Minichil et al. 2022, Table 1 (all adults).
D_HIATUS, D_SUPRARENAL, D_INFRARENAL, D_ILIAC = 2.13 * CM, 1.91 * CM, 1.63 * CM, 1.10 * CM
# Góes Junior et al. 2020.
BIFURCATION_ANGLE = 45.0
# Not from a source (see the docstring).
L_DESCENDING, L_ABDOMINAL, L_ILIAC = 20 * CM, 13 * CM, 5 * CM
BRANCH_EXTENSION = 4  # branch diameters

NANG = 8
GAP = D_ARCH / 2  # curved arch kept between two branches' tees
#: The arch's width and height are scaled up by this factor so the
#: branches' straight tees fit on it (not from a source; see the docstring).
ARCH_SCALE = 1.2

#: Where each branch's centre ends up, as arc length from the STJ (set by
#: ``build()``): the cited spacing where the tees fit, else further on.
PLACED: dict[str, float] = {}


def pipe(diameter: float) -> PipeSpec:
    """The lumen at *diameter*: one fluid layer, the same counts everywhere."""
    return PipeSpec(nang=NANG).core("fluid", radius=diameter / 2, nrad=4)


def _arch(n: int = 400):
    """The arch's centreline from its start: points, unit tangents, unit
    outward normals (in the arch's plane, away from its centre) and arc
    length from the STJ.  x posterior, y to the patient's left, z
    superior; the STJ at the origin."""
    t = np.linspace(0.0, np.pi, n)
    w, h = ARCH_SCALE * ARCH_W, ARCH_SCALE * ARCH_H
    sag = ARCH_R - np.sqrt(ARCH_R ** 2 - (w / 2) ** 2)
    p = np.stack([w / 2 * (1 - np.cos(t)), sag * np.sin(t),
                  ARCH_L + h * np.sin(t)], axis=1)
    dp = np.gradient(p, t, axis=0)
    tan = dp / np.linalg.norm(dp, axis=1)[:, None]
    centre = np.array([w / 2, 0.0, ARCH_L])
    out = p - centre
    out -= np.sum(out * tan, axis=1)[:, None] * tan
    out /= np.linalg.norm(out, axis=1)[:, None]
    s = ARCH_L + np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    return p, tan, out, s


def _at(arch, s0):
    p, tan, out, s = arch
    i = int(np.clip(np.searchsorted(s, s0), 1, len(s) - 1))
    return p[i], tan[i], out[i]


def _spline_to(asm, start, s_from, s_to, end, end_tangent):
    """A ``SplinePipe`` from the current outlet *start* to the point *end*,
    arriving along *end_tangent*: points on the cubic Hermite curve between
    the two poses (tangent lengths the chord), which turns as evenly as the
    two tangents allow.  *s_from* and *s_to* (arc length along the arch)
    only set the axial layers."""
    p0, t0 = np.asarray(start.frame.position), np.asarray(start.frame.normal)
    p1 = np.asarray(end, float)
    t1 = np.asarray(end_tangent, float) / np.linalg.norm(end_tangent)
    k = np.linalg.norm(p1 - p0)
    pts = []
    for u in np.linspace(0.0, 1.0, 9)[1:]:
        h00, h10 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u
        h01, h11 = -2 * u**3 + 3 * u**2, u**3 - u**2
        pts.append(h00 * p0 + h10 * k * t0 + h01 * p1 + h11 * k * t1)
    return asm.add(start, SplinePipe([p0, *pts], end_tangent=tuple(t1),
                                     n_layers=max(4, int(round((s_to - s_from) / (D_ARCH / 4))))))


def build() -> Assembly:
    arch = _arch()
    asm = Assembly(pipe(D_ASC), direction=[0, 0, 1], up=[1, 0, 0], inlet_name="aortic_root")
    # Ascending aorta: the STJ to the arch's start, narrowing to the arch.
    end = asm.add(Reducer(pipe(D_ARCH), length=ARCH_L, n_layers=8))
    # The arch: a spline to each branch, the branch's tee on a chord.
    s_here = ARCH_L
    centres = np.cumsum([STJ_TO_BA, BA_TO_LCA, LCA_TO_LSA])
    # Each branch's tee is a straight run (a lead straight that takes the
    # roll toward the head, task 0062, then the tee), along the arch's
    # tangent at the branch.  A branch whose tee doesn't leave GAP of
    # curved arch after the previous one moves downstream (PLACED).
    lead, margin = D_ARCH / 20, D_ARCH / 8
    for (name, d), s_c in zip(BRANCHES, centres):
        half = d / 2 + margin
        s_c = max(s_c, s_here + GAP + lead + half)
        PLACED[name] = s_c
        c, tan, out = _at(arch, s_c)
        end = _spline_to(asm, end, s_here, s_c - half - lead,
                         c - (half + lead) * tan, tan)
        end = asm.add(end, Straight(lead, n_layers=1))
        end, branch = asm.add(end, Tee(run_length=half, branch_length=D_ARCH,
                                       branch_radius=d / 2, toward=tuple(out),
                                       n_run=3, n_branch=4))
        asm.add(branch, Straight(BRANCH_EXTENSION * d, n_layers=6), names=[name])
        s_here = s_c + half
    # The rest of the arch, then down the descending aorta.
    # The spline runs on below the arch's start, into the descending aorta,
    # so it has room to turn down; that drop counts toward L_DESCENDING.
    drop = 4 * CM
    end = _spline_to(asm, end, s_here, arch[3][-1],
                     arch[0][-1] - (0, 0, drop), (0, 0, -1))
    end = asm.add(end, Reducer(pipe(D_DESC), length=3 * CM, n_layers=4))
    end = asm.add(end, Reducer(pipe(D_HIATUS), length=L_DESCENDING - drop - 3 * CM, n_layers=36))
    # Abdominal aorta: hiatus → suprarenal → infrarenal.
    end = asm.add(end, Reducer(pipe(D_SUPRARENAL), length=L_ABDOMINAL / 3, n_layers=10))
    end = asm.add(end, Reducer(pipe(D_INFRARENAL), length=L_ABDOMINAL / 3, n_layers=10))
    end = asm.add(end, Straight(L_ABDOMINAL / 3 - 2 * CM, n_layers=8))
    # The iliac fork, splitting to the patient's right and left.
    # The daughters' stations must clear each other: R·(cot(angle/2) + 1)
    # from the fork, 2.8 cm here; the common iliac's 5 cm is counted from it.
    fork = 3 * CM
    left, right = asm.add(end, Wye(BIFURCATION_ANGLE, run_length=1.2 * CM,
                                   branch_length=fork, toward=(0, -1, 0)))
    for port, name in ((right, "right_common_iliac"), (left, "left_common_iliac")):
        port = asm.add(port, Reducer(pipe(D_ILIAC), length=1.5 * CM, n_layers=4))
        asm.add(port, Straight(L_ILIAC - fork - 1.5 * CM, n_layers=2), names=[name])
    return asm


def gallery_cutaway() -> dict:
    """The gallery's cut-away (``docs/gallery/build.py``): the arch and the
    first 2 cm of each branch, front half removed along the arch's bowed
    mid-surface, so the three tees' blocks show; seen from the front."""
    w, h = ARCH_SCALE * ARCH_W, ARCH_SCALE * ARCH_H
    sag = ARCH_R - np.sqrt(ARCH_R ** 2 - (w / 2) ** 2)
    top = ARCH_L + h + D_ARCH / 2

    def keep(c):
        u = -(c[:, 0] - w / 2) / (w / 2)                 # the arch's ellipse, unit
        v = np.maximum((c[:, 2] - ARCH_L) / h, 0.0)
        y_mid = sag * np.sin(np.arctan2(v, u)) * np.hypot(u, v)
        cut = (c[:, 2] > ARCH_L - 1.5 * CM) & (c[:, 1] < y_mid) & (c[:, 2] < top + 2 * CM)
        return ~cut & (c[:, 2] > ARCH_L - 3 * CM)

    return {"keep": keep, "direction": (-0.35, -1.0, 0.45), "up": (0, 0, 1),
            "focus": (w / 2, 0.0, ARCH_L + h / 2)}


def main(output: str = "idealised_aorta.msh", **options):
    from hexmesh.examples._run import run
    return run(build, output, **options)


if __name__ == "__main__":
    main()
