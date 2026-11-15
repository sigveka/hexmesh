# Reference: Štigler, Klas & Šperka (2014), figures 5, 6, 9–12, 15 and 16

`stigler_2014.csv` holds the T-junction coefficients of
Štigler, Klas & Šperka, "Characteristics of the T-junction with the
equal diameters of all branches for the variable angle of the adjacent
branch", *EPJ Web of Conferences* 67, 02110 (2014),
doi 10.1051/epjconf/20146702110 (`stigler_and_klas_etal_2014` in
`docs/references.bib`).  The article is open access under the Creative
Commons Attribution License 2.0; these values are derived from its
figures, with this credit.

The paper doesn't tabulate them.  They are **digitised** on 2026-11-15
for task 0162, at q = 0.2, 0.4, 0.6, 0.8 and 1.0:
- Div a and Com a at γ = 90° and 45° (figures 5, 6, 11, 12);
- Div c and Com c at γ = 90° only (figures 9, 10, 15, 16).

The 45° points wait for equal laterals, which hexmesh doesn't build
(`EQUAL_LATERAL_ANGLE_MIN`); the case runs the 90° tee only.

## What the columns are

- `measured`: the experiment's marker (legend `E-Da90`, `E-Ca45`, …).
- `cfd_line`: their CFD (legend `F-…`): GAMBIT all-hex mesh, about 2.3 M
  cells, realizable k–ε with non-equilibrium wall functions, unsteady.
- `xi_PG`: the geometry power coefficient, eq. (15),
  ξ_PG = ξ_P − ξ_PF: the total power coefficient of eq. (5) less the
  friction part of eq. (11).
- `xi_MGb`: the geometry momentum coefficient along the run, eq. (16),
  ξ_MGb = ξ_Mb − ξ_MFb.  The reference pressure is that of the branch
  carrying the total flow: p_a = 0 in Div a and Com a, p_c = 0 in Div c
  and Com c.
- `q`, in Div a and Com a: q_ca = |Q_c / Q_a| (eqs. 17 and 20), the
  branch's flow over the flow in the run's end `a`, which carries the
  total.
- `q`, in Div c and Com c: q_ac = |Q_a / Q_c| (eqs. 19 and 22).  The
  branch `c` carries the total, which `a` and `b` share.
- `u_measured`, `u_cfd_line`: the reading uncertainty, a half-width.

Branches (their figure 2): `a` and `b` are the run's ends, `c` the
branch; γ is the angle between `b` and `c`.  In Div a the flow enters
at `a` and leaves at `b` and `c`; in Com a it enters at `b` and `c` and
leaves at `a`.  In Div c the flow enters at `c` and leaves at `a` and
`b`; in Com c it enters at `a` and `b` and leaves at `c`.  On hexmesh's `Tee`, `a` is the inlet port, `b` the
`main` port and `c` the `branch` port, and γ is `Tee.angle`.

## Method

1. Pages 7 and 10 rendered at 300 dpi (`pdftoppm -r 300`).
2. **Axes**, in pixels on those renders:
   - y: from the gridlines.  Figures 5 and 11 have 0.5 per 166.3 px and
     0.5 per 168.0 px, with 3.0 at row 394 in both.  Figure 6 has 0.2
     per 232.8 px, with 0.8 at row 1840.  Figure 12 has 0.5 per 243.3 px,
     with 2.0 at row 1826.5.  Figure 9 has 0.5 per 179.75 px, with 3.0 at
     row 394.  Figure 10 has 0.1 per 194 px, with 0.3 at row 1840.
     Figure 15 has 0.5 per 177.9 px, with 3.0 at row 394.5.  Figure 16
     has 0.5 per 143.8 px, with 2.0 at row 1827.
   - x: from the tick marks.  q = 0 and 1 are at columns 448 and 1957
     (figures 5 and 6), 389.5 and 1877 (figure 11), 348 and 1951
     (figure 12), 433.5 and 1961 (figure 9), 447.5 and 1961 (figure 10),
     and 446.5 and 1956.5 (figures 15 and 16).
3. **Reading:** the figures are greyscale, with overlapping marker
   shapes, so the markers weren't separated automatically.  At each q,
   a column strip was cut, zoomed 2× to 4×, and ruled every 0.05 (0.02
   where crowded).  Each marker's centre was then read against the
   rules, identified by the legend's shape and fill:
   - 90° is the open circle, 45° the black diamond;
   - for the lines, 90° is solid black and 45° the second-lightest solid
     grey.
4. **Uncertainty:**
   - 0.01 for an isolated marker or the black line;
   - up to 0.04 in figure 9 at q = 0.4 and 0.6, where the markers of
     60° to 105° overlap the 90° circle.  At 90°, Div c and Com c are
     symmetric under q ↔ 1 − q (`a` and `b` swap), which the
     readings at 0.2 and 0.8 agree with;
   - 0.02 to 0.05 where markers of other angles overlap (at q = 0.2 and
     0.4 they cluster), or where the grey lines' shades must be told
     apart (the 45° lines).

The paper gives no uncertainty for its measurements, nor the flow rates
or Reynolds number (task 0162, *Questions for design*).
