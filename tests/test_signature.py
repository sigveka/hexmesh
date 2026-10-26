"""
Port-face signatures and the switch classifier (decision 0011,
docs/tasks/0019).  Pure Python: no GMSH.
"""

import gmsh
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Reducer, Straight, Tee
from hexmesh.assembly.signature import classify, signature
from hexmesh.core.spec import PipeSpec


def _spec(r=0.1, nang=4, nrad=3, layers=(("wall", 0.02, 2),), mprg=None, rot=0.0, names=None):
    names = names or ["fluid"] + [l[0] for l in layers]
    s = PipeSpec(nang=nang, rot=rot).core(names[0], radius=r, nrad=nrad, mprg=mprg)
    for name, (_, dR, n) in zip(names[1:], layers):
        s = s.shell(name, dR=dR, nrad=n)
    return s


def _cls(a, b):
    return classify(signature(a), signature(b))


class TestSignature:
    def test_hashable_and_equal(self):
        assert hash(signature(_spec())) == hash(signature(_spec()))
        assert signature(_spec()) == signature(_spec())

    def test_geometry_excluded(self):
        assert signature(_spec(r=0.1)) == signature(_spec(r=0.3, layers=(("wall", 0.05, 2),)))

    def test_rot_is_placement(self):
        assert signature(_spec(rot=0.0)) == signature(_spec(rot=0.3))

    def test_contents(self):
        sig = signature(_spec())
        assert (sig.n_outer, sig.period, sig.nang) == (4, 90.0, 4)
        assert [(l.name, l.kind, l.nrad) for l in sig.layers] == [
            ("fluid", "oh_core", 3), ("wall", "annulus", 2)]


class TestClassify:
    def test_equal_is_0(self):
        assert _cls(_spec(), _spec()).cls == 0

    def test_radius_only_is_0(self):
        assert _cls(_spec(r=0.1), _spec(r=0.05)).cls == 0

    def test_outermost_layer_removed_is_1(self):
        c = _cls(_spec(), _spec(layers=()))
        assert c.cls == 1 and c.ends == "wall"
        assert "layer `wall` present only at the inlet" in str(c.differences[0])
        c = _cls(_spec(layers=()), _spec())
        assert c.cls == 1 and "only at the outlet" in str(c.differences[0])

    @pytest.mark.parametrize("b, field", [
        (_spec(nang=8), "nang (4 vs 8)"),
        (_spec(nrad=5), "core nrad (3 vs 5)"),
        (_spec(layers=(("wall", 0.02, 4),)), "shell `wall` nrad (2 vs 4)"),
        (_spec(mprg=1.2), "core mprg (1.0 vs 1.2)"),          # grading kept (decision 0011 Q3)
    ])
    def test_counts_or_grading_is_2(self, b, field):
        c = _cls(_spec(), b)
        assert c.cls == 2
        assert field in [str(d) for d in c.differences]

    def test_renamed_is_3(self):
        c = _cls(_spec(), _spec(names=["fluid", "steel"]))
        assert c.cls == 3 and "`wall` (annulus) vs `steel` (annulus)" in str(c.differences[0])

    def test_reordered_is_3(self):
        two = (("a", 0.02, 2), ("b", 0.02, 2))
        assert _cls(_spec(layers=two), _spec(layers=two, names=["fluid", "b", "a"])).cls == 3

    def test_termination_with_density_change_is_3(self):
        assert _cls(_spec(), _spec(nrad=5, layers=())).cls == 3

    def test_partition_change_is_3(self):
        a = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3)
        b = PipeSpec(nang=4, n_outer=8).core("fluid", radius=0.1, nrad=3)
        c = _cls(a, b)
        assert c.cls == 3 and {d.field for d in c.differences} == {"n_outer", "period"}


# ---------------------------------------------------------------------------
# Rejected before GMSH, naming the difference
# ---------------------------------------------------------------------------

def test_reducer_changing_nang_rejected():
    asm = Assembly(_spec())
    asm.add(Reducer(_spec(r=0.06, nang=8), 0.2, n_layers=3))
    with pytest.raises(AssemblyError, match=r"nang \(4 vs 8\)\. That is switch class 2"):
        asm.validate()
    assert not gmsh.isInitialized()


def test_straight_dropping_a_layer_rejected():
    """Straight bridges class 1 only through its own stack changes (task
    0018); an outlet spec edited by hand is still not the declared type."""
    asm = Assembly(_spec())
    out = asm.add(Straight(0.3, n_layers=2))
    out.spec = _spec(layers=())
    with pytest.raises(AssemblyError,
                       match=r"port type .* \(shells: layer `wall` present only at the inlet\)"):
        asm.validate()
    assert not gmsh.isInitialized()


def test_class_1_rejected_where_not_declared():
    from hexmesh.assembly import MiterBend
    from hexmesh.assembly.signature import check_port_pairs
    with pytest.raises(ValueError, match="class 1, which needs layer termination"):
        check_port_pairs(MiterBend(0.3, 90, n_cuts=1), [_spec(), _spec(layers=())])


def test_straight_joined_to_another_stack_rejected():
    asm = Assembly(_spec())
    out = asm.add(Straight(0.3, n_layers=2))
    out.spec = _spec(names=["fluid", "steel"])
    with pytest.raises(AssemblyError, match=r"`wall` \(annulus\) vs `steel`.*class 3"):
        asm.validate()
    assert not gmsh.isInitialized()


def test_every_fitting_declares_strategies():
    from hexmesh.assembly import fittings
    for cls in (fittings.MiterBend, fittings.Elbow, fittings.Reducer,
                fittings.SplinePipe, fittings.Closure, Tee):
        assert cls.__dict__.get("strategies") == frozenset({0}), cls.__name__
    for cls in (fittings.Straight, fittings.Bend):          # layer termination (0018)
        assert cls.__dict__.get("strategies") == frozenset({0, 1}), cls.__name__
