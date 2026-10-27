"""
Two-level bifurcation tree: one inlet, two wyes deep, four parallel outlets.

    python3 -m hexmesh.examples.bifurcation_tree # writes bifurcation_tree.msh

A flow-splitting manifold, or a symmetric model of a branching airway or
artery.  A 90° wye splits the inlet; each daughter bends back parallel to
the inlet and splits again in a 60° wye, whose daughters bend parallel
too.  The four outlets come out side by side, named ``a`` to ``d``.

- A wye splits in the inlet's (normal, ``right``) plane; ``right`` turns
  toward the inlet's ``right``.  Its ports are ``[left, right]``.
- A bend turns toward ``up`` at ``roll=0`` and toward ``right`` at
  ``roll=90``, so the left daughters straighten with ``roll=90`` and the
  right ones with ``roll=-90``.

Every junction keeps the inlet's spec, so the whole tree is one
connectivity type and meshes all-hex.  (Prototype limits of the wye:
single-layer, equal daughters, 30°–120°.)
"""

from hexmesh import Assembly, Bend, PipeSpec, Straight, Wye

PIPE = PipeSpec(nang=6).core("fluid", radius=0.05, nrad=3)


def _split(asm, at, angle, branch):
    """Wye at *at*, each daughter bent back parallel to the wye's inlet;
    returns the two bend outlets."""
    left, right = asm.add(at, Wye(angle, run_length=0.15, branch_length=branch,
                                  n_run=3, n_branch=4, n_split=4))
    return [asm.add(port, Bend(radius=0.12, angle=angle / 2, n_layers=4, roll=roll))
            for port, roll in ((left, 90), (right, -90))]


def build() -> Assembly:
    asm = Assembly(PIPE, direction=[1, 0, 0], up=[0, 0, 1])
    inlet_run = asm.add(Straight(0.4, n_layers=8))
    left, right = _split(asm, inlet_run, 90, 0.45)
    outlets = []
    for end in (left, right):
        run = asm.add(end, Straight(0.15, n_layers=3))
        outlets += _split(asm, run, 60, 0.25)
    for end, name in zip(outlets, "abcd"):
        asm.add(end, Straight(0.3, n_layers=6), names=[name])
    return asm


def main(output: str = "bifurcation_tree.msh"):
    from hexmesh.examples._run import run
    return run(build, output)


if __name__ == "__main__":
    main()
