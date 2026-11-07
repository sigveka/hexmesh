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
Insulation planning (decision 0023, task 0038; split from ``build``, task
0066): the thickness at each end of each part, the switches along a run,
and the dressed spec.  Format-neutral, as ``build``.
"""

from __future__ import annotations

import math

import numpy as np

from .model import NetworkModel
from .graph import _Comp, _source, _part_id, _describe


def _radius(spec) -> float:
    """The core radius: pipe sections are round (``max_extent``)."""
    return spec.core_shape.max_extent


#: Name of the shell ``to_assembly(insulation=True)`` adds.
INSULATION = "insulation"


def _resolve_insulation(model: NetworkModel, comps: list[_Comp]) -> None:
    """Set ``ins`` (thickness at each end, 0 = bare) and ``ins_junction`` on
    every component.  Insulated only where the part's insulation is on; a
    port's own status overrides that end.  The thickness is the network's."""
    from ..assembly import AssemblyError
    for c in comps:
        label = c.label
        def thick(status):
            if status != "ON":
                return 0.0
            net = model.networks.get(c.system)
            t = net.insulation_thickness if net is not None else None
            if not t:
                kind = net.kind if net is not None else "network"
                raise AssemblyError(
                    f"{kind} {c.system or '(none)'!r}: {_describe(c, label)} is "
                    f"insulated but the {kind} has no insulation thickness",
                    code="insulation_thickness_missing",
                    where={"part": _part_id(c), "source": _source(c)})
            return t
        own = c.insulation
        c.ins = tuple(thick(e or own) for e in c.end_insulation)
        legs = [own] + [b or own for b in c.branch_insulation]
        c.ins_junction = (_junction_thickness(
            [thick(x) for x in legs + [e or own for e in c.end_insulation]],
            _describe(c, label)) if c.kind in ("tee", "seton", "ypiece") else 0.0)


def _junction_thickness(ts, what: str) -> float:
    """The insulation thickness through a junction: that of its insulated
    legs (0 if none).  The insulation runs through the junction (task 0054);
    a bare leg ends it one cell into its first straight."""
    from ..assembly import AssemblyError
    found = sorted({t for t in ts if t > 0})
    if len(found) > 1:
        raise AssemblyError(f"{what}: its legs have insulation {found[0]:.4g} m and "
                            f"{found[-1]:.4g} m; a junction carries one thickness",
                            code="junction_insulation_differs", value=found,
                            hint="give the junction's legs one insulation thickness; change it on a straight pipe next to it")
    return found[0] if found else 0.0


def _dressed(spec, t: float, nrad: int):
    """*spec* without its ``insulation`` shell, plus one of thickness *t*
    (none if ``t`` is 0)."""
    shells = spec.shells
    if shells and shells[-1].name == INSULATION:
        shells = shells[:-1]
    bare = spec.with_radii([_radius(spec)] + [sh.dR for sh in shells])
    return bare.shell(INSULATION, dR=t, nrad=nrad) if t > 0 else bare


def _thickness(spec) -> float:
    sh = spec.shells
    return sh[-1].dR if sh and sh[-1].name == INSULATION else 0.0


def _straight_like(c: _Comp, tol: float) -> bool:
    return c.kind in ("pipe", "fitting") and float(np.linalg.norm(c.end - c.start)) > tol


def _plan_insulation(comps, labels, t_in, to_junction, tol):
    """Insulation switches along a run of oriented two-port components.

    *t_in* is the thickness of the interface the run starts from;
    *to_junction* is the thickness of the junction the run ends at (None:
    an open end).  Returns, per
    component, ``(t_inlet, t_outlet, cell_pattern)``: the thickness at its
    ports and, for a straight that hosts a switch, the per-cell thickness
    as ``(first, middle_in, middle_out, last)``.  A switch sits one cell
    inside a straight neighbour, the bare one if both are straight."""
    from ..assembly import AssemblyError
    n = len(comps)
    a = [c.ins[0] for c in comps]
    b = [c.ins[1] for c in comps]
    straight = [_straight_like(c, tol) for c in comps]
    port_in, port_out = list(a), list(b)     # thickness at each port
    for k, c in enumerate(comps):
        if a[k] != b[k] and not straight[k]:
            raise AssemblyError(f"{labels[k]}: insulation changes inside it, and only "
                                f"a straight component can hold the change",
                                code="insulation_change_not_straight",
                                where={"part": _part_id(comps[k]), "source": _source(comps[k])})
        if a[k] > 0 and b[k] > 0 and a[k] != b[k]:
            raise AssemblyError(f"{labels[k]}: insulation thickness changes inside it",
                                code="insulation_change_inside",
                                where={"part": _part_id(comps[k]), "source": _source(comps[k])})

    def host(k_left, k_right, t_left, t_right, where):
        """Boundary between *k_left* (outlet) and *k_right* (inlet); either
        may be None (fixed: the interface or a junction)."""
        if t_left == t_right:
            return
        if t_left > 0 and t_right > 0:
            name = labels[k_left if k_left is not None else k_right]
            raise AssemblyError(f"{name}: insulation thickness changes from "
                                f"{t_left:.4g} m to {t_right:.4g} m at {where}; only "
                                f"a layer that ends or starts is supported",
                                code="insulation_thickness_change",
                                where={"part": _part_id(comps[k_left if k_left is not None
                                                              else k_right])},
                                value=t_right, limit=t_left)
        options = [k for k in (k_left, k_right) if k is not None and straight[k]]
        options.sort(key=lambda k: (t_left if k == k_left else t_right) > 0)  # bare first
        if not options:
            name = labels[k_left if k_left is not None else k_right]
            raise AssemblyError(f"{name}: insulation starts or stops at {where}, and "
                                f"no straight component next to it can hold the change",
                                code="insulation_change_not_straight",
                                where={"part": _part_id(comps[k_left if k_left is not None
                                                              else k_right])})
        k = options[0]
        if k == k_left:                       # the left one takes the right's status
            port_out[k] = t_right
        else:
            port_in[k] = t_left

    host(None, 0, t_in, a[0], "its inlet")
    for k in range(n - 1):
        host(k, k + 1, b[k], a[k + 1], f"its joint with {labels[k + 1]}")
    if to_junction is not None:
        host(n - 1, None, b[-1], to_junction, "the junction after it")
    return [(port_in[k], port_out[k], (port_in[k], a[k], b[k], port_out[k]))
            for k in range(n)]


def _stack_changes(pattern, length, axial_cell, base, nrad):
    """``(n_layers, stack_changes)`` for a straight with per-cell pattern
    ``(first, middle_in, middle_out, last)`` (thickness, m); None if
    uniform."""
    first, mid_a, mid_b, last = pattern
    if first == mid_a == mid_b == last:
        return None
    n = max(1, math.ceil(length / axial_cell - 1e-9))
    need = 1 + (first != mid_a) + (last != mid_b) + (mid_a != mid_b)
    n = max(n, need, 4 if mid_a != mid_b and need > 2 else 0)
    cells = [mid_a] * (n // 2) + [mid_b] * (n - n // 2)
    cells[0], cells[-1] = first, last
    changes, cur = [], cells[0]
    for i, t in enumerate(cells):
        if i and t != cur:
            changes.append((i, _dressed(base, t, nrad)))
            cur = t
    return n, tuple(changes)
