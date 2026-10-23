"""
Tests for t_block.py — Stage 1: saddle curve parameterisation
                        Stage 2: branch stub block GMSH geometry.
"""
from __future__ import annotations
import math

import numpy as np
import pytest

import gmsh

from hexmesh.connectors.t_block import (
    saddle_curve, saddle_corners, _frame, build_stub_block,
    saddle_conformality_check,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORIGIN     = np.array([0.0, 0.0, 0.0])
MAIN_DIR   = np.array([0.0, 1.0, 0.0])   # +Y
BRANCH_DIR = np.array([1.0, 0.0, 0.0])   # +X
R          = 0.36                          # main outer radius
r_SMALL    = 0.18                          # half main — fits within one quadrant
r_EQUAL    = R                             # equal diameter


def _dist_from_axis(pts: np.ndarray, origin: np.ndarray,
                    axis: np.ndarray) -> np.ndarray:
    """Radial distance of each point from a line through origin along axis."""
    axis = axis / np.linalg.norm(axis)
    v    = pts - origin
    t    = (v @ axis)[:, None] * axis
    return np.linalg.norm(v - t, axis=1)


# ---------------------------------------------------------------------------
# Saddle curve: points lie on both surfaces
# ---------------------------------------------------------------------------

class TestSaddleCurveOnSurfaces:
    def test_upstream_arc_on_main_surface(self):
        up, _ = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        d = _dist_from_axis(up, ORIGIN, MAIN_DIR)
        np.testing.assert_allclose(d, R, atol=1e-12)

    def test_downstream_arc_on_main_surface(self):
        _, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        d = _dist_from_axis(dn, ORIGIN, MAIN_DIR)
        np.testing.assert_allclose(d, R, atol=1e-12)

    def test_upstream_arc_on_branch_surface(self):
        up, _ = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        d = _dist_from_axis(up, ORIGIN, BRANCH_DIR)
        np.testing.assert_allclose(d, r_SMALL, atol=1e-12)

    def test_downstream_arc_on_branch_surface(self):
        _, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        d = _dist_from_axis(dn, ORIGIN, BRANCH_DIR)
        np.testing.assert_allclose(d, r_SMALL, atol=1e-12)


# ---------------------------------------------------------------------------
# Corner geometry
# ---------------------------------------------------------------------------

class TestSaddleCurveCorners:
    def test_tips_at_theta_zero(self):
        """At θ=0, upstream/downstream tips should be at ±r along main_dir."""
        up, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL, n_points=21)
        # Mid-index = centre of linspace = θ=0
        mid = len(up) // 2

        expected_dn = ORIGIN + r_SMALL * MAIN_DIR + R * BRANCH_DIR
        expected_up = ORIGIN - r_SMALL * MAIN_DIR + R * BRANCH_DIR
        np.testing.assert_allclose(dn[mid], expected_dn, atol=1e-12)
        np.testing.assert_allclose(up[mid], expected_up, atol=1e-12)

    def test_arcs_meet_at_endpoints(self):
        """Upstream and downstream arcs must share both endpoint corners."""
        up, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        np.testing.assert_allclose(up[0],  dn[0],  atol=1e-12)
        np.testing.assert_allclose(up[-1], dn[-1], atol=1e-12)

    def test_endpoints_have_zero_main_component(self):
        """At θ=±θ_max the saddle arcs touch t=0 — no main-axis displacement."""
        up, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        for pt in (up[0], up[-1], dn[0], dn[-1]):
            t = float(np.dot(pt - ORIGIN, MAIN_DIR))
            assert abs(t) < 1e-12, f"Expected t≈0 at saddle endpoint, got {t}"

    def test_saddle_corners_match_arc_endpoints(self):
        up, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        # side_neg = first endpoint (θ=-θ_max), side_pos = last endpoint
        np.testing.assert_allclose(up[0],  c["side_neg"], atol=1e-12)
        np.testing.assert_allclose(up[-1], c["side_pos"], atol=1e-12)
        np.testing.assert_allclose(dn[mid := len(dn) // 2],
                                   c["tip_downstream"], atol=1e-12)
        up_mid = len(up) // 2
        np.testing.assert_allclose(up[up_mid], c["tip_upstream"], atol=1e-12)


# ---------------------------------------------------------------------------
# Saddle corners: named positions
# ---------------------------------------------------------------------------

class TestSaddleCorners:
    def test_tip_downstream_position(self):
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        expected = ORIGIN + r_SMALL * MAIN_DIR + R * BRANCH_DIR
        np.testing.assert_allclose(c["tip_downstream"], expected, atol=1e-12)

    def test_tip_upstream_position(self):
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        expected = ORIGIN - r_SMALL * MAIN_DIR + R * BRANCH_DIR
        np.testing.assert_allclose(c["tip_upstream"], expected, atol=1e-12)

    def test_side_points_on_main_surface(self):
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        for key in ("side_pos", "side_neg"):
            d = float(np.linalg.norm(
                _dist_from_axis(c[key][None, :], ORIGIN, MAIN_DIR)
            ))
            assert abs(d - R) < 1e-12

    def test_side_points_on_branch_surface(self):
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        for key in ("side_pos", "side_neg"):
            d = float(np.linalg.norm(
                _dist_from_axis(c[key][None, :], ORIGIN, BRANCH_DIR)
            ))
            assert abs(d - r_SMALL) < 1e-12

    def test_side_points_at_t_zero(self):
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)
        for key in ("side_pos", "side_neg"):
            t = float(np.dot(c[key] - ORIGIN, MAIN_DIR))
            assert abs(t) < 1e-12


# ---------------------------------------------------------------------------
# Special cases
# ---------------------------------------------------------------------------

class TestSaddleCurveSpecialCases:
    def test_equal_diameter_theta_max_is_90(self):
        """For r=R, the saddle spans a full 90° arc (θ_max = π/2)."""
        theta_max = math.asin(r_EQUAL / R)
        assert abs(theta_max - math.pi / 2) < 1e-12

    def test_equal_diameter_side_points_at_equator(self):
        """For r=R, side_pos/side_neg lie in the plane through origin ⊥ main_dir."""
        c = saddle_corners(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_EQUAL)
        for key in ("side_pos", "side_neg"):
            t = float(np.dot(c[key] - ORIGIN, MAIN_DIR))
            assert abs(t) < 1e-12

    def test_equal_diameter_curves_on_surfaces(self):
        up, dn = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_EQUAL)
        np.testing.assert_allclose(
            _dist_from_axis(up, ORIGIN, MAIN_DIR), R, atol=1e-12
        )
        np.testing.assert_allclose(
            _dist_from_axis(up, ORIGIN, BRANCH_DIR), r_EQUAL, atol=1e-12
        )

    def test_non_axis_aligned_pipe(self):
        """Pipe not along any coordinate axis — results should still be correct."""
        main   = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)
        branch = np.array([0.0, 0.0, 1.0])
        origin = np.array([1.0, 2.0, 3.0])
        up, dn = saddle_curve(origin, main, branch, R, r_SMALL)
        np.testing.assert_allclose(
            _dist_from_axis(up, origin, main), R, atol=1e-12
        )
        np.testing.assert_allclose(
            _dist_from_axis(up, origin, branch), r_SMALL, atol=1e-12
        )

    def test_rotation_invariance(self):
        """Rotating the whole setup by 90° gives the same shaped curve rotated."""
        up0, dn0 = saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R, r_SMALL)

        # Rotate 90° around +Z: +Y→−X, +X→+Y
        rot = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        main2   = rot @ MAIN_DIR
        branch2 = rot @ BRANCH_DIR
        up2, dn2 = saddle_curve(ORIGIN, main2, branch2, R, r_SMALL)

        rotated_up0 = (rot @ up0.T).T
        np.testing.assert_allclose(
            np.sort(rotated_up0, axis=0),
            np.sort(up2,         axis=0),
            atol=1e-12,
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestSaddleConformality:
    """Tests for saddle_conformality_check()."""

    def test_conformal_r_half_R_nang6(self):
        # r = R/2 → θ_max = 30° = 2 × (90°/6)
        m, ok, _ = saddle_conformality_check(r=0.18, R=0.36, nang=6)
        assert ok is True
        assert m == 2

    def test_not_conformal_r_half_R_nang5(self):
        # nang=5 is odd → never conformal
        m, ok, suggestions = saddle_conformality_check(r=0.18, R=0.36, nang=5)
        assert ok is False
        assert m is None
        assert suggestions == []     # odd nang → no conforming values

    def test_not_conformal_nang4_wrong_r(self):
        # nang=4, θ_max must be 45° → r = R·sin(45°) = R·√2/2 ≈ 0.2546
        # r=0.18 gives θ_max=30°, not a multiple of 90°/4=22.5°
        m, ok, _ = saddle_conformality_check(r=0.18, R=0.36, nang=4)
        assert ok is False

    def test_conformal_nang4_correct_r(self):
        # nang=4 → conforming at θ = 45° (m=2=nang/2): r = R·sin(45°)
        r_conf = 0.36 * math.sin(math.pi / 4)
        m, ok, suggestions = saddle_conformality_check(r=r_conf, R=0.36, nang=4)
        assert ok is True
        assert m == 2
        # suggestions: m=1 (R·sin(22.5°)) and m=2 (R·sin(45°)) → 2 entries
        assert len(suggestions) == 2

    def test_suggestions_populated_for_even_nang(self):
        # nang=6: conforming at m=1 (15°), m=2 (30°), m=3 (45°) → 3 suggestions
        _, _, suggestions = saddle_conformality_check(r=0.18, R=0.36, nang=6)
        assert len(suggestions) == 3   # m=1, m=2, m=3 (m=nang/2=3 now included)

    def test_odd_nang_returns_empty_suggestions(self):
        _, _, suggestions = saddle_conformality_check(r=0.18, R=0.36, nang=7)
        assert suggestions == []


class TestValidation:
    def test_r_greater_than_R_raises(self):
        with pytest.raises(ValueError, match="exceeds"):
            saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R=0.3, r=0.4)

    def test_R_zero_raises(self):
        with pytest.raises(ValueError):
            saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R=0.0, r=0.1)

    def test_r_zero_raises(self):
        with pytest.raises(ValueError):
            saddle_curve(ORIGIN, MAIN_DIR, BRANCH_DIR, R=0.3, r=0.0)

    def test_parallel_dirs_raises(self):
        with pytest.raises(ValueError, match="parallel"):
            saddle_curve(ORIGIN, MAIN_DIR, MAIN_DIR, R=0.3, r=0.1)

    def test_branch_length_too_short_raises(self):
        with pytest.raises(ValueError):
            # branch_length must be > R
            _gmsh_session_call(
                lambda: build_stub_block(
                    ORIGIN, MAIN_DIR, BRANCH_DIR, R=0.36, r=0.18,
                    branch_length=0.3,   # < R=0.36
                )
            )


# ---------------------------------------------------------------------------
# Helpers for GMSH-based tests
# ---------------------------------------------------------------------------

def _gmsh_session_call(fn):
    """Run fn inside a fresh throw-away GMSH session."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("_test")
    try:
        return fn()
    finally:
        gmsh.finalize()


def _count_hex(vols: "list[int]") -> int:
    """Count 3-D Hexahedron elements across the given volume tags."""
    total = 0
    for v in vols:
        etypes, etags, _ = gmsh.model.mesh.getElements(3, v)
        for etype, tags in zip(etypes, etags):
            name = gmsh.model.mesh.getElementProperties(etype)[0]
            if "Hexahedron" in name:
                total += len(tags)
    return total


@pytest.fixture
def stub_result():
    """Build default stub block, generate mesh, yield result dict."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("stub_test")
    result = build_stub_block(
        ORIGIN, MAIN_DIR, BRANCH_DIR,
        R=R, r=r_SMALL,
        branch_length=0.6,
        nang=3, nrad=3, n_axial=3,
    )
    gmsh.model.mesh.generate(3)
    yield result
    gmsh.finalize()


# ---------------------------------------------------------------------------
# Stage 2: stub block geometry and mesh
# ---------------------------------------------------------------------------

class TestStubBlockStructure:
    def test_five_volumes_created(self, stub_result):
        assert len(stub_result["volumes"]) == 5

    def test_five_saddle_surfaces(self, stub_result):
        assert len(stub_result["saddle_surfs"]) == 5

    def test_branch_cs_has_five_surfaces(self, stub_result):
        assert len(stub_result["branch_cs"].surfaces) == 5

    def test_all_elements_are_hex(self, stub_result):
        """After generate(3) every volume element must be a hexahedron."""
        non_hex = 0
        for v in stub_result["volumes"]:
            etypes, etags, _ = gmsh.model.mesh.getElements(3, v)
            for etype, tags in zip(etypes, etags):
                name = gmsh.model.mesh.getElementProperties(etype)[0]
                if "Hexahedron" not in name:
                    non_hex += len(tags)
        assert non_hex == 0, f"{non_hex} non-hex elements found"

    def test_element_count_matches_formula(self, stub_result):
        """Total hex count = centre(nang²·n_axial) + 4·quadrants(nang·nrad·n_axial)."""
        nang, nrad, n_axial = 3, 3, 3
        expected = nang ** 2 * n_axial + 4 * nang * nrad * n_axial
        actual   = _count_hex(stub_result["volumes"])
        assert actual == expected

    def test_saddle_corner_positions(self, stub_result):
        """Saddle outer corners are the 4 expected saddle curve corner points."""
        import math as _m
        e1, e2, e3 = _frame(MAIN_DIR, BRANCH_DIR)
        theta_max  = _m.asin(r_SMALL / R)
        cos_tm, sin_tm = _m.cos(theta_max), _m.sin(theta_max)

        expected = [
            ORIGIN + r_SMALL * e3 + R * e1,
            ORIGIN + R * cos_tm * e1 - R * sin_tm * e2,
            ORIGIN - r_SMALL * e3 + R * e1,
            ORIGIN + R * cos_tm * e1 + R * sin_tm * e2,
        ]

        # The saddle_surfs[1..4] each have one outer corner on the saddle
        # curve. Verify that each expected corner appears as a GMSH point
        # in the model (check by coordinate).
        for exp_pt in expected:
            found = False
            for tag in gmsh.model.getEntities(0):
                coords = gmsh.model.getValue(0, tag[1], [])
                if np.linalg.norm(np.array(coords) - exp_pt) < 1e-10:
                    found = True
                    break
            assert found, f"Saddle corner {exp_pt} not found as GMSH point"

    def test_inner_corners_outside_main_pipe(self, stub_result):
        """Stage 8: all saddle inner corners must be at r ≥ R from the main axis.

        The side-corner inner points (m_inner[1] and m_inner[3]) used to fall
        slightly inside the main pipe outer cylinder (r < R) due to linear
        interpolation toward saddle_ctr.  The Stage 8 fix projects them back to
        r ≥ R so the stub block never volumetrically overlaps the main pipe.
        """
        e1, e2, e3 = _frame(MAIN_DIR, BRANCH_DIR)
        # All GMSH points in the model — check that none lie inside the main pipe
        # outer cylinder (distance from main axis < R − tol).
        tol = 1e-8
        for dim, tag in gmsh.model.getEntities(0):
            coords = np.array(gmsh.model.getValue(0, tag, []))
            # Distance from the main pipe axis (e3 direction through ORIGIN)
            coords_from_origin = coords - np.asarray(ORIGIN)
            axial_component = float(np.dot(coords_from_origin, e3)) * e3
            perp = coords_from_origin - axial_component
            dist_from_axis = float(np.linalg.norm(perp))
            # Only check points in the stub block region (positive e1 side)
            e1_comp = float(np.dot(coords_from_origin, e1))
            if e1_comp > 0.5 * R:  # definitely in the stub block region
                assert dist_from_axis >= R - tol, (
                    f"Point {tag} at {coords} has dist {dist_from_axis:.6f} < R={R} "
                    "— stub block inner corner is inside the main pipe outer cylinder."
                )


# ---------------------------------------------------------------------------
# Stage 3: outer_point_tags conformality
# ---------------------------------------------------------------------------

class TestStubBlockConformality:
    """Verify that pre-existing GMSH point tags are reused (not duplicated)."""

    def test_tip_up_point_reused(self):
        """
        Pre-create a GMSH point at the tip_up position, pass it as
        outer_point_tags[2], and verify the stub reuses it (no duplicate
        point created at that location).
        """
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("conformality_test")
        try:
            nang, nrad, n_axial = 3, 3, 3
            e1, e2, e3 = _frame(MAIN_DIR, BRANCH_DIR)
            lc = r_SMALL / (nang * 1.5)

            tip_up_pos = ORIGIN - r_SMALL * e3 + R * e1  # = tip_up = [0.36, -0.18, 0]

            # Pre-create a GMSH point at tip_up (simulating a point shared with
            # the upstream main pipe cross-section)
            tip_up_tag = gmsh.model.occ.addPoint(
                float(tip_up_pos[0]), float(tip_up_pos[1]), float(tip_up_pos[2]), lc
            )
            gmsh.model.occ.synchronize()

            # Build stub with tip_up_tag reused as outer_point_tags[2]
            outer_tags = [None, None, tip_up_tag, None]
            result = build_stub_block(
                ORIGIN, MAIN_DIR, BRANCH_DIR,
                R=R, r=r_SMALL,
                branch_length=0.6,
                nang=nang, nrad=nrad, n_axial=n_axial,
                lc=lc,
                outer_point_tags=outer_tags,
            )
            gmsh.model.occ.synchronize()

            # Exactly one point should exist at tip_up_pos (no duplicate)
            tip_up_tags_in_model = []
            for _dim, tag in gmsh.model.getEntities(0):
                coords = gmsh.model.getValue(0, tag, [])
                if np.linalg.norm(np.array(coords) - tip_up_pos) < 1e-10:
                    tip_up_tags_in_model.append(tag)

            assert len(tip_up_tags_in_model) == 1, (
                f"Expected exactly 1 point at tip_up, "
                f"got {len(tip_up_tags_in_model)}: {tip_up_tags_in_model}"
            )
            assert tip_up_tags_in_model[0] == tip_up_tag, (
                f"Point at tip_up should be original tag {tip_up_tag}, "
                f"got {tip_up_tags_in_model[0]}"
            )

            # Mesh must remain all hex
            gmsh.model.mesh.generate(3)
            non_hex = 0
            for v in result["volumes"]:
                etypes, etags, _ = gmsh.model.mesh.getElements(3, v)
                for etype, tags in zip(etypes, etags):
                    name = gmsh.model.mesh.getElementProperties(etype)[0]
                    if "Hexahedron" not in name:
                        non_hex += len(tags)
            assert non_hex == 0, f"{non_hex} non-hex elements in conformed stub"

        finally:
            gmsh.finalize()

    def test_no_outer_point_tags_unchanged(self):
        """Default call (outer_point_tags=None) still produces 5 volumes."""
        result = _gmsh_session_call(lambda: build_stub_block(
            ORIGIN, MAIN_DIR, BRANCH_DIR,
            R=R, r=r_SMALL,
            branch_length=0.6,
            nang=3, nrad=3, n_axial=3,
        ))
        assert len(result["volumes"]) == 5


# ---------------------------------------------------------------------------
# Stage 4: multi-layer support via PipeSpec
# ---------------------------------------------------------------------------

from hexmesh.core.spec import PipeSpec   # noqa: E402

# r_core=0.12, r_outer=0.18=r_SMALL — same outer radius as single-layer tests
_SPEC = (
    PipeSpec(nang=3)
    .core("fluid",     radius=0.12, nrad=2)
    .shell("pipe_wall", dR=0.06,   nrad=2)
)


@pytest.fixture
def stub_ml_result():
    """Build multi-layer stub (fluid core + pipe_wall shell), mesh it."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("stub_ml_test")
    result = build_stub_block(
        ORIGIN, MAIN_DIR, BRANCH_DIR,
        R=R, r=0, nrad=0,           # r/nrad ignored when spec is given
        branch_length=0.6,
        nang=3, n_axial=3,
        spec=_SPEC,
    )
    gmsh.model.mesh.generate(3)
    yield result
    gmsh.finalize()


class TestStubBlockMultiLayer:
    def test_nine_volumes_created(self, stub_ml_result):
        """5 core OH + 4 shell annular = 9 total volumes."""
        assert len(stub_ml_result["volumes"]) == 9

    def test_branch_lcs_two_layers(self, stub_ml_result):
        """branch_lcs contains exactly 2 layers (fluid + pipe_wall)."""
        assert len(stub_ml_result["branch_lcs"].layers) == 2

    def test_branch_lcs_layer_names(self, stub_ml_result):
        assert stub_ml_result["branch_lcs"].names == ["fluid", "pipe_wall"]

    def test_all_elements_hex(self, stub_ml_result):
        """After generate(3) every element must be a hexahedron."""
        non_hex = 0
        for v in stub_ml_result["volumes"]:
            etypes, etags, _ = gmsh.model.mesh.getElements(3, v)
            for etype, tags in zip(etypes, etags):
                name = gmsh.model.mesh.getElementProperties(etype)[0]
                if "Hexahedron" not in name:
                    non_hex += len(tags)
        assert non_hex == 0, f"{non_hex} non-hex elements found"

    def test_element_count_formula(self, stub_ml_result):
        """Total hex count matches topology formula.

        Core  (5 OH vols): nang²·n_axial + 4·nang·nrad_core·n_axial
        Shell (4 ann vols): 4·nang·nrad_shell·n_axial
        """
        nang_v, nrad_core, nrad_shell, n_axial_v = 3, 2, 2, 3
        expected = (
            nang_v ** 2 * n_axial_v
            + 4 * nang_v * nrad_core * n_axial_v
            + 4 * nang_v * nrad_shell * n_axial_v
        )
        actual = _count_hex(stub_ml_result["volumes"])
        assert actual == expected

    def test_backward_compat_branch_cs(self, stub_ml_result):
        """branch_cs key is still present and equals the innermost layer."""
        assert stub_ml_result["branch_cs"] is stub_ml_result["branch_lcs"].innermost

    def test_saddle_surfs_count(self, stub_ml_result):
        """Saddle surfaces: 5 (core) + 4 (shell) = 9."""
        assert len(stub_ml_result["saddle_surfs"]) == 9
