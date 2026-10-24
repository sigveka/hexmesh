"""
Mesh quality report: per-region element statistics.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RegionQuality:
    """Mesh quality statistics for one named region (physical volume group).

    Attributes
    ----------
    name : str
        Region (material) name.
    n_elements : int
        Total number of 3-D elements in this region.
    n_bad : int
        Elements with quality < ``threshold`` (default 0 — inverted cells).
    min_quality : float
        Worst (lowest) quality value among all elements.
    max_quality : float
        Best (highest) quality value.
    mean_quality : float
        Average quality across all elements.
    quality_name : str
        Name of the quality measure used (e.g. ``"minSICN"``).
    threshold : float
        The threshold below which an element is considered bad.
    """

    name:         str
    n_elements:   int
    n_bad:        int
    min_quality:  float
    max_quality:  float
    mean_quality: float
    quality_name: str
    threshold:    float

    @property
    def ok(self) -> bool:
        """True when no elements fall below the quality threshold."""
        return self.n_bad == 0

    def __str__(self) -> str:
        status = "OK" if self.ok else f"WARN ({self.n_bad} bad)"
        return (
            f"{self.name:<20s}  {self.n_elements:>6d} el  "
            f"min={self.min_quality:+.4f}  mean={self.mean_quality:+.4f}  "
            f"max={self.max_quality:+.4f}  [{status}]"
        )


@dataclass
class QualityReport:
    """Quality report for a meshed assembly.

    Returned by :meth:`Assembly.check_quality`.  Contains per-region
    statistics and a summary flag.

    Attributes
    ----------
    regions : list[RegionQuality]
        One entry per named physical volume group.
    quality_name : str
        Quality measure used.
    threshold : float
        Bad-element threshold.
    """

    regions:      list[RegionQuality] = field(default_factory=list)
    quality_name: str   = "minSICN"
    threshold:    float = 0.0

    @property
    def total_elements(self) -> int:
        return sum(r.n_elements for r in self.regions)

    @property
    def total_bad(self) -> int:
        return sum(r.n_bad for r in self.regions)

    @property
    def ok(self) -> bool:
        return self.total_bad == 0

    @property
    def min_quality(self) -> float:
        return min((r.min_quality for r in self.regions), default=float("nan"))

    def __str__(self) -> str:
        lines = [
            f"Quality report  ({self.quality_name}, threshold={self.threshold})",
            "-" * 70,
        ]
        for r in self.regions:
            lines.append(str(r))
        lines.append("-" * 70)
        lines.append(
            f"{'TOTAL':<20s}  {self.total_elements:>6d} el  "
            f"min={self.min_quality:+.4f}  "
            f"{'OK' if self.ok else f'WARN ({self.total_bad} bad elements)'}"
        )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"QualityReport(regions={len(self.regions)}, "
            f"total={self.total_elements}, bad={self.total_bad}, "
            f"min={self.min_quality:.4f})"
        )
