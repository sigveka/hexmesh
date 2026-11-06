# Results: fully developed turbulent pipe flow, k-ω SST

**Status: in progress.**  Task 0049 is blocked on its questions for
design.  The U_c/U_b gate fails, and so do both of the wall-function
gates.

- **Run:** 2026-11-06, with OpenFOAM v2406 (Docker
  `opencfd/openfoam-default:2406`) and gmsh 4.12.1, at hexmesh 42357ca
  plus this task's uncommitted changes, on 4 MPI processes.
- **References:**
  - f: McKeon, Zagarola & Smits (2005), eq. 3.5.  It gives 0.02651,
    0.02249 and 0.01818 at Re_b 19 000, 37 700 and 10⁵.
  - U_c/U_b and u⁺: El Khoury et al. (2013), the DNS (`data/`).  At Re_τ
    550 and 1000 it gives f 0.02682 and 0.02247, and U_c/U_b 1.2620 and
    1.2417.
- **Recheck:** `python3 -m validation.tools.recheck turbulent_pipe`.

## Gates

| case | level | first-cell y⁺ (max) | Re_τ | f vs McKeon | gate | U_c/U_b vs DNS | gate |
|---|---|---|---|---|---|---|---|
| lowre_550 | k = 4 | 0.12 | 553 | +2.41 % | 3 %: **pass** | −3.98 % | 3 %: **fail** |
| lowre_1000 | k = 2 | 0.24 | 997 | −0.55 % | 3 %: **pass** | −4.68 % | 3 %: **fail** |
| lowre_1e5 | k = 2 | 0.24 | 2364 | −1.60 % | 3 %: **pass** | — | |
| wf_550 | k = 1 | 46.5 | 527 | −7.26 % | 5 %: **fail** | −7.64 % | 3 %: **fail** |
| wf_1000 | k = 1 | 47.2 | 963 | −7.08 % | 5 %: **fail** | −6.71 % | 3 %: **fail** |
| wf_1e5 | k = 1 | 47.6 | 2296 | −7.22 % | 5 %: **fail** | — | |

Against the DNS's own f, lowre_550 at k = 4 is +1.22 % and lowre_1000 is
−0.48 %.

## Convergence (lowre_550; k = 1, 2, 4)

`refined(k)`: nang and nrad are ×k, the radial growth is its k-th root,
and the axial layers are ×k (irrelevant to an axially uniform flow).

| quantity | k = 1 | k = 2 | k = 4 | status | order | extrapolated | GCI (fine) |
|---|---|---|---|---|---|---|---|
| f | 0.02584 | 0.02668 | 0.02715 | converging | 0.84 | 0.02774 (+4.6 % McKeon, +3.4 % DNS) | 2.7 % |
| U_c/U_b | 1.2086 | 1.2107 | 1.2118 | converging | 0.98 | 1.2129 (−3.9 % DNS) | 0.1 % |

The U_c deficit is the model's, not the mesh's: its GCI is 0.1 %.
f converges slowly and from below.  Its extrapolation lies outside the
3 % gate, although the finest level is inside it.

## u⁺(y⁺) against the DNS (reported, no gate)

At the 45° radius of one cross-section, interpolated in (wall distance,
angle).

| case | y⁺ = 1 | 10 | 30 | 100 | centre |
|---|---|---|---|---|---|
| DNS, Re_τ 550 | 1.00 | 8.47 | 13.57 | 16.66 | 21.80 |
| lowre_550, k = 4 | 1.00 | 8.29 | 12.90 | 16.80 | 20.80 |
| wf_550 | — | — | — | 17.18 | 21.03 |
| DNS, Re_τ 1000 | 1.00 | 8.45 | 13.48 | 16.51 | 23.43 |
| lowre_1000, k = 2 | 1.00 | 8.37 | 12.97 | 16.80 | 22.39 |

The model's buffer layer is low (−0.6 at y⁺ 30), and its log layer is
slightly high at y⁺ 100.  The wake is weaker than the DNS's, by about
1 u⁺ at the centre.  That is the U_c deficit.  `results.json` holds the
full profiles.

## Wall-function sensitivity (reported, not gated)

The meshes and the k and ω wall functions are the same as `wf_*`; only
the nut wall function changes.

| Re_b | nutkWallFunction (gated) | nutUWallFunction | nutUSpaldingWallFunction |
|---|---|---|---|
| 19 000 | −7.26 % | −5.34 % | −0.37 % |
| 37 700 | −7.08 % | −6.53 % | −2.04 % |
| 10⁵ | −7.22 % | −7.29 % | −3.27 % |

U_c/U_b is 6.4–7.6 % low with all three.  Neither nang 12–48 nor nrad
3–12 changed wf_550's f by more than 0.3 % (trials, task Agent notes).
