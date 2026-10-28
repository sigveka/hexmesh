"""
Study runner (decision 0025): one study file → many variants, checked in
seconds, meshed in parallel jobs, recorded in one manifest.

    python3 -m hexmesh.study run study.json [--stage preflight|mesh] [--jobs N]
                                            [--keep-going]
    python3 -m hexmesh.study status study.json
    python3 -m hexmesh.study export study.json

The study file is described in ``hexmesh.study.definition``, sampling in
``hexmesh.study.sampling``, the stages in ``hexmesh.study.stages`` and
the manifest and aligned export in ``hexmesh.study.manifest``.  The
runner uses only the public ``Assembly`` API and the JSON description.
From Python::

    from hexmesh.study import load_study, run
    rows = run(load_study("study.json"), jobs=2)
"""

from __future__ import annotations

from collections import Counter

from .definition import Study, StudyError, canonical, load_study, variant_hash
from .manifest import export, read_manifest, write_manifest
from .sampling import variants
from .stages import STATUS, failure_table, load_results, mesh, preflight, topology_key

STAGES = ("preflight", "mesh")

__all__ = ["Study", "StudyError", "PreflightFailed", "load_study", "variants", "variant_hash", "preflight",
           "mesh", "run", "status", "export", "topology_key", "canonical", "STAGES"]


class PreflightFailed(StudyError):
    """Preflight found failing variants; nothing was meshed."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        n = sum(r["status"] == "preflight_failed" for r in rows)
        super().__init__(f"preflight: {n} of {len(rows)} variant(s) failed; nothing meshed "
                         f"(--keep-going meshes the rest)\n{failure_table(rows)}")


def run(study: Study, stage: str = "mesh", jobs: int | None = None,
        keep_going: bool = False, log=None) -> list[dict]:
    """Run the stages up to *stage*; write the manifest; return the rows.

    Raises ``PreflightFailed`` (after writing the manifest) if a variant
    fails preflight, unless *keep_going*.
    """
    if stage not in STAGES:
        raise StudyError(f"stage must be one of {STAGES}, got {stage!r}")
    say = log or (lambda *a: None)
    rows = preflight(study)
    cells = sum(r["cells"] or 0 for r in rows)
    say(f"preflight: {len(rows)} variant(s), {cells} cells, "
        f"{sum(r['status'] == 'preflight_failed' for r in rows)} failed")
    failed = any(r["status"] == "preflight_failed" for r in rows)
    if stage == "mesh" and (keep_going or not failed):
        done = mesh(study, rows, jobs)
        say(f"mesh: {len(done)} meshed, {len(rows) - len(done)} skipped or failed preflight")
    else:
        load_results(study, rows)
    write_manifest(study, rows)
    if failed and not keep_going:
        raise PreflightFailed(rows)
    return rows


def status(study: Study) -> Counter:
    return Counter(r["status"] for r in read_manifest(study)["variants"])
