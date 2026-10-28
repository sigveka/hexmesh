# Layered conduction: results

**Status: accepted** (task 0034, gates of decision 0015).

hexmesh `91c897a` plus task 0034's changes to `hexmesh/study/openfoam.py`
(the patch-value reader).  The runs' version stamp shows `91c897a`
without `+local`, because of a bug in the check, since fixed.  Also
gmsh 4.12.1, OpenFOAM v1912, 2026-10-28.  Errors are signed and relative
to the total temperature rise T₀ − 300 K.

## Gates

| gate | fixed | convection |
|---|---|---|
| Mesh OK, every region, every level | yes | yes |
| Energy balance through every interface and the outer wall | ≤ 5e-12 | ≤ 1.2e-9 |
| Extrapolated T₀, T(r₁), T(r₂) within 0.1 % of exact | ≤ 0.0007 % | ≤ 0.0005 % (and T₃ 0.00002 %) |
| L2 order ≈ 2 per region | 1.99–2.01 | 1.99–2.01 |

### fixed

Exact: T₀ = 812.2579 K, T(r₁) = 811.0079 K, T(r₂) = 810.8256 K, T₃ = 300.0000 K; total rise T₀ − 300 K = 512.2579 K.

| nang | cells | Mesh OK (3 regions) | mappedWall pairs equal | converged at | energy balance (max) | e(T₀) | e(T(r₁)) | e(T(r₂)) | e(T₃) | L2 rod | L2 steel | L2 insulation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 456 | yes | yes | 47076 of 60000 | 5.1e-12 | -0.9501% | -0.9468% | -0.9462% | +0.0000% | 9.50e-03 | 9.48e-03 | 2.84e-02 |
| 12 | 1824 | yes | yes | 91960 of 120000 | 1.8e-12 | -0.2362% | -0.2351% | -0.2349% | +0.0000% | 2.36e-03 | 2.35e-03 | 7.13e-03 |
| 24 | 7296 | yes | yes | 181188 of 240000 | 2.7e-12 | -0.0591% | -0.0587% | -0.0586% | +0.0000% | 5.90e-04 | 5.88e-04 | 1.79e-03 |

| quantity | observed order | extrapolated (K) | extrapolated − exact (of the rise) | GCI fine |
|---|---|---|---|---|
| T₀ (centre) | 2.011 | 812.25449 | -0.00067% | 0.0461% |
| T(r₁) | 2.012 | 811.00523 | -0.00053% | 0.0459% |
| T(r₂) | 2.012 | 810.82290 | -0.00053% | 0.0459% |

L2 observed orders (log₂ of successive ratios): rod 2.01, 2.00; steel 2.01, 2.00; insulation 1.99, 2.00.


### convection

Exact: T₀ = 937.2579 K, T(r₁) = 936.0079 K, T(r₂) = 935.8256 K, T₃ = 425.0000 K; total rise T₀ − 300 K = 637.2579 K.

| nang | cells | Mesh OK (3 regions) | mappedWall pairs equal | converged at | energy balance (max) | e(T₀) | e(T(r₁)) | e(T(r₂)) | e(T₃) | L2 rod | L2 steel | L2 insulation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 456 | yes | yes | 58605 of 60000 | 1.2e-09 | -0.9316% | -0.9289% | -0.9284% | -0.1678% | 9.31e-03 | 9.30e-03 | 2.45e-02 |
| 12 | 1824 | yes | yes | 114474 of 120000 | 8.4e-10 | -0.2319% | -0.2310% | -0.2308% | -0.0420% | 2.32e-03 | 2.31e-03 | 6.15e-03 |
| 24 | 7296 | yes | yes | 225605 of 240000 | 7.7e-10 | -0.0580% | -0.0577% | -0.0576% | -0.0105% | 5.79e-04 | 5.77e-04 | 1.54e-03 |

| quantity | observed order | extrapolated (K) | extrapolated − exact (of the rise) | GCI fine |
|---|---|---|---|---|
| T₀ (centre) | 2.009 | 937.25458 | -0.00053% | 0.0489% |
| T(r₁) | 2.010 | 936.00531 | -0.00041% | 0.0487% |
| T(r₂) | 2.010 | 935.82299 | -0.00041% | 0.0487% |
| T₃ (outer) | 1.998 | 425.00010 | +0.00002% | 0.0197% |

L2 observed orders (log₂ of successive ratios): rod 2.01, 2.00; steel 2.01, 2.00; insulation 1.99, 2.00.


## Observations

- **All errors are negative and second order.**  The coarse error,
  −0.95 % of the rise, is almost the same at T₀, T(r₁) and T(r₂).  It is
  the insulation's temperature drop, carried inward: the insulation
  holds 99.7 % of the rise.  Its L2 error is the largest of the three
  regions, 3 × the others.
- **The interfaces couple exactly.**
  - The heat leaving each region matches q‴ · V_rod to 1e-12 (fixed) and
    1e-9 (convection).
  - Each `mappedWall` pair has equal face counts.
  - The steel's small drop (0.18 K) and the rod's (1.25 K) are carried
    without visible error.
- **Iterations:** about 47 000 (fixed) or 59 000 (convection) at the
  coarse level, doubling per level.  This is the segregated coupling
  across a 1000:1 conductivity ratio, not the mesh
  (`docs/integrations/openfoam.md`).
