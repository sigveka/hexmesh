# Laminar 90° square-duct bend (Taylor, Whitelaw & Yianneskis, Re 790)

Developing laminar flow through a strongly curved bend of square section,
against LDV measurements (decision 0012, V3; task 0072).

```bash
python3 validation/square_bend/run.py --np 4             # inlet match, then k = 1, 2, 3
python3 -m validation.tools.recheck square_bend           # gates, from results.json
```

The runs need OpenFOAM v2406 (Docker `opencfd/openfoam-default:2406` by
default).

## Case

| | |
|---|---|
| Duct | 40 × 40 mm (D_h = 40 mm), bend radii 72 / 112 mm (mean 92 mm, radius ratio 2.3), 90°, 10 D_h downstream to a zero-pressure outlet |
| Flow | V_c = 0.0198 m/s, Re = V_c D_h / ν = 790 (De 368), laminar steady `simpleFoam` (SIMPLEC, `linearUpwind`) |
| Inlet | a plug, 12.6 D_h before the bend: matched to the measured profile at X_H = −0.50 in a straight duct (`match_inlet`, k = 2) |
| Mesh | hexmesh's H section (`layout="h"`, decision 0036), graded to every wall: `first_cell` D_h/120 at k = 1; 12 cells per side; k = 1, 2, 3 by `refined(k)` |
| Comparison | U/V_c (and V/V_c) at every point of Table I, interpolated linearly in the cell centres' Delaunay tetrahedra; RMS per station; the gapwise peak on the symmetry plane |

The station coordinates: g = (r − r_o)/(r_i − r_o) runs from the outer
wall (0) to the inner (1); z/z½ runs from the symmetry plane.  V is
positive toward the inner wall.

Data: [data/README.md](data/README.md).  Results: [RESULTS.md](RESULTS.md).
