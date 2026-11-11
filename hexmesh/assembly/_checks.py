#        _.-------._
#    .-''     |     ''-.
#  .'  \      |      /  '.     _                                         _
# /     +-----+-----+     \   | |__   ___  __  __  _ __ ___   ___  ___  | |__
# |     |     |     |     |   | '_ \ / _ \ \ \/ / | '_ ` _ \ / _ \/ __| | '_ \
# |-----+-----+-----+-----|   | | | |  __/  >  <  | | | | | |  __/\__ \ | | | |
# |     |     |     |     |   |_| |_|\___| /_/\_\ |_| |_| |_|\___||___/ |_| |_|
# \     +-----+-----+     /
#  '.  /      |      \  .'    structured all-hex meshes for pipe networks
#    '-..     |     ..-'
#        '---------'
#
"""
Checks around meshing: the GMSH session, the meshed cells, second order,
and the correction record and quality report (task 0136).
"""

from __future__ import annotations
import copy
import warnings

import numpy as np

from .._gmsh import gmsh
from ..errors import HexmeshWarning
from .errors import AssemblyError
from ..quality_hex import METRICS, hex_vertices, max_non_orthogonality, min_scaled_jacobians
from . import limits
from .quality import QualityReport, RegionQuality


def _require_session() -> None:
    """Raise before any GMSH call when no GMSH session is open (task 0039)."""
    if not gmsh.isInitialized():
        raise AssemblyError("needs a GMSH session: use `with Session(...):`",
                            code="no_gmsh_session", hint="open one with `with Session(...):`")


def _check_projection(asm, moved: dict[int, tuple[np.ndarray, np.ndarray]]) -> None:
    """Record each projected fitting's largest move (absolute, and in
    local wall radii) and, after volume meshing, its cells' min corner
    scaled Jacobian (its cells and its neighbours'), in
    ``projection_report``.  A move beyond
    ``limits.WALL_PROJECTION_WARN_MOVE`` radii warns; a cell with a
    corner SJ ≤ 0 is an ``AssemblyError`` naming the fitting
    (decision 0029, task 0056)."""
    asm.projection_report = {}
    meshed = bool(moved) and len(gmsh.model.mesh.getElements(3)[0]) > 0
    if meshed:
        ntag, nx, _ = gmsh.model.mesh.getNodes()
        pos = np.full(int(ntag.max()) + 1, -1)
        pos[ntag.astype(int)] = np.arange(len(ntag))
        nx = nx.reshape(-1, 3)
    for e in asm._edges:
        if e.index not in moved:
            continue
        move, radius, _ = moved[e.index]
        ratio = move / radius
        rep = asm.projection_report[e.name] = {
            "move": float(move.max()), "ratio": float(ratio.max())}
        if ratio.max() > limits.WALL_PROJECTION_WARN_MOVE:
            msg = (f"{e.name}{e.at}: wall projection moves a node by "
                   f"{move[ratio.argmax()]:.3g}, "
                   f"{ratio.max():.2f} local wall radii (WALL_PROJECTION_WARN_MOVE "
                   f"{limits.WALL_PROJECTION_WARN_MOVE:g})")
            asm.warnings.append(msg)
            warnings.warn(HexmeshWarning(msg,
                                         code="wall_projection_moves_node",
                                         where=e.where,
                                         value=float(ratio.max()),
                                         limit="WALL_PROJECTION_WARN_MOVE"), stacklevel=4)
        if not meshed:
            continue
        # the fitting and its neighbours: a projector that moves port
        # nodes (it must not) folds the swept cells next to them
        ports = {i.index for i in e.ports}
        near = [f.index for f in asm._edges if ports & {i.index for i in f.ports}]
        hexes = [n.reshape(-1, 8) for i in near for v in asm._fitting_volumes[i]
                 for t, _, n in zip(*gmsh.model.mesh.getElements(3, v)) if t == 5]
        sj = min_scaled_jacobians(nx[pos[np.vstack(hexes).astype(int)]])
        rep["min_sj"] = float(sj.min())
        if sj.min() <= 0:
            raise AssemblyError(
                f"{e.name}{e.at}: wall projection folded {int((sj <= 0).sum())} cell(s), "
                f"min corner scaled Jacobian {sj.min():.3g} (decision 0029)",
                code="wall_projection_folded", where=e.where,
                value=float(sj.min()), limit={"min_exclusive": 0})


def _check_second_order(asm) -> None:
    """An ``AssemblyError`` naming the fitting for any high-order hex
    whose Jacobian determinant is ≤ 0 at one of its nodes or at a
    ``Gauss4`` integration point."""
    msh = gmsh.model.mesh
    for e in asm._edges:
        bad = total = 0
        for v in asm._fitting_volumes.get(e.index, []):
            for t, tags, _ in zip(*msh.getElements(3, v)):
                t = int(t)
                props = msh.getElementProperties(t)
                gauss, _ = msh.getIntegrationPoints(t, "Gauss4")
                worst = None
                for local in (np.asarray(props[4]), gauss):
                    _, det, _ = msh.getJacobians(t, local, tag=v)
                    det = det.reshape(len(tags), -1).min(axis=1)
                    worst = det if worst is None else np.minimum(worst, det)
                bad += int((worst <= 0).sum())
                total += len(tags)
        if bad:
            raise AssemblyError(
                f"{e.name}{e.at}: {bad} of {total} second-order hexes have a Jacobian "
                "determinant <= 0 at a node or Gauss point",
                code="second_order_inverted", where=e.where, value=bad,
                limit={"max": 0}, hint="mesh it at order=1, or refine it")


def _check_meshed_sj(asm) -> None:
    """For fittings whose predicted corner SJ is not a bound
    (``meshed_sj_check``: round duct taps, task 0070; switches to a
    graded H face and the fittings that embed them, task 0086), apply the
    predicted-SJ tiers to the meshed cells: a warning below
    ``PREDICTED_SJ_WARN``, an ``AssemblyError`` below
    ``PREDICTED_SJ_MIN``, each naming the fitting.  Fittings whose
    ``meshed_nonorth_check`` is true (switches to a graded H face, task
    0086; every junction, task 0104) get the outline tiers on the meshed
    non-orthogonality too: a warning above ``OUTLINE_NONORTH_WARN``, an
    error above ``OUTLINE_NONORTH_MAX`` (a warning where the fitting's
    ``meshed_nonorth_reject`` is false: the wye).  A fill may name the volumes measured
    (``FillResult.checked_volumes``)."""
    check = lambda e, name: (getattr(e.fitting, name, None)
                             and e.fitting.__getattribute__(name)(e.ports[0].spec))
    edges = [e for e in asm._edges
             if check(e, "meshed_sj_check") or check(e, "meshed_nonorth_check")]
    if not edges:
        return
    ntag, nx, _ = gmsh.model.mesh.getNodes()
    pos = np.full(int(ntag.max()) + 1, -1)
    pos[ntag.astype(int)] = np.arange(len(ntag))
    nx = nx.reshape(-1, 3)
    def conn_of(vols):
        hexes = [n.reshape(-1, 8) for v in vols
                 for t, _, n in zip(*gmsh.model.mesh.getElements(3, v)) if t == 5]
        return pos[np.vstack(hexes).astype(int)]

    for e in edges:
        conn = conn_of(asm._checked_volumes.get(e.index, asm._fitting_volumes[e.index]))
        if check(e, "meshed_nonorth_check"):
            # a junction's whole fill, its switch legs included (task 0104)
            c = (conn_of(asm._fitting_volumes[e.index])
                 if hasattr(e.fitting, "predicted_nonorth") else conn)
            _check_meshed_nonorth(asm, e, max_non_orthogonality(nx[c], c))
        if not check(e, "meshed_sj_check"):
            continue
        sj = float(min_scaled_jacobians(nx[conn]).min())
        if sj < limits.PREDICTED_SJ_MIN:
            hint = getattr(e.fitting, "meshed_sj_hint",
                           "a smaller tap, or the wide face, may do better")
            if callable(hint):                  # depends on the spec (Tee)
                hint = hint(e.ports[0].spec)
            raise AssemblyError(
                f"{e.name}{e.at}: meshed corner scaled Jacobian {sj:.3f} is below "
                f"PREDICTED_SJ_MIN {limits.PREDICTED_SJ_MIN:g}; {hint}",
                code="meshed_sj_below_minimum", where=e.where,
                value=sj, limit="PREDICTED_SJ_MIN", hint=hint)
        if sj < limits.PREDICTED_SJ_WARN:
            msg = (f"{e.name}{e.at}: meshed corner scaled Jacobian {sj:.3f} is below "
                   f"PREDICTED_SJ_WARN {limits.PREDICTED_SJ_WARN:g}")
            asm.warnings.append(msg)
            warnings.warn(HexmeshWarning(msg,
                                         code="meshed_sj_low",
                                         where=e.where, value=sj,
                                         limit="PREDICTED_SJ_WARN"), stacklevel=4)


def _check_meshed_nonorth(asm, e, angle: float) -> None:
    # it rises with a switch's length (task 0086), so not the SJ hint;
    # a junction names its own (task 0104)
    f, spec = e.fitting, e.ports[0].spec
    hint = (f.meshed_nonorth_hint(spec) if hasattr(f, "meshed_nonorth_hint")
            else "a gentler wall grading of the H face, or a smaller ring nrad")
    reject = getattr(f, "meshed_nonorth_reject", True)
    if angle > limits.OUTLINE_NONORTH_MAX and reject:
        raise AssemblyError(
            f"{e.name}{e.at}: meshed non-orthogonality {angle:.1f}° is above "
            f"OUTLINE_NONORTH_MAX {limits.OUTLINE_NONORTH_MAX:g}°; {hint}",
            code="meshed_nonorth_above_maximum", where=e.where,
            value=angle, limit="OUTLINE_NONORTH_MAX", hint=hint)
    # a junction whose prediction already warned on this tier says it once
    if hasattr(f, "predicted_nonorth"):
        tier = lambda a: (a > limits.OUTLINE_NONORTH_WARN) + (a > limits.OUTLINE_NONORTH_MAX)
        if tier(f.predicted_nonorth([p.frame for p in e.ports], spec)) >= tier(angle):
            return
    if angle > limits.OUTLINE_NONORTH_WARN:
        limit = ("OUTLINE_NONORTH_MAX" if angle > limits.OUTLINE_NONORTH_MAX
                 else "OUTLINE_NONORTH_WARN")
        msg = (f"{e.name}{e.at}: meshed non-orthogonality {angle:.1f}° is above "
               f"{limit} {getattr(limits, limit):g}°; {hint}")
        asm.warnings.append(msg)
        warnings.warn(HexmeshWarning(msg,
                                     code="meshed_nonorth_high",
                                     where=e.where, value=angle,
                                     limit=limit), stacklevel=5)


def _written_elements(asm, e) -> int:
    """The elements hexmesh writes for fitting *e* (decision 0046 rule 3),
    0 for gmsh's: a fitting opts in with a true ``written_elements``
    (task 0124; none does yet)."""
    if not getattr(e.fitting, "written_elements", False):
        return 0
    return asm.cell_counts()[e.index]


def _record_corrections(asm, moved: dict, placed: dict, arcs: dict) -> None:
    """``corrections``, for every fitting (decision 0046 rule 5, tasks
    0123 and 0130): the wall nodes projection moved, a bend's
    second-order nodes placed on its arcs, the second-order wall nodes
    placed, each with its largest move (absolute, in local wall radii,
    in local edge lengths), or ``"none"``; and the elements hexmesh
    wrote.  A node counts as moved beyond ``CORRECTION_MIN_MOVE`` local
    wall radii (rounding below it).  A wall node of a bend is placed
    on its arc, then on the wall: each entry measures its own step."""
    def record(m):
        if m is None:
            return "none"
        move, radius, edge = m
        hit = move / radius > limits.CORRECTION_MIN_MOVE
        if not hit.any():
            return "none"
        return {"nodes": int(hit.sum()), "largest_move": float(move.max()),
                "largest_move_radii": float((move / radius).max()),
                "largest_move_edges": float((move / edge).max())}
    asm.corrections = {
        e.name: {"fitting": e.index, "type": type(e.fitting).__name__,
                 "wall_projection": record(moved.get(e.index)),
                 "second_order_arc_nodes": record(arcs.get(e.index)),
                 "second_order_wall_nodes": record(placed.get(e.index)),
                 "elements_written": _written_elements(asm, e)}
        for e in asm._edges}


def check_quality(asm, quality_name: str = "minSICN",
                  threshold: float | None = None,
                  by: str = "material") -> QualityReport:
    _require_session()
    if not asm._meshed:
        raise AssemblyError("no mesh yet; call mesh() or write() first",
                            code="no_mesh_yet", hint="call mesh() or write() first")
    if by == "material":
        groups = [(name, None, vols) for name, vols in asm.volumes.items()]
    elif by == "fitting":
        asm.build()
        groups = [(f"#{e.index} {type(e.fitting).__name__}", e.index,
                   asm._fitting_volumes[e.index]) for e in asm._edges]
    else:
        raise AssemblyError(f'by must be "material" or "fitting", got {by!r}',
                            code="option_invalid", where={"field": "by"}, value=by,
                            limit=["material", "fitting"])

    metric = METRICS.get(quality_name)
    higher = metric.higher_is_better if metric else True
    if threshold is None:
        threshold = metric.default_threshold if metric else 0.0
    report = QualityReport(quality_name=quality_name, threshold=threshold,
                           higher_is_better=higher, corrections=copy.deepcopy(asm.corrections))
    for name, index, vols in groups:
        q = _element_qualities(vols, quality_name, metric)
        if not q.size:
            continue
        bad = (q <= threshold) if higher else (q >= threshold)
        report.regions.append(RegionQuality(
            name=name, n_elements=len(q), n_bad=int(bad.sum()),
            min_quality=float(q.min()), max_quality=float(q.max()),
            mean_quality=float(q.mean()),
            quality_name=quality_name, threshold=threshold,
            higher_is_better=higher, fitting=index,
        ))
    return report


def _element_qualities(vols: list[int], quality_name: str, metric) -> np.ndarray:
    if metric is not None:
        _, verts = hex_vertices(vols)
        return np.array([metric.fn(v) for v in verts])
    tags: list[int] = []
    for v in vols:
        _, etags, _ = gmsh.model.mesh.getElements(3, v)
        for arr in etags:
            tags.extend(arr.tolist())
    if not tags:
        return np.empty(0)
    return np.array(gmsh.model.mesh.getElementQualities(tags, quality_name))
