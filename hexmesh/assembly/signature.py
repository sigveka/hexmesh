"""
Port-face signatures and the topology-switch classifier (DESIGN A4,
decision 0011, docs/tasks/0019).

A face's **signature** is what fixes its mesh connectivity: per layer the
name, the layout kind and the chord-family counts, plus the section-level
counts and symmetry.  Geometry is left out: radii, shape dimensions and
``rot``.  Shape is geometry too (decision 0009): a circular and a
rectangular O-H core share the ``oh_core`` layout, the counts are per side
(``nang_w``, ``nang_h``; a circle has both equal to ``nang``), and the
period is the combinatorial one, from the counts: 90° when they are equal,
180° when not (roll handling uses the geometric ``PipeSpec.period``).  ``rot`` rotates the whole face rigidly, with the same entities
and nodes (task 0019), so it is placement, not connectivity.  Grading
(``mprg``, ``mbmp``) is kept: an interface has one node set (decision
0016).

``classify(a, b)`` sorts a pair of signatures into a switch class:

* **0**: equal;
* **1**: they differ only by whole outermost layers present on one side
  (layer termination: the ring's end face is exposed, so it ends on a wall);
* **2**: same layers and layouts, different counts or grading.  When
  the only differences are per-layer radial ``mprg`` (all counts and
  ``mbmp`` equal), it is marked ``grading_only`` (decision 0016);
* **3**: anything else.

A fitting declares the classes it can bridge in ``strategies``: one
frozenset for every port pair (inlet → each outlet), or a tuple with one
frozenset per outlet.  ``check_port_pairs`` raises for any pair whose
class is not declared, naming what differs.  Declaring class 2 bridges
grading-only pairs only: a sweep interpolates grading per station, while
count changes need a refinement template (decision 0003), which no
fitting has yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.spec import LayerSpec, PipeSpec

# What a class needs, for error messages.
BRIDGES = {
    1: "layer termination (task 0018)",
    2: "a density switch (decision 0003)",
    3: "a topology switch (decision 0003)",
}


@dataclass(frozen=True)
class LayerSig:
    name:  str
    kind:  str      # "oh_core" | "annulus"
    nrad:  int
    mprg:  float


@dataclass(frozen=True)
class Signature:
    n_outer: int
    period:  float  # combinatorial symmetry period, degrees (decisions 0009, 0010)
    nang_w:  int    # divisions per side: width (corner 0 → 1) …
    nang_h:  int    # … and height (corner 1 → 2); equal on a circle
    mbmp:    float
    layers:  tuple[LayerSig, ...]


@dataclass(frozen=True)
class Difference:
    field: str
    a:     object
    b:     object
    text:  str = ""

    def __str__(self) -> str:
        return self.text or f"{self.field} ({self.a!r} vs {self.b!r})"


@dataclass(frozen=True)
class SwitchClass:
    cls:         int
    differences: tuple[Difference, ...] = ()
    ends:        str | None = None   # class 1: "wall" (termination); see module doc
    grading_only: bool = False       # class 2: only radial mprg differs (decision 0016)

    def __int__(self) -> int:
        return self.cls


def signature(spec: PipeSpec) -> Signature:
    """Connectivity signature of *spec* (pure Python, hashable)."""
    name, _ = spec._core
    layers = [LayerSig(name, "oh_core", spec._core_nrad, spec._core_mprg)]
    for sh in spec.shells:
        if not isinstance(sh, LayerSpec):
            raise ValueError(f"no signature for a {type(sh).__name__} layer")
        layers.append(LayerSig(sh.name, "annulus", sh.nrad, sh.mprg))
    c = spec.side_counts
    period = 360.0 / spec.n_outer if c[0] == c[1] else 180.0
    return Signature(spec.n_outer, period, c[0], c[1], spec.mbmp, tuple(layers))


def classify(a: Signature, b: Signature) -> SwitchClass:
    """Switch class of the pair *a* → *b*, with what differs."""
    if a == b:
        return SwitchClass(0)
    section = [Difference(f, getattr(a, f), getattr(b, f))
               for f in ("n_outer", "period") if getattr(a, f) != getattr(b, f)]
    if section:
        return SwitchClass(3, tuple(section))

    la, lb = a.layers, b.layers
    common = min(len(la), len(lb))
    same_frame = all((x.name, x.kind) == (y.name, y.kind) for x, y in zip(la, lb))
    if not same_frame:
        diffs = []
        for i, (x, y) in enumerate(zip(la, lb)):
            if (x.name, x.kind) != (y.name, y.kind):
                diffs.append(Difference(
                    "shells" if i else "core", (x.name, x.kind), (y.name, y.kind),
                    f"{'shells' if i else 'core'}: layer {i} is `{x.name}` ({x.kind}) "
                    f"vs `{y.name}` ({y.kind})"))
        if len(la) != len(lb):
            diffs.append(_extra_layers(la, lb))
        return SwitchClass(3, tuple(diffs))

    counts = _count_differences(a, b, common)
    if len(la) != len(lb):
        extra = _extra_layers(la, lb)
        if counts:
            return SwitchClass(3, tuple(counts) + (extra,))
        return SwitchClass(1, (extra,), ends="wall")
    return SwitchClass(2, tuple(counts),
                       grading_only=all(d.field.endswith(" mprg") for d in counts))


def _count_differences(a: Signature, b: Signature, common: int) -> list[Difference]:
    out = []
    if a.nang_w == a.nang_h and b.nang_w == b.nang_h:
        fields = ("mbmp",)           # one count per side on both: say ``nang``
        if a.nang_w != b.nang_w:
            out.append(Difference("nang", a.nang_w, b.nang_w))
    else:
        fields = ("nang_w", "nang_h", "mbmp")
    for f in fields:
        if getattr(a, f) != getattr(b, f):
            out.append(Difference(f, getattr(a, f), getattr(b, f)))
    for i in range(common):
        x, y = a.layers[i], b.layers[i]
        where = "core" if i == 0 else f"shell `{x.name}`"
        for f in ("nrad", "mprg"):
            if getattr(x, f) != getattr(y, f):
                out.append(Difference(f"{where} {f}", getattr(x, f), getattr(y, f)))
    return out


def _extra_layers(la, lb) -> Difference:
    side, extra = ("the inlet", la[len(lb):]) if len(la) > len(lb) else ("the outlet", lb[len(la):])
    names = ", ".join(f"`{l.name}`" for l in extra)
    return Difference("shells", len(la), len(lb),
                      f"shells: layer {names} present only at {side}")


def strategies_for(fitting, k: int) -> frozenset:
    """Classes *fitting* can bridge on its port pair inlet → outlet *k*."""
    s = getattr(fitting, "strategies", None)
    if s is None:
        raise TypeError(f"{type(fitting).__name__} declares no strategies (DESIGN A4)")
    return s[k] if isinstance(s, tuple) else s


def check_port_pairs(fitting, specs: list[PipeSpec]) -> None:
    """Raise ValueError if a port pair's class is not in the fitting's
    strategies.  *specs* is ``[inlet, outlet 0, outlet 1, …]``."""
    name = type(fitting).__name__
    a = signature(specs[0])
    for k, spec in enumerate(specs[1:]):
        c = classify(a, signature(spec))
        allowed = strategies_for(fitting, k)
        port = "outlet" if len(specs) == 2 else f"outlet {k}"
        what = "; ".join(str(d) for d in c.differences)
        if c.cls == 2 and 2 in allowed and not c.grading_only:
            raise ValueError(
                f"{name}: {port} spec differs from the inlet in {what}. That is "
                f"switch class 2 beyond radial grading (counts or mbmp), which "
                f"needs {BRIDGES[2]}; {name} bridges grading-only class-2 pairs "
                f"(radial mprg) only")
        if c.cls in allowed:
            continue
        raise ValueError(
            f"{name}: {port} spec differs from the inlet in {what}. That is "
            f"switch class {c.cls}, which needs {BRIDGES[c.cls]}; {name} "
            f"declares strategies {sorted(allowed)}")
