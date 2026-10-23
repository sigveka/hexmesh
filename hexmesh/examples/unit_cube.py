"""
Unit cube — quality metric validation using the single-patch SquareShape.

Creates a 1×1×1 cube as a square duct (SquareShape core) extruded one unit
along Y, then evaluates all Table-2 hex quality metrics.

Because SquareShape produces a single-patch, directly structured hex grid
(no OH butterfly topology), the mesh elements are perfect cubes and all
quality metrics should return their ideal values:

    warping                 → 0   (all faces flat)
    aspect_ratio            → 1   (all faces square)
    skewness                → 0   (principal axes orthogonal)
    taper                   → 0   (no taper, parallelogram faces)
    interp_quality_min/avg  → 1   (perfect 3×3 Jacobian at every corner)
    mean_ratio_min/avg      → 1   (uniform Jacobian across all 8 vertices)
    shape_regularity_ratio  → 1   (all vertex Jacobians equal)
    shape_regularity_knupp  → 1   (Knupp ζ₅ criterion)

Run
---
    python -m hexmesh.examples.unit_cube
"""

from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hexmesh import Model, Network
from hexmesh.core import PipeSpec
from hexmesh.core.shape import SquareShape
from hexmesh.connectors import Straight


def build_unit_cube(n: int = 4) -> Network:
    """Return a Network representing a 1×1×1 cube with n×n×n hex elements.

    Uses SquareShape (single-patch, direct topology) so every element is a
    perfect cube when n divides 1 evenly.

    Parameters
    ----------
    n : int
        Number of divisions per axis.  Gives n×n×n = n³ hex elements.
    """
    shape  = SquareShape(half_w=0.5, half_h=0.5, nang_w=n, nang_h=n)
    spec   = PipeSpec(nang_w=n, nang_h=n).core("cube", shape=shape, nrad=1)
    net = Network(spec, lc=1.0 / n)
    net.add(Straight(length=1.0, n_layers=n))
    return net


def main() -> None:
    n = 4   # 4 × 4 × 4 = 64 perfect cube elements

    with Model("unit_cube", verbose=False):
        net = build_unit_cube(n)
        net.write_physical_groups()

        # ── GMSH built-in quality ──────────────────────────────────────
        print("=" * 62)
        print(f"Unit cube  {n}×{n}×{n}  ({n**3} elements)  — SquareShape topology")
        print("=" * 62)
        report = net.check_quality(quality_name="minSICN", print_report=True)

        # ── Table-2 metrics (Sorgente et al. 2023) ────────────────────
        print()
        results = net.check_hex_quality(mesh=False, print_report=True)

        # ── Ideal-value assertions ─────────────────────────────────────
        print("=" * 62)
        all_pass = True
        tol_zero = 1e-8   # warping, skewness, taper ≈ 0
        tol_one  = 1e-6   # aspect_ratio, quality indicators ≈ 1

        for vq in results:
            s = vq.summary()
            failures: list[str] = []

            if s["warping"]["max"]                    > tol_zero: failures.append(f"warping max={s['warping']['max']:.2e}")
            if abs(s["aspect_ratio"]["max"] - 1.0)   > tol_one:  failures.append(f"aspect_ratio max={s['aspect_ratio']['max']:.6f}")
            if s["skewness"]["max"]                   > tol_zero: failures.append(f"skewness max={s['skewness']['max']:.2e}")
            if s["taper"]["max"]                      > tol_zero: failures.append(f"taper max={s['taper']['max']:.2e}")
            if abs(s["mean_ratio_min"]["min"] - 1.0)  > tol_one:  failures.append(f"mean_ratio_min min={s['mean_ratio_min']['min']:.6f}")
            if abs(s["mean_ratio_avg"]["min"] - 1.0)  > tol_one:  failures.append(f"mean_ratio_avg min={s['mean_ratio_avg']['min']:.6f}")
            if abs(s["shape_regularity_ratio"]["min"] - 1.0) > tol_one: failures.append(f"shape_regularity_ratio min={s['shape_regularity_ratio']['min']:.6f}")
            if abs(s["shape_regularity_knupp"]["min"] - 1.0) > tol_one: failures.append(f"shape_regularity_knupp min={s['shape_regularity_knupp']['min']:.6f}")

            if failures:
                print(f"FAIL  region={vq.name!r}:")
                for f in failures:
                    print(f"        {f}")
                all_pass = False
            else:
                print(f"PASS  region={vq.name!r}  ({vq.n_elements} elements) — all metrics at ideal values")

        print("=" * 62)
        if all_pass:
            print("All Table-2 quality metrics are at their ideal values.")
        else:
            print("Some metrics deviated from ideal — see above.")


if __name__ == "__main__":
    main()
