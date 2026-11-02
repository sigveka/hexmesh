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
Three-level Richardson extrapolation and the GCI [celik_and_ghia_etal_2008],
shared by every validation case (decision 0015; task 0089).

    import importlib.util                      # validation/ is not a package
    spec = importlib.util.spec_from_file_location(
        "convergence", ROOT / "validation/tools/convergence.py")
    conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
    rich = conv.richardson(coarse, medium, fine)          # ratio 2
    rich = conv.richardson(coarse, medium, fine, 4 / 3, 3 / 2)
    ok, why = conv.gate_extrapolated(rich, exact, 1e-3)

The result says which regime the three levels are in (``status``):

- ``"converging"``: the differences shrink with the same sign,
  |ε32| > |ε21|.  Only then is there an observed order, an extrapolated
  value, e_a, e_ext and the GCI.
- ``"oscillatory"``: the differences change sign.  No order and no
  extrapolation; the three values' range is reported (``bounds``).
- ``"diverging"``: the same sign, |ε32| ≤ |ε21|: no asymptotic range.
- ``"zero_difference"``: two levels agree exactly, so the ratio is
  undefined.

ε21 = f2 − f1 and ε32 = f3 − f2, with f1 the finest level.
"""

from __future__ import annotations

import math

STATUSES = ("converging", "oscillatory", "diverging", "zero_difference")


def richardson(coarse: float, medium: float, fine: float, r21: float = 2.0,
               r32: float | None = None, *, scale: float | None = None) -> dict:
    """Three-level Richardson extrapolation, coarse → fine values.

    *r21* = h2/h1 (medium over fine spacing) and *r32* = h3/h2 (default
    *r21*).  At non-constant ratios the order solves
    p = |ln|ε32/ε21| + q(p)| / ln r21 by fixed-point iteration (§2.1,
    steps 3–5); at a constant ratio q = 0.

    *scale* replaces |f1| in e_a and |extrapolated| in e_e, so the GCI is
    absolute, e.g. for a signed error whose exact value is 0.

    Every key is present in every result; the order and the values that
    need it are None unless ``status == "converging"``."""
    r32 = r21 if r32 is None else r32
    f3, f2, f1 = float(coarse), float(medium), float(fine)
    e21, e32 = f2 - f1, f3 - f2
    out = {"status": None, "order": None, "extrapolated": None, "e_a": None,
           "e_ext": None, "gci_fine": None, "oscillatory": False,
           "differences": [e32, e21], "bounds": [min(f1, f2, f3), max(f1, f2, f3)],
           "note": ""}
    if e21 == 0 or e32 == 0:
        which = "all three levels" if e21 == e32 == 0 else \
            "the medium and fine levels" if e21 == 0 else "the coarse and medium levels"
        out.update(status="zero_difference", note=f"{which} agree exactly")
        return out
    if e32 / e21 < 0:
        out.update(status="oscillatory", oscillatory=True,
                   note=f"the differences change sign; values within "
                        f"[{out['bounds'][0]:.6g}, {out['bounds'][1]:.6g}]")
        return out
    if abs(e32) <= abs(e21):
        out.update(status="diverging",
                   note=f"the differences don't shrink (|ε32| {abs(e32):.3g} ≤ "
                        f"|ε21| {abs(e21):.3g}): no asymptotic range")
        return out
    p = math.log(e32 / e21) / math.log(r21)
    if r32 != r21:
        for _ in range(100):
            q = math.log((r21 ** p - 1) / (r32 ** p - 1))
            p_new = abs(math.log(e32 / e21) + q) / math.log(r21)
            if abs(p_new - p) < 1e-10:
                p = p_new
                break
            p = p_new
    rp = r21 ** p
    ext = (rp * f1 - f2) / (rp - 1)
    e_a = abs(f1 - f2) / (abs(f1) if scale is None else scale)
    out.update(status="converging", order=p, extrapolated=ext, e_a=e_a,
               e_ext=abs(ext - f1) / (abs(ext) if scale is None else scale),
               gci_fine=1.25 * e_a / (rp - 1))
    return out


def gate_extrapolated(rich: dict, exact: float, limit: float, *,
                      relative: bool = True) -> tuple[bool, str]:
    """An extrapolated-value gate: passes only on a converging series whose
    extrapolated value is within *limit* of *exact* (relative, or absolute
    with ``relative=False``).  Any other status fails with its reason."""
    if rich["status"] != "converging":
        return False, f"{rich['status']}: {rich['note']}"
    err = rich["extrapolated"] - exact
    if relative:
        err /= exact
    ok = abs(err) <= limit
    return ok, f"extrapolated − exact {err:+.3g} ({'within' if ok else 'outside'} {limit:g})"


def describe(rich: dict) -> str:
    """The order where it is defined, else the status (for report-only
    quantities)."""
    return f"{rich['order']:.2f}" if rich["status"] == "converging" else rich["status"]
