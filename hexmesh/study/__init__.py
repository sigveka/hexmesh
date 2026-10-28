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
from .stages import (
    STATUS, case_stage, failure_table, load_case_run, load_results, mesh, other_runs,
    preflight, run_stage, topology_key,
)

STAGES = ("preflight", "mesh", "case", "run")

__all__ = ["Study", "StudyError", "PreflightFailed", "case_stage", "run_stage", "other_runs",
           "load_study", "variants", "variant_hash", "preflight",
           "mesh", "run", "status", "export", "topology_key", "canonical", "STAGES"]


class PreflightFailed(StudyError):
    """Preflight found failing variants; nothing was meshed."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        n = sum(r["status"] == "preflight_failed" for r in rows)
        super().__init__(f"preflight: {n} of {len(rows)} variant(s) failed; nothing meshed "
                         f"(--keep-going meshes the rest)\n{failure_table(rows)}")


def last_stage(study: Study) -> str:
    """The last stage the study file configures: run, case or mesh."""
    return "run" if study.run else "case" if study.case else "mesh"


def run(study: Study, stage: str | None = None, jobs: int | None = None,
        keep_going: bool = False, log=None, force: bool = False) -> list[dict]:
    """Run the stages up to *stage* (default: the study's last); write the
    manifest; return the rows.

    Raises ``PreflightFailed`` (after writing the manifest) if a variant
    fails preflight, unless *keep_going*.  The run stage refuses while
    another session's pytest or OpenFOAM runs are active, unless *force*.
    """
    stage = stage or last_stage(study)
    if stage not in STAGES:
        raise StudyError(f"stage must be one of {STAGES}, got {stage!r}")
    if stage == "case" and not study.case or stage == "run" and not study.run:
        raise StudyError(f"the study file has no {stage!r} block")
    say = log or (lambda *a: None)
    rows = preflight(study)
    cells = sum(r["cells"] or 0 for r in rows)
    say(f"preflight: {len(rows)} variant(s), {cells} cells, "
        f"{sum(r['status'] == 'preflight_failed' for r in rows)} failed")
    failed = any(r["status"] == "preflight_failed" for r in rows)
    later = STAGES.index(stage)
    if later >= 1 and (keep_going or not failed):
        done = mesh(study, rows, jobs)
        say(f"mesh: {len(done)} meshed, {len(rows) - len(done)} skipped or failed preflight")
    else:
        load_results(study, rows)
    if later >= 2 and (keep_going or not failed):
        done = case_stage(study, rows, jobs)
        say(f"case: {len(done)} made")
    if later >= 3 and (keep_going or not failed):
        try:
            done = run_stage(study, rows, jobs, force)
        except StudyError:
            write_manifest(study, rows)
            raise
        say(f"run: {len(done)} run")
    load_case_run(study, rows)
    write_manifest(study, rows)
    if failed and not keep_going:
        raise PreflightFailed(rows)
    return rows


def status(study: Study) -> Counter:
    return Counter(r["status"] for r in read_manifest(study)["variants"])
