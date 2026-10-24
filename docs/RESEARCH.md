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
  tubular shapes, including junctions of higher valence.  Relevant to
  crosses and multi-branch headers.
- [`pietroni_and_campen_etal_2023`]: survey.  For tubular domains it
  concludes that the hard part is splitting the domain into sweepable
  sub-volumes, not meshing them.

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
[`zamir_1976`] give optimal bifurcation angles for transport networks.  A
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

---

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
already in the repository root and have been moved here.

Not downloaded:

- Paywalled, with no open copy found: `bishop_1975`,
  `desantis_and_debeule_etal_2011`, `gordon_and_hall_1973a`,
  `gordon_and_hall_1973b`, `winslow_1966`, `zamir_1976`, and
  `wang_and_juttler_etal_2008` (use the 2007 tech report instead).
- Open copy exists but the download failed: `livesu_and_muntoni_etal_2016`
  (the host timed out; URL in the `.bib`) and `farouki_2002` (the server
  returned a corrupt multipart response).

The double-reflection listing (§1) and §4.1–4.2 were checked against the
full papers.  The formulas in §2, §3.1 and §5 are standard results or
derived here: §3.1 was verified numerically, the rest were not.  The
descriptions of the paywalled items, and of `zhang_and_bazilevs_etal_2007`
and `livesu_and_muntoni_etal_2016`, rest on abstracts and secondary
citations.
