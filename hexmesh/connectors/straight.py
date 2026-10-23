"""
Straight connector — linear extrusion of all layers.

Extrudes ALL patches from ALL concentric layers in a *single*
gmsh.model.occ.extrude call.

Extruding all layers together (rather than one layer at a time) preserves
the shared boundary topology of adjacent layers: when the core outer arcs
are the same GMSH entities as the annulus inner arcs, OCC extrudes them
once and the outlet face has a single, shared set of corner points.

Per-layer extrusion creates duplicate coincident corner points at the
core–annulus interface on the outlet face.  Those duplicates later cause
addCurveLoop in downstream taper connectors to insert short bridging
curves, producing 5-edge side-surfaces that fail transfinite meshing
("Incompatible surface in transfinite volume").

After the single extrude call, end-faces and lateral surfaces are
identified via getBoundary queries on each volume:

    end-face  : the non-inlet boundary surface whose bounding-box centre is
                displaced by (dx, dy, dz) from the corresponding inlet patch.
    laterals  : all remaining non-inlet boundary surfaces of the volume.

Lateral classification (outer / inner / intra) is determined by the
surface's maximum radial distance from the pipe axis, which is stable for
all extrusion directions.
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import gmsh

from ..core.cross_section import CrossSection, LayeredCrossSection
from ..core.cursor import Cursor
from ..core.region import RegionSet
from .base import Connector, SegmentResult


@dataclass
class Straight:
    """Linear extrusion along the current cursor direction.

    Parameters
    ----------
    length : float
        Extrusion length.
    n_layers : int
        Number of hex layers along the extrusion direction.
    """

    length:   float
    n_layers: int

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(f"Straight.length must be positive, got {self.length!r}")
        if self.n_layers < 1:
            raise ValueError(f"Straight.n_layers must be >= 1, got {self.n_layers!r}")

    def connect(
        self,
        inlet:  LayeredCrossSection,
        cursor: Cursor,
    ) -> SegmentResult:
        """Extrude all layers linearly and return a SegmentResult."""
        dx, dy, dz = (cursor.direction * self.length).tolist()

        regions:    dict[str, RegionSet]  = {}
        interfaces: dict[str, list[int]] = {}

        end_layers: list[tuple[str, CrossSection]] = []
        prev_outer_walls: list[int] | None = None

        iface_names = inlet.interface_names()

        # ------------------------------------------------------------------
        # Extrude ALL patches from ALL layers in a single OCC call.
        # This guarantees that shared boundary curves between concentric
        # layers (core outer arcs = annulus inner arcs) are extruded once
        # so the outlet face has a single set of shared corner points —
        # no duplicate coincident entities at the core–annulus interface.
        # Per-layer extrusion creates duplicate corner points there, which
        # cause addCurveLoop in downstream taper connectors to insert
        # bridging curves → "Incompatible surface" transfinite errors.
        # ------------------------------------------------------------------
        all_dimtags: list[tuple[int, int]] = []
        layer_surf_counts: list[int] = []
        for _, cs in inlet:
            all_dimtags.extend((2, s) for s in cs.surfaces)
            layer_surf_counts.append(len(cs.surfaces))

        out = gmsh.model.occ.extrude(
            all_dimtags, dx, dy, dz,
            numElements=[self.n_layers],
            recombine=True,
        )
        gmsh.model.occ.synchronize()

        # Volumes are the (3, tag) entries in out, in input-surface order.
        all_vols = [tag for dim, tag in out if dim == 3]

        # Use the union of all inlet surfaces to filter end-faces/laterals.
        # This prevents an outlet face of one layer from being mistaken as
        # an inlet face when classifying volumes of another layer.
        all_inlet_set = set(s for _, cs in inlet for s in cs.surfaces)

        vol_offset = 0

        for idx, (name, cs) in enumerate(inlet):
            is_core       = (len(cs.surfaces) == cs.n_outer + 1)  # OH core: 1 center + n_outer
            is_split_core = (len(cs.surfaces) == cs.n_outer + 2)  # split-center OH (Y-junction)
            is_single     = (len(cs.surfaces) == 1)               # single-patch square

            n_surfs = layer_surf_counts[idx]
            vols    = all_vols[vol_offset:vol_offset + n_surfs]
            vol_offset += n_surfs

            # Pipe-axis parameters for radius-based lateral classification.
            _centre = np.array([cs.cx, cs.cy, cs.cz], dtype=float)
            _axis   = cursor.direction          # unit vector

            def _max_radius(surf_tag: int) -> float:
                """Max distance from pipe axis sampled at bounding-box corners."""
                bb = gmsh.model.getBoundingBox(2, surf_tag)
                rmax = 0.0
                for px in (bb[0], bb[3]):
                    for py in (bb[1], bb[4]):
                        for pz in (bb[2], bb[5]):
                            p = np.array([px, py, pz])
                            t = float(np.dot(p - _centre, _axis))
                            r = float(np.linalg.norm(p - _centre - t * _axis))
                            if r > rmax:
                                rmax = r
                return rmax

            # ------------------------------------------------------------------
            # Per-volume: identify end-face and classify laterals.
            # ------------------------------------------------------------------
            vols_out      = []
            outer_walls   = []
            inner_walls   = []
            intra_walls   = []
            end_surfaces  = []

            for i, (vol, surf_in) in enumerate(zip(vols, cs.surfaces)):
                bnd_surfs = [
                    t for d, t in
                    gmsh.model.getBoundary([(3, vol)], oriented=False)
                    if d == 2
                ]

                # End face: not in all_inlet_set, bounding-box centre ≈ inlet + d
                bb_in = gmsh.model.getBoundingBox(2, surf_in)
                out_cx = (bb_in[0] + bb_in[3]) / 2 + dx
                out_cy = (bb_in[1] + bb_in[4]) / 2 + dy
                out_cz = (bb_in[2] + bb_in[5]) / 2 + dz

                end_face = None
                for s in bnd_surfs:
                    if s in all_inlet_set:
                        continue
                    bb_s = gmsh.model.getBoundingBox(2, s)
                    scx  = (bb_s[0] + bb_s[3]) / 2
                    scy  = (bb_s[1] + bb_s[4]) / 2
                    scz  = (bb_s[2] + bb_s[5]) / 2
                    if (scx - out_cx)**2 + (scy - out_cy)**2 + (scz - out_cz)**2 < 1e-10:
                        end_face = s
                        break
                if end_face is None:
                    raise RuntimeError(
                        f"Straight: could not identify end-face for vol {vol} "
                        f"(patch {i}, inlet surf {surf_in})"
                    )

                end_surfaces.append(end_face)
                vols_out.append(vol)

                laterals = [
                    s for s in bnd_surfs if s not in all_inlet_set and s != end_face
                ]

                if is_split_core and i < 2:
                    # Half-centre patches (split-centre OH from Y-junction)
                    inner_walls.extend(laterals)
                elif is_core and i == 0:
                    # Centre patch: all laterals are internal
                    inner_walls.extend(laterals)
                elif is_core or is_split_core:
                    # Outer quadrant patches: max-radius lateral = outer wall
                    outer_lat = max(laterals, key=_max_radius)
                    outer_walls.append(outer_lat)
                    intra_walls.extend(s for s in laterals if s != outer_lat)
                elif is_single:
                    outer_walls.extend(laterals)
                else:
                    # Annular / square-shell: classify by radius
                    sorted_lats = sorted(laterals, key=_max_radius)
                    inner_walls.append(sorted_lats[0])    # min r = inner arc
                    outer_walls.append(sorted_lats[-1])   # max r = outer arc
                    intra_walls.extend(sorted_lats[1:-1]) # radials

            regions[name] = RegionSet(
                volumes  = vols_out,
                inlets   = list(cs.surfaces),
                outlets  = end_surfaces,
                walls    = outer_walls,
            )

            # Conformal interface: this layer's outer wall == next layer's inner wall.
            if prev_outer_walls is not None and idx - 1 < len(iface_names):
                iface_label = iface_names[idx - 1]
                interfaces[iface_label] = prev_outer_walls

            prev_outer_walls = outer_walls

            # Build updated CrossSection for the end-face.
            end_cs = CrossSection(
                surfaces      = end_surfaces,
                center        = cs.center,
                outer_points  = cs.outer_points,
                outer_curves  = cs.outer_curves,
                shape         = cs.shape,
                boundary_type = cs.boundary_type,
                h_axis        = cs.h_axis,
                v_axis        = cs.v_axis,
                cx=cs.cx, cy=cs.cy, cz=cs.cz,
                inner_points  = list(cs.inner_points),
                inner_curves  = list(cs.inner_curves),
                radial_curves = list(cs.radial_curves),
                nrad          = cs.nrad,
                lc            = cs.lc,
            )
            end_layers.append((name, end_cs))

        end_cursor = cursor.advanced(self.length)
        end_face   = LayeredCrossSection(end_layers)

        return SegmentResult(
            end_face   = end_face,
            end_cursor = end_cursor,
            regions    = regions,
            interfaces = interfaces,
        )
