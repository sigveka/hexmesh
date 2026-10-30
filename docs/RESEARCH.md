# Fitting geometry and junction topology: literature notes

This document collects the mathematics hexmesh needs to describe pipe bends
and junctions, and the published block topologies for structured all-hex
junctions.  Each section ends with what it means for hexmesh under the rules
in [`DESIGN.md`](../DESIGN.md).

Citation keys refer to [`references.bib`](references.bib).  Local copies of
open-access papers are in [`papers/`](papers/), named by citation key.

---

## 1. Frames along a centreline

Every swept fitting (`Straight`, `Bend`, `SplinePipe`) places a cross-section
in a frame $(T, U, V)$ moving along a centreline $x(s)$.  The frame decides
where the cross-section's structural corners land at the outlet, which makes
it topology, not density.

**Frenet frame.**  It is undefined where curvature vanishes and flips at
inflection points, so it is unusable for general routes.

**Bishop (parallel-transport) frame** [`bishop_1975`].  $U, V$ are
transported without rotation about $T$:

$$
T' = k_1 U + k_2 V,\qquad U' = -k_1 T,\qquad V' = -k_2 T
$$

with $k_1 = \kappa\cos\theta$, $k_2 = \kappa\sin\theta$.  It needs only the
first derivative and is defined on straight segments.  This is the
rotation-minimizing frame (RMF).

**Double reflection method** [`wang_and_juttler_etal_2008`,
`wang_and_juttler_etal_2007`].  This is a discrete RMF.  Given samples
$x_i$, unit tangents $t_i$ and the frame vector $r_i$:

```
v1 = x[i+1] - x[i];          c1 = v1·v1
rL = r[i] - (2/c1)(v1·r[i]) v1      # reflect frame across bisector plane
tL = t[i] - (2/c1)(v1·t[i]) v1
v2 = t[i+1] - tL;            c2 = v2·v2
r[i+1] = rL - (2/c2)(v2·rL) v2      # second reflection aligns tangent
s[i+1] = t[i+1] × r[i+1]
```

Its global error is 4th order, against 2nd order for the projection and
rotation methods, at about the same per-step cost.

**Exact or rational RMFs.**  Pythagorean-hodograph (PH) curves have RMFs in
closed form [`farouki_2002`], with rational approximations in
[`farouki_and_han_2003`].  A subset of PH curves has exactly *rational* RMFs
[`farouki_and_gentili_etal_2017`].  This only matters if spline routes ever
need an analytically twist-free sweep.

**Closing twist.**  The RMF of a route that returns to its start direction
generally comes back rotated (holonomy).  When a fitting's outlet must match
a fixed interface frame, the remaining angle has to be spread linearly
along the sweep.

**For hexmesh.**  The shared sweep path (`Closure`, Spline pipe) should
compute frames with double reflection.  `Closure.stations` in
`hexmesh/assembly/fittings.py` currently uses the rotation method, which is
2nd order.  The outlet roll is then a well-defined function of the route.
Under DESIGN A3 the fitting absorbs the residual twist, modulo
$2\pi/n_\text{outer}$, and checks it in `validate()` before GMSH.

---

## 2. Bends

### 2.1 Torus bend (`Bend`)

For bend centre $C$, bend radius $R_b$, in-plane unit vectors $e_1, e_2$,
bend-plane normal $b = e_1\times e_2$ and pipe radius $\rho\le R$:

$$
N(\psi) = \cos\psi\,e_1 + \sin\psi\,e_2,\qquad
x(\psi,\rho,\varphi) = C + R_b N(\psi) + \rho\left(\cos\varphi\,N(\psi) + \sin\varphi\,b\right)
$$

with $\psi\in[0,\Psi]$.  On a circular arc the RMF is exactly $(T, N, b)$,
so a bend introduces no twist.  Validity requires $R_b > R_\text{outer}$;
cells on the intrados shrink by $(R_b - \rho)/R_b$.

Use this formula to place station-face nodes and the exact axial circular
arcs (`sweep.Arc`).  Don't use it as an OCC `revolve`: DESIGN §6 forbids
`extrude`/`revolve` fills, because filled OCC surfaces deviate from the
true torus.

### 2.2 Standard elbow proportions

ASME B16.9 long-radius elbows have centreline radius $1.5\times$ NPS.  The
former ASME B16.28 short-radius elbows have $1.0\times$ NPS.  For anything
beyond elbow radius (tee run and outlet dimensions, reducer lengths), use
the standard's tables, not secondary web sources.  The ones checked while
writing these notes disagreed with each other.

### 2.3 Miter bend (`MiterBend`)

For incoming and outgoing unit axes $t_1, t_2$ and deflection angle
$\theta = \arccos(t_1\cdot t_2)$, the joint plane passes through the
intersection point $P$ of the axes with normal

$$
n = \frac{t_1 + t_2}{\lVert t_1 + t_2\rVert}.
$$

Both cylinders cut this plane in the same ellipse.  Its semi-axes are $R$
(along $b = t_1\times t_2$) and $R/\cos(\theta/2)$ (in the bend plane).  A
point on the incoming pipe surface projects onto the plane along $t_1$:

$$
x_\text{plane} = x - \frac{(x - P)\cdot n}{t_1\cdot n}\,t_1 .
$$

**For hexmesh.**  The ellipse face is **internal** to a MiterBend fitting,
not an interface.  An interface must be a circular boundary normal to the
pipe axis (DESIGN A4), so the fitting's ports stay circular.  Each OH
corner keeps its angular position: on the plane, the corner at angle
$\varphi$ maps to $(R\cos\varphi\,/\cos(\theta/2),\; R\sin\varphi)$ in the
in-plane and $b$ directions.

The miter does not fit the current `Sweep` model.  `Sweep.validate`
rejects paths with `min_radius ≤ R` and chord slabs turning more than
`MAX_CHORD_TURN = 30°`, and station faces are assumed normal to the path.
A miter needs either an oblique-station concept in `Sweep` or its own
template.

### 2.4 Reducers

A concentric reducer has $R(s) = R_1 + (R_2 - R_1)\,s/L$.  An eccentric
reducer (flat on one side) also offsets the axis,
$e(s) = (R_1 - R(s))$ along the flat-side normal.  Both are fills between
two concentric interfaces with the same `n_outer` and layer stack.  Only the
radii differ, so the structured topology carries through unchanged.

---

## 3. Tee and lateral: the intersection curve

### 3.1 General branch (any angle, any offset)

Take the main (header) pipe along $x$ with surface $y^2 + z^2 = R^2$, and a
branch of radius $r$ whose axis passes through $(0, h, 0)$ in direction
$d = (\cos\alpha, 0, \sin\alpha)$.  Here $\alpha$ is the branch angle
($90°$ for a tee, $45°$ for a lateral) and $h$ is the axis offset.  With
$u = (-\sin\alpha, 0, \cos\alpha)$ and branch angle $\varphi$:

$$
P(\varphi) = h\,e_y + s(\varphi)\,d + r\cos\varphi\,u + r\sin\varphi\,e_y,
$$

$$
s(\varphi) = \frac{\sqrt{R^2 - (h + r\sin\varphi)^2} - r\cos\varphi\cos\alpha}{\sin\alpha}.
$$

It is valid for $|h| + r < R$ and $0 < \alpha \le 90°$.  This was checked
numerically: residual on both cylinder equations below $10^{-15}$ for
$R=1$, $r=0.4$, $h=0.2$, $\alpha=45°$.

**Special case: perpendicular, centred tee** ($\alpha=90°$, $h=0$):
$P(\varphi) = (r\cos\varphi,\; r\sin\varphi,\; \sqrt{R^2 - r^2\sin^2\varphi})$.

- Tips ($\varphi = 0, \pi$) sit at height $R$, at angle $0$ around the main
  axis.
- Sides ($\varphi = \pm\pi/2$) sit at height $\sqrt{R^2 - r^2}$, at angle
  $\pm\arcsin(r/R)$ around the main axis.

This is what `t_block.saddle_curve()` implements; see the θ_max note in
`CLAUDE.md`.

Derivations of the same curve: [`lloyd_2012`] (rotated axes, with offset
$h$), [`stockie_2015`] §3.1 (arbitrary joint angle; the original is in
MapleTech 1998).  The general theory of exact parametrization of
quadric–quadric intersections is in [`miller_1987`].

### 3.2 Consequences for block topology

- **Note (2026-10-29, decision 0031):** the side-corner split described
  in the next item is obsolete.  The block-layout tee (DESIGN §7.1) puts
  its saddle corners on the branch diagonals, so no sub-arc rule is
  needed.  The laterals-and-offsets item below still applies.
- **Tips and sides are not equivalent.**  For a perpendicular tee the
  tips land on main-pipe angle $0$, which is a structural corner when
  `n_outer = 8`.  The sides land at $\pm\arcsin(r/R)$, which is generally
  not a corner and not a transfinite node.  Making the side corners
  conformal means splitting the main pipe's outer arc at $\pm\arcsin(r/R)$
  in the topology layer.  The split angles depend only on $r/R$, so they
  can be computed before GMSH.  The split happens inside the tee
  template (DESIGN §7).  The template still needs a fixed rule assigning
  divisions to each sub-arc from the global `nang` (DESIGN A5); that rule
  is not defined yet.
- **Laterals and offsets** move both tips: tip angle around the main axis
  is $\arcsin(h/R)$, and the tip positions along $x$ become asymmetric
  ($s(0) \ne s(\pi)$ when $\alpha \ne 90°$).  The approach and departure
  T-zone steps then have unequal length.
- **The saddle edge between corners** is the curve $P(\varphi)$ above.
  Using it as the edge definition (sampled into a spline, as now) keeps the
  stub block exact for any $\alpha$ and $h$.

---

## 4. Y-junctions and n-furcations: published block topologies

Two recent papers build structured, all-hex bifurcations from centrelines
and cross-sections alone.  Both arrive at an explicit dividing surface
between daughter branches: the design Stage 6 is aiming for.

### 4.1 Separation-plane decomposition [`decroocq_and_frindel_etal_2023`]

**Geometry model** (after Zakaria).  Five cross-sections, each given by a
centre, radius and normal: inlet $C_0$, apical sections $AC_1, AC_2$ at the
apex $AP$, and outlets $C_1, C_2$ about one diameter downstream.  The radius
is linear along each centreline spline, and the apex is rounded with a
constant radius of curvature.

**Decomposition.**  The junction is split into one inlet and two outlet
branches by **three separation half-planes**.  They are defined by five
points:

- $AP$, the apex.
- $X$, the barycentre of $AP$ and the projections $pm_1, pm_2$ of the
  points where each centreline exits the other vessel.
- $SP_1, SP_2$: $X$ projected onto the surface, away from $AP$.
- $CT_0, CT_1$: $X$ projected onto the surface along the normal of the
  plane $(AP, SP_1, SP_2)$.

The three half-planes share the line $CT_0 \to X \to CT_1$.  Placing $X$ at
the barycentre pulls the split towards the smaller vessel, which keeps
plane angles moderate when the radii differ a lot.

**Cross-section template.**  The section node count $N$ must be a
multiple of 4 (they use $N=24$).  End sections start from a reference
vector chosen to minimize rotation relative to $SP_{1,2}$.  Separation
half-sections are sampled equally along the arcs $AP\!\to\!CT$ and
$SP\!\to\!CT$.  The interior is an O-grid: boundary, intermediate and
centre regions with radial fractions 0.2/0.3/0.5.

**Volume.**  Sections are swept from each end to its separation planes.
The hex volumes meet at the planes as $n+1$ half-grids.  A planar
$n$-furcation uses $n+1$ separation planes.  They finish with 5 Laplacian
relaxation steps plus radial reprojection; hexmesh should not copy this
step (see 4.4).

### 4.2 Hermite-curve butterfly [`marcinno_and_hinz_etal_2025`]

**Anchors.**  Each end section (inlet and two outlets) has four anchors at
$\theta_i = i\pi/2$ plus its centre.  The inlet frame takes
$n_\text{in} = (t_1\times t_2)$ projected onto the inlet plane.  Outlet
frames come from a discrete rotation-minimizing transport (§1).

**Hermite curves** join matching anchors $p, q$ of two branches:

$$
C(t) = H_{00}(t)\,p + H_{01}(t)\,\lVert p - q\rVert\,m_1 + H_{10}(t)\,q + H_{11}(t)\,\lVert p - q\rVert\,m_2
$$

The end tangents $m_{1,2}$ are the section normals.  Twelve curves are used
(right/left, top, centre and bottom anchors for each of three branch
pairs).  At $t=\tfrac12$ they give $SP_1, SP_2, AP$ and three collinear
points $X_\text{top}, X_\text{center}, X_\text{bottom}$.

**Butterfly (dividing face).**  Six ellipse quadrants centred at
$X_\text{center}$ make three petals, one per branch pair.  With
$x = SP_2 - X_c$, $y = SP_1 - X_c$, $z = AP - X_c$, $r = X_\text{top} - X_c$ and
$l = X_\text{bottom} - X_c$, the quadrants are $e(\lVert x\rVert,\lVert r\rVert)$,
$e(\lVert x\rVert,\lVert l\rVert)$, and likewise for $y$ and $z$.  Each is
placed by the rotation $[x, r]$, $[y, r]$ or $[z, r]$ plus $X_c$.

**Volume map.**  The inlet section $\Omega_\text{in}$ is blended to its
butterfly face by a Hermite map in $t$:

$$
V(r_1, r_2, t) = H_{00}(t)\,p + H_{01}(t)\,t_\text{in} + H_{10}(t)\,q + H_{11}(t)\,t_{BF}(r_1, r_2)
$$

$t_{BF}$ blends $H_1'(\tfrac12)$, $X_c - P_C^\text{in}$ and $H_2'(\tfrac12)$
with hat functions across the petal.  There is no smoothing step.

**Generalization.**  With $n_b$ branches, there are $4n_b$ Hermite curves
and $2n_b$ ellipse quadrants.  $C^1$ continuity at the centre point is lost
for $n_b = 5$.

**Reported quality** for a bifurcation of about 64k nodes:

| Mesher | min scaled Jacobian | mean | max NES |
|---|---|---|---|
| This method | 0.488 | 0.907 | 0.634 |
| VMTK | 0.078 | 0.627 | 0.883 |
| gmsh (unstructured) | 0.080 | 0.564 | 0.890 |

Worst cells sit at the extraordinary vertices next to the butterfly.  The
authors suggest targets of min scaled Jacobian > 0.6 and normalized
equiangular skewness

$$
\text{NES} = \max\!\left(\frac{\theta_\max - 90°}{90°},\;\frac{90° - \theta_\min}{90°}\right) < 0.5 .
$$

### 4.3 Earlier and related work

- [`zhang_and_bazilevs_etal_2007`]: the first skeleton-based decomposition
  of vessel trees into **branching templates**, each a mapped (sweepable)
  patch.  Conceptually the same as hexmesh's fitting block templates.
- [`desantis_and_debeule_etal_2011`]: structured, conformal bifurcation
  meshes from triangulated surfaces using cutting planes.  It treats the
  bifurcation as planar.
- [`livesu_and_muntoni_etal_2016`]: skeleton-driven hex meshing of
  tubular shapes, including junctions of higher valence: an octopus with
  eight limbs meeting at one point, without high-valence vertices.  Full
  text read 2026-10-28.  Relevant to crosses and multi-branch headers,
  and its refinement "cones" to density changes (§9.4).
- [`pietroni_and_campen_etal_2023`]: survey.  For tubular domains it
  concludes that the hard part is splitting the domain into sweepable
  sub-volumes, not meshing them.

### 4.3b Wall exactness at the wye's crease (task 0051, 2026-10-29)

With node projection (decision 0029) every wye wall node is on the
canal surface to 1e-15 R.  The remaining error is the chord across the
crease, where faces cut across it:

| `nang` | wye 60° | wye 90° |
|---|---|---|
| 4 | 2.9 % R | 3.2 % R |
| 8 | 0.95 % R | 0.88 % R |
| 16 | 0.26 % R | 0.24 % R |
| 32 | 0.07 % R | 0.06 % R |

- **Second order in `nang`, and under decision 0029's 1 % threshold at
  `nang` 8**, so no layout change for now.  The crease would be exact
  only on block edges (the separation half-planes of §4.4).  Revisit if
  a wye validation case is sensitive at the crotch.
- **Nearest-point projection folds the crotch:** the filled face is a
  sharper V than the wall.  A smoothed-normal projector (`TubeUnion`)
  avoids it.
- **The knee:** the hub's spherical cap was resolved by `n_run` only,
  with chords of 8–10 % R at any `nang` (task 0056).

### 4.4 What this means for Stage 6 (Y-junction redesign)

1. **The dividing surface is an internal block face.**  Both papers make
   the faces between daughter branches explicit and build them first.  In
   hexmesh terms each separation half-plane, or butterfly petal, is a face
   shared between the wye's internal blocks through the DESIGN §6.1 block
   registry.  It is not an assembler interface: DESIGN §7 keeps junction
   internals private, and only the three branch ends are interfaces.  That
   removes the need for `occ.fragment()` and bbox recovery.
2. **The split must land on corners.**  Decroocq needs $N \equiv 0
   \pmod 4$, and Marcinnó anchors at $i\pi/2$.  Both need structural
   corners at $0°, 90°, 180°, 270°$ in the branch frame.  `n_outer = 8`
   provides these.  But so does `n_outer = 4` with the interface roll
   offset by $\pi/4$: corner $k$ lies at $\pi/4 + \text{rot} + k\pi/2$
   (DESIGN §6.1).  Marcinnó reaches min SJ 0.49 on a 5-patch section with
   no fragment step.  That suggests the old SICN ≈ 0 seam came from
   `occ.fragment()`, not from `n_outer = 4`.  Whether `n_outer = 8` gives
   better cells at the extraordinary vertices is untested.
3. **Geometry recipe.**  Use Decroocq for the topology (which faces exist,
   how $X$, $SP$ and $CT$ are placed) and Marcinnó for the geometry
   (Hermite edges between anchors, elliptic petal edges).  Both are closed
   form, so the whole junction can be validated before GMSH.
4. **No smoothing.**  Decroocq's Laplacian relaxation contradicts "fail
   before meshing" and moves interface nodes.  Marcinnó shows explicit
   placement is enough for min SJ ≈ 0.5.
5. **n-furcations.**  The same construction with $n+1$ planes (or $n_b$
   petals) covers planar trifurcations and crosses.  Per DESIGN §6.1 ("not
   built on speculation"), wait for working tee and wye templates before
   generalizing.
6. **Quality limits.**  Marcinnó's suggested min SJ > 0.6 is above their
   own best bifurcation (0.49).  A hard global limit would reject the best
   published result.  This bears on DESIGN §10 "Reject or degrade?":
   consider limits set per fitting, or a warning at junctions.  Metric
   definitions and a flow-validation case are in §7.

---

## 5. Filling blocks between fixed boundaries

**Transfinite interpolation** [`gordon_and_hall_1973a`,
`gordon_and_hall_1973b`].  For a block with known boundary faces (or
edges), the Boolean-sum (Coons) interpolant fixes every interior point.  In
2-D, with edges $c_{0,1}(u)$, $d_{0,1}(v)$ and corners $P_{ij}$:

$$
x(u,v) = (1-v)\,c_0(u) + v\,c_1(u) + (1-u)\,d_0(v) + u\,d_1(v)
       - \big[(1-u)(1-v)P_{00} + u(1-v)P_{10} + (1-u)vP_{01} + uvP_{11}\big]
$$

The 3-D form adds face terms and subtracts edge terms, then adds back
corner terms.  gmsh's transfinite meshing is this interpolant.  It
formally justifies "fittings are fills": once the interfaces and fitting
edges are fixed, the interior needs no further geometric decisions.

**Elliptic (Winslow) smoothing** [`winslow_1966`].  It solves the inverse
Laplace equations for the computational coordinates, and it fixes TFI
fold-over near extraordinary vertices.  hexmesh should not adopt it.  It
runs after point placement and moves nodes, which conflicts with DESIGN
A2 (port faces untouched) and with "a network that passes step 3 must
mesh".  If it is ever needed, it may only move nodes inside a single
fitting, with port and wall nodes pinned.  Better corner placement in the
block template is the preferred fix.

---

## 6. Default branching angles (optional)

Murray's law ($r_0^3 = r_1^3 + r_2^3$) and its angle extension
[`zamir_1976`] give optimal bifurcation angles for transport networks.
[`lubashevsky_and_gafiychuk_1999`] (arXiv preprint, read 2026-10-28)
shows two optimality principles leading to Murray's law are equivalent:
minimum work to maintain the flow, and minimum drag and lumen volume.
It also derives the law from flow redistribution in a symmetric
microcirculatory tree.  Useful for default radius ratios when hexmesh
generates idealised vascular trees (decision 0018).  A
closed form for a symmetric Y is in [`bennett_2025`]:
$\cos(\theta/2) = 2^{(m-p)/(m+p)}$, which tends to the Steiner angle
$120°$ as $m\to 0$.  These apply to biological and fluidic trees.
Industrial wyes and laterals use catalogue angles ($45°$, $60°$, $90°$).

---

## 7. Validation and quality metrics

### 7.1 Quality indicators [`sorgente_and_biasotti_etal_2023`]

This survey covers quality indicators for simplicial, quad/hex and
polytopal elements: aspect ratio, skew, taper, warpage, Jacobian-based
measures, and condition number.  For hexahedra, the Jacobian family in its
§4 is the relevant one.  At the corners $i$ of an element, with corner
Jacobian matrices $A_i$:

$$
\varsigma_3 = \frac{\min_i J_i}{\max_i J_i},\qquad
\varsigma_4 = \min_i \frac{J_i}{h_{e_{i-1}}\,h_{e_i}}
$$

The second is the **scaled Jacobian** [Knupp] used in §4.2.  Indicators
based on the condition number $\kappa(A_i)$ measure distortion
independently of size.  Most indicators are implemented in the Verdict
library (also exposed through Cinolib and HexaLab).  gmsh implements only a
subset.  The survey also stresses that a-priori geometric indicators
correlate only partly with solver accuracy.  That argues for checking
hexmesh output against a flow benchmark as well as against cell metrics
(§7.2).

**For hexmesh.**  SICN (gmsh), scaled Jacobian and NES measure different
things.  Name the metric in every quality limit, and compute them the way
Verdict does, so numbers can be compared with published meshes.

### 7.2 Equal-diameter T-junction benchmark [`stigler_and_klas_etal_2014`]

The paper reports measured and computed pressure-loss coefficients for
**equal-diameter** T-junctions with branch angle
$\gamma \in \{30°, 45°, 60°, 75°, 90°\}$, extended to $105°$–$150°$ by
exchanging branches.  It covers six flow configurations per angle
(dividing and combining), with coefficients given as functions of the
flow-rate ratio.  It uses Miller's loss-coefficient definition, e.g.

$$
K_{31} = \frac{\left(\frac{v_3^2}{2g} + h_3\right) - \left(\frac{v_1^2}{2g} + h_1\right)}{\frac{v_3^2}{2g}}
$$

and introduces a new model with geometry coefficients fitted to
experiment.  Their CFD used an all-hex GAMBIT mesh of about 2.3 M cells,
worst EquiAngle skewness 0.51 (the same formula as NES in §4.2), and the
realizable $k$–$\varepsilon$ turbulence model.  The paper gives no block
topology or mesh-construction details.

**For hexmesh.**

- It is a ready OpenFOAM validation case for the lateral template
  (§3.1): loss coefficients against branch angle test the mesh where it
  matters for CFD.
- It targets the equal-diameter tee ($r = R$), which `TJunction`
  currently rejects.  It is the natural acceptance test when that case is
  built.
- Its worst skewness of 0.51 shows an industrial all-hex equal-diameter
  tee lands right at the NES < 0.5 target of §4.2.

### 7.3 Smooth axisymmetric constriction (stenosis) benchmark [`varghese_and_frankel_etal_2007`]

**Geometry.**  A straight pipe of diameter $D$ with a cosine-shaped
constriction centred at $x_0$:

$$
R(x) = \frac{D}{2}\left[1 - s_0\left(1 + \cos\frac{2\pi(x - x_0)}{L}\right)\right],
\qquad |x - x_0| \le L/2
$$

With $s_0 = 0.25$ the throat radius is $D/4$: 50 % radius and 75 % area
reduction.  **$L = 2D$** (paper eq. 2.1; preprint in `docs/papers/`,
read 2026-10-28).  Domain: 3 D upstream and 16 D downstream of the
throat; parabolic inlet profile.

**Eccentric model** (eq. 2.2): the stenosis axis is offset by
$E(x) = \frac{s_0}{10}\left(1 + \cos\frac{2\pi(x - x_0)}{L}\right)$,
i.e. 0.05 D at the throat, in one plane.

**Reference data.**
- DNS of steady inlet flow (Part 1) at **Re = 500 and 1000** (not 750).
  - **Axisymmetric, Re 500:** laminar and steady; the peak velocity just
    after the throat exceeds 4 u_m, the flow reattaches at about
    x ≈ 10 D, and the peak is still above 3 u_m at 15 D.  Results are
    given as figures only: profiles at x/D = −2…15 (fig. 4).
  - The Ahmed & Giddens (1983a) experiment reattaches earlier (4–6 D);
    the authors attribute this to incomplete laminarity.
  - **Eccentric, Re 500:** laminar but asymmetric; the jet deflects
    toward the eccentric side and reattaches at about 14 D.
  - **Eccentric, Re 1000:** transitions to turbulence after about
    4–6 D and reattaches by about 10 D.
  - The local copy is the 2005 preprint; cite the 2007 article.
  - **Purdue database** (Axi_stdy/Re500, fetched 2026-10-28; no
    licence, not committed): radial velocity profiles at x/D = −2…15,
    no wall shear stress.  Peak centreline 4.596 u_m at x = 0;
    reattachment ≈ **11.0 D**, from the sign change of the near-wall
    axial velocity at r = 0.48 D.  The paper's text says ≈ 10 D.
  - **The whole database** (surveyed 2026-10-29, design session; every
    file downloads; Tecplot ASCII, one zone per station; normalised by
    u_i = 0.5; no licence statement, so download at run time and never
    commit):

    | Case | Files | Stations |
    |---|---|---|
    | axisymmetric steady, Re 500 | `Axi_stdy/Re500/vel.dat`: r, u, v, w; 101 radial points | x/D −2…15 |
    | axisymmetric steady, Re 750 and 1000 | `Axi_stdy/Re750/vel.dat`, `Re1000/vel.dat`: r, z, u, v, w; 501 points | x/D −2…15 |
    | axisymmetric pulsatile, mean Re 600 | `Axi_puls/vel_p1…p6.dat`: velocity at 6 phases | x/D −2…15 |
    | eccentric steady, time-averaged | `Ec_stdy_Re2000/{XZ,XY}-plane/timeavg_{vel,rms,tke}_*.dat` | x/D −2…22 |
    | eccentric pulsatile, mean Re 600 | `Ec_puls/{XZ,XY}-plane/phaseavg_{vel,tke}_*_p1…p6.dat` | x/D −2…22 |

    - **The eccentric steady case's Reynolds number is ambiguous:** the
      page says Re 1000, the folder `Re2000`.  The paper's transitional
      eccentric case (the one with RMS and TKE) is Re 1000, so the folder
      name is probably a mislabel.  Confirm before use.
    - **The pulsatile case** [`varghese_and_frankel_etal_2007b`]
      (Part 2; the 2005 preprint is in `docs/papers/`, read
      2026-10-29):
      - **Geometry:** the same as Part 1: cosine stenosis, s₀ = 0.25,
        L = 2D, 3D upstream and 16D downstream of the throat.
      - **Inlet:** the Womersley solution, eq. 2.1,
        u/u_c = (1 − r²) + A·[1 − J₀(i^{3/2} α r)/J₀(i^{3/2} α)]·sin(ωt)
        (r = r/R).  **As printed the oscillatory term is complex times
        sin(ωt); read it as A·Im{[1 − J₀(i^{3/2} α r)/J₀(i^{3/2} α)]
        e^{iωt}}.**  That reading gives a centreline of 0.337–1.663 u_c,
        peaking at t/T = 0.255: matching the text's "minimum and maximum
        Reynolds of approximately 200 and 1000" and the timing of
        fig. 1 (fig. 1 read by eye is about 5 % wider).
      - **Parameters:** α = (D/2)√(ω/ν) = 7.5; A = 0.667.  **Re = 600
        on D and the mean *centreline* inlet velocity u_c** (bulk-velocity
        Re 300: not Part 1's convention).  So with D = u_c = 1,
        ν = 1/600, ω = 4α²ν/D² = 0.375 and T = 2π/ω ≈ 16.76 time units.
      - **Data:** six phases at intervals of T/6; from fig. 1, about
        t/T ≈ 0.09 + k/6 (T1 … T6, read by eye, ±0.01), with T2 at peak
        flow and T5 at minimum.  The database's `vel_p1…p6` are taken to
        be T1 … T6 (to confirm against the phase-averaged profiles).
      - **Method:** spectral elements K = 1600, N = 9; Δt = 1e-3;
        started from the steady Re 500 solution; a periodic state after
        the initial transients left the domain.
      - **Result:** the axisymmetric model stays laminar.  Upstream
        profiles match Womersley; peak throat velocity above
        3.65 u_c.
 `simpleFoam` / SIMPLEC plateau and
    leave the converged state.  Transient `pimpleFoam` reaches steady
    in 10–20 time units.  The coarsest hexmesh level (`nang` 6,
    15 k cells) has no steady axisymmetric state: the jet drifts off
    axis, a resolution artefact.  The medium level (123 k cells) gives
    reattachment 11.12 D (+0.9 %).
- The [Purdue CFD Lab database](https://engineering.purdue.edu/CFDLAB/DNS_stenoticflow_database/main.html)
  covers the axisymmetric and an eccentric model.
- Part 2 (JFM 582:281–318) covers pulsatile flow.
- [`griffith_and_leweke_etal_2008`] (read 2026-10-28, PDF in
  `docs/papers/`) studies a **different** geometry.  It is not the cosine:
  a blockage **semicircular in cross-section**, set by the stenosis degree
  b = 1 − (d/D)² (by area), with blockage radius r_b = (D/2)(1 − √(1 − b)).
  - **Range:** Re 50–2500, b 0.2–0.95.  Poiseuille inlet; axisymmetric
    spectral-element base flows, linear stability analysis, and dye
    experiments in water.
  - **The recirculation length L_R** (where the wall shear stress is 0)
    grows linearly with Re for every b, and collapses with
    L_R/D = C · [(1 − b/2)/(1 − b) − 1/√(1 − b)] · Re (eq. 4.3; the
    analogy is a cylinder wake).
  - **Converged values** (Table 1, polynomial order 9): L_R/D = 7.356
    (b = 0.5, Re = 2000), 18.38 (b = 0.75, Re = 800), 41.40 (b = 0.9,
    Re = 500).  These are tabulated numbers good to four digits, unlike
    Varghese's figures.
  - **For hexmesh:** a possible second laminar stenosis case.  It needs a
    semicircular profile, whose wall meets the tube at a right angle (a
    vertical tangent at the blockage ends).  A smooth R(x) sweep can't
    follow that without clustering stations at the ends; it would need a
    named `("semicircle", b)` profile with end clustering (not planned).
- Background: experiments with the same smooth cosine stenosis (Cassanova
  & Giddens 1978, cited by Griffith et al.; not checked).

**Local prior work.**  `../geometry_valve/` (a 2018 gmsh `.geo` model)
builds this profile as $R(x) = R\,[1 - \tfrac{f_0}{2}(1 + \cos(2\pi(x -
x_0)/L))]$, with $f_0 = 0.5$ (same as $s_0 = 0.25$).  But it uses
$L = D$, not $2D$.  Its old `mesh.msh`, checked 2026-10-24:
16,653 hexes, 17,856 nodes, no duplicated node positions.  It is
conformal, but only because the old `.geo` kernel merges coincident
points, which DESIGN P2 rules out for hexmesh.  Its topology keeps a
**constant-radius core square** (radius half the throat radius) and lets
only the ring follow $R(x)$.

**For hexmesh.**
- A good **first OpenFOAM validation case**: one axisymmetric fitting,
  laminar to transitional, with public high-fidelity data.  It is
  simpler than the tee benchmark (§7.2).  Natural after task 0005
  (OpenFOAM-readable output).
- It needs a varying-radius sweep (decision 0008, proposed).  The
  current `Reducer` handles only a linear $R(s)$.

### 7.4 Laminar Hagen–Poiseuille verification (task 0020)

Measured 2026-10-26: hexmesh `82147f4`, gmsh 4.12.1, OpenFOAM v1912.
D = 0.02 m, Re = 100, 30 D long, Δp measured from 15 D to 25 D.  Three
levels: `nang` 6/12/24, `nrad` 3/6/12, 48/96/192 axial cells (5 184 /
41 472 / 331 776 cells).  Full tables: `validation/poiseuille/RESULTS.md`.

**Finding 1: plate-filled straight walls are not exact.**
- Δp error stuck at **+2.59 / +2.63 / +2.60 %**: it doesn't converge.
- Cause: a multi-layer `Straight` slab has OCC plate side surfaces, and
  gmsh puts the interior nodes on them.
  - Single-layer pipe: up to **1.08 % of R** inside the circle.
  - Two-layer pipe, 16 layers (design session check): −0.15 % to
    +0.69 % of R, on the outer wall and on the fluid/steel interface
    alike, the same at `nang` 6 and 24.
- The sagged cross-section's area predicts the measured Δp within 0.1 %
  (Δp ∝ 1/A² at fixed Q).
- Ruled side surfaces (`addBSplineFilling(type="Stretch")`) put the
  nodes on the cylinder to 4e-16 R.  Decision 0015 makes them the rule
  (DESIGN §6).

**Finding 2: with exact walls, the remaining error is two errors of
opposite sign.**  Diagnostic run, ruled walls patched in:

| Level | Δp error | inlet-flow deficit | polygon area deficit | Δp geometric part | remainder |
|---|---|---|---|---|---|
| coarse | +0.451 % | 1.138 % | 1.138 % | +1.151 % | −0.692 % |
| medium | +0.207 % | 0.285 % | 0.285 % | +0.286 % | −0.079 % |
| fine | +0.104 % | 0.071 % | 0.071 % | +0.071 % | +0.033 % |

- The mesh's cross-section is the inscribed $N$-gon, $N = 4\,$`nang`, with
  area deficit $1 - \frac{N}{2\pi}\sin\frac{2\pi}{N} \approx
  \frac{(2\pi/N)^2}{6}$.  The measured inlet-flow deficit (uniform
  inlet U) equals it to four digits.  Every finite-volume mesh with flat
  faces between wall nodes has this second-order error.
- At fixed inlet velocity, Δp ∝ 1/A, which gives the "geometric part"
  column.  The remainder is the discretisation error; it shrinks fast
  and changes sign between medium and fine.
- So the order from |e| against the circle (1.12, 0.99) means nothing.
  Richardson extrapolation of the three levels
  [`celik_and_ghia_etal_2008`]:

  | Quantity | observed order | extrapolated error |
  |---|---|---|
  | Δp | 1.25 | +0.030 % |
  | u_max (fitted centreline) | 1.91 | −0.007 % |

- Both converge to the exact solution.  u_max, which no competing
  geometric error affects, converges at about second order.

**Mesh metrics.**  min scaled Jacobian 0.79 / 0.75 / 0.73.  Max
non-orthogonality 23 / 33 / 38°, max skewness 0.43 / 0.48 / 0.51.  At an
inner-square corner of the O-H section the angles are 90° / 135° / 135°,
and refinement resolves that kink more sharply.  The maxima are expected
to level off near the kink's limit (about 45° non-orthogonality); not
yet measured.  If they don't, inner-square sizing (`OH_RATIO` = 0.6) and
bulged inner-square sides are the levers.

**For hexmesh.**
- Judge verification cases by signed errors against a reference for the
  meshed geometry, plus Richardson extrapolation (decision 0015).
- A uniform inlet into a polygonal section delivers less flow than
  Ū·πR².  Compare against the flow actually delivered.

### 7.5 Analytic validation cases: planned and tasked

Exact solutions that each test a specific part of hexmesh.  Judged by
signed errors and Richardson extrapolation (decision 0015,
[`celik_and_ghia_etal_2008`]); post-processing in Python, since function
objects abort on the local OpenFOAM build (`docs/integrations/openfoam.md`).

| Case | Exact result | Tests in hexmesh | Status |
|---|---|---|---|
| Hagen–Poiseuille | $\Delta p = 32\nu\bar U L/D^2$, $u_\max = 2\bar U$ | straight pipe, O-H core | task 0020 (§7.4) |
| Rod with uniform heat generation | $T = T_w + q'''(R^2 - r^2)/4k$ | O-H core, pure diffusion (no p–U coupling) | task 0033 |
| Heated rod with cladding (solids) | series resistances $\sum \ln(r_{i+1}/r_i)/2\pi k_i$, log profiles | layer stack, interfaces, `mappedWall` coupling | task 0034 |
| Heated multi-layer pipe, laminar | $dT_b/dx = q'/\dot m c_p$; Nu = 48/11 (uniform flux); log profiles | full CHT | task 0035 |
| Smooth cosine constriction | DNS data (§7.3) | profiled reducer | task 0032 (Re 500; Re 750 and 1000 as a follow-up step) |
| Pulsatile flow through the cosine stenosis, mean Re 600 (centreline-velocity Re) | Purdue DNS, velocity at 6 phases; inlet from [`varghese_and_frankel_etal_2007b`] (§7.3) | first time-dependent validation; vascular direction (decision 0018) | task 0068 (after 0067 and 0032) |
| Eccentric stenosis, steady (Re 1000, transitional) and pulsatile | Purdue DNS: mean, RMS, TKE in two planes (§7.3) | off-centre cores (decision 0021, stage 3); transitional flow | future: needs eccentric outlines and transition-resolving runs |
| Fully developed turbulent pipe | friction factor [`mckeon_and_zagarola_etal_2005`]; DNS profiles [`el_khoury_and_schlatter_etal_2013`] (Re_τ 180–1000) | wall grading for RANS (y⁺), k-ω SST | task 0049 |
| Turbulent 90° bend | hot-wire profiles, Re 6 × 10⁴ [`sudo_and_sumida_etal_1998`] | `Bend` in turbulent flow; basis for loss-coefficient studies | task 0050 |
| Uniform wall temperature | Nu = 3.66 | as 0035, wall BC variant | planned |
| Graetz problem | series solution for local Nu(x) | axial resolution and grading near an inlet | planned |
| Annular Poiseuille (solid core, fluid shell) | $u = \frac{G}{4\mu}\left[R_2^2 - r^2 + (R_2^2 - R_1^2)\frac{\ln(r/R_2)}{\ln(R_1/R_2)}\right]$ | a fluid region in a shell layer | planned |
| Taylor–Couette | $u_\theta = Ar + B/r$ | circumferential resolution in shells | planned |
| Rectangular duct | Fourier series; $f\,Re \approx 56.9$ for a square ($D_h$) | rectangular sections (task 0028) | task 0071 |
| Laminar 90° square bend, Re 790 | LDA profiles (Taylor, Whitelaw & Yianneskis 1982; §7.8) | duct bends | task 0072 |
| Circle-to-rectangle transition duct (turbulent) | Davis & Gessner 1992 (§7.8) | `Transition` | planned, after 0049 |
| Square-duct turbulence | KIT DNS (Pinelli et al. 2010; §7.8) | straight ducts; tests the turbulence model | planned, later |
| Dean flow, weak curvature | Dean's perturbation for the flow reduction at small Dean number (check coefficients against the source) | `Bend` | planned |
| Womersley flow | Bessel-function velocity profile | transient runs, the time-varying inlet; vascular direction (decision 0018) | task 0067 |
| Fusiform aneurysm (symmetric bulge) | in-vitro PIV wall shear stress for growing symmetric AAA models [`salsac_and_sparks_etal_2006`] (pulsatile; open access via UCL Discovery) | cosine profile with s0 < 0 (task 0055); vascular direction (decision 0018) | planned, after 0055 |

Order: 0033 → 0034 → 0035 (each reuses the previous one's setup).  The
planned cases get tasks when their fitting exists or the area is in
focus.

### 7.6 Heated rod: convergence order of the O-H section (task 0033)

Measured 2026-10-27: hexmesh `d71d0d8`, gmsh 4.12.1, OpenFOAM v1912.
Steady conduction with uniform generation, $T = T_w + q'''(R^2 -
r^2)/4k$; the same Poisson problem as Poiseuille, without p–U coupling.
Two series (uniform, wall-graded), `nang`/`nrad` 6/3 → 48/24.  Full
tables: `validation/heated_rod/RESULTS.md`.

| Series | L2 order per refinement | ΔT₀ order | extrapolated ΔT₀ − exact | GCI fine |
|---|---|---|---|---|
| uniform | 1.77, 1.57, 1.34 | 1.58, 1.38, 1.22 | −0.020 % | 0.070 % |
| graded | 1.70, 1.61, 1.31 | 1.62, 1.45, 1.25 | −0.026 % | 0.075 % |

- Values converge to the exact solution; the **order falls** with
  refinement instead of approaching 2.
- Slowest in the **core square** (order 1.23 at k = 4 → 8; ring 1.41,
  ring near the diagonals 1.73).  The error is a near-uniform negative
  bias.
- Max non-orthogonality 23.5 / 33.2 / 38.9 / 41.9°, the worst faces
  moving onto the core-square corners (r/R 0.50 → 0.59), so the §7.4
  expectation that it levels off near 45° holds; the mesh family is not
  self-similar at those corners.
- Together with Poiseuille's Δp order 1.25 (§7.4), this suggests the O-H
  family converges at about 1.3–1.5 for `Gauss linear corrected`
  (correlation, cause unproven).

**For hexmesh.**  Order reported, not gated, on O-H sections; GCI with
the observed order (decision 0015, amended).  Whether the order levels
off: the k = 16 level (task 0033).  Corner-free control and a
self-similar core square: decision 0022 (proposed).

### 7.7 Build time (task 0036)

Measured 2026-10-27 on an idle machine (`benchmarks/build_time.py`,
serpentine of `Straight` + `Bend(180)` pairs, `nang` 4, one layer).

| volumes | cells | `synchronize` calls before → after | total s before → after | speed-up |
|---|---|---|---|---|
| 70 | 1 280 | 136 → 4 | 3.28 → 1.27 | 2.6× |
| 280 | 5 120 | 520 → 4 | 29.4 → 4.79 | 6.1× |
| 1 050 | 19 200 | 1 928 → 4 | 340.0 → 19.8 | 17.2× |
| 2 100 | 38 400 | — → 4 | — → 50.0 | — |

- Growth exponent of total time vs volumes: 1.73 before, **1.03** after
  (70–1050 volumes); 1.07 including 2100.
- `synchronize` is now called 4 times per assembly, 0 per fitting;
  hexmesh records the end points and kinds of the curves it creates
  instead of reading the model back.
- Remaining super-linear term: `occ.remove` of construction points,
  whose cost per point grows with the model (19.7 s for 2900 points at
  2100 volumes).
- B-spline "Stretch" side faces cost 1.6 ms against 6.4 ms for a plate
  filling, with identical meshes on one-layer slabs.
- `pipe_rack`: 61.7 s → 6.2 s.  Test suite: 687 s → 328 s.
- Facts about OCC/gmsh synchronization: `docs/integrations/gmsh.md`.

---

### 7.8 Duct validation references (surveyed 2026-10-30, design session)

For hexmesh's rectangular sections (task 0028), duct bends,
circle ↔ rectangle transitions (task 0029) and duct taps (task 0070).
Category labels as decision 0012's amendment (V1 exact, V2
high-fidelity simulation, V3 experiment, V4 correlation).

- **V1: fully developed laminar flow in a rectangular duct.**  The
  Poisson problem for the axial velocity in a rectangle has an exact
  Fourier series.  Shah & London (1978) compile f·Re and Nu against
  aspect ratio; f·Re ≈ 56.9 for a square on the hydraulic diameter.  The
  polynomial fits quoted in handbooks are fits; compute the series
  ourselves (task 0071).
- **V3: laminar and turbulent flow in a 90° square bend.**
  - **Source:** Taylor, Whitelaw & Yianneskis, *J. Fluids Eng.* 1982,
    and NASA contractor report (NTRS 19820016574).  Imperial College
    water tunnel.
  - **Geometry:** hydraulic diameter 40 mm, mean bend radius 92 mm
    (R/D_h ≈ 2.3), thin inlet boundary layers after a straight section.
  - **Data:** laser-Doppler profiles at **Re 790 (laminar)** and 40 000
    (turbulent), through and after the bend.
  - **Companions:** an S-duct (two 22.5° sectors), and a laminar
    strongly curved square duct (Humphrey, Taylor & Whitelaw, *JFM*
    1977).
  - **Note:** later CFD agreed qualitatively, less well at 60° and 77.5°
    (secondary sources).  Task 0072 uses the laminar case.
- **V3: circle-to-rectangle transition duct.**
  - **Source:** Davis & Gessner (NASA TM 105210, 1991; *AIAA J.* 30,
    1992).
  - **Geometry and flow:** superellipse cross-sections, length 4.5 D,
    equal inlet and outlet areas, turbulent, Re 3.9 × 10⁵.
  - **Data:** static pressures, mean velocities and all six Reynolds
    stresses.
  - **Note:** the authors caution against standard wall functions.  A
    second-moment closure study matched the mean flow but not the
    downstream decay of the stresses.
  - Planned after the turbulent pipe (task 0049).
- **V2: turbulent square-duct DNS.**
  - **Source:** Pinelli, Uhlmann, Sekimoto & Kawahara, *JFM* 644, 2010;
    Uhlmann et al., *JFM* 588, 2007.
  - **Data:** KIT, `https://www.iwu.kit.edu/nfm/dns_data/duct/`:
    statistics binaries over a range of low bulk Reynolds numbers, a
    data sheet, friction factors.  No licence statement, so download at
    run time.
  - **Caution:** the secondary flows of the second kind are missed by
    linear eddy-viscosity RANS (k-ω SST included), so this tests the
    turbulence model more than the mesh.  A reference for later.
  - Rectangular-duct DNS by Orlandi & Pirozzoli (*J. Turbul.* 2020;
    arXiv 1907.07987) has no data release found.
- **V3/V4: duct T-junction loss coefficients.**  An Ohio State thesis
  (Christian) measured junctions with square, rectangular and oval side
  branches at several area and aspect ratios.  Its snippets say the
  losses are independent of Reynolds number and depend little on the
  branch shape.  Read before use; a comparison for duct taps (task
  0070), not a gate.  Handbook coefficients (ASHRAE Duct Fitting
  Database, Idelchik) are commercial or book-only: V4 comparisons.

## 8. Proposed hexmesh actions

| Area | Action | Source |
|---|---|---|
| Sweep frames (`Closure`, Spline pipe) | Replace the rotation-method transport with double reflection | §1 |
| `MiterBend` | Ellipse joint face internal to the fitting; decide oblique stations in `Sweep` vs. own template | §2.3 |
| Tee and lateral | Replace the perpendicular saddle with general $s(\varphi)$ (angle $\alpha$, offset $h$) | §3.1 |
| Tee side corners | Split main-pipe outer arc at $\pm\arcsin(r/R)$ inside the template; define the `nang` sub-arc rule | §3.2 |
| Y-junction (Stage 6) | Separation half-planes / butterfly as internal block faces; Hermite anchor edges | §4.4 |
| `n_outer` choice | Test whether `n_outer = 4` + π/4 interface roll suffices at the wye | §4.4 |
| Quality gates | Report min scaled Jacobian and NES next to SICN; set limits per fitting | §4.2, §4.4, §7.1 |
| Flow validation | OpenFOAM loss-coefficient runs for laterals (30–90°) against the Štigler data; acceptance test for equal-diameter tee | §7.2 |
| `n_outer` | Define `n_outer = 8` as a sub-partition of the 4-corner grid; check node connectivity is unchanged | §9.2 |
| Density change | Refinement-transition fitting (×2 per direction) or declared non-conformal break; design decision first | §9.3–9.4 |
| Local refinement | Single-sheet (pillow) insertion inside a fitting, ending on the outermost wall; ports unchanged | §9.5 |
| Port-face compatibility | Classify port-face pairs (classes 0–3) by mesh signature in `validate()`; decision 0011 (proposed) | §9.6 |
| Stenosis benchmark | Varying-radius sweep (decision 0008); OpenFOAM validation against the Varghese/Purdue data | §7.3 |

---

## 9. Changing topology along a network

What can change between two interfaces of a network, and at what cost.
Organized by the dual view of a hex mesh from
[`harris_and_benzley_etal_2004`].

### 9.1 The dual view: twist planes and hex sheets

Every hex is the intersection of three **twist planes**, the surfaces of
the mesh's dual (the "spatial twist continuum").  The cells cut by one
twist plane form a **hex sheet**.  In 2-D the planes reduce to **chords**,
each running through one row or column of quads.  A twist plane either
ends on the domain boundary or closes on itself.  It cannot end inside
the mesh.

Two consequences matter for hexmesh:

- **Changing block boundaries changes nothing in the mesh** if the new
  boundaries lie along existing grid lines.  No twist plane is added or
  removed.
- **Changing a node count changes the twist planes.**  New planes have to
  start somewhere inside the domain.  The only way to do that is to turn
  a plane back 180°, which creates *transition* cells with irregular
  vertices.

### 9.2 `n_outer` as a sub-partition (no mesh change)

With `nang` even, the `n_outer = 4` face already has grid lines through
0°/90°/180°/270°: the middle line of each ring patch, and the two centre
lines of the core.  Cutting along them gives 8 ring patches and a 2×2
core, with **the same twist planes**, so the same node connectivity.
Node positions on the new cut lines may move slightly once they become
explicit curves.

This differs from the current `build_oh_circle8`.  It builds an 8-arc
inner boundary and one 8-sided centre patch (`faces/oh_circle.py:34–36`).
That's a different mesh, and it's the DESIGN §9 deviation.

If `n_outer = 8` is defined as the sub-partition:

- `n_outer` stops being a mesh-topology parameter and becomes a block
  partition, chosen per fitting as the finest any of its ports needs;
- the DESIGN §10 question "`n_outer` per network or per interface"
  becomes moot;
- tee tips and wye split planes land on block corners without a
  π/4 roll.

Status: reasoning, not tested.  The test is to mesh both partitions of
one face and compare node counts and connectivity.

### 9.3 Node-count changes: twist-plane insertion [`harris_and_benzley_etal_2004`]

The paper refines all-hex meshes conformally by inserting twist planes
that close on themselves (3-D "spheroids") or end on the boundary.  Each
refinement direction is a separate step inside one sheet or a pair of
sheets:

| Operation | Edge split | Hexes per target hex | Templates |
|---|---|---|---|
| Single sheet | 1 → 3 | 27 | main (8 marked nodes), face transition (4), edge transition (2) |
| Parallel sheets | 1 → 2 | 8 | main (4 marked nodes on a face), edge (2), corner (1) |
| Combination | parallel, then single | — | parallel templates split at ⅓ edge length, then single-sheet |

Transition cells sit where the inserted plane turns back.  They always
have lower quality than the original cells.  Quality is worst where two
transition zones overlap.

**Restrictions** in the paper:

- the target region must be **convex**, because a concave region forces
  the inserted plane to self-intersect;
- parallel-sheet refinement needs the two sheets to stay **parallel**.
  Sheets that cross or diverge, common in unstructured meshes, force
  early turn-backs.

**Quality** (shape metric: 1 ideal, 0 degenerate; min before → after,
then after Mesquite mean-ratio smoothing):

| Case | Original min | Refined min | Smoothed min |
|---|---|---|---|
| Single sheet, element group (Fig. 7b) | 0.726 | 0.294 | 0.312 |
| Combination, along a curve (Fig. 17b) | 0.612 | 0.306 | 0.447 |
| Parallel sheets, along a curve (Fig. 17c) | 0.612 | 0.417 | 0.416 |
| Single sheet, along a curve (Fig. 17d) | 0.612 | 0.166 | 0.257 |

The base meshes in the paper are unstructured, and the authors rely on
smoothing.

### 9.4 What this means for a density change in a pipe

- **Axial count** (`n_layers`) is already per fitting (A5).  Axial twist
  planes are cross-sections, and they can end at any slab.  No
  transition is needed.
- **Angular count (`nang`)** and **radial count (`nrad`)** form sheet
  families that run along the whole pipe:
  - angular sheets cross the core and end on the wall at both sides;
  - radial sheets are the concentric O-rings.
  Doubling one of them means inserting new planes that come in through
  the downstream interface and turn back inside a **transition slab**.
  That is the paper's parallel-sheet case (×2), and the single-sheet
  case gives ×3.
- **The paper's restrictions largely vanish in hexmesh.**  In a
  structured O-grid pipe, every sheet family is regular and parallel,
  and the transition region (a full cross-section slab) is convex.  The
  paper's difficulties come from unstructured base meshes.  This is
  reasoning, not tested.
- **Quality without smoothing** is the open risk.  Smoothing is ruled out
  (§5, DESIGN A2).  The paper's best unsmoothed transition minimum was
  0.417, from an unstructured base.  A structured base with analytically
  placed template nodes might do better, but that is unmeasured.
- **Realisation in GMSH** needs one of:
  - each transition cell as its own one-cell transfinite block, built
    through the §6.1 block registry (could mean thousands of OCC volumes
    per slab);
  - or the slab's elements written directly into a discrete GMSH volume,
    with nodes shared with the neighbouring interfaces.
  Either is a new fitting kind.
- **DESIGN A5** says density is "solved globally".  A transition fitting
  would change that to "solved per zone".  Zones would be separated by
  declared refinement fittings, with fixed ratios (×2 or ×3) between
  them.
- **The alternative** is a declared non-conformal break, coupled with
  OpenFOAM AMI.  That is the same scope question as decision 0003,
  option C.
- **Published precedent for refinement transitions along a tube**
  [`livesu_and_muntoni_etal_2016`] (full text read 2026-10-28, §5):
  - "cones" are conforming **2×2 → 4×4** (and 1×1 → 2×2) cross-section
    subdivision transitions placed along a skeleton limb.  Two in series
    give a 4² scaling.
  - Where to subdivide is solved globally as an integer linear program:
    neighbours split equally, and a cone's base splits once more than
    its tip.
  - Cones are allowed only on terminal limbs, so no loop can make the
    system unsolvable.  That's the same issue a density switch in a
    looped hexmesh network would meet.
  - Their meshes are smoothed afterwards (the interior is optimised), and
    their sections are polycube-like quads, not O-H.  So the scheme is a
    pattern to adapt, not a drop-in.

### 9.5 Single-sheet insertion in swept meshes: cleave and fill [`borden_and_benzley_etal_2000`]

**Method.**  Refinement aimed specifically at **swept** meshes:

1. Choose a path of nodes across the source or target mesh.  The paper
   uses a weighted Dijkstra search that prefers few nodes, few turns, and
   paths away from the surface.
2. Project the path along the sweep over a chosen range of sweep layers.
   This gives the "cleaved plane".
3. Split ("cleave") the mesh along that plane, and fill the gap with a
   **pillow**: one new layer of hexes with the same connectivity as the
   cleaved surface.

In dual terms (§9.1), each operation inserts **one** new sheet (+1 cell
across it), not a ×2 or ×3 multiplication as in §9.3.  The sheet ends
where it emerges on a surface, or closes on itself.  Variants:

- cleaving along the sweep or across it;
- *internal* cleaving: a closed loop of nodes at a fixed number of
  intervals from the linking surfaces, projected through the volume, so
  the linking (side-wall) surfaces stay untouched;
- *totally contained*: the cleaved volume and pillow sit inside the mesh,
  so no boundary changes at all.

**Motivating case.**  Tapered sweeps.  With the same intervals at both
ends of a sweep whose cross-section changes size, cells on one side get
poor aspect ratios.  Inserting sheets where the section is large fixes
that.  The paper reports, for a wedge model, average aspect ratio 1.956
before and 1.441 after cleave, fill and smoothing; maximum 2.683 before
and 1.857 after.  The table is garbled in the text extraction, so check
these against the PDF.  Smoothing is part of the method throughout.

**What it means for hexmesh.**

- **Local refinement without touching interfaces.**  A sheet that runs
  over only part of a sweep must end somewhere.  If it ends on the
  **outermost wall** (a true boundary), or closes on itself, the fitting's
  port faces are unchanged.  A fitting could then add resolution inside
  itself, e.g. near a tee or bend exit, while A5's global `nang`/`nrad`
  stays intact at every interface.  In a multi-layer (CHT) pipe the sheet
  must cross *all* layers out to the outermost wall.  Ending on the
  fluid/wall interface would make that interface non-conformal.
- **Extra O-rings locally.**  In an O-grid, the paper's internal loop at k
  intervals from the wall is an O-ring.  Pillowing it over a few slabs
  adds a ring layer there.  This adds +1 radial cell per radius inside
  the segment, and +1 axial cell at each segment end where the pillow
  closes.  Grading (tasks 0000–0002) covers most near-wall needs more
  cheaply.
- **High-ratio reducers and head nozzles** (decision 0003, cases 1–2) are
  tapered sweeps, the paper's motivating case.  Sheets that start inside
  the large end and end on the wall would reduce the circumferential size
  jump without changing either port.
- **Path search is not needed.**  In a structured O-grid every candidate
  path is a known grid line or ring.  The Dijkstra step, which is most of
  the paper, doesn't transfer.
- **Same open risk as §9.3.**  Pillow corners are irregular vertices, and
  the paper smooths afterwards.  Quality with analytic node placement and
  no smoothing is unmeasured.
- **Limits** (stated by the authors):
  - internal cleaving must lie in one sweep layer, i.e. along the sweep;
  - it doesn't handle holes;
  - coarsening is future work.
  The 2004 paper (§9.3) calls pillow-based refinement limited in "control
  and scale".

**Compared with §9.3.**  Twist-plane templates multiply a region's counts
(×2 or ×3), which suits *density breaks* between zones.  Cleave and fill
adds single sheets along sweeps, which suits *local refinement inside a
fitting* with unchanged ports.  The two are complementary.  Both put
irregular vertices where a sheet turns or ends.

### 9.6 Connecting two faces of different topology

**Question.**  Can a fitting have port faces whose quad meshes differ,
and still fill the volume between them with conformal hexes?  On a
single interface the answer is always no: under A1 both sides share one
face mesh.  The question is only about fittings.

**Existence: settled, but not practical.**
- **Ball-shaped volumes** [`mitchell_1996`]: a quad mesh of a sphere
  admits a compatible all-hex fill **iff it has an even number of
  quads**.  The proof is not constructive.
- **Size** [`eppstein_1999`]: a fill with O(n) hexes always exists.  Its
  buffer-layer construction gives unusable cell quality.
- **Non-ball volumes** [`erickson_2014`]: a fill exists iff the quad
  count is even **and no odd cycle of the boundary mesh bounds a surface
  inside the domain**.  It can be built in polynomial time.  This matters
  for hexmesh: every shell layer of a pipe (wall, insulation) is a
  **solid torus** (annulus × length), not a ball, so Erickson's
  condition, not Mitchell's, is the right check per layer.  For hexmesh's
  annuli the loop around the pipe has 4·`nang` quads, which is even.
- **Small cases** [`verhetsel_and_pellerin_etal_2019`,
  `verhetsel_2024`]: computer search for minimal fills.
  - All 54,943 even quadrangulations of the sphere with up to 20 quads
    were filled with at most 72 hexes.
  - The general bound improves to 78n hexes (from 5396n).
  - The thesis builds the first geometric meshes with planar faces for
    Schneiders' pyramid and the tetragonal trapezohedron.
  The technique (quad flips ≙ hexes glued to the boundary, plus shelling)
  is a way to **find** small transition templates by machine instead of
  designing them by hand.

**Practice: matching two existing meshes** [`staten_and_shepherd_etal_2008`,
`staten_and_shepherd_etal_2010`, `chen_and_gao_etal_2016`].
- "Mesh matching" makes a non-conforming hex-to-hex interface conforming
  by locally changing one or both meshes.  Chords of the two interface
  meshes are paired.  Sheets whose chords lie on the interface are then
  inserted or extracted recursively until every chord has a partner.
- The operations used:
  - pillowing;
  - **sheet inflation**, an extension of pillowing for sheets that
    intersect or touch themselves;
  - sheet extraction, dicing and column collapse.
- Chen et al. extend it to interfaces with internal loops and
  self-intersecting sheets.
- **Difference from hexmesh:** chords are paired by a geometric
  **distance threshold**, because the two meshes were built
  independently.  DESIGN P2 forbids that.  In hexmesh both port faces are
  generated from known specs, so chords can be paired **combinatorially**,
  by layer, family and index (§9.1).

**Transition templates for count changes** [`pitzalis_and_livesu_etal_2021`,
`livesu_and_pitzalis_etal_2022`].
- Grid-based hex meshing converts adaptively refined (2:1) grids into
  conforming hexes with dual transition schemes.
- Livesu et al. 2022 list every transition configuration, show that
  earlier schemes miss some and are asymmetric, and choose a minimal set
  that always gives edge valence 3–6.  Edge valence bounds the achievable
  scaled Jacobian (their Fig. 2).
- Pitzalis et al. 2021 (read in full) define the two conditions an
  adaptive grid must meet before dual transition schemes can turn it
  into conforming hexes:
  - **balancing:** adjacent cells differ by at most one refinement
    level (×2).  It is local and enforced by iterative splitting.
  - **pairing:** every cluster of face-adjacent cells of equal size has
    an **even number of cells along all its sides**.  It is non-local.
    Octree methods enforce it with tree rules that over-refine.
  - Their method assigns refinement to grid **vertices** (each controls
    its 2×2×2 incident cells, so clusters are even by construction) and
    resolves conflicts with linear constraints.  This gives a binary
    integer program, solved locally and interleaved with balancing
    (Gurobi).
  - Result: never more refinement than octree pairing, and about half
    the extra cells on average.
  - **Stated limitation, relevant to pipes:** a **closed ring** of
    refined cells may be thickened unnecessarily.  A ring exposes no
    side with an odd count, but the local vertex formulation can't see
    the global cycle.  The authors conjecture an edge-based formulation
    might fix it, and leave that open.
  - Input grids are Cartesian (regular, adaptive, or polycube-sampled).
    Whether the schemes carry over to irregular vertices, such as an
    O-grid's core corners, is not addressed.
- Code is public (`gen-adapt-ref-for-hexmeshing`).  These are the modern
  successors of Schneiders- and Harris-style templates (§9.3), for
  Cartesian grids.  Inside one block of a structured pipe, the local
  structure is Cartesian, so the schemes should apply per block.  This is
  unverified at block corners (valence 3/5).

**Classification of a port-face pair** (my framework, built on the dual
view of §9.1 and the operations above):

| Class | Chords of A vs B | Fitting must | Examples |
|---|---|---|---|
| 0 | identical (only geometry or block boundaries differ) | sweep; every sheet continues | Reducer; circle ↔ rectangle (0009); `n_outer` sub-partition (0005) |
| 1 | differ by closed loops | insert or remove a capped sheet (pillow / sheet inflation) | O-H face ↔ single-patch square; layer termination (0006, sheets end on the end-annulus wall) |
| 2 | same pattern, different counts | sheets start inside by turning back: refinement templates, fixed ratios | `nang`/`nrad` density breaks (0003) |
| 3 | no acceptable conformal fill | declared non-conformal joint | equipment, 0003 option C |

**For hexmesh.**
- The class is pure combinatorics on the two port faces' chords, so
  `validate()` could compute it **before GMSH**.  It would then either
  pick the required transition (class 0: any sweep; 1/2: a named template
  or a rejection) or demand a declared joint (class 3).  This would
  replace "port types must match exactly" with a check that explains
  *what* is missing.
- **Existence is never the blocker** for pipe sections: even counts hold
  by construction (4·`nang` around, `nang`² core).  The blockers are
  template availability and cell quality without smoothing.
- **Machine-searched templates** (Verhetsel) are a route to class 1/2
  transition templates with known minimal hex counts.  Geometric quality
  would still need checking.
- A **density solve over the whole network as an integer program**
  (Pitzalis) is a natural formulation if A5 ever moves to
  density-per-zone with fixed transition ratios (decision 0003).
- **Pairing gives checkable parity rules for a ×2 density break**
  (derived here, untested).  Refining everything downstream of a
  transition slab makes the refined cluster a full cross-section:
  - around the pipe, every ring is a **closed ring**, so it exposes no
    side and the angular direction is free.  This is the case Pitzalis's
    local solver handles poorly, so don't reuse their solver for it;
  - across the section, the cluster's sides are each layer's radial span
    and the core's sides, so **`nrad` (per refined layer) and `nang` must
    be even** on the coarse side;
  - along the pipe, the refined zone must be an even number of coarse
    cells long, or reach the network boundary.
  All three can be checked in `validate()` before GMSH.  The irregular
  core corners (valence 3/5) are not covered by the paper.

**Status:** the classification and its use in `validate()` are my
proposal and are untested.  The cited results come from abstracts and
the downloaded papers.  The Staten papers were read only through their
abstracts and patent text: no open copy was found (OSTI refused the
connection).

---

## 10. Flow restrictions: how the literature handles them

Context: decision 0021 (staged plan for orifices, nozzles, venturis and
beyond).  Searched 2026-10-27.  Most sources were read through
abstracts and repository records, not full text; the claims below are
marked where they rest on snippets.

### 10.1 Standards and the reference text

- **ISO 5167** (parts 1–4: general, orifice plates, nozzles and Venturi
  nozzles, Venturi tubes) and **ISO/TR 15377** (non-standard devices:
  quarter-circle, conical-entrance, eccentric orifices) set geometry,
  installation and discharge coefficients.
- The orifice discharge coefficient is the **Reader–Harris/Gallagher
  equation**, a function of β, Re_D and tapping positions; background
  in NEL's 1996 paper
  ([NFOGM copy](https://nfogm.no/wp-content/uploads/2019/02/1996-24-The-Orifice-Plate-Discharge-Coefficient-Equation-Reader-Harris-NEL.pdf)).
- [`reader_harris_2015`] (Springer) explains the reasoning behind the
  ISO 5167 rules, which the standard itself rarely gives.
- **Validity limits:** orifice correlations hold for turbulent flow
  (Re_D ≳ 5 000).  For ISO 5167-4 Venturi tubes two summaries give
  different lower limits (2 × 10⁴ and 2 × 10⁵); check the edition before
  relying on either.  The standard also notes machined-convergent
  Venturis outside its predicted coefficients by 2 % or more.

### 10.2 How devices are simulated

- **Concentric devices are usually 2-D axisymmetric.**  OpenFOAM users
  build wedge meshes with `blockMesh`; commercial studies use 2-D
  axisymmetric RANS.  Full 3-D is used when symmetry is broken:
  installation effects, eccentric plates, V-cone supports, valves.
- **Turbulence models (RANS):**
  - SST k-ω tracks the ISO coefficients better than realizable k-ε,
    whose deviation reached about 4.9 % in one study; mesh uncertainty
    there was assessed by GCI (up to about 4 %)
    ([report hosted at Unicamp](https://sites.fem.unicamp.br/~phoenics/EM974/PROJETOS/Temas%20Projetos/ORIFICE%20PLATE%20FLOW%20METER/402%20orifice%20plates%20Balino.pdf);
    snippet).
  - [`shah_and_joshi_etal_2012`] used OpenFOAM 1.6 with standard k-ε,
    validated against the LDA measurements of Nail (1991) and Morrison
    et al. (1993) from Texas A&M, plus their own pressure-drop data.
  - Other RANS studies report the discharge coefficient within about
    4–6 % of experiment, usually under-predicted (snippets).
- [`tukiman_and_ghazali_etal_2017`] (read 2026-10-28, CC-BY, PDF in
  `docs/papers/`): a commercial-code RANS study of an orifice.
  - **Setup:** D = 12.3 mm, d = 5 mm (β ≈ 0.41), plate 2 mm thick;
    246 mm upstream and 494 mm in total; water, uniform inlet at
    0.38 m/s (Re_D ≈ 4 700).  Standard k-ε, first-order schemes,
    740 000 unstructured hexahedra.
  - **Weak as a reference:** results are qualitative only (velocity and
    pressure along the centreline, the vena contracta position).  There
    is no discharge coefficient, no grid-convergence study and no
    measured data.
  - **Useful as:** a concrete orifice configuration for a hexmesh example
    once decision 0021 stage 1 exists.  It also leads to Shan et al.
    (2016, Chem. Eng. Sci. 152:497–506), PIV of orifice flows across β
    (not checked).
- **What is reported:** discharge coefficient against Re and β; vena
  contracta position; the downstream jet, recirculation and reattachment;
  pressure-loss coefficients.

### 10.3 Low Reynolds numbers and laminar flow

- [`johansen_1930`]: the classic measurements of pipe-orifice
  discharge coefficients at low Reynolds numbers.
- [`hollingshead_and_johnson_etal_2011`]: RANS plus experiments for
  Venturi, standard concentric orifice, V-cone and wedge meters at low
  Re.  Venturi, V-cone and wedge coefficients fall quickly with
  decreasing Re; the orifice's coefficient first **rises to a maximum,
  then drops sharply**.
- A 2023 study tests cylindrical orifices in laminar flow at β = 0.5,
  Re about 450–1 400, noting the coefficient varies strongly with Re
  below about 10 000
  ([Scientific Reports](https://www.nature.com/articles/s41598-023-42451-0)).
- Plate thickness matters more at low Re (thin plates show a stronger
  Re dependence; snippet).

### 10.4 Installation effects: the upstream network matters

- Bends upstream of a meter distort the profile and create swirl.  Two
  close-coupled out-of-plane 90° elbows give a single-direction swirl
  that persists far downstream; a single elbow gives a counter-rotating
  pair.  Errors of several per cent are reported for high-β orifices,
  and straight-length recommendations reach 40–60 D (industry and vendor
  sources; to check against ISO 5167-2 tables and AGA-3).
- Headers produce similar 3-D disturbances
  ([IMEKO TC9 2003](https://www.imeko.org/publications/tc9-2003/IMEKO-TC9-2003-042.pdf)).
- CFD is used to quantify these errors, including uncertainty
  quantification over elbow distance and meter orientation (polynomial
  chaos; [PTB-related study](https://www.researchgate.net/publication/305820958_Simulation-based_determination_of_systematic_errors_of_flow_meters_due_to_uncertain_inflow_conditions)):
  the sickle-shaped profile behind elbows rotates with the inflow.

### 10.5 Perforated plates, flow conditioners, valves, eccentric plates

- **Perforated plates:** [`malavasi_and_messa_etal_2012`] measured
  pressure-loss coefficients against equivalent diameter ratio, hole
  thickness and number of holes, compared with ISO 5167-2 single-hole
  values.
- **Flow conditioners** (19-tube bundle in ISO 5167, Zanker, NOVA, NEL,
  others): judged by the ISO criteria (axial velocity within ±5 % of
  fully developed, swirl below 2°).  Tube bundles kill swirl but leave a
  flatter profile; Zanker plates have a loss coefficient above 5.
  Experimental LDA profiles behind five perforated plates
  ([PTB, IMEKO 2000](https://imeko.org/publications/tc9-2000/IMEKO-TC9-2000-008.pdf));
  a numerical comparison of NOVA, NEL and Zanker plates at Re 2.5 × 10⁵
  ([Metrologie 2015](https://cfmetrologie.edpsciences.org/fr/articles/metrology/pdf/2015/01/metrology_metr2015_03005.pdf)).
- **Valves:** butterfly-valve CFD predicts flow coefficients well at
  mid openings (30–60°) and poorly at small openings; meshes are
  hex-dominant unstructured, refined at the disc; convergence checked by
  Richardson extrapolation in some studies (snippets; vendor validation
  cases follow Song and Park's butterfly-valve study).
- **Eccentric and segmental plates:** mostly experimental.  ISO/TR 15377
  gives C = 0.629 for a fully eccentric plate at β = 0.6
  ([NEL 2005](https://nfogm.no/wp-content/uploads/2019/02/2005-04-Estimation-of-the-Measurement-Error-of-Eccentrically-Installed-Orifice-Plates-Barton-National-Engineering-Laboratory.pdf));
  about 600 tests on eccentric and segmental plates in a
  [Surrey thesis](https://openresearch.surrey.ac.uk/esploro/outputs/doctoral/Flow-measurement-with-eccentric-and-segmental/99512020602346).
  No CFD study of them was found.

### 10.6 What this means for hexmesh

1. **The niche is the network, not the device.**  For a concentric
   device alone, a 2-D axisymmetric wedge mesh is the academic baseline,
   and hexmesh's 3-D mesh adds cost, not accuracy.  hexmesh's value is
   the device *in its piping*: elbows, headers and the meter in one
   conformal all-hex mesh, which is exactly what installation-effect
   studies need (10.4).
2. **A laminar orifice case is possible before any turbulence model.**
   Johansen (1930), Hollingshead et al. (2011) and the 2023 laminar
   study give low-Re data, so stage 1 of decision 0021 can be validated
   with the laminar pipeline of tasks 0020/0033–0035.
3. **Turbulent accuracy is limited by RANS, not the mesh.**  Typical
   discharge-coefficient errors are 2–6 % with SST k-ω doing best, so
   turbulent gates should be set from that, and judged with GCI
   (decision 0015).
4. **A showcase case:** two out-of-plane elbows upstream of an orifice,
   compared against the ISO straight-length requirements and published
   installation-effect data.  It uses only bends, straights and the
   stage-1 orifice.
5. **Stage 4 is confirmed as outside the swept model:** perforated
   plates, conditioners and valves are meshed unstructured in the
   literature, and judged by loss coefficients and profile criteria.
6. **Eccentric and segmental plates** have experimental data but no
   CFD literature found: an opportunity, but low priority.

---

## Source availability

Downloaded to `papers/`: `bennett_2025`, `decroocq_and_frindel_etal_2023`
(arXiv v2), `farouki_and_gentili_etal_2017` (arXiv),
`farouki_and_han_2003`, `lloyd_2012`, `marcinno_and_hinz_etal_2025`
(arXiv v2), `miller_1987`, `pietroni_and_campen_etal_2023` (arXiv),
`sorgente_and_biasotti_etal_2023`, `stigler_and_klas_etal_2014`,
`stockie_2015`, `wang_and_juttler_etal_2007` (tech report of the 2008 TOG
paper), and `zhang_and_bazilevs_etal_2007` (author preprint).
`sorgente_and_biasotti_etal_2023` and `stigler_and_klas_etal_2014` were
already in the repository root and have been moved here, and so were
`harris_and_benzley_etal_2004` and `borden_and_benzley_etal_2000` (from
`docs/`).  Added later: `mitchell_1996` and `eppstein_1999` (supplied by
the user; the latter is the arXiv preprint), and `erickson_2014` (author
copy), `verhetsel_and_pellerin_etal_2019` (arXiv), `verhetsel_2024`
(thesis) and `livesu_and_pitzalis_etal_2022` (arXiv), all downloaded.
`pitzalis_and_livesu_etal_2021` was supplied by the user (publisher PDF).
Supplied by the user 2026-10-28 and filed under their keys:
`staten_and_shepherd_etal_2008`, `chen_and_gao_etal_2016`,
`livesu_and_muntoni_etal_2016`, `wang_and_juttler_etal_2008` (the TOG
version), `griffith_and_leweke_etal_2008`,
`varghese_and_frankel_etal_2007` (the 2005 preprint),
`tukiman_and_ghazali_etal_2017`, `lubashevsky_and_gafiychuk_1999`
(arXiv) and `rushdi_and_mitchell_etal_2015` (IMR24, not cited yet).
Downloaded: `salsac_and_sparks_etal_2006` (UCL Discovery) and
`mckeon_and_zagarola_etal_2005` (Caltech).  The §9.6 mesh-matching
description was checked against the Staten 2008 and Chen 2016 full
texts: chords are paired "within a tolerance".  Still not downloaded:
`staten_and_shepherd_etal_2010` (paywalled).

Not downloaded:

- Paywalled, with no open copy found: `bishop_1975`,
  `desantis_and_debeule_etal_2011`, `gordon_and_hall_1973a`,
  `gordon_and_hall_1973b`, `winslow_1966`, `zamir_1976`.
- Open copy exists but the download failed: `farouki_2002` (the server
  returned a corrupt multipart response).

The double-reflection listing (§1) and §4.1–4.2 were checked against the
full papers.  The formulas in §2, §3.1 and §5 are standard results or
derived here: §3.1 was verified numerically, the rest were not.  The
descriptions of the paywalled items, and of `zhang_and_bazilevs_etal_2007`,
rest on abstracts and secondary citations.
