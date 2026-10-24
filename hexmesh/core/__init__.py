from .shape import CircleShape, RectShape, Shape
from .cross_section import CrossSection, BoundaryType
from .region import RegionSet, MaterialGraph
from .spec import LayerSpec, PipeSpec, BundleSpec

__all__ = [
    "CircleShape", "RectShape", "Shape",
    "CrossSection", "BoundaryType",
    "Cursor", "Plane",
    "RegionSet", "MaterialGraph",
    "LayerSpec", "PipeSpec", "BundleSpec",
]


def __getattr__(name):
    # Legacy cursor API, loaded on first use so the assembly never imports
    # it (docs/tasks/0011; removed with the legacy code in task 0017).
    if name in ("Cursor", "Plane"):
        from . import cursor
        return getattr(cursor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
