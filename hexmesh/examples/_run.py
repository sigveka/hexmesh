"""
Shared runner for the examples: validate, count, mesh, write, report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import gmsh

from hexmesh import Assembly, QualityReport, Session


@dataclass
class Result:
    output:    str
    predicted: int            # cell count from Assembly.cell_count(), before GMSH
    meshed:    int            # hexahedra in the written mesh
    quality:   QualityReport


def run(build: Callable[[], Assembly], output: str, show: bool = False) -> Result:
    """Build the assembly from *build*, mesh it and write *output*."""
    with Session(output.rsplit(".", 1)[0]) as session:
        asm = build()
        asm.validate()
        predicted = asm.cell_count()
        asm.write(output)
        meshed = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
        quality = asm.check_quality()
        groups = sorted(gmsh.model.getPhysicalName(d, t)
                        for d, t in gmsh.model.getPhysicalGroups())
        print(f"{output}: {meshed} cells (predicted {predicted}), "
              f"min SICN {quality.min_quality:.3f}")
        print(f"  groups: {', '.join(groups)}")
        if show:
            session.show()
    return Result(output, predicted, meshed, quality)
