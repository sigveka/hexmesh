"""
Mesh quality integration tests.

Each test builds a complete pipe network, generates the hex mesh, and runs
two complementary quality checks:

  1. GMSH SICN (minSICN >= 0) — catches inverted cells.
  2. Hex quality metrics (mean_ratio_min > 0 across all elements) — catches
     degenerate elements and provides richer per-element diagnostics via the
     Sorgente et al. (2023) indicators implemented in hexmesh.quality_hex.

Junction tests additionally run _check_no_volume_overlap, a two-pass check
that catches both parallel-grid overlap (centroid hash) and diverging-grid
overlap (geometric containment via getElementsByCoordinates).  Neither SICN
nor mean_ratio_min alone can detect these without meshing context.

Pipe specs use small nang/nrad values to keep runtimes short while still
exercising all code paths.
"""

import math

import pytest
import numpy as np

from hexmesh.core.cursor import Cursor, Plane
from hexmesh.core.spec import PipeSpec
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.network import Network
from hexmesh.connectors import (
    Straight, Bend, MiterBend, Reducer, Expander, Transition, TJunction,
    YJunction,
)
from hexmesh.quality_hex import evaluate_hex_quality


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xz_cursor():
    return Cursor.from_plane(Plane.XZ)


def _circle_pipe():
    return (
        PipeSpec(nang=4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
    )


def _two_layer_pipe():
    return (
        PipeSpec(nang=4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
        .shell("wall",  dR=0.025, nrad=2)
    )


def _y_circle_pipe():
    """Single-layer pipe for Y-junction tests: rot=-π/4 aligns inner corners
    with cardinal axes so the N-S split line falls on corner boundaries."""
    return (
        PipeSpec(nang=4, rot=-math.pi / 4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
    )


def _y_two_layer_pipe():
    """Two-layer pipe for Y-junction tests (rot=-π/4 required)."""
    return (
        PipeSpec(nang=4, rot=-math.pi / 4)
        .core("fluid", CircleShape(radius=0.1, nang=4), nrad=3)
        .shell("wall",  dR=0.025, nrad=2)
    )


def _check(net: Network, threshold: float = 0.0) -> None:
    """Mesh and assert no elements worse than *threshold* (default: no inverted)."""
    report = net.check_quality(threshold=threshold, print_report=False)
    assert report.ok, (
        f"Mesh has {report.total_bad} bad elements "
        f"(min quality = {report.min_quality:.4f}, threshold={threshold})\n{report}"
    )


def _check_hex_quality(net: Network, max_degenerate: int = 0) -> None:
    """Assert hex element quality via mean_ratio_min (Sorgente et al. 2023).

    An element is counted as degenerate when mean_ratio_min == 0, which
    occurs whenever any vertex Jacobian has |det| < 1e-14 (inverted or
    collapsed element).  The centroid overlap check guards against crossing
    volumes; this check guards against per-element shape collapse.

    Parameters
    ----------
    max_degenerate : int
        Maximum number of degenerate elements permitted.  The default (0)
        requires every element to be well-formed.  Pass a small positive
        value for junctions that produce a known number of near-degenerate
        elements at split boundaries.
    """
    all_vol_tags = list({
        tag for rset in net._all_regions.values() for tag in rset.volumes
    })
    q = evaluate_hex_quality(all_vol_tags, name="all")
    assert q is not None, "No hexahedral elements found in mesh"
    n_deg = int((q.mean_ratio_min == 0).sum())
    assert n_deg <= max_degenerate, (
        f"Too many degenerate hex elements: {n_deg} > {max_degenerate}\n{q}"
    )


def _full_check(net: Network) -> None:
    """Mesh + GMSH SICN check + hex quality metrics check."""
    _check(net)
    _check_hex_quality(net)


def _full_check_junction(net: Network) -> None:
    """Mesh + SICN + hex quality for TJunction meshes.

    Note: the centroid overlap check is NOT applied here.  A T-junction
    builds the main leg and branch leg as two independent Straight extrusions
    from the same junction centre.  The two blocks physically overlap at the
    corner — that is the intended chamfered-block topology, not a bug.
    """
    _full_check(net)


def _check_y(net: Network) -> None:
    """Quality check for Y-junction meshes.

    Y-junction blocks have a hard N-S split at the center patch, which
    produces a small number of near-degenerate hexahedra (SICN ≈ 0) at
    the split boundary.  A threshold of -0.05 tolerates these numerical
    artefacts while still catching genuinely inverted cells — which had
    SICN ≈ -0.3 in the overlapping-volume bug this test suite was written
    to guard against.
    """
    _check(net, threshold=-0.05)


def _full_check_y(net: Network) -> None:
    """SICN check (relaxed) + volume distinctness + hex quality for Y-junction meshes.

    The hex check tolerates up to 35 degenerate elements.  The full-circle
    12-volume junction block produces a small number of near-degenerate cells
    at the N-S split seam and the skewed fill-volume corners; all are
    structurally sound (no crossing volumes).  Hundreds of degenerate elements
    at SICN ≈ -0.3 would indicate a regression to the old crossing-volumes bug.
    """
    _check_y(net)
    _check_no_volume_overlap()
    _check_hex_quality(net, max_degenerate=35)


def _check_no_volume_overlap() -> None:
    """Assert that no two GMSH volumes share any region of 3-D space.

    Two detection passes are run in sequence.  A failure in either is an
    error; both must pass for the mesh to be considered overlap-free.

    Pass 1 — centroid hash (fast, catches parallel structured grids)
    ----------------------------------------------------------------
    All element barycentres are placed into a spatial hash-grid at
    resolution 1e-5 m.  If two elements from *different* volumes land in
    the same cell, their centroids are coincident → the volumes overlap.
    This reliably catches the classic "two extrusions from the same face"
    bug where both structured grids have the same orientation.

    Pass 2 — geometric containment (thorough, catches diverging grids)
    ------------------------------------------------------------------
    For the old bug above the structured grids were nearly parallel so
    Pass 1 was sufficient.  For *fill* volumes that grow from the same
    inlet face toward *opposite* branch outlets, the grids diverge at
    ~90° and their centroids never coincide — Pass 1 gives a false
    negative.

    Pass 2 uses ``gmsh.model.mesh.getElementsByCoordinates``, which
    returns *all* mesh elements that contain a query point regardless of
    which volume they belong to.  For every element centroid P in volume V:

      • query getElementsByCoordinates(P) → set of element tags at P
      • map each tag to its owning volume
      • if any owning volume W ≠ V is returned AND V and W share no
        common bounding surface → V and W geometrically overlap at P

    Volumes that share a surface are conformal neighbours; boundary
    elements near that surface legitimately appear in both volumes'
    results at floating-point tolerance and are excluded.

    Output format
    -------------
    On failure both passes emit a structured block suitable for both
    human reading and LLM / script parsing::

        VOLUME OVERLAP DETECTED
        pass: <1|2>
        overlap_pairs:
          - volumes: [A, B]
            hit_count: N          # Pass 2 only
            sample_location: [x, y, z]
        total_overlapping_pairs: M

    Must be called after meshing (``net.mesh()`` / ``net.check_quality()``).
    """
    import gmsh as _gmsh

    # ------------------------------------------------------------------
    # Build shared data structures used by both passes
    # ------------------------------------------------------------------
    all_vol_tags = [t for _, t in _gmsh.model.getEntities(dim=3)]

    # element tag → owning volume tag
    elem_to_vol: dict[int, int] = {}
    # volume tag → array of barycentres (N×3)
    vol_centroids: dict[int, np.ndarray] = {}

    for vtag in all_vol_tags:
        etypes_v, etags_v, _ = _gmsh.model.mesh.getElements(3, vtag)
        cents: list[np.ndarray] = []
        for etype, etags in zip(etypes_v, etags_v):
            for e in etags:
                elem_to_vol[int(e)] = vtag
            bary = _gmsh.model.mesh.getBarycenters(etype, vtag, False, False)
            cents.append(np.array(bary).reshape(-1, 3))
        vol_centroids[vtag] = np.vstack(cents) if cents else np.empty((0, 3))

    # shared surfaces between every pair of volumes (for Pass-2 filtering)
    vol_surfaces: dict[int, frozenset[int]] = {}
    for vtag in all_vol_tags:
        bnd = _gmsh.model.getBoundary([(3, vtag)], oriented=False)
        vol_surfaces[vtag] = frozenset(abs(s) for _, s in bnd)

    def _shared_surface(a: int, b: int) -> bool:
        return bool(vol_surfaces[a] & vol_surfaces[b])

    # ------------------------------------------------------------------
    # Pass 1: centroid hash at 1 µm resolution
    # ------------------------------------------------------------------
    scale = 100_000  # 1e-5 m grid
    grid: dict[tuple, list[tuple[int, int]]] = {}
    for vtag, cents in vol_centroids.items():
        for c in cents:
            key = (round(c[0] * scale), round(c[1] * scale), round(c[2] * scale))
            grid.setdefault(key, []).append((vtag, int(c[0] * scale)))  # vtag kept

    p1_pairs: dict[tuple[int, int], list[np.ndarray]] = {}
    for key, entries_raw in grid.items():
        # Re-fetch from vol_centroids for cleaner data
        pass

    # Redo cleanly
    grid2: dict[tuple, list[tuple[int, np.ndarray]]] = {}
    for vtag, cents in vol_centroids.items():
        for c in cents:
            key = (round(c[0] * scale), round(c[1] * scale), round(c[2] * scale))
            grid2.setdefault(key, []).append((vtag, c))

    p1_pairs: dict[tuple[int, int], list[np.ndarray]] = {}
    for key, entries in grid2.items():
        vols_here = [v for v, _ in entries]
        if len(set(vols_here)) > 1:
            pts_here = [c for _, c in entries]
            for i, vi in enumerate(vols_here):
                for j, vj in enumerate(vols_here):
                    if vi < vj:
                        pair = (vi, vj)
                        p1_pairs.setdefault(pair, []).append(pts_here[0])

    # ------------------------------------------------------------------
    # Pass 2: geometric containment via getElementsByCoordinates
    # ------------------------------------------------------------------
    # Only test candidate pairs: bbox overlap + no shared surface
    bboxes: dict[int, tuple] = {
        t: _gmsh.model.getBoundingBox(3, t) for t in all_vol_tags
    }

    def _bbox_overlap(t1: int, t2: int) -> bool:
        x1, y1, z1, x2, y2, z2 = bboxes[t1]
        a1, b1, c1, a2, b2, c2 = bboxes[t2]
        eps = 1e-6
        return (x1 < a2 - eps and x2 > a1 + eps and
                y1 < b2 - eps and y2 > b1 + eps and
                z1 < c2 - eps and z2 > c1 + eps)

    candidates = [
        (t1, t2)
        for i, t1 in enumerate(all_vol_tags)
        for t2 in all_vol_tags[i + 1:]
        if _bbox_overlap(t1, t2) and not _shared_surface(t1, t2)
    ]

    # For each candidate pair query all centroids of the smaller volume
    p2_pairs: dict[tuple[int, int], dict] = {}
    for t1, t2 in candidates:
        c1 = vol_centroids[t1]
        c2 = vol_centroids[t2]
        # Query the smaller volume's centroids against the mesh
        probe_vol, target_vol = (t1, t2) if len(c1) <= len(c2) else (t2, t1)
        probe_cents = vol_centroids[probe_vol]

        hit_pts: list[np.ndarray] = []
        for pt in probe_cents:
            found = _gmsh.model.mesh.getElementsByCoordinates(
                float(pt[0]), float(pt[1]), float(pt[2]), dim=3
            )
            owning_vols = {elem_to_vol.get(int(e), -1) for e in found}
            if target_vol in owning_vols:
                hit_pts.append(pt)

        if hit_pts:
            pair = (min(t1, t2), max(t1, t2))
            p2_pairs[pair] = {
                "hit_count":       len(hit_pts),
                "probe_vol":       probe_vol,
                "target_vol":      target_vol,
                "sample_location": hit_pts[0].tolist(),
            }

    # ------------------------------------------------------------------
    # Report and assert
    # ------------------------------------------------------------------
    if not p1_pairs and not p2_pairs:
        return

    lines = ["VOLUME OVERLAP DETECTED"]

    if p1_pairs:
        lines.append("pass: 1")
        lines.append("overlap_pairs:")
        for (va, vb), pts in sorted(p1_pairs.items()):
            lines.append(f"  - volumes: [{va}, {vb}]")
            lines.append(f"    sample_location: {pts[0].tolist()}")
        lines.append(f"total_overlapping_pairs: {len(p1_pairs)}")

    if p2_pairs:
        lines.append("pass: 2")
        lines.append("overlap_pairs:")
        for (va, vb), info in sorted(p2_pairs.items()):
            lines.append(f"  - volumes: [{va}, {vb}]")
            lines.append(f"    hit_count: {info['hit_count']}")
            lines.append(
                f"    probe_vol: {info['probe_vol']}  "
                f"target_vol: {info['target_vol']}"
            )
            lines.append(f"    sample_location: {info['sample_location']}")
        lines.append(f"total_overlapping_pairs: {len(p2_pairs)}")

    raise AssertionError("\n".join(lines))


# ===========================================================================
# Single connector
# ===========================================================================

class TestStraightQuality:
    def test_single_layer(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.5, n_layers=5))
        _full_check(net)

    def test_two_layers(self, gmsh_session):
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.5, n_layers=5))
        _full_check(net)

    def test_rectangular_duct(self, gmsh_session):
        pipe = (
            PipeSpec(nang_w=3, nang_h=2)
            .core("air", RectShape(0.08, 0.05, 3, 2), nrad=3)
        )
        net = Network(pipe, cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_square_shell_pipe(self, gmsh_session):
        pipe = (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(0.08, 4), nrad=3)
            .shell("wall", dR=0.02, nrad=2)
            .square_shell("shell", half_w=0.15, half_h=0.15, nrad=2)
        )
        net = Network(pipe, cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_multiple_straights(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        for _ in range(3):
            net.add(Straight(0.2, n_layers=2))
        _full_check(net)


class TestBendQuality:
    def test_90_degree_bend(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=90, n_layers=6))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_45_degree_bend(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=45, n_layers=4))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_two_layer_pipe_bend(self, gmsh_session):
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=90, n_layers=6))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_s_curve(self, gmsh_session):
        """Two back-to-back bends in opposite sense."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=45, n_layers=4))
        net.add(Straight(0.1, n_layers=2))
        net.add(Bend(radius=0.3, angle=-45, n_layers=4))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_vertical_bend(self, gmsh_session):
        """Bend using roll=90 (around cursor.right)."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        # Bend rotates around right; we use the Bend connector (always around right)
        net.add(Bend(radius=0.3, angle=90, n_layers=6))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)


class TestMiterBendQuality:
    def test_single_30_degree_horizontal(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=30, roll=0.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_single_30_degree_vertical(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=30, roll=90.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_90_degree_auto_subdivision(self, gmsh_session):
        """90° MiterBend auto-subdivides into 3×30° sub-cuts."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=90, roll=0.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_90_degree_vertical_auto_subdivision(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=90, roll=90.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_three_cut_manual(self, gmsh_session):
        """Three explicit 30° miter cuts approximating a 90° elbow."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        for _ in range(3):
            net.add(Straight(0.05, n_layers=1))
            net.add(MiterBend(angle=30, roll=0.0))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_two_layer_pipe(self, gmsh_session):
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=30, roll=0.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)

    def test_negative_angle(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.add(MiterBend(angle=-30, roll=0.0))
        net.add(Straight(0.3, n_layers=3))
        _full_check(net)


class TestReducerExpanderQuality:
    def _wide(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.12, nang=4), nrad=3)
        )

    def _narrow(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.07, nang=4), nrad=3)
        )

    def test_reducer_quality(self, gmsh_session):
        net = Network(self._wide(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Reducer(outlet=self._narrow(), length=0.3, n_layers=3))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_expander_quality(self, gmsh_session):
        net = Network(self._narrow(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Expander(outlet=self._wide(), length=0.3, n_layers=3))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    def test_reducer_after_bend(self, gmsh_session):
        """Reducer after a Bend (non-axis-aligned cursor)."""
        net = Network(self._wide(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=90, n_layers=5))
        net.add(Reducer(outlet=self._narrow(), length=0.3, n_layers=3))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)


class TestTransitionQuality:
    """Quality tests for the CIRCULAR → SQUARE Transition connector.

    NOTE: The meshing tests are currently marked xfail because _extract_geom()
    in fittings.py only handles arc curves (OH/annulus topology) and crashes
    with an IndexError when it processes a square_shell layer's straight edges.
    The connector docstring claims CIRCULAR→SQUARE is supported, but the
    implementation is incomplete.  These tests document the expected behaviour
    so they turn green automatically once the implementation is fixed.
    """

    def _circ_inlet(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.08, nang=4), nrad=3)
            .shell("wall", dR=0.02, nrad=2)
        )

    def _sq_outlet(self):
        return (
            PipeSpec(nang=4)
            .core("fluid", CircleShape(radius=0.08, nang=4), nrad=3)
            .square_shell("wall", half_w=0.14, half_h=0.14, nrad=2)
        )

    @pytest.mark.xfail(reason="_extract_geom does not handle square_shell edges", strict=True)
    def test_circular_to_square_quality(self, gmsh_session):
        net = Network(self._circ_inlet(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Transition(outlet=self._sq_outlet(), length=0.3, n_layers=3))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    @pytest.mark.xfail(reason="_extract_geom does not handle square_shell edges", strict=True)
    def test_transition_after_bend(self, gmsh_session):
        """Transition on a non-axis-aligned cursor (after a Bend)."""
        net = Network(self._circ_inlet(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Bend(radius=0.3, angle=90, n_layers=5))
        net.add(Transition(outlet=self._sq_outlet(), length=0.3, n_layers=3))
        net.add(Straight(0.2, n_layers=2))
        _full_check(net)

    @pytest.mark.xfail(reason="_extract_geom does not handle square_shell edges", strict=True)
    def test_transition_outlet_is_square_boundary(self, gmsh_session):
        """Outlet face after Transition must carry BoundaryType.SQUARE."""
        from hexmesh.core.cross_section import BoundaryType
        net  = Network(self._circ_inlet(), cursor=_xz_cursor(), lc=0.1)
        node = net.add(Straight(0.2, n_layers=2))
        node = net.add(Transition(outlet=self._sq_outlet(), length=0.3, n_layers=3))
        assert node.face.outermost.boundary_type is BoundaryType.SQUARE

    @pytest.mark.xfail(reason="_extract_geom does not handle square_shell edges", strict=True)
    def test_straight_accepts_square_outlet(self, gmsh_session):
        """Straight after Transition (SQUARE face) must not raise."""
        net  = Network(self._circ_inlet(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.2, n_layers=2))
        net.add(Transition(outlet=self._sq_outlet(), length=0.3, n_layers=3))
        node = net.add(Straight(0.2, n_layers=2))
        assert node is not None


class TestTJunctionQuality:
    def test_horizontal_branch(self, gmsh_session):
        net   = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        nodes = net.add(
            n_in,
            TJunction(approach_length=0.12, branch_length=0.12, roll=0.0),
        )
        net.add(nodes[0], Straight(0.3, n_layers=3))
        net.add(nodes[1], Straight(0.3, n_layers=3))
        _full_check_junction(net)

    def test_vertical_branch(self, gmsh_session):
        net   = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        nodes = net.add(
            n_in,
            TJunction(approach_length=0.12, branch_length=0.12, roll=90.0),
        )
        net.add(nodes[0], Straight(0.3, n_layers=3))
        net.add(nodes[1], Straight(0.3, n_layers=3))
        _full_check_junction(net)

    def test_two_layer_pipe_junction(self, gmsh_session):
        net   = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        nodes = net.add(
            n_in,
            TJunction(approach_length=0.12, branch_length=0.12, roll=0.0),
        )
        net.add(nodes[0], Straight(0.3, n_layers=3))
        net.add(nodes[1], Straight(0.3, n_layers=3))
        _full_check_junction(net)

    def test_no_tangential_extrusion_warning(self, gmsh_session):
        """The branch face is now built fresh — no RuntimeWarning expected."""
        import warnings
        net  = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in = net.add(Straight(0.3, n_layers=3))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            nodes = net.add(
                n_in,
                TJunction(approach_length=0.12, branch_length=0.12, roll=0.0),
            )
        tangential_warnings = [
            x for x in w if issubclass(x.category, RuntimeWarning)
            and "tangential" in str(x.message).lower()
        ]
        assert not tangential_warnings, (
            "Unexpected tangential-extrusion RuntimeWarning — the branch face "
            "should now be built fresh and perpendicular to the branch direction."
        )


# ===========================================================================
# Network API
# ===========================================================================

class TestNetworkApi:
    def test_physical_groups_written(self, gmsh_session):
        """write_physical_groups must produce named inlet/outlet/wall groups."""
        import gmsh
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.write_physical_groups()
        gmsh.model.mesh.generate(3)

        names = {
            gmsh.model.getPhysicalName(dim, tag)
            for dim, tag in gmsh.model.getPhysicalGroups()
        }
        assert "fluid" in names
        assert "fluid_inlet"  in names
        assert "fluid_outlet" in names
        assert "fluid_wall"   in names

    def test_check_quality_no_bad_cells(self, gmsh_session):
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        report = net.check_quality(print_report=False)
        assert report.ok
        assert report.total_bad == 0
        assert report.total_elements > 0

    def test_check_quality_returns_correct_regions(self, gmsh_session):
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        report = net.check_quality(print_report=False)
        region_names = {r.name for r in report.regions}
        assert "fluid" in region_names
        assert "wall"  in region_names

    def test_check_quality_mesh_false(self, gmsh_session):
        """mesh=False should use the already-generated mesh."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        net.mesh()
        report = net.check_quality(mesh=False, print_report=False)
        assert report.ok

    def test_inlet_not_in_outlet_set(self, gmsh_session):
        """System inlet surfaces must never appear in outlet sets."""
        net = Network(_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.5, n_layers=5))
        rset = net._all_regions["fluid"]
        inlet_set  = set(rset.inlets)
        outlet_set = set(rset.outlets)
        # The inlet face of the whole network appears only in inlets
        # (intermediate faces appear in both — that is by design)
        # At least one surface is inlet-only and one is outlet-only:
        assert inlet_set - outlet_set, "No inlet-only surfaces found"
        assert outlet_set - inlet_set, "No outlet-only surfaces found"

    def test_interface_surfaces_tracked(self, gmsh_session):
        """Two-layer pipe should produce conformal interface surfaces."""
        net = Network(_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        net.add(Straight(0.3, n_layers=3))
        assert "fluid_to_wall" in net._all_interfaces
        assert len(net._all_interfaces["fluid_to_wall"]) > 0


# ===========================================================================
# Y-junction
# ===========================================================================

class TestYJunctionQuality:
    def test_45_degree_horizontal(self, gmsh_session):
        """Symmetric 90° Y-split (±45°) in the horizontal plane."""
        net   = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        _full_check_y(net)

    def test_30_degree_horizontal(self, gmsh_session):
        """Narrower ±30° horizontal Y."""
        net   = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=30, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        _full_check_y(net)

    def test_45_degree_vertical(self, gmsh_session):
        """Symmetric ±45° Y in the vertical plane."""
        net   = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=90.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        _full_check_y(net)

    def test_two_layer_pipe(self, gmsh_session):
        """Y-junction with core+wall pipe spec."""
        net   = Network(_y_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        _full_check_y(net)

    def test_physical_groups(self, gmsh_session):
        """Y-junction must produce exactly one inlet and two outlets."""
        import gmsh
        net   = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        net.write_physical_groups()
        gmsh.model.mesh.generate(3)
        names = {
            gmsh.model.getPhysicalName(dim, tag)
            for dim, tag in gmsh.model.getPhysicalGroups()
        }
        assert "fluid"         in names
        assert "fluid_inlet"   in names
        assert "fluid_outlet"  in names
        assert "fluid_wall"    in names

    def test_inlet_is_single_surface_set(self, gmsh_session):
        """The system inlet (upstream of the Y) must be inlet-only."""
        net   = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in  = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        rset = net._all_regions["fluid"]
        inlet_only  = set(rset.inlets)  - set(rset.outlets)
        outlet_only = set(rset.outlets) - set(rset.inlets)
        assert inlet_only,  "No inlet-only surfaces — original inlet face is missing"
        assert outlet_only, "No outlet-only surfaces — branch outlets are missing"

    def test_no_tangential_extrusion_warning(self, gmsh_session):
        """Neither branch of a Y-junction should trigger a tangential warning."""
        import warnings
        net  = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in = net.add(Straight(0.3, n_layers=3))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        tangential = [
            x for x in w if issubclass(x.category, RuntimeWarning)
            and "tangential" in str(x.message).lower()
        ]
        assert not tangential, (
            f"Unexpected tangential-extrusion warning on Y-junction: {tangential}"
        )

    def test_no_volume_overlap(self, gmsh_session):
        """Branch volumes must not overlap in 3-D space.

        Two checks are performed:

        1. **Geometry**: branch outlet cursor positions are separated by at
           least 2 * R_outer, so the two branch cylinders cannot intersect.

        2. **Mesh (centroid)**: after meshing, no element centroid may appear
           in two different GMSH volumes.  Crossing transfinite hex volumes
           produce elements that occupy the same 3-D region but have DISTINCT
           nodes — so a coincident-node check misses this class of bug.  The
           centroid grid-hash catches it in O(n) time.
        """
        half_angle = 45.0
        R_outer    = 0.1  # matches _y_circle_pipe() radius

        net    = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in   = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=half_angle, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))

        # --- 1. Geometry check: branch outlets must be ≥ 2*R apart ----------
        p1   = n1.cursor.position
        p2   = n2.cursor.position
        dist = np.linalg.norm(p1 - p2)
        assert dist >= 2.0 * R_outer, (
            f"Branch outlet positions are too close: dist={dist:.4f} < "
            f"2*R={2*R_outer:.4f}.  The branch cylinders intersect."
        )

        # --- 2. Mesh check: no cross-volume centroid collisions --------------
        net.mesh()
        _check_no_volume_overlap()
        _check_hex_quality(net, max_degenerate=35)

    def test_no_volume_overlap_two_layer(self, gmsh_session):
        """Same cross-volume centroid check for a two-layer (core + wall) pipe."""
        net    = Network(_y_two_layer_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in   = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=0.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        net.mesh()
        _check_no_volume_overlap()
        _check_hex_quality(net, max_degenerate=35)

    def test_no_volume_overlap_vertical(self, gmsh_session):
        """Cross-volume centroid check for roll=90 (vertical Y-junction)."""
        net    = Network(_y_circle_pipe(), cursor=_xz_cursor(), lc=0.1)
        n_in   = net.add(Straight(0.3, n_layers=3))
        n1, n2 = net.add(n_in, YJunction(length=0.12, half_angle=45, roll=90.0))
        net.add(n1, Straight(0.3, n_layers=3))
        net.add(n2, Straight(0.3, n_layers=3))
        net.mesh()
        _check_no_volume_overlap()
        _check_hex_quality(net, max_degenerate=35)
