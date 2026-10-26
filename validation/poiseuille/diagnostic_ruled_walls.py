"""Diagnostic only (task 0020): the validation with ruled (exact) Straight
side surfaces, patched in at run time.  Not a fix."""
import sys
sys.path.insert(0, "validation/poiseuille"); sys.path.insert(0, ".")
from hexmesh.assembly import sweep
orig = sweep._fill_slab
def ruled(*a, **k):
    k.setdefault("side_surface", None)
    if k["side_surface"] is None:
        k["side_surface"] = sweep._ruled
    return orig(*a, **k)
sweep._fill_slab = ruled
import run
run.main(sys.argv[1:])
