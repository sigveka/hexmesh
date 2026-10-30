"""
Duct taps: ``Tee`` on a rectangular main (decision 0033 B; prototype task
0069, merged in task 0070).  The kit (``test_fitting_conformance``) covers
all-hex, meshed = predicted, class-0 ports and exact walls on 2:1 and 3:1
ducts; here the dispatch, the checks, the quality tiers and the JSON.
"""

import math
import warnings

import gmsh
import numpy as np
import pytest

from hexmesh.assembly import Assembly, AssemblyError, Straight, Tee, intent, limits
from hexmesh.assembly.duct_tap import DuctTap
from hexmesh.assembly.interface import Frame
from hexmesh.core.shape import CircleShape, RectShape
from hexmesh.core.spec import PipeSpec

B = 0.05
A = 2 * B           # 2:1 duct, the tap on a wide face (half-width A)


def _spec(aspect=2, n=4, **kw):
    return PipeSpec(nang_w=n, nang_h=n, **kw).core("fluid", half_w=aspect * B, half_h=B, nrad=3)


def _asm(tee, spec=None, n=4):
    asm = Assembly(spec or _spec(n=n), direction=[1, 0, 0], up=[0, 0, 1], lc=0.1)
    asm.add(Straight(0.2, n_layers=n))
    main, branch = asm.add(tee)
    asm.add(main, Straight(0.2, n_layers=n))
    asm.add(branch, Straight(0.1, n_layers=n))
    return asm


def _rect(q, n=4):
    return RectShape(q, q, n, n)


def _tee(branch, **kw):
    kw.setdefault("branch_length", B + 2 * A)
    return Tee(branch=branch, n_run=4, n_branch=4, **kw)


def test_tunables_resolved_and_overridable():
    asm = _asm(_tee(_rect(0.6 * A)))
    tee = asm.edges[1].fitting
    assert None not in (tee.run_length, tee.margin, tee.dome, tee.sheet)
    fixed = _asm(_tee(_rect(0.6 * A), margin=1.0, dome=0.35, sheet=0.35)).edges[1].fitting
    assert (fixed.margin, fixed.dome, fixed.sheet) == (1.0, 0.35, 0.35)


@pytest.mark.parametrize("branch", [_rect(0.6 * A), CircleShape(radius=0.6 * A, nang=4)])
def test_json_round_trip_and_refinement(branch):
    asm = _asm(_tee(branch))
    d = intent.to_dict(asm)
    back = Assembly.from_dict(d)
    assert back.edges[1].fitting == asm.edges[1].fitting      # tunables explicit in the JSON
    assert back.cell_count() == asm.cell_count()
    fine = Assembly.from_dict(intent.refined_dict(d, 2))
    assert fine.edges[1].fitting.branch.to_dict()["nang_w" if isinstance(branch, RectShape)
                                                   else "nang"] == 8
    assert fine.cell_count() == 8 * asm.cell_count()


def test_layout_is_valid_on_every_face():
    """Pure: wide and narrow face, both sides, 1:1 to 3:1."""
    inlet = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    for asp in (1, 2, 3):
        spec = _spec(aspect=asp)
        for face in ("wide", "narrow"):
            fw = asp * B if face == "wide" else B
            for roll in (0, 180):
                tee = _tee(_rect(0.5 * fw), face=face, roll=roll).resolve(inlet, spec)
                frames = [inlet] + [f for f, _ in tee.ports(inlet, spec)]
                assert tee.layout(frames, spec).validate()["min_corner_sj"] > 0.05


def test_roll_picks_the_side():
    inlet = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    spec = _spec()
    zs = [_tee(_rect(0.5 * A), roll=r).resolve(inlet, spec).ports(inlet, spec)[1][0].normal
          for r in (0, 180)]
    np.testing.assert_allclose(zs, [[0, 0, 1], [0, 0, -1]], atol=1e-12)
    narrow = _tee(_rect(0.5 * B), face="narrow").resolve(inlet, spec)
    np.testing.assert_allclose(narrow.ports(inlet, spec)[1][0].normal, [0, -1, 0], atol=1e-12)   # +right


@pytest.mark.parametrize("make, message", [
    (lambda: _tee(RectShape(A, 0.4 * A, 4, 4)), "full-width tap: task 0057"),
    (lambda: _tee(_rect(0.96 * A)), "exceeds DUCT_TAP_MAX_RATIO"),
    (lambda: _tee(CircleShape(radius=0.96 * A, nang=4)), "exceeds DUCT_TAP_MAX_RATIO"),
    (lambda: _tee(_rect(0.5 * A), roll=90), "roll is 0 or 180"),
    (lambda: _tee(_rect(0.5 * A), toward=(0, 1, 0)), "toward= is for pipe tees"),
    (lambda: _tee(_rect(0.5 * A), face="top"), "face must be"),
    (lambda: _tee(RectShape(0.5 * A, 0.5 * A, 4, 2)), "must be the main's"),
    (lambda: Tee(branch_length=0.3, branch_radius=0.05), "needs branch=RectShape"),
    (lambda: _tee(_rect(0.5 * A), run_length=0.06), "run_length must exceed"),
])
def test_rejections(make, message):
    with pytest.raises((AssemblyError, ValueError), match=message):
        _asm(make()).validate()


def test_round_tap_needs_equal_counts():
    spec = PipeSpec(nang_w=4, nang_h=2).core("fluid", half_w=A, half_h=B, nrad=3)
    with pytest.raises((AssemblyError, ValueError), match="equal counts per side"):
        _asm(_tee(CircleShape(radius=0.5 * A, nang=4)), spec=spec).validate()


def test_shelled_or_rotated_duct_rejected():
    shelled = _spec().shell("steel", dR=0.005, nrad=1)
    with pytest.raises((AssemblyError, ValueError), match="single-layer"):
        _asm(_tee(_rect(0.5 * A)), spec=shelled).validate()


def test_duct_fields_on_a_pipe_rejected():
    pipe = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3)
    with pytest.raises((AssemblyError, ValueError), match="are for a duct tap"):
        _asm(Tee(branch_length=0.3, branch_radius=0.05, face="wide"), spec=pipe).validate()


def test_circle_branch_on_a_pipe_is_branch_radius():
    pipe = PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3)
    a = _asm(Tee(branch_length=0.3, branch_radius=0.05), spec=pipe)
    b = _asm(Tee(branch_length=0.3, branch=CircleShape(radius=0.05, nang=4)), spec=pipe)
    assert a.edges[1].fitting == b.edges[1].fitting


def test_narrow_face_of_a_deep_duct_warns():
    asm = _asm(_tee(_rect(0.5 * B), face="narrow", branch_length=4 * B), spec=_spec(aspect=3))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        asm.validate()
    assert any("DUCT_TAP_NARROW_ASPECT_WARN" in str(x.message) for x in w)


def test_ratio_limit_is_measured_value():
    assert limits.DUCT_TAP_MAX_RATIO == 0.93
    inlet = Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]))
    _tee(_rect(0.93 * A)).resolve(inlet, _spec())          # at the limit: fits


def test_round_tap_meshed_sj_rejects_below_the_floor(gmsh_session, monkeypatch):
    """The meshed check (prediction overestimates round taps by ≤ 0.11)
    names the fitting; forced here by raising the floor after validation."""
    asm = _asm(_tee(CircleShape(radius=0.6 * A, nang=4)))
    asm.validate()
    monkeypatch.setattr(limits, "PREDICTED_SJ_MIN", 0.99)
    with pytest.raises(AssemblyError, match="Tee1: meshed corner scaled Jacobian"):
        asm.mesh()


def test_rect_tap_has_no_meshed_check():
    assert not _tee(_rect(0.5 * A)).meshed_sj_check(_spec())
    assert _tee(CircleShape(radius=0.5 * A, nang=4)).meshed_sj_check(_spec())
    assert not Tee(branch_length=0.3, branch_radius=0.05).meshed_sj_check(
        PipeSpec(nang=4).core("fluid", radius=0.1, nrad=3))

