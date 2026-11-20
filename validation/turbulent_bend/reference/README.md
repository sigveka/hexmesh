# Reference: the PTB bend's LDA profiles

**Source.**  A. Ekat, A. Weissenbrunner, M. Straka, T. Eichler and
K. Oberleithner, *Hybrid LES/RANS Simulations of a 90° Pipe Bend Using
Different CFD Solvers*, OpenFOAM Journal 3 (2023) 49–65,
doi [10.51560/ofj.v3.36](https://doi.org/10.51560/ofj.v3.36), Fig. 3
(page 56).  The LDA measurements are those of M. Straka, C. Koglin and
T. Eichler, *tm – Technisches Messen* 87 (2020) 18–31,
doi [10.1515/teme-2019-0120](https://doi.org/10.1515/teme-2019-0120).

**Licence.**  The article is CC BY-SA 4.0 and the measurements CC BY
4.0.  `ekat2023_fig3.png` is a crop of the article's Fig. 3, shared
under CC BY-SA 4.0 with this attribution; the numbers in
`lda_fig3.json` are taken from that figure.

**The rig.**  Water at 30 °C, D = 0.1 m, w_vol = 0.40035 m/s,
Re = 50 000; a 90° bend of curvature radius 1.425 D after about 95 D
of straight smooth pipe; the axial velocity on the horizontal line
y = 0 at six planes, 2.43, 5.56, 10.7, 15.69, 20.82 and 30.82 D after
the bend.  x/R = −1 is the outer wall.

**Files.**
- `lda_fig3.json`: per plane, the 19 LDA points (x/R, w/w_vol); the
  paper's own k-ω SST curve read at the same points, and its RMS
  against the LDA (`sst_ekat`).
- `ekat2023_fig3.png`: the figure, 150 dpi, to check the numbers by eye.

**How the numbers were taken.**  The figure is vector graphics, so the
curves are read from the PDF's drawing paths (PyMuPDF), not by eye.
Each panel's LDA curve is one solid black path of 21 vertices; the two
end vertices, drawn at the walls, are dropped, leaving 19 points.  The
vertices are mapped linearly through the panel's grey grid lines.  The
PDF's coordinates carry two decimals of a point, so the extraction
adds under 1e-3 to w/w_vol and x/R; the LDA's own expanded uncertainty
is 0.5 % (k = 2).  The paper's SST curve (dotted purple, mesh 3c, half
domain, OpenFOAM v1812) is extracted the same way and interpolated
linearly in x/R.
