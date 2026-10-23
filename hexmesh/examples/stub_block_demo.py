"""
Stage 2 standalone test — branch stub block.

Builds the branch stub block geometry in isolation (no main pipe, no
network framework) and meshes it to verify the hex topology is valid.

Run::

    python -m hexmesh.examples.stub_block_demo
    # produces stub_block.msh and prints an element-type summary

"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import gmsh
import numpy as np

from hexmesh.connectors.t_block import build_stub_block


def stub_block_demo(output: str = "stub_block.msh") -> None:
    """Build and mesh the stub block; report element counts."""
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 2)
    gmsh.model.add("stub_block")

    # Geometry parameters (axis-aligned for easy visual inspection)
    origin     = np.array([0.0, 0.0, 0.0])
    main_dir   = np.array([0.0, 1.0, 0.0])   # main pipe along +Y
    branch_dir = np.array([1.0, 0.0, 0.0])   # branch along +X
    R          = 0.36    # main outer radius
    r          = 0.18    # branch outer radius  (= R/2)
    branch_length = 0.60 # stub length along +X (must be > R)

    result = build_stub_block(
        origin, main_dir, branch_dir,
        R=R, r=r,
        branch_length=branch_length,
        nang=5,
        nrad=4,
        n_axial=4,
        ratio=0.6,
    )

    vols       = result["volumes"]
    branch_cs  = result["branch_cs"]
    saddle_srf = result["saddle_surfs"]

    print(f"Stub block: {len(vols)} volumes, "
          f"{len(saddle_srf)} saddle surfaces, "
          f"branch face has {len(branch_cs.surfaces)} patches")

    # Physical groups for post-processing
    gmsh.model.addPhysicalGroup(3, vols, tag=-1)
    gmsh.model.setPhysicalName(3, gmsh.model.addPhysicalGroup(3, vols), "stub")
    gmsh.model.addPhysicalGroup(2, saddle_srf)
    gmsh.model.setPhysicalName(2, gmsh.model.addPhysicalGroup(2, saddle_srf), "saddle_end")
    gmsh.model.addPhysicalGroup(2, list(branch_cs.surfaces))
    gmsh.model.setPhysicalName(
        2, gmsh.model.addPhysicalGroup(2, list(branch_cs.surfaces)), "branch_face"
    )

    # Generate 3-D hex mesh
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.optimize("Laplace2D")

    # Report element types
    elem_counts: dict[str, int] = {}
    for dim, tag in gmsh.model.getEntities(3):
        elem_types, _, _ = gmsh.model.mesh.getElements(dim, tag)
        for et in elem_types:
            name, _, _, n_nodes, _, _ = gmsh.model.mesh.getElementProperties(et)
            elem_counts[name] = elem_counts.get(name, 0) + 1

    gmsh.write(output)
    gmsh.finalize()

    print(f"Output: {output}")
    print("Element types in 3-D volumes:")
    for name, count in sorted(elem_counts.items()):
        print(f"  {name:30s}: {count}")

    if elem_counts:
        non_hex = {k: v for k, v in elem_counts.items() if "Hexahedron" not in k}
        if non_hex:
            print(f"WARNING: non-hex elements present: {non_hex}")
        else:
            print("OK: all 3-D elements are hexahedra.")


if __name__ == "__main__":
    stub_block_demo()
