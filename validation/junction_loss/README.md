# Equal-diameter 90° tee: loss coefficients (k-ω SST)

The geometry coefficients of an equal 90° tee against the measurements of
Štigler, Klas & Šperka (2014) (decision 0042 criterion 4, decision 0012,
V3; task 0162).

**Status: missed.**  At Div a, q = 0.6, the one point run, ξ_MGb passes
its gate and ξ_PG misses it: 0.605, 0.105 from the measured 0.50,
against a gate of 0.03.  The
three mesh levels converge (order 1.9, GCI 0.012 on ξ_PG), so the gap is
the model and set-up's, not the mesh's resolution.  The paper's own CFD
(realizable k-ε, 2.3 M cells, transient) gave 0.48; ours with that model,
steady, gives 0.575 with Spalding's wall function and 0.567 with
`nutkWallFunction`.  Results and the reasons in [RESULTS.md](RESULTS.md).

```bash
python3 validation/junction_loss/run.py --points div_a:0.6 --levels 1 2 3 --end-time 8000 --window 2400 --samples 12 --np 3
python3 validation/junction_loss/run.py --points div_a:0.6 --levels 2 --model rke ...   # their model, not gated
python3 validation/junction_loss/run.py --points div_a:0.6 --levels 2 --model rke --wall nutk ...   # and their wall treatment's nearest
python3 -m validation.tools.recheck junction_loss       # gates, from results.json
```

The runs need OpenFOAM v2406 (Docker `opencfd/openfoam-default:2406` by
default).  At `--np 3` a point takes about 33 min at k = 1, 4 h at k = 2
and 14 h at k = 3.

## Case

| | |
|---|---|
| Network | an equal `Tee` (D = 0.1 m), each branch a `Straight` 25 D from the tee, as in the paper's CFD.  Sharp intersection (the default) |
| Branches | the paper's `a` is the inlet port (`fluid_inlet`), `b` the run outlet (`fluid_b`), `c` the branch (`fluid_c`) |
| Configurations | Div a: in at a, out at b and c, q = Q_c / Q_a.  Com a, Div c and Com c are set up in `run.py` but not run |
| Flow | the branch with the total flow at U = 1 m/s, Re 10⁵ (the paper gives none).  One pressure outlet (p = 0), the others at fixed flow rates.  Uniform inlets, 5 % intensity, as in the paper's CFD |
| Model | `kOmegaSST`, steady `simpleFoam`, Spalding's wall function (`nutUSpaldingWallFunction`) with the wall cell at y⁺ ≈ 30 at k = 1: task 0049's gated wall-function set-up |
| Levels | `refined(k)`, k = 1, 2, 3: 65 792, 526 336 and 1 776 384 cells.  Each runs 8000 iterations; the coefficients are the mean over the last 2400 (12 samples), because the steady solve oscillates with a period of about 1200 |
| Comparison (not gated) | realizable k-ε (`--model rke`) at k = 2, the paper's model, steady, with Spalding's wall function and with `nutkWallFunction` (`--wall nutk`) |

## Coefficients

ξ_PG (their eq. 15) and ξ_MGb (eq. 16, p_a = 0).  Each branch's static
pressure is area-averaged per axial cell layer at stations 10–18 D from
the junction centre, and carried back to the centre along the solution's
own friction gradient (a line through the stations), as the paper does
for its CFD (§3).  The experiment's way, McKeon's developed gradient in
place of a measured one, is stored beside it (`*_mckeon`) and never
gated.

## Gates (fixed before the first run; `case.json`)

Each value within u_measured + T of the measurement, where T is the
largest miss of the paper's own CFD for that configuration and
coefficient over the five q: for Div a, T = 0.02 (ξ_PG) and 0.015
(ξ_MGb).  That is: as close to the experiment as their CFD.  And mesh
convergence by Richardson at q = 0.6.

## Data

- `reference/stigler_2014.csv`: 60 values digitised from the paper's
  figures (CC-BY 2.0), with their reading uncertainty and the paper's
  CFD at the same q; method in `reference/README.md`.
- `results.json`: every level's coefficients, spreads, slope profile and
  checkMesh numbers.  The four levels were run before the compared value
  became the own gradient (2026-11-17); their keys were mapped
  (`keys_mapped` in each level).
