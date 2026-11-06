# Data: De Amicis et al. (2014), Fig. 12

`deamicis_2014_fig12.csv` holds the measured Darcy friction factors of
the SIET helical coil: De Amicis, Cammi, Colombo, Colombo & Ricotti,
"Experimental and numerical study of the laminar flow in helically
coiled pipes", *Prog. Nucl. Energy* 76 (2014) 206–215
(`deamicis_and_cammi_etal_2014` in `docs/references.bib`).

The paper doesn't tabulate them.  They are **digitised** from its
Fig. 12 ("Experimental Data", the red circles), on 2026-11-06 for task
0075.  They are reported, not gated: the gate is Ito's correlation
(design answer Q2).

## Method

1. Page 9 of the paper was rendered at 600 dpi (`pdftoppm -r 600`).
2. **Axes:** from the tick marks.  x = 1750 at pixel column 555 and
   5250 at 2281 (246.6 px per 500).  y = 0.02 at row 1782 and 0.08 at
   row 484 (216.3 px per 0.01).
3. **Markers:** each red circle is a connected set of pure-red pixels
   (R > 190, G and B < 90).  A complete circle is about 415 px and 23 px
   across.  The value is its centroid.
4. **Rejected blobs:**
   - the legend's marker;
   - a 317 px blob at (3224, 0.0480), a segment of White's red dashed
     curve, with no circle in the figure there.
5. **Error bars:** the dark pixels above and below each circle, along
   its column, up to a 4 px gap.  Where another marker covers part of
   the circle (`hidden = 1`, smaller blobs), the bar is mixed with that
   marker, so it is given as NaN.

## Uncertainty

- **Full circles:** ±5 in Re and ±0.0001 in f.  That is about 2 px, and
  well under the markers' scatter.
- **Partly hidden circles** (`hidden = 1`): the centroid is biased
  toward the visible part, by up to a radius, so ±25 in Re and ±0.0006
  in f.
- **The paper's error bars** are about ±10–15 % of f below Re 2400, and
  ±3–5 % above Re 3000.
- **Check:** these 15 points (Re ≤ 3200) have an RMS deviation of 5.2 %
  from Ito's correlation.  The paper's Table 3 gives 4.1 % on its full
  data set, which may include points whose circles are hidden
  completely.
